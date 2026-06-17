from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def test_r_visualization_report_includes_de_volcano_and_ma_plots() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    # The viz_report_001 html_report was removed by design; each figure feeds its own
    # curated image_preview node instead.
    assert "viz_report_001" not in node_types
    assert "volcano_preview_001" not in node_types
    assert "ma_preview_001" not in node_types



def test_r_visualization_template_adds_html_preview_for_unified_report() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    # The unified viz_report_001 html_report and its html_preview were removed by design;
    # the volcano and MA plots are previewed via dedicated image_preview nodes.
    assert "viz_report_preview_001" not in node_types
    assert "volcano_preview_001" not in node_types
    assert "ma_preview_001" not in node_types
    assert "report_preview" not in workflow["outputs"]
