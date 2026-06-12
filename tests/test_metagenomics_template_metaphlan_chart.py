from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)



def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node_by_id(workflow, node_id)
    return (
        node.get("ui", {})
        .get("validation", {})
        .get("outputs", {})
        .get(output, {})
    )

def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_metagenomics_template_charts_metaphlan_profile_in_taxonomy_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["metaphlan_001"] == "metaphlan"
    assert "validate_metaphlan_profile_001" not in node_types
    assert node_types["metaphlan_bar_001"] == "bar_chart"
    assert node_types["taxonomy_report_001"] == "html_report"
    assert node_types["taxonomy_report_preview_001"] == "html_preview"

    validator = _output_validation(workflow, "metaphlan_001", "profile")
    chart = _node_by_id(workflow, "metaphlan_bar_001")
    report = _node_by_id(workflow, "taxonomy_report_001")
    assert validator["expected_format"] == "tsv"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert chart["params"]["title"] == "MetaPhlAn Relative Abundance"
    assert chart["params"]["x_column"] == "clade_name"
    assert chart["params"]["y_column"] == "relative_abundance"
    assert chart["params"]["orientation"] == "horizontal"
    assert chart["params"]["format"] == "png"
    assert report["params"]["section_names"] == (
        "Bracken taxonomy chart,MetaPhlAn relative abundance,"
        "Bracken abundance heatmap,Bracken report"
    )

    assert not _has_edge(workflow, "metaphlan_001", "profile", "validate_metaphlan_profile_001", "input")
    assert _has_edge(workflow, "metaphlan_001", "profile", "metaphlan_bar_001", "table")
    assert _has_edge(workflow, "metaphlan_bar_001", "chart_image", "taxonomy_report_001", "images")
    assert _has_edge(workflow, "taxonomy_report_001", "html_report", "taxonomy_report_preview_001", "file")
    assert _has_edge(workflow, "metaphlan_001", "profile", "metaphlan_bar_001", "table")
    assert workflow["outputs"]["validated_metaphlan_profile"] == "metaphlan_001"
    assert workflow["outputs"]["metaphlan_chart"] == "metaphlan_bar_001"
    assert workflow["outputs"]["taxonomy_report_preview"] == "taxonomy_report_preview_001"
