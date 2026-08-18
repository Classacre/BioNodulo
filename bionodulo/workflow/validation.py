"""Workflow validation for BioNodulo.

Checks node types exist, edges are valid, no cycles exist, and all
required inputs are connected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import re
from typing import Any

from bionodulo.workflow.graph import (
    edge_source,
    edge_source_port,
    edge_target,
    edge_target_port,
    topological_sort,
)


WORKFLOW_PARAMETER_REFERENCE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}")
NODE_LOCAL_TEMPLATE_FIELDS = {
    "custom_prompt",
    "custom_script",
    "prompt",
    "system_prompt",
    "template",
    "workflow_template",
}

SUBGRAPH_NODE_TYPE = "subgraph"
# The executor injects this workflow parameter into every subgraph's inner
# execution, so inner nodes may bind {{subgraph_seed}} without a declaration.
SUBGRAPH_IMPLICIT_PARAMETERS = frozenset({"subgraph_seed"})
# Subgraph params whose contents are validated by the recursive inner pass
# rather than against the outer workflow's parameter set.
_SUBGRAPH_PARAM_KEYS = {"workflow", "input_ports", "output_ports", "promoted_widgets"}
# A subgraph embedding itself (directly or transitively) would recurse
# forever; the executor has the same bound on nesting depth.
MAX_SUBGRAPH_DEPTH = 8


@dataclass
class ValidationResult:
    """Result of workflow validation."""

    valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sorted_node_order: list[str] = field(default_factory=list)


def validate_workflow(
    workflow: dict[str, Any],
    registry: Any,
    *,
    _depth: int = 0,
    _implicit_parameters: frozenset[str] = frozenset(),
) -> ValidationResult:
    """Validate a workflow for structural and semantic correctness.

    Checks:
    1. Node types are registered (``subgraph`` nodes instead carry an embedded
       workflow that is validated recursively with these same rules).
    2. Edges reference valid node IDs.
    3. No cycles (DAG).
    4. Required inputs are connected or have defaults.
    """
    errors: list[str] = []
    warnings: list[str] = []
    sorted_order: list[str] = []

    if _depth > MAX_SUBGRAPH_DEPTH:
        return ValidationResult(
            valid=False,
            errors=[f"Subgraph nesting exceeds the maximum depth of {MAX_SUBGRAPH_DEPTH}"],
            warnings=warnings,
        )

    nodes_raw = workflow.get("nodes", {})
    if isinstance(nodes_raw, dict):
        nodes = {
            nid: (n if isinstance(n, dict) else n.model_dump())
            for nid, n in nodes_raw.items()
        }
    elif isinstance(nodes_raw, list):
        nodes = {
            (
                n["id"] if isinstance(n, dict) else getattr(n, "id", "")
            ): (
                n if isinstance(n, dict) else n.model_dump()
            )
            for n in nodes_raw
        }
    else:
        errors.append("Invalid workflow: 'nodes' must be a dict or list")
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    edges = workflow.get("edges", [])
    parameter_names = _validate_workflow_parameters(workflow.get("parameters", []), errors, warnings)

    def registry_lookup(node_type: str) -> Any:
        if registry is None:
            return None
        if hasattr(registry, "get_node"):
            return registry.get_node(node_type)
        if hasattr(registry, "get"):
            return registry.get(node_type)
        return None

    # Check 1: All node types exist
    subgraph_orders: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        if not node:
            errors.append(f"Node '{node_id}' has no data")
            continue
        node_type = node.get("type", "") if isinstance(node, dict) else getattr(node, "type", "")
        if not node_type:
            errors.append(f"Node '{node_id}' has no type")
            continue
        if _is_subgraph_type(node_type):
            subgraph_orders[node_id] = _validate_subgraph_node(
                node_id, node, registry, errors, warnings, _depth
            )
            continue
        meta = registry_lookup(node_type)
        if registry is not None and meta is None:
            errors.append(f"Node '{node_id}' uses unregistered type '{node_type}'")
            continue
        saved_version = _saved_node_version(node)
        registry_version = _registry_node_version(meta)
        if saved_version and registry_version and saved_version != registry_version:
            warnings.append(
                f"Node '{node_id}' ({node_type}) was saved with version {saved_version} "
                f"but registry has {registry_version}"
            )
            migration = _matching_migration(meta, saved_version)
            if migration:
                from_version = str(migration.get("from_version", "") or saved_version)
                to_version = str(migration.get("to_version", "") or registry_version)
                description = str(migration.get("description", "") or "No description provided.")
                warnings.append(
                    f"Node '{node_id}' ({node_type}) has a migration available from "
                    f"{from_version} to {to_version}: {description}"
                )

    # Check 2: Edges reference valid nodes
    loop_executors = _loop_executor_nodes(nodes, registry_lookup)
    internal_nodes = _control_body_nodes(nodes, edges, registry_lookup)
    for edge in edges:
        src = edge_source(edge)
        dst = edge_target(edge)
        if src and src not in nodes:
            errors.append(f"Edge references unknown source node '{src}'")
        if dst and dst not in nodes:
            errors.append(f"Edge references unknown target node '{dst}'")
        if src == dst:
            warnings.append(f"Self-loop on node '{src}'")

        target_port = edge_target_port(edge, "")
        if (
            dst
            and dst in nodes
            and target_port
            and target_port != "default"
            and _node_is_subgraph(nodes[dst])
        ):
            if target_port not in _subgraph_port_names(nodes[dst], "input_ports"):
                errors.append(
                    f"Edge into subgraph node '{dst}' references unknown "
                    f"input port '{target_port}'"
                )

        source_port = edge_source_port(edge, "")
        if not src or not source_port or source_port == "default" or src not in nodes:
            continue
        source_node = nodes[src]
        source_type = (
            source_node.get("type", "")
            if isinstance(source_node, dict)
            else getattr(source_node, "type", "")
        )
        if _node_is_subgraph(source_node):
            # A subgraph's visible output ports are exactly its declared
            # output_ports (plus the executor-provided subgraph_dir).
            output_names = _subgraph_port_names(source_node, "output_ports") | {"subgraph_dir"}
        else:
            source_meta = registry_lookup(str(source_type))
            if isinstance(source_meta, dict):
                output_names = source_meta.get("output_name", source_meta.get("return_names", []))
            else:
                output_names = getattr(source_meta, "RETURN_NAMES", ()) if source_meta else ()
        # Loop control nodes drive their body through a virtual ``iteration``
        # output the executor provides at run time; it is not part of the
        # node's declared RETURN_NAMES, so exempt it here.
        if src in loop_executors and source_port == "iteration":
            output_names = ()
        if output_names and source_port not in {str(name) for name in output_names}:
            errors.append(
                f"Edge from node '{src}' ({source_type}) references unknown "
                f"output port '{source_port}'"
            )

    # Check 3: No cycles.
    #
    # Loop and try/catch control nodes own their bodies: the executor
    # re-runs body nodes inside the control node and rewires a feedback edge
    # (body -> control node) into loop state, so those nodes and edges never
    # form part of the outer DAG. Validate the outer graph and each control
    # body as separate DAGs, mirroring the executor's own discovery.
    outer_nodes = {nid: node for nid, node in nodes.items() if nid not in internal_nodes}
    outer_workflow = {"nodes": outer_nodes, "edges": [
        edge
        for edge in edges
        if edge_source(edge) in outer_nodes and edge_target(edge) in outer_nodes
    ]}
    try:
        sorted_order = topological_sort(outer_workflow)
    except ValueError as exc:
        errors.append(f"Cycle detected: {exc}")

    bodies = _control_bodies(nodes, edges, registry_lookup)
    for control_id, body_ids in sorted(bodies.items()):
        body_workflow = {"nodes": {nid: nodes[nid] for nid in body_ids if nid in nodes}, "edges": [
            edge
            for edge in edges
            if edge_source(edge) in body_ids and edge_target(edge) in body_ids
        ]}
        try:
            sorted_order.extend(topological_sort(body_workflow))
        except ValueError as exc:
            errors.append(f"Cycle detected inside control body of '{control_id}': {exc}")

    for subgraph_id, inner_order in sorted(subgraph_orders.items()):
        sorted_order.extend(f"{subgraph_id}/{inner_id}" for inner_id in inner_order)

    # Check 4: Required inputs connected
    connected_inputs: dict[str, set[str]] = {nid: set() for nid in nodes}
    for edge in edges:
        dst = edge_target(edge)
        dst_in = edge_target_port(edge, "")
        if dst and dst_in:
            connected_inputs.setdefault(dst, set()).add(dst_in)

    for node_id, node in nodes.items():
        if not node:
            continue
        node_type = node.get("type", "") if isinstance(node, dict) else getattr(node, "type", "")
        meta = registry_lookup(node_type)
        if meta and isinstance(meta, dict):
            inputs = meta.get("inputs", {})
        elif meta and hasattr(meta, "INPUT_TYPES"):
            # Preserve raw INPUT_TYPES tuples so we can read defaults below.
            # Each entry is either a (type, options) tuple/list or a bare type
            # name.
            input_types = meta.INPUT_TYPES()
            inputs = {
                name: {"required": True, "spec": spec}
                for name, spec in input_types.get("required", {}).items()
            }
        else:
            inputs = {}
        if isinstance(inputs, dict):
            for in_name, in_spec in inputs.items():
                if not isinstance(in_spec, dict) or not in_spec.get("required", False):
                    continue
                if in_name in connected_inputs.get(node_id, set()):
                    continue
                params = (
                    node.get("params", {})
                    if isinstance(node, dict)
                    else getattr(node, "params", {})
                )
                if in_name in params:
                    continue
                # A required input is also satisfied when its schema declares a
                # default value — the engine will substitute it at run time, so
                # the user never needs to wire or set it. This matches the
                # behaviour described in the validator's docstring.
                if _spec_has_default(in_spec.get("spec")):
                    continue
                if "default" in in_spec:
                    continue
                errors.append(
                    f"Node '{node_id}' ({node_type}) "
                    f"missing required input '{in_name}'"
                )

    _validate_workflow_parameter_references(
        nodes, parameter_names, errors, implicit_parameters=_implicit_parameters
    )

    valid = len(errors) == 0
    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        sorted_node_order=sorted_order if valid else [],
    )


def _spec_has_default(spec: Any) -> bool:
    """Return True when an input spec declares a default value.

    Specs come in three shapes: a flat dict ``{"type": "INT", "default": ...}``,
    a tuple ``("INT", {"default": ...})`` carried verbatim from INPUT_TYPES(),
    or a bare type name string with no options. Only the first two can carry a
    default; treat the third as "no default".
    """
    if isinstance(spec, dict):
        return "default" in spec
    if isinstance(spec, (list, tuple)):
        if len(spec) >= 2 and isinstance(spec[1], dict):
            return "default" in spec[1]
    return False


def _is_subgraph_type(node_type: Any) -> bool:
    return str(node_type or "") == SUBGRAPH_NODE_TYPE


def _node_is_subgraph(node: Any) -> bool:
    if isinstance(node, dict):
        return _is_subgraph_type(node.get("type", ""))
    return _is_subgraph_type(getattr(node, "type", ""))


def _node_params(node: Any) -> dict[str, Any]:
    params = node.get("params", {}) if isinstance(node, dict) else getattr(node, "params", {})
    return params if isinstance(params, dict) else {}


def _subgraph_port_names(node: Any, key: str) -> set[str]:
    """Declared port names on a subgraph node (``input_ports``/``output_ports``)."""
    names: set[str] = set()
    raw = _node_params(node).get(key)
    if not isinstance(raw, (list, tuple)):
        return names
    for entry in raw:
        if isinstance(entry, dict):
            name = str(entry.get("name", "") or "")
            if name:
                names.add(name)
    return names


def _workflow_node_ids(workflow: dict[str, Any]) -> set[str]:
    nodes_raw = workflow.get("nodes", {})
    if isinstance(nodes_raw, dict):
        return {str(nid) for nid in nodes_raw}
    if isinstance(nodes_raw, list):
        return {
            str(n["id"] if isinstance(n, dict) else getattr(n, "id", ""))
            for n in nodes_raw
        }
    return set()


def _validate_subgraph_node(
    node_id: str,
    node: Any,
    registry: Any,
    errors: list[str],
    warnings: list[str],
    depth: int,
) -> list[str]:
    """Validate a subgraph node's ports and its embedded inner workflow.

    Returns the inner workflow's sorted node order (prefixed by the caller)
    so the outer result exposes ``<subgraph_id>/<inner_id>`` ordering.
    """
    params = _node_params(node)
    inner_workflow = params.get("workflow")
    if not isinstance(inner_workflow, dict) or not inner_workflow.get("nodes"):
        errors.append(f"Subgraph node '{node_id}' is missing its embedded workflow")
        _validate_subgraph_port_lists(node_id, params, set(), errors)
        return []

    inner_result = validate_workflow(
        inner_workflow,
        registry,
        _depth=depth + 1,
        _implicit_parameters=SUBGRAPH_IMPLICIT_PARAMETERS,
    )
    for error in inner_result.errors:
        errors.append(f"Subgraph '{node_id}': {error}")
    for warning in inner_result.warnings:
        warnings.append(f"Subgraph '{node_id}': {warning}")

    _validate_subgraph_port_lists(node_id, params, _workflow_node_ids(inner_workflow), errors)
    return inner_result.sorted_node_order


def _validate_subgraph_port_lists(
    node_id: str,
    params: dict[str, Any],
    inner_node_ids: set[str],
    errors: list[str],
) -> None:
    for key, label in (("input_ports", "input"), ("output_ports", "output")):
        raw = params.get(key)
        if raw is None:
            continue
        if not isinstance(raw, list):
            errors.append(f"Subgraph node '{node_id}' {key} must be a list")
            continue
        for entry in raw:
            if not isinstance(entry, dict) or not str(entry.get("name", "") or "").strip():
                errors.append(
                    f"Subgraph node '{node_id}' has a {label} port without a name"
                )
                continue
            inner_node = str(
                entry.get("innerNodeId", entry.get("inner_node_id", "")) or ""
            )
            if inner_node_ids and inner_node not in inner_node_ids:
                errors.append(
                    f"Subgraph '{node_id}' {label} port '{entry.get('name')}' "
                    f"references unknown inner node '{inner_node}'"
                )


def _node_executes_loop_body(meta: Any) -> bool:
    if isinstance(meta, dict):
        return bool(meta.get("executes_loop_body"))
    return bool(getattr(meta, "EXECUTES_LOOP_BODY", False))


def _node_executes_try_catch_branches(meta: Any) -> bool:
    if isinstance(meta, dict):
        return bool(meta.get("executes_try_catch_branches"))
    return bool(getattr(meta, "EXECUTES_TRY_CATCH_BRANCHES", False))


def _loop_executor_nodes(
    nodes: dict[str, Any],
    registry_lookup: Any,
) -> set[str]:
    """IDs of nodes whose class re-runs a loop body (while/foreach/parallel_for)."""
    executors: set[str] = set()
    for node_id, node in nodes.items():
        node_type = str(node.get("type", "") if isinstance(node, dict) else getattr(node, "type", ""))
        if _node_executes_loop_body(registry_lookup(node_type)):
            executors.add(node_id)
    return executors


def _control_bodies(
    nodes: dict[str, Any],
    edges: list[Any],
    registry_lookup: Any,
) -> dict[str, set[str]]:
    """Map each control node to its body node IDs.

    Mirrors the executor's discovery: loop bodies are downstream of the loop's
    virtual ``iteration`` output; try/catch branches hang off its ``try`` and
    ``catch`` outputs. Traversal stops at the control node itself, so feedback
    edges (body -> control node) never pull the control node into its own body.
    """
    control_ports: dict[str, tuple[str, ...]] = {}
    for node_id, node in nodes.items():
        node_type = str(node.get("type", "") if isinstance(node, dict) else getattr(node, "type", ""))
        meta = registry_lookup(node_type)
        if _node_executes_loop_body(meta):
            control_ports[node_id] = ("iteration",)
        elif _node_executes_try_catch_branches(meta):
            control_ports[node_id] = ("try", "catch")
    bodies: dict[str, set[str]] = {}
    for control_id, ports in control_ports.items():
        body: set[str] = set()
        queue: list[str] = []
        for edge in edges:
            if edge_source(edge) != control_id or edge_source_port(edge) not in ports:
                continue
            target = edge_target(edge)
            if target in nodes and target != control_id and target not in body:
                body.add(target)
                queue.append(target)
        while queue:
            current = queue.pop()
            # Nested control nodes own their own bodies: the outer body stops
            # at the nested node itself so feedback edges inside the nested
            # body cannot form a cycle in the outer body's graph.
            current_node = nodes.get(current)
            current_type = str(
                current_node.get("type", "") if isinstance(current_node, dict) else getattr(current_node, "type", "")
            )
            current_meta = registry_lookup(current_type)
            if _node_executes_loop_body(current_meta) or _node_executes_try_catch_branches(current_meta):
                continue
            for edge in edges:
                if edge_source(edge) != current:
                    continue
                nxt = edge_target(edge)
                if nxt in nodes and nxt != control_id and nxt not in body:
                    body.add(nxt)
                    queue.append(nxt)
        bodies[control_id] = body
    return bodies


def _control_body_nodes(
    nodes: dict[str, Any],
    edges: list[Any],
    registry_lookup: Any,
) -> set[str]:
    """Union of every control node's body nodes."""
    union: set[str] = set()
    for body in _control_bodies(nodes, edges, registry_lookup).values():
        union.update(body)
    return union


def _saved_node_version(node: Any) -> str:
    """Return the version cached in a workflow node's stored node_info."""
    node_info: Any = {}
    if isinstance(node, dict):
        node_info = node.get("node_info", {})
    else:
        node_info = getattr(node, "node_info", {})
    if not isinstance(node_info, dict):
        return ""
    version = node_info.get("version", "")
    return str(version) if version else ""


def _registry_node_version(meta: Any) -> str:
    """Return the current registry version for a node class or metadata dict."""
    if isinstance(meta, dict):
        version = meta.get("version", "")
    else:
        version = getattr(meta, "VERSION", "")
    return str(version) if version else ""


def _matching_migration(meta: Any, saved_version: str) -> dict[str, Any] | None:
    migrations = meta.get("versioning", {}).get("migrations", []) if isinstance(meta, dict) else getattr(meta, "MIGRATIONS", [])
    if not isinstance(migrations, list):
        return None
    for migration in migrations:
        if not isinstance(migration, dict):
            continue
        from_version = str(migration.get("from_version", "") or "")
        if not from_version or _version_matches(saved_version, from_version):
            return migration
    return None


def _version_matches(saved_version: str, pattern: str) -> bool:
    if pattern.endswith(".x"):
        return saved_version.startswith(pattern[:-1])
    return saved_version == pattern or fnmatch.fnmatch(saved_version, pattern)


def _validate_workflow_parameters(
    raw_parameters: Any, errors: list[str], warnings: list[str]
) -> set[str]:
    """Validate workflow-level parameter definitions."""
    if raw_parameters in (None, {}):
        return set()
    if not isinstance(raw_parameters, list):
        errors.append("Workflow parameters must be a list")
        return set()

    seen: set[str] = set()
    for index, parameter in enumerate(raw_parameters):
        if not isinstance(parameter, dict):
            errors.append(f"Workflow parameter at index {index} must be an object")
            continue
        raw_name = parameter.get("name", "")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if not name:
            errors.append(f"Workflow parameter at index {index} must have a non-empty name")
            continue
        if name in seen:
            errors.append(f"Workflow parameter '{name}' is defined more than once")
        seen.add(name)

        raw_type = parameter.get("type", "STRING")
        param_type = raw_type.strip() if isinstance(raw_type, str) else ""
        if not param_type:
            errors.append(f"Workflow parameter '{name}' must have a non-empty type")

        # A required parameter with neither value nor default cannot resolve
        # from the definition alone. It is NOT an error: the run may supply it
        # (the executor accepts runtime overrides), and some templates require a
        # user-provided file by design — a custom SnpEff predictor, say. But it
        # is worth surfacing, because if the submission also omits it the run
        # dies on the worker after a VM has booted and a credit is spent, which
        # is how two official templates failed at ~41s into a paid run.
        if bool(parameter.get("required", False)):
            if parameter.get("value") is None and parameter.get("default") is None:
                warnings.append(
                    f"Required workflow parameter '{name}' has no value or default; "
                    "the run must supply it"
                )
    return seen


def _validate_workflow_parameter_references(
    nodes: dict[str, dict[str, Any]],
    parameter_names: set[str],
    errors: list[str],
    implicit_parameters: frozenset[str] = frozenset(),
) -> None:
    """Validate ``{{name}}`` references in execution-bound node values."""
    known = set(parameter_names) | set(implicit_parameters)
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        for root_key in ("params", "inputs", "widgets"):
            value = node.get(root_key)
            if value is None:
                continue
            if root_key == "params" and _node_is_subgraph(node):
                # The embedded workflow's own references are validated by the
                # recursive subgraph pass against the INNER parameter set.
                value = {
                    key: item
                    for key, item in value.items()
                    if key not in _SUBGRAPH_PARAM_KEYS
                }
            for path, name in _iter_workflow_parameter_references(value, root_key):
                if name not in known:
                    errors.append(
                        f"Node '{node_id}' references unknown workflow parameter '{name}' in {path}"
                    )


def _iter_workflow_parameter_references(value: Any, path: str) -> list[tuple[str, str]]:
    """Return parameter references found in a nested node value."""
    references: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in NODE_LOCAL_TEMPLATE_FIELDS:
                continue
            references.extend(_iter_workflow_parameter_references(item, f"{path}.{key_text}"))
        return references
    if isinstance(value, list):
        for index, item in enumerate(value):
            references.extend(_iter_workflow_parameter_references(item, f"{path}[{index}]"))
        return references
    if not isinstance(value, str):
        return references

    for match in WORKFLOW_PARAMETER_REFERENCE_RE.finditer(value):
        references.append((path, match.group(1)))
    return references
