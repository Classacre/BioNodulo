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

    assert "validate_humann_pathways_001" not in node_types
    assert "validate_humann_pathcoverage_001" not in node_types
    assert node_types["humann_pathcoverage_bar_001"] == "bar_chart"
    # The functional_report_001 html_report and its html_preview were removed by design;
    # each HUMAnN feeder renders into a dedicated preview node.
    assert "functional_report_001" not in node_types
    assert "functional_report_preview_001" not in node_types
    assert node_types["render_humann_tab_0"] == "table_preview"
    assert node_types["render_humann_tab_1"] == "table_preview"
    assert node_types["render_humann_tab_2"] == "table_preview"
    assert "render_humann_pathcoverage_bar_ima_3" not in node_types

    abundance_validator = _output_validation(workflow, "humann_001", "pathabundance")
    coverage_validator = _output_validation(workflow, "humann_001", "pathcoverage")
    coverage_chart = next(node for node in workflow["nodes"] if node["id"] == "humann_pathcoverage_bar_001")
    assert abundance_validator["expected_format"] == "tsv"
    assert abundance_validator["min_size_bytes"] > 0
    assert abundance_validator["fail_on_error"] is True
    assert coverage_validator["expected_format"] == "tsv"
    assert coverage_validator["min_size_bytes"] > 0
    assert coverage_validator["fail_on_error"] is True
    assert coverage_chart["params"]["title"] == "HUMAnN Pathway Coverage"
    assert coverage_chart["params"]["x_column"] == "# Pathway"
    assert coverage_chart["params"]["y_column"] == "trimmed_reads_Coverage"
    assert coverage_chart["params"]["orientation"] == "horizontal"
    assert coverage_chart["params"]["format"] == "svg"

    assert not _has_edge(workflow, "humann_001", "pathabundance", "validate_humann_pathways_001", "input")
    assert _has_edge(workflow, "humann_001", "pathabundance", "render_humann_tab_0", "file")
    assert not _has_edge(workflow, "humann_001", "pathcoverage", "validate_humann_pathcoverage_001", "input")
    assert _has_edge(workflow, "humann_001", "pathcoverage", "humann_pathcoverage_bar_001", "table")
    assert _has_edge(workflow, "humann_001", "pathcoverage", "render_humann_tab_1", "file")
    assert _has_edge(workflow, "humann_001", "genefamilies", "render_humann_tab_2", "file")
    assert workflow["outputs"]["validated_humann_pathways"] == "humann_001"
    assert workflow["outputs"]["validated_humann_pathcoverage"] == "humann_001"
    assert workflow["outputs"]["functional_pathcoverage_chart"] == "humann_pathcoverage_bar_001"


def test_metagenomics_template_adds_bracken_abundance_heatmap_to_taxonomy_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["bracken_heatmap_001"] == "heatmap"
    # The taxonomy_report_001 html_report was removed by design; the heatmap renders
    # into a dedicated image_preview node.
    assert "taxonomy_report_001" not in node_types
    assert "render_bracken_heatmap_ima_2" not in node_types
    heatmap = next(node for node in workflow["nodes"] if node["id"] == "bracken_heatmap_001")

    assert heatmap["params"]["title"] == "Bracken Abundance Heatmap"
    assert heatmap["params"]["scale"] == "column"
    assert heatmap["params"]["format"] == "html"

    assert _has_edge(workflow, "bracken_001", "report", "bracken_heatmap_001", "matrix")
    assert workflow["outputs"]["taxonomy_heatmap"] == "bracken_heatmap_001"
