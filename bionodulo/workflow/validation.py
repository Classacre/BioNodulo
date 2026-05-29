"""Workflow validation for BioNodulo.

Checks node types exist, edges are valid, no cycles exist, and all
required inputs are connected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bionodulo.workflow.graph import edge_source, edge_target, edge_target_port, topological_sort


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
) -> ValidationResult:
    """Validate a workflow for structural and semantic correctness.

    Checks:
    1. Node types are registered.
    2. Edges reference valid node IDs.
    3. No cycles (DAG).
    4. Required inputs are connected or have defaults.
    """
    errors: list[str] = []
    warnings: list[str] = []
    sorted_order: list[str] = []

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

    def registry_lookup(node_type: str) -> Any:
        if registry is None:
            return None
        if hasattr(registry, "get_node"):
            return registry.get_node(node_type)
        if hasattr(registry, "get"):
            return registry.get(node_type)
        return None

    # Check 1: All node types exist
    for node_id, node in nodes.items():
        if not node:
            errors.append(f"Node '{node_id}' has no data")
            continue
        node_type = node.get("type", "") if isinstance(node, dict) else getattr(node, "type", "")
        if not node_type:
            errors.append(f"Node '{node_id}' has no type")
            continue
        if registry is not None and registry_lookup(node_type) is None:
            errors.append(f"Node '{node_id}' uses unregistered type '{node_type}'")

    # Check 2: Edges reference valid nodes
    for edge in edges:
        src = edge_source(edge)
        dst = edge_target(edge)
        if src and src not in nodes:
            errors.append(f"Edge references unknown source node '{src}'")
        if dst and dst not in nodes:
            errors.append(f"Edge references unknown target node '{dst}'")
        if src == dst:
            warnings.append(f"Self-loop on node '{src}'")

    # Check 3: No cycles
    try:
        sorted_order = topological_sort(workflow)
    except ValueError as exc:
        errors.append(f"Cycle detected: {exc}")

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
