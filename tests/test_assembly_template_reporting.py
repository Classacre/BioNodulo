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


def test_assembly_template_validates_prokka_gff_before_final_report_preview() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_prokka_001"] == "data_validator"
    assert node_types["assembly_report_001"] == "html_report"
    assert node_types["assembly_report_preview_001"] == "html_preview"

    validator = _node_by_id(workflow, "validate_prokka_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True

    report = _node_by_id(workflow, "assembly_report_001")
    assert report["params"]["title"] == "Assembly Annotation Report"
    assert report["params"]["section_names"] == (
        "Contig lengths,Per-contig metric summary,Contig statistics,QUAST report,Prokka annotation"
    )

    assert _has_edge(workflow, "prokka_001", "gff", "validate_prokka_001", "input")
    assert _has_edge(workflow, "validate_prokka_001", "passthrough", "assembly_report_001", "tables")
    assert _has_edge(workflow, "validate_quast_001", "passthrough", "assembly_report_001", "tables")
    assert _has_edge(workflow, "assembly_report_001", "html_report", "assembly_report_preview_001", "file")
    assert not _has_edge(workflow, "prokka_001", "gff", "assembly_report_001", "tables")
    assert not _has_edge(workflow, "quast_001", "report", "assembly_report_001", "tables")

    assert workflow["outputs"]["validated_prokka_annotation"] == "validate_prokka_001"
    assert workflow["outputs"]["assembly_report"] == "assembly_report_001"
    assert workflow["outputs"]["assembly_report_preview"] == "assembly_report_preview_001"


def test_assembly_template_reports_aggregated_contig_summary() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["assembly_contig_summary_001"] == "aggregate"

    summary = _node_by_id(workflow, "assembly_contig_summary_001")
    assert summary["params"] == {
        "group_columns": "id",
        "agg_column": "length",
        "agg_function": "sum",
        "agg_column_2": "gc_content",
        "agg_function_2": "mean",
        "output_type": "TSV",
    }

    report = _node_by_id(workflow, "assembly_report_001")
    assert report["params"]["section_names"] == (
        "Contig lengths,Per-contig metric summary,Contig statistics,QUAST report,Prokka annotation"
    )

    assert _has_edge(workflow, "assembly_stats_001", "stats_tsv", "assembly_contig_summary_001", "table")
    assert _has_edge(workflow, "assembly_contig_summary_001", "aggregated_table", "assembly_report_001", "tables")
    assert workflow["outputs"]["assembly_contig_summary"] == "assembly_contig_summary_001"
