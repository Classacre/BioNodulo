from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.types import is_compatible
from bionodulo.workflow.graph import GraphError, topological_sort
from bionodulo.workflow.schema import ValidationIssue, ValidationResult, Workflow


def validate_workflow(
    workflow: Workflow,
    registry: NodeRegistry,
    *,
    mock_tools: bool = True,
    project_root: Path | None = None,
) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    nodes_by_id = {node.id: node for node in workflow.nodes}

    if len(nodes_by_id) != len(workflow.nodes):
        errors.append(ValidationIssue(code="duplicate_node_id", message="Node IDs must be unique."))

    for node in workflow.nodes:
        if not registry.has(node.type):
            errors.append(ValidationIssue(node_id=node.id, code="unknown_node_type", message=f"Unknown node type: {node.type}"))

    edge_inputs: dict[tuple[str, str], str] = {}
    incoming_by_node: dict[str, list] = {}
    outgoing_by_node: dict[str, list] = {}
    for edge in workflow.edges:
        incoming_by_node.setdefault(edge.to.node, []).append(edge)
        outgoing_by_node.setdefault(edge.from_.node, []).append(edge)
        if edge.from_.node not in nodes_by_id:
            errors.append(ValidationIssue(edge_id=edge.id, code="missing_source", message=f"Missing source node {edge.from_.node}"))
            continue
        if edge.to.node not in nodes_by_id:
            errors.append(ValidationIssue(edge_id=edge.id, code="missing_target", message=f"Missing target node {edge.to.node}"))
            continue
        if edge.from_.output is None or edge.to.input is None:
            errors.append(ValidationIssue(edge_id=edge.id, code="bad_endpoint", message="Edges must specify source output and target input."))
            continue
        target_key = (edge.to.node, edge.to.input)
        if target_key in edge_inputs:
            errors.append(ValidationIssue(edge_id=edge.id, node_id=edge.to.node, code="duplicate_input_connection", message=f"Input {edge.to.input} already has a connection."))
        edge_inputs[target_key] = edge.id

        if registry.has(nodes_by_id[edge.from_.node].type) and registry.has(nodes_by_id[edge.to.node].type):
            source_cls = registry.get(nodes_by_id[edge.from_.node].type)
            target_cls = registry.get(nodes_by_id[edge.to.node].type)
            source_outputs = {name: typ for name, typ in zip(source_cls.RETURN_NAMES, source_cls.RETURN_TYPES, strict=False)}
            target_inputs = _input_types(target_cls.INPUT_TYPES())
            source_type = source_outputs.get(edge.from_.output)
            target_type = target_inputs.get(edge.to.input)
            if source_type is None:
                errors.append(ValidationIssue(edge_id=edge.id, node_id=edge.from_.node, code="unknown_output", message=f"Unknown output {edge.from_.output}"))
            elif target_type is None:
                errors.append(ValidationIssue(edge_id=edge.id, node_id=edge.to.node, code="unknown_input", message=f"Unknown input {edge.to.input}"))
            elif not is_compatible(source_type, target_type):
                errors.append(
                    ValidationIssue(
                        edge_id=edge.id,
                        node_id=edge.to.node,
                        code="type_mismatch",
                        message=f"Cannot connect {source_type} to {target_type}.",
                    )
                )

    for node in workflow.nodes:
        if not registry.has(node.type):
            continue
        if node.ui.muted:
            if outgoing_by_node.get(node.id):
                warnings.append(ValidationIssue(node_id=node.id, level="warning", code="muted_node_blocks_downstream", message="Muted node will be skipped and downstream connected nodes may be blocked."))
            continue
        node_cls = registry.get(node.type)
        if node.ui.bypassed:
            _validate_bypass(node.id, workflow, registry, nodes_by_id, incoming_by_node.get(node.id, []), outgoing_by_node.get(node.id, []), errors)
            continue
        inputs = node_cls.INPUT_TYPES()
        for input_name, (_, options) in inputs.get("required", {}).items():
            if (node.id, input_name) not in edge_inputs and input_name not in node.params and "default" not in options:
                errors.append(ValidationIssue(node_id=node.id, code="required_input_missing", message=f"Required input {input_name} is not connected or configured."))
        if node_cls.REQUIRES_EXTERNAL_TOOLS and not mock_tools:
            for exe in node_cls.REQUIRED_EXECUTABLES:
                if not exe:
                    continue
                import shutil

                if shutil.which(exe) is None:
                    errors.append(ValidationIssue(node_id=node.id, code="missing_executable", message=f"Required executable '{exe}' was not found on PATH."))
        if node.type.startswith("input_") and not mock_tools:
            file_values = [value for value in node.params.values() if isinstance(value, str) or isinstance(value, list)]
            for value in file_values:
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if isinstance(item, str) and item and not Path(item).exists():
                        warnings.append(ValidationIssue(node_id=node.id, level="warning", code="input_path_missing", message=f"Input path does not exist yet: {item}"))

    topological_order: list[str] = []
    try:
        topological_order = topological_sort(workflow)
    except GraphError as exc:
        errors.append(ValidationIssue(code="cycle_detected", message=str(exc)))

    if workflow.outputs:
        for output_id in workflow.outputs:
            if output_id not in nodes_by_id:
                errors.append(ValidationIssue(node_id=output_id, code="missing_output_node", message=f"Workflow output node {output_id} does not exist."))
    elif workflow.nodes:
        warnings.append(ValidationIssue(level="warning", code="no_outputs", message="Workflow has no explicit outputs; all nodes will execute."))

    return ValidationResult(valid=not errors, errors=errors, warnings=warnings, topological_order=topological_order)


def _input_types(inputs: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for section in ("required", "optional"):
        for name, (typ, _) in inputs.get(section, {}).items():
            result[name] = typ
    return result


def _validate_bypass(node_id: str, workflow: Workflow, registry: NodeRegistry, nodes_by_id: dict, incoming: list, outgoing: list, errors: list[ValidationIssue]) -> None:
    incoming_types: list[str] = []
    for edge in incoming:
        source = nodes_by_id.get(edge.from_.node)
        if not source or not registry.has(source.type) or edge.from_.output is None:
            continue
        source_cls = registry.get(source.type)
        outputs = {name: typ for name, typ in zip(source_cls.RETURN_NAMES, source_cls.RETURN_TYPES, strict=False)}
        source_type = outputs.get(edge.from_.output)
        if source_type:
            incoming_types.append(source_type)
    if not incoming_types and outgoing:
        errors.append(ValidationIssue(node_id=node_id, code="bypass_without_input", message="Bypassed node needs at least one compatible upstream input to pass through."))
        return
    for edge in outgoing:
        target = nodes_by_id.get(edge.to.node)
        if not target or not registry.has(target.type) or edge.to.input is None:
            continue
        target_cls = registry.get(target.type)
        target_type = _input_types(target_cls.INPUT_TYPES()).get(edge.to.input)
        if target_type and not any(is_compatible(source_type, target_type) for source_type in incoming_types):
            errors.append(ValidationIssue(edge_id=edge.id, node_id=node_id, code="bypass_type_mismatch", message=f"Bypassed node cannot pass any upstream value into {target_type}."))
