"""Workflow validation for BioNodulo.

Checks node types exist, edges are valid, no cycles exist, and all
required inputs are connected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bionodulo.workflow.graph import topological_sort


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

    # Check 1: All node types exist
    for node_id, node in nodes.items():
        if not node:
            errors.append(f"Node '{node_id}' has no data")
            continue
        node_type = node.get("type", "") if isinstance(node, dict) else getattr(node, "type", "")
        if not node_type:
            errors.append(f"Node '{node_id}' has no type")
            continue
        if registry is not None and hasattr(registry, "get_node"):
            meta = registry.get_node(node_type)
            if meta is None:
                errors.append(f"Node '{node_id}' uses unregistered type '{node_type}'")

    # Check 2: Edges reference valid nodes
    for edge in edges:
        if isinstance(edge, dict):
            src = edge.get("from_node") or edge.get("source_node", "")
            dst = edge.get("to_node") or edge.get("target_node", "")
        else:
            src = getattr(edge, "source_node", "")
            dst = getattr(edge, "target_node", "")
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
        if isinstance(edge, dict):
            dst = edge.get("to_node") or edge.get("target_node", "")
            dst_in = edge.get("to_input") or edge.get("target_input", "")
        else:
            dst = getattr(edge, "target_node", "")
            dst_in = getattr(edge, "target_input", "")
        if dst and dst_in:
            connected_inputs.setdefault(dst, set()).add(dst_in)

    for node_id, node in nodes.items():
        if not node:
            continue
        node_type = node.get("type", "") if isinstance(node, dict) else getattr(node, "type", "")
        if registry is not None and hasattr(registry, "get_node"):
            meta = registry.get_node(node_type)
            if meta and isinstance(meta, dict):
                inputs = meta.get("inputs", {})
                if isinstance(inputs, dict):
                    for in_name, in_spec in inputs.items():
                        if isinstance(in_spec, dict) and in_spec.get("required", False):
                            if in_name not in connected_inputs.get(node_id, set()):
                                params = (
                                    node.get("params", {})
                                    if isinstance(node, dict)
                                    else getattr(node, "params", {})
                                )
                                if in_name not in params:
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
