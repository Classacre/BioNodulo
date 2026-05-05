from __future__ import annotations

from typing import Any


def summarize_outputs(node_outputs: dict[str, Any]) -> list[str]:
    summary: list[str] = []
    for node_id, outputs in node_outputs.items():
        summary.append(f"{node_id}: {outputs}")
    return summary
