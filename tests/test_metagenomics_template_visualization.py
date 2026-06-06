from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _has_edge(
    workflow: dict[str, Any],
    source: str,
    source_output: str,
    target: str,
    target_input: str,
) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_metagenomics_template_adds_qc_dashboard_from_fastqc_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    assert node_types["qc_dashboard_preview_001"] == "html_preview"
    dashboard = next(node for node in workflow["nodes"] if node["id"] == "qc_dashboard_001")
    assert dashboard["params"]["run_name"] == "Metagenomics QC"
    assert dashboard["params"]["title"] == "Metagenomics QC Dashboard"
    assert dashboard["params"]["theme"] == "light"
    assert _has_edge(workflow, "qc_001", "report_dir", "qc_dashboard_001", "fastqc_dir")
    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"
    assert workflow["outputs"]["qc_dashboard_preview"] == "qc_dashboard_preview_001"


def test_metagenomics_template_reports_humann_pathway_profiles() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_humann_pathways_001"] == "data_validator"
    assert node_types["validate_humann_pathcoverage_001"] == "data_validator"
    assert node_types["humann_pathcoverage_bar_001"] == "bar_chart"
    assert node_types["functional_report_001"] == "html_report"
    assert node_types["functional_report_preview_001"] == "html_preview"

    abundance_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_humann_pathways_001")
    coverage_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_humann_pathcoverage_001")
    coverage_chart = next(node for node in workflow["nodes"] if node["id"] == "humann_pathcoverage_bar_001")
    report = next(node for node in workflow["nodes"] if node["id"] == "functional_report_001")
    assert abundance_validator["params"]["expected_format"] == "tsv"
    assert abundance_validator["params"]["min_size_bytes"] > 0
    assert abundance_validator["params"]["fail_on_error"] is True
    assert coverage_validator["params"]["expected_format"] == "tsv"
    assert coverage_validator["params"]["min_size_bytes"] > 0
    assert coverage_validator["params"]["fail_on_error"] is True
    assert coverage_chart["params"]["title"] == "HUMAnN Pathway Coverage"
    assert coverage_chart["params"]["x_column"] == "# Pathway"
    assert coverage_chart["params"]["y_column"] == "trimmed_reads_Coverage"
    assert coverage_chart["params"]["orientation"] == "horizontal"
    assert coverage_chart["params"]["format"] == "png"
    assert report["params"]["title"] == "Metagenomics Functional Report"
    assert report["params"]["section_names"] == (
        "HUMAnN pathway abundance,HUMAnN pathway coverage,HUMAnN pathway coverage chart,HUMAnN gene families"
    )

    assert _has_edge(workflow, "humann_001", "pathabundance", "validate_humann_pathways_001", "input")
    assert _has_edge(workflow, "validate_humann_pathways_001", "passthrough", "functional_report_001", "tables")
    assert _has_edge(workflow, "humann_001", "pathcoverage", "validate_humann_pathcoverage_001", "input")
    assert _has_edge(workflow, "validate_humann_pathcoverage_001", "passthrough", "humann_pathcoverage_bar_001", "table")
    assert _has_edge(workflow, "validate_humann_pathcoverage_001", "passthrough", "functional_report_001", "tables")
    assert _has_edge(workflow, "humann_pathcoverage_bar_001", "chart_image", "functional_report_001", "images")
    assert _has_edge(workflow, "humann_001", "genefamilies", "functional_report_001", "tables")
    assert _has_edge(workflow, "functional_report_001", "html_report", "functional_report_preview_001", "file")
    assert workflow["outputs"]["validated_humann_pathways"] == "validate_humann_pathways_001"
    assert workflow["outputs"]["validated_humann_pathcoverage"] == "validate_humann_pathcoverage_001"
    assert workflow["outputs"]["functional_pathcoverage_chart"] == "humann_pathcoverage_bar_001"
    assert workflow["outputs"]["functional_report"] == "functional_report_001"
    assert workflow["outputs"]["functional_report_preview"] == "functional_report_preview_001"


def test_metagenomics_template_adds_bracken_abundance_heatmap_to_taxonomy_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["bracken_heatmap_001"] == "heatmap"
    heatmap = next(node for node in workflow["nodes"] if node["id"] == "bracken_heatmap_001")
    report = next(node for node in workflow["nodes"] if node["id"] == "taxonomy_report_001")

    assert heatmap["params"]["title"] == "Bracken Abundance Heatmap"
    assert heatmap["params"]["scale"] == "column"
    assert heatmap["params"]["format"] == "png"
    assert report["params"]["section_names"] == (
        "Bracken taxonomy chart,MetaPhlAn relative abundance,"
        "Bracken abundance heatmap,Bracken report"
    )

    assert _has_edge(workflow, "validate_bracken_001", "passthrough", "bracken_heatmap_001", "matrix")
    assert _has_edge(workflow, "bracken_heatmap_001", "heatmap_image", "taxonomy_report_001", "images")
    assert workflow["outputs"]["taxonomy_heatmap"] == "bracken_heatmap_001"
