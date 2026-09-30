"""Read real editor nodes and older converter fixtures through one contract."""

from __future__ import annotations

from typing import Any


_SCALAR_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN", "JSON"}


def node_parameters(node: dict[str, Any]) -> dict[str, Any]:
    """Editor ``params`` are authoritative; reject conflicting legacy values."""
    params = node.get("params") or {}
    widgets = node.get("widgets") or {}
    if not isinstance(params, dict) or not isinstance(widgets, dict):
        raise ValueError(f"Node {node.get('id')!r} params/widgets must be objects")
    conflict = {name for name in params.keys() & widgets.keys() if params[name] != widgets[name]}
    if conflict:
        raise ValueError(f"Node {node.get('id')!r} has conflicting params/widgets: {', '.join(sorted(conflict))}")
    return {**widgets, **params}


def node_input_specs(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    info = node.get("node_info") or {}
    sections = info.get("input_types") or info.get("input") or {}
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(sections, dict):
        return result
    for section in ("required", "optional"):
        entries = sections.get(section) or {}
        if not isinstance(entries, dict):
            continue
        for name, spec in entries.items():
            if isinstance(spec, dict):
                result[name] = spec
            elif isinstance(spec, (list, tuple)) and spec:
                options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                result[name] = {"type": str(spec[0]), **options}
    return result


def node_input_ports(node: dict[str, Any]) -> dict[str, Any]:
    explicit = node.get("inputs") or {}
    if not isinstance(explicit, dict):
        raise ValueError(f"Node {node.get('id')!r} inputs must be an object")
    result = dict(explicit)
    promoted = (node.get("ui") or {}).get("promotedInputs") or []
    for name, spec in node_input_specs(node).items():
        kind = str(spec.get("type", "")).upper()
        interactive = kind in _SCALAR_TYPES or bool(spec.get("options"))
        if not interactive or spec.get("forceInput") or spec.get("link") or name in promoted:
            result.setdefault(name, {"type": kind})
    return result


def node_option_widgets(
    node: dict[str, Any], *, connected_inputs: set[str] | None = None,
) -> dict[str, Any]:
    """Return scalar options and one unconnected input path, never a fake CLI flag."""
    values = node_parameters(node)
    connected = connected_inputs or set()
    file_ports = set(node_input_ports(node))
    options = {name: value for name, value in values.items() if name not in file_ports}
    node_type = node.get("type")
    primary = "reads" if node_type == "fastqc" else "reports" if node_type == "multiqc" else None
    for name in file_ports:
        value = values.get(name)
        if name in connected:
            if value not in (None, "", []):
                raise ValueError(f"Node {node.get('id')!r} has both a connected and inline {name!r} input")
        elif name == primary and value not in (None, "", []):
            if isinstance(value, list):
                if len(value) != 1 or not isinstance(value[0], str):
                    raise ValueError(f"Node {node.get('id')!r} export supports one inline {name!r} file")
                value = value[0]
            if not isinstance(value, str):
                raise ValueError(f"Node {node.get('id')!r} inline {name!r} must be a file path")
            if "input_path" in options and options["input_path"] != value:
                raise ValueError(f"Node {node.get('id')!r} has conflicting input paths")
            options["input_path"] = value
        elif value not in (None, "", []):
            raise ValueError(f"Node {node.get('id')!r} has unsupported inline file input {name!r}")
    return options


def canonicalize_foreign_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """Give structural foreign imports the canvas' actual node/edge shape."""
    nodes = workflow.get("nodes", [])
    node_by_id = {node["id"]: node for node in nodes}
    canonical_nodes: list[dict[str, Any]] = []
    for node in nodes:
        inputs = node.get("inputs") or {}
        outputs = node.get("outputs") or {}
        position = node.get("position", node.get("pos", [100, 100]))
        params = node_parameters(node)
        canonical_nodes.append({
            "id": node["id"], "type": node["type"], "position": position,
            "params": params, "meta": node.get("meta", {}),
            "node_info": {
                "id": node["type"], "display_name": "Imported tool — review before run",
                "category": "imported", "input_types": {
                    "required": {name: {"type": (spec.get("type", "FILE") if isinstance(spec, dict) else "FILE")}
                                 for name, spec in inputs.items()},
                },
                "return_names": list(outputs),
                "return_types": [(spec.get("type", "FILE") if isinstance(spec, dict) else "FILE")
                                 for spec in outputs.values()],
            },
        })
    canonical_edges: list[dict[str, Any]] = []
    from bionodulo.converter.edge_utils import edge_source, edge_source_port, edge_target, edge_target_port

    for edge in workflow.get("edges", []):
        source, target = str(edge_source(edge)), str(edge_target(edge))
        source_port, target_port = edge_source_port(edge), edge_target_port(edge)
        source_outputs = node_by_id[source].get("outputs") or {}
        target_inputs = node_by_id[target].get("inputs") or {}
        if source_port == "default" and len(source_outputs) == 1:
            source_port = next(iter(source_outputs))
        if target_port == "default" and len(target_inputs) == 1:
            target_port = next(iter(target_inputs))
        if source_port not in source_outputs or target_port not in target_inputs:
            raise ValueError("Foreign workflow edge cannot be mapped to an editor port")
        canonical_edges.append({
            "id": edge.get("id") or f"edge_{source}_{target}_{target_port}",
            "from": {"node": source, "output": source_port},
            "to": {"node": target, "input": target_port},
        })
    return {
        "version": "2.0", "app": "bionodulo", "description": "",
        "groups": [], "outputs": {}, "parameters": [], "comments": [],
        **workflow, "nodes": canonical_nodes, "edges": canonical_edges,
    }
