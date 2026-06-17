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

    assert node_types["counts_heatmap_001"] == "r_pheatmap"
    # The counts_report_001 html_report and its html_preview were removed by design;
    # each feeder now renders into a dedicated preview node.
    assert "counts_report_001" not in node_types
    assert "counts_report_preview_001" not in node_types
    assert "render_counts_heatmap_ima_2" not in node_types
    assert node_types["render_counts_tab_0"] == "table_preview"
    assert node_types["render_normalize_counts_tab_1"] == "table_preview"

    heatmap = _node(workflow, "counts_heatmap_001")
    assert heatmap["params"]["scale"] == "row"
    assert heatmap["params"]["cluster_rows"] is True

    assert _has_edge(workflow, "normalize_counts_001", "normalized_table", "counts_heatmap_001", "data_csv")
    assert _has_edge(workflow, "counts_001", "counts", "render_counts_tab_0", "file")
    assert _has_edge(workflow, "normalize_counts_001", "normalized_table", "render_normalize_counts_tab_1", "file")

    assert workflow["outputs"]["counts_heatmap"] == "counts_heatmap_001"
    assert "counts_report" not in workflow["outputs"]
    assert "counts_report_preview" not in workflow["outputs"]
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


def test_rna_seq_template_reports_qualimap_alignment_qc() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    # The alignment_qc_report_001 html_report and its html_preview were removed by
    # design; QualiMap and flagstat outputs render into dedicated preview nodes.
    assert "alignment_qc_report_001" not in node_types
    assert "alignment_qc_report_preview_001" not in node_types
    assert node_types["render_qualimap_tab_0"] == "table_preview"
    assert node_types["render_flagstat_tab_1"] == "table_preview"

    assert _has_edge(workflow, "qualimap_001", "report", "render_qualimap_tab_0", "file")
    assert _has_edge(workflow, "flagstat_001", "stats", "render_flagstat_tab_1", "file")
    assert "alignment_qc_report" not in workflow["outputs"]
    assert "alignment_qc_report_preview" not in workflow["outputs"]
