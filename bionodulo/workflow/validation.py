"""Workflow validation for BioNodulo.

Checks node types exist, edges are valid, no cycles exist, and all
required inputs are connected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import re
from typing import Any

from bionodulo.workflow.graph import edge_source, edge_target, edge_target_port, topological_sort


WORKFLOW_PARAMETER_REFERENCE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}")
NODE_LOCAL_TEMPLATE_FIELDS = {
    "custom_prompt",
    "custom_script",
    "prompt",
    "system_prompt",
    "template",
    "workflow_template",
}


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
    parameter_names = _validate_workflow_parameters(workflow.get("parameters", []), errors)

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

    _validate_workflow_parameter_references(nodes, parameter_names, errors)

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


def _validate_workflow_parameters(raw_parameters: Any, errors: list[str]) -> set[str]:
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
    return seen


def _validate_workflow_parameter_references(
    nodes: dict[str, dict[str, Any]],
    parameter_names: set[str],
    errors: list[str],
) -> None:
    """Validate ``{{name}}`` references in execution-bound node values."""
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        for root_key in ("params", "inputs", "widgets"):
            value = node.get(root_key)
            if value is None:
                continue
            for path, name in _iter_workflow_parameter_references(value, root_key):
                if name not in parameter_names:
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
