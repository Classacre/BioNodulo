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


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_chip_seq_template_adds_final_html_report_from_validated_peaks() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types.get("peak_annotation_001") == "bedtools_closest"
    assert node_types.get("chip_seq_report_001") == "html_report"
    assert node_types.get("chip_seq_report_preview_001") == "html_preview"

    annotator = _node_by_id(workflow, "peak_annotation_001")
    report = _node_by_id(workflow, "chip_seq_report_001")
    assert annotator["params"]["distance"] is True
    assert annotator["params"]["mode"] == "first"
    assert report["params"]["title"] == "ChIP-Seq Report"
    assert "MACS2 peaks" in report["params"]["text_sections"]
    assert report["params"]["section_names"] == (
        "ChIP-seq signal coverage,Validated MACS2 peaks,Nearest peak annotations"
    )

    assert _has_edge(workflow, "macs2_001", "peaks", "chip_seq_report_001", "tables")
    assert _has_edge(workflow, "peak_annotation_001", "closest", "chip_seq_report_001", "tables")
    assert _has_edge(workflow, "chip_seq_report_001", "html_report", "chip_seq_report_preview_001", "file")
    assert not _has_edge(workflow, "coverage_001", "coverage_bw", "chip_seq_report_001", "images")
    assert workflow["outputs"]["peak_annotation"] == "peak_annotation_001"
    assert workflow["outputs"]["report"] == "chip_seq_report_001"
    assert workflow["outputs"]["chip_seq_report"] == "chip_seq_report_001"
    assert workflow["outputs"]["chip_seq_report_preview"] == "chip_seq_report_preview_001"
