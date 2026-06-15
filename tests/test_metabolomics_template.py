from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


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


def _target_input_count(workflow: dict[str, Any], target: str, target_input: str) -> int:
    return sum(
        edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_metabolomics_lcms_template_covers_xcms_camera_workflow() -> None:
    workflow = _load_template("metabolomics_lcms_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Metabolomics LC-MS Workflow"
    assert workflow["category"] == "Metabolomics"
    assert {"metabolomics", "lc-ms", "xcms", "camera", "peak-detection", "retention-time"}.issubset(
        set(workflow["tags"])
    )
    assert {
        "input_file",
        "xcms_peak_detection",
        "xcms_retention_correction",
        "camera_annotation",
    }.issubset(set(workflow["tools"]))

    assert node_types["mzml_001"] == "input_file"
    assert "validate_mzml_001" not in node_types
    assert node_types["xcms_peak_detection_001"] == "xcms_peak_detection"
    assert "validate_feature_table_001" not in node_types
    assert node_types["xcms_retention_correction_001"] == "xcms_retention_correction"
    assert "validate_aligned_features_001" not in node_types
    assert node_types["camera_annotation_001"] == "camera_annotation"
    assert "validate_camera_peaklist_001" not in node_types
    assert "metabolomics_report_001" not in node_types
    assert "metabolomics_report_preview_001" not in node_types

    assert not _has_edge(workflow, "mzml_001", "file", "validate_mzml_001", "input")
    assert _has_edge(workflow, "mzml_001", "file", "xcms_peak_detection_001", "mzml_files")
    assert not _has_edge(workflow, "xcms_peak_detection_001", "feature_table", "validate_feature_table_001", "input")
    assert _has_edge(workflow, "xcms_peak_detection_001", "xcms_object", "xcms_retention_correction_001", "xcms_object")
    assert not _has_edge(
        workflow,
        "xcms_retention_correction_001",
        "aligned_feature_table",
        "validate_aligned_features_001",
        "input",
    )
    assert _has_edge(
        workflow,
        "xcms_retention_correction_001",
        "aligned_xcms_object",
        "camera_annotation_001",
        "xcms_object",
    )
    assert not _has_edge(workflow, "camera_annotation_001", "annotated_peaklist", "validate_camera_peaklist_001", "input")

    assert _has_edge(workflow, "mzml_001", "file", "xcms_peak_detection_001", "mzml_files")
    assert not _has_edge(workflow, "xcms_peak_detection_001", "xcms_object", "camera_annotation_001", "xcms_object")


def test_metabolomics_lcms_template_validates_outputs_and_analysis_parameters() -> None:
    workflow = _load_template("metabolomics_lcms_pipeline.json")

    mzml_input = _node_by_id(workflow, "mzml_001")
    mzml_validator = _output_validation(workflow, "mzml_001", "file")
    xcms = _node_by_id(workflow, "xcms_peak_detection_001")
    feature_validator = _output_validation(workflow, "xcms_peak_detection_001", "feature_table")
    retention = _node_by_id(workflow, "xcms_retention_correction_001")
    aligned_validator = _output_validation(workflow, "xcms_retention_correction_001", "aligned_feature_table")
    camera = _node_by_id(workflow, "camera_annotation_001")
    camera_validator = _output_validation(workflow, "camera_annotation_001", "annotated_peaklist")

    assert mzml_input["params"]["file"] == "examples/data/metabolomics/sample.mzML"
    assert mzml_validator["expected_format"] == "auto"
    assert mzml_validator["min_size_bytes"] > 0
    assert mzml_validator["fail_on_error"] is True

    assert xcms["params"]["ppm"] == 25.0
    assert xcms["params"]["peakwidth_min"] == 8.0
    assert xcms["params"]["peakwidth_max"] == 35.0
    assert xcms["params"]["snthresh"] == 10.0
    assert xcms["params"]["threads"] >= 2
    assert xcms["params"]["output_name"] == "lcms"
    assert feature_validator["expected_format"] == "tsv"
    assert feature_validator["min_size_bytes"] > 0

    assert retention["params"]["method"] == "obiwarp"
    assert retention["params"]["bin_size"] == 1.0
    assert retention["params"]["min_fraction"] == 0.5
    assert retention["params"]["output_name"] == "lcms_aligned"
    assert aligned_validator["expected_format"] == "tsv"
    assert aligned_validator["fail_on_error"] is True

    assert camera["params"]["polarity"] == "positive"
    assert camera["params"]["run_group_corr"] is True
    assert camera["params"]["run_adducts"] is True
    assert camera["params"]["output_name"] == "lcms_camera"
    assert camera_validator["expected_format"] == "tsv"
    assert camera_validator["fail_on_error"] is True

    assert workflow["outputs"]["validated_mzml"] == "mzml_001"
    assert workflow["outputs"]["xcms_features"] == "xcms_peak_detection_001"
    assert workflow["outputs"]["aligned_features"] == "xcms_retention_correction_001"
    assert workflow["outputs"]["camera_peaklist"] == "camera_annotation_001"


def test_metabolomics_lcms_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/metabolomics_lcms_pipeline.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "metabolomics_lcms_pipeline.json"
    )
    assert listed["name"] == "Metabolomics LC-MS Workflow"
    assert listed["category"] == "Metabolomics"
    assert listed["node_count"] >= 4
    assert "xcms_peak_detection" in listed["tools"]
    assert "camera_annotation" in listed["tools"]
    assert "XCMS Peak Detection" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Metabolomics LC-MS Workflow"
