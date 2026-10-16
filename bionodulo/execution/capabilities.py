"""Conservative instance exceptions to class-level capability defaults."""
from __future__ import annotations

from typing import Any

from bionodulo.workflow.graph import edge_target, edge_target_port


def explicit_dorado_cpu_mode(node: dict[str, Any], edges: Any, *, nested: bool = False) -> bool:
    """Only a top-level, unbound literal CPU simplex selection needs no GPU.

    Inputs/widgets, connected devices, placeholders and nested port mappings
    can change effective execution. Keep their conservative GPU requirement.
    Dorado correct/duplex and unknown prefix variants are deliberately excluded.
    """
    if nested or node.get("type") != "dorado_basecaller":
        return False
    params = node.get("params")
    if not isinstance(params, dict) or params.get("device") != "cpu":
        return False
    for key in ("inputs", "widgets"):
        values = node.get(key, {})
        if not isinstance(values, dict) or "device" in values:
            return False
    if not isinstance(edges, list) or any(not isinstance(edge, dict) for edge in edges):
        return False
    return not any(
        edge_target(edge) == str(node.get("id", "")) and edge_target_port(edge) == "device"
        for edge in edges
    )
