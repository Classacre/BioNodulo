"""Helpers for reading workflow edges across BioNodulo payload shapes."""

from __future__ import annotations

from typing import Any


def node_outputs(node: dict[str, Any]) -> dict[str, Any]:
    outputs = node.get("outputs")
    if isinstance(outputs, dict) and outputs:
        return outputs

    node_info = node.get("node_info")
    if not isinstance(node_info, dict):
        return {}
    return_names = node_info.get("return_names")
    if not isinstance(return_names, list):
        return {}
    return {str(name): {} for name in return_names if name}


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
