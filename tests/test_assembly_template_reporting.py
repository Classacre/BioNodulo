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


def test_assembly_template_validates_prokka_gff_before_final_report_preview() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_prokka_001" not in node_types
    assert node_types["render_prokka_tab_0"] == "table_preview"

    validator = _output_validation(workflow, "prokka_001", "gff")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True

    assert not _has_edge(workflow, "prokka_001", "gff", "validate_prokka_001", "input")
    assert _has_edge(workflow, "prokka_001", "gff", "render_prokka_tab_0", "file")

    assert workflow["outputs"]["validated_prokka_annotation"] == "prokka_001"


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

    assert node_types["render_assembly_contig_summary_tab_2"] == "table_preview"

    assert _has_edge(workflow, "assembly_stats_001", "stats_tsv", "assembly_contig_summary_001", "table")
    assert _has_edge(workflow, "assembly_contig_summary_001", "aggregated_table", "render_assembly_contig_summary_tab_2", "file")
    assert workflow["outputs"]["assembly_contig_summary"] == "assembly_contig_summary_001"
