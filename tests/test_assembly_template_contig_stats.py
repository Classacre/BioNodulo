from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_assembly_template_adds_contig_stats_chart_to_final_report() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["assembly_stats_001"] == "bp_seq_stats"
    assert node_types["assembly_stats_chart_001"] == "bar_chart"

    chart = _node(workflow, "assembly_stats_chart_001")
    assert chart["params"]["x_column"] == "id"
    assert chart["params"]["y_column"] == "length"
    assert chart["params"]["orientation"] == "horizontal"
    assert chart["params"]["format"] == "svg"

    # The HTML report was replaced by direct render nodes (table_preview /
    # image_preview) — the chart and stats table are previewed individually.
    assert "render_assembly_stats_chart_ima_4" not in node_types
    assert node_types["render_assembly_stats_tab_1"] == "table_preview"

    assert _has_edge(workflow, "gate_assembly_001", "output", "assembly_stats_001", "input_file")
    assert _has_edge(workflow, "assembly_stats_001", "stats_tsv", "assembly_stats_chart_001", "table")
    assert _has_edge(workflow, "assembly_stats_001", "stats_tsv", "render_assembly_stats_tab_1", "file")

    assert workflow["outputs"]["assembly_stats"] == "assembly_stats_001"
    assert workflow["outputs"]["assembly_stats_chart"] == "assembly_stats_chart_001"
