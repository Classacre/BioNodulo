"""Helpers for reading workflow edges across BioNodulo payload shapes."""

from __future__ import annotations

from typing import Any

from bionodulo.converter.node_adapter import node_input_ports


def executable_nodes(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Exclude canvas notes, which have no runtime ports or execution semantics."""
    raw_nodes = workflow.get("nodes", [])
    if not isinstance(raw_nodes, list):
        raise ValueError("Workflow nodes must be a list")
    nodes: dict[str, dict[str, Any]] = {}
    ids: set[str] = set()
    for node in raw_nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise ValueError("Workflow nodes require a nonempty string id")
        node_id = node["id"]
        if node_id in ids:
            raise ValueError(f"Duplicate workflow node id: {node_id}")
        ids.add(node_id)
        if node.get("type") != "note":
            nodes[node_id] = node
    return nodes


def executable_edges(
    workflow: dict[str, Any], nodes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep note decorations but reject broken executable connections.

    Silently dropping an edge would export a different computation from the
    one the user drew, often leaving a downstream step with an unbound input.
    """
    note_ids = {
        node["id"] for node in workflow.get("nodes", []) if node.get("type") == "note"
    }
    raw_edges = workflow.get("edges", [])
    if not isinstance(raw_edges, list):
        raise ValueError("Workflow edges must be a list")
    result: list[dict[str, Any]] = []
    for edge in raw_edges:
        if not isinstance(edge, dict):
            raise ValueError("Workflow edges must be objects")
        source, target = edge_source(edge), edge_target(edge)
        if source in note_ids or target in note_ids:
            continue
        if source not in nodes or target not in nodes:
            raise ValueError(f"Cannot export edge {edge.get('id', '')!r}: unknown executable node")
        result.append(edge)
    return result


def validate_edge_ports(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]],
) -> None:
    """Reject edges that would bind the wrong port or overwrite an input."""
    bound_inputs: set[tuple[str, str]] = set()
    for edge in edges:
        source, target = str(edge_source(edge)), str(edge_target(edge))
        source_port, target_port = edge_source_port(edge), edge_target_port(edge)
        if source_port not in node_outputs(nodes[source]):
            raise ValueError(f"Edge {edge.get('id', '')!r} references an unknown output port")
        target_inputs = node_input_ports(nodes[target])
        if target_inputs and target_port not in target_inputs:
            raise ValueError(f"Edge {edge.get('id', '')!r} references an unknown input port")
        binding = (target, target_port)
        if binding in bound_inputs:
            raise ValueError(f"Edge {edge.get('id', '')!r} binds an input port more than once")
        bound_inputs.add(binding)

    indegree = {node_id: 0 for node_id in nodes}
    children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        source, target = str(edge_source(edge)), str(edge_target(edge))
        indegree[target] += 1
        children[source].append(target)
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        source = ready.pop()
        visited += 1
        for target in children[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(nodes):
        raise ValueError("Cannot export workflow with a dependency cycle")


def node_outputs(node: dict[str, Any]) -> dict[str, Any]:
    outputs = node.get("outputs")
    if isinstance(outputs, dict) and outputs:
        return outputs

    node_info = node.get("node_info")
    if not isinstance(node_info, dict):
        return {}
    return_names = node_info.get("return_names") or node_info.get("output_name")
    if not isinstance(return_names, list):
        return {}
    return_types = node_info.get("return_types") or node_info.get("output") or []
    return {str(name): {"type": return_types[index] if index < len(return_types) else "FILE"}
            for index, name in enumerate(return_names) if name}


def node_output_path(node_id: str, port: str, spec: Any) -> str:
    if isinstance(spec, dict) and "path" in spec:
        return str(spec["path"])
    return "results/" + node_id + "/" + port + "_output"


def edge_source(edge: dict[str, Any]) -> Any:
    source = edge.get("source", edge.get("source_node"))
    if source is None and isinstance(edge.get("from"), dict):
        source = edge["from"].get("node")
    return source


def edge_target(edge: dict[str, Any]) -> Any:
    target = edge.get("target", edge.get("target_node"))
    if target is None and isinstance(edge.get("to"), dict):
        target = edge["to"].get("node")
    return target


def edge_source_port(edge: dict[str, Any], default: str = "default") -> str:
    source_port = edge.get("source_output", edge.get("source_port"))
    if source_port is None and isinstance(edge.get("from"), dict):
        source_port = edge["from"].get("output")
    return str(source_port if source_port is not None else default)


def edge_target_port(edge: dict[str, Any], default: str = "default") -> str:
    target_port = edge.get("target_input", edge.get("target_port"))
    if target_port is None and isinstance(edge.get("to"), dict):
        target_port = edge["to"].get("input")
    return str(target_port if target_port is not None else default)
