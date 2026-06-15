from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def _node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node(workflow, node_id)
    return (
        node.get("ui", {})
        .get("validation", {})
        .get("outputs", {})
        .get(output, {})
    )


def test_single_cell_template_retries_only_cellranger_count_after_fastq_validation() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["cr_count_retry_001"] == "retry"
    retry = next(node for node in workflow["nodes"] if node["id"] == "cr_count_retry_001")
    assert retry["params"] == {
        "max_retries": 2,
        "delay_seconds": 5.0,
        "backoff_multiplier": 2.0,
        "max_delay": 120,
        "retry_on": "all",
        "only_retry_specific_nodes": "cr_count_001",
    }

    assert not _has_edge(workflow, "fastq_001", "directory", "validate_fastq_dir_001", "input")
    assert _has_edge(workflow, "fastq_001", "directory", "cr_count_retry_001", "input")
    assert _has_edge(workflow, "cr_count_retry_001", "passthrough", "cr_count_001", "fastq_dir")
    assert _has_edge(workflow, "ref_001", "directory", "cr_count_001", "transcriptome")
    assert not _has_edge(workflow, "validate_fastq_dir_001", "passthrough", "cr_count_001", "fastq_dir")
    assert not _has_edge(workflow, "fastq_001", "directory", "cr_count_001", "fastq_dir")
    assert _has_edge(workflow, "ref_001", "directory", "cr_count_001", "transcriptome")
    assert workflow["outputs"]["cellranger_retry_policy"] == "cr_count_retry_001"


def test_single_cell_template_validates_cellranger_metrics_and_includes_them_in_report() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_metrics_summary_001" not in node_types
    assert node_types["metrics_summary_chart_001"] == "bar_chart"
    validator = _output_validation(workflow, "cr_count_001", "metrics_summary")
    chart = _node(workflow, "metrics_summary_chart_001")
    node_types = _node_types(workflow)

    assert validator["expected_format"] == "csv"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert chart["params"] == {
        "title": "Cell Ranger Metrics Summary",
        "x_column": "Metric Name",
        "y_column": "Metric Value",
        "orientation": "horizontal",
        "format": "png",
    }
    # The HTML report was replaced by direct render nodes: the metrics table and
    # the chart are each previewed individually.
    assert node_types["render_cr_count_tab_0"] == "table_preview"
    assert node_types["render_metrics_summary_chart_ima_1"] == "image_preview"

    assert not _has_edge(workflow, "cr_count_001", "metrics_summary", "validate_metrics_summary_001", "input")
    assert _has_edge(workflow, "cr_count_001", "metrics_summary", "metrics_summary_chart_001", "table")
    assert _has_edge(workflow, "metrics_summary_chart_001", "chart_image", "render_metrics_summary_chart_ima_1", "file")
    assert _has_edge(workflow, "cr_count_001", "metrics_summary", "render_cr_count_tab_0", "file")
    assert workflow["outputs"]["validated_metrics_summary"] == "cr_count_001"
    assert workflow["outputs"]["metrics_summary_chart"] == "metrics_summary_chart_001"


def test_single_cell_template_advertises_qc_dashboard_preview() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_preview_001"] == "html_preview"
    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert workflow["outputs"]["qc_dashboard_preview"] == "qc_dashboard_preview_001"


def test_single_cell_template_advertises_cellranger_filtered_matrix_outputs() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["cr_count_001"] == "cellranger_count"
    assert workflow["outputs"]["filtered_feature_bc_matrix"] == "cr_count_001"
    assert workflow["outputs"]["filtered_feature_bc_matrix_h5"] == "cr_count_001"
