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


def test_rna_seq_template_adds_counts_html_report_from_raw_and_normalized_tables() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["counts_report_001"] == "html_report"
    assert node_types["counts_report_preview_001"] == "html_preview"

    report = _node(workflow, "counts_report_001")
    assert report["params"]["title"] == "RNA-Seq Counts Report"
    assert report["params"]["section_names"] == "Raw featureCounts,Normalized CPM counts"
    assert report["params"]["max_table_rows"] == 100

    assert _has_edge(workflow, "counts_001", "counts", "counts_report_001", "tables")
    assert _has_edge(workflow, "normalize_counts_001", "normalized_table", "counts_report_001", "tables")
    assert _has_edge(workflow, "counts_report_001", "html_report", "counts_report_preview_001", "file")

    assert workflow["outputs"]["counts_report"] == "counts_report_001"
    assert workflow["outputs"]["counts_report_preview"] == "counts_report_preview_001"
    assert workflow["outputs"]["report"] == "qc_dashboard_001"


def test_rna_seq_template_previews_alignment_qc_dashboard() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    assert node_types["qc_dashboard_preview_001"] == "html_preview"

    dashboard = _node(workflow, "qc_dashboard_001")
    assert dashboard["params"]["title"] == "RNA-Seq Alignment QC Dashboard"

    assert _has_edge(workflow, "qc_001", "report_dir", "qc_dashboard_001", "fastqc_dir")
    assert _has_edge(workflow, "flagstat_001", "stats", "qc_dashboard_001", "alignment_stats")
    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"
    assert workflow["outputs"]["qc_dashboard_preview"] == "qc_dashboard_preview_001"
