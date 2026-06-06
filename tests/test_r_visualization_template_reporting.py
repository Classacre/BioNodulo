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


def test_r_visualization_report_includes_de_volcano_and_ma_plots() -> None:
    workflow = _load_template("r_visualization_pipeline.json")

    report = _node(workflow, "viz_report_001")
    assert report["params"]["section_names"] == (
        "QC plot,Expression plot,Heatmap,Volcano plot,MA plot"
    )

    assert _has_edge(workflow, "qc_plot_001", "plot_png", "viz_report_001", "images")
    assert _has_edge(workflow, "expr_plot_001", "plot_png", "viz_report_001", "images")
    assert _has_edge(workflow, "pheatmap_001", "plot_png", "viz_report_001", "images")
    assert _has_edge(workflow, "volcano_001", "volcano_image", "viz_report_001", "images")
    assert _has_edge(workflow, "ma_plot_001", "ma_image", "viz_report_001", "images")
