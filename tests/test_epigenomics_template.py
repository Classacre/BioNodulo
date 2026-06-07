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


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_wgbs_methylation_template_covers_bismark_and_methyldackel_workflow() -> None:
    workflow = _load_template("wgbs_methylation_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "WGBS Methylation Profiling"
    assert workflow["category"] == "Epigenomics"
    assert {"epigenomics", "wgbs", "bismark", "methyldackel", "methylation"}.issubset(set(workflow["tags"]))
    assert {"bismark_align", "bismark_methylation_extractor", "methyldackel"}.issubset(set(workflow["tools"]))

    assert node_types["r1_001"] == "input_file"
    assert node_types["r2_001"] == "input_file"
    assert node_types["genome_001"] == "input_directory"
    assert node_types["reference_001"] == "input_fasta"
    assert node_types["validate_r1_001"] == "data_validator"
    assert node_types["validate_r2_001"] == "data_validator"
    assert node_types["validate_genome_001"] == "data_validator"
    assert node_types["validate_reference_001"] == "data_validator"
    assert node_types["bismark_align_001"] == "bismark_align"
    assert node_types["gate_bismark_bam_001"] == "gate"
    assert node_types["bismark_methylation_001"] == "bismark_methylation_extractor"
    assert node_types["methyldackel_001"] == "methyldackel"
    assert node_types["validate_methylation_output_001"] == "data_validator"
    assert node_types["validate_methyldackel_bedgraph_001"] == "data_validator"
    assert node_types["wgbs_report_001"] == "html_report"
    assert node_types["wgbs_report_preview_001"] == "html_preview"

    assert _has_edge(workflow, "r1_001", "file", "validate_r1_001", "input")
    assert _has_edge(workflow, "r2_001", "file", "validate_r2_001", "input")
    assert _has_edge(workflow, "genome_001", "directory", "validate_genome_001", "input")
    assert _has_edge(workflow, "reference_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "validate_r1_001", "passthrough", "bismark_align_001", "r1")
    assert _has_edge(workflow, "validate_r2_001", "passthrough", "bismark_align_001", "r2")
    assert _has_edge(workflow, "validate_genome_001", "passthrough", "bismark_align_001", "genome_folder")
    assert _has_edge(workflow, "bismark_align_001", "aligned_bam", "gate_bismark_bam_001", "value")
    assert _has_edge(workflow, "gate_bismark_bam_001", "output", "bismark_methylation_001", "bam")
    assert _has_edge(workflow, "validate_genome_001", "passthrough", "bismark_methylation_001", "genome_folder")
    assert _has_edge(workflow, "gate_bismark_bam_001", "output", "methyldackel_001", "bam")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "methyldackel_001", "reference")
    assert _has_edge(workflow, "bismark_methylation_001", "methylation_output", "validate_methylation_output_001", "input")
    assert _has_edge(workflow, "methyldackel_001", "methylation_bedgraph", "validate_methyldackel_bedgraph_001", "input")
    assert _has_edge(workflow, "validate_methylation_output_001", "passthrough", "wgbs_report_001", "tables")
    assert _has_edge(workflow, "validate_methyldackel_bedgraph_001", "passthrough", "wgbs_report_001", "tables")
    assert _has_edge(workflow, "wgbs_report_001", "html_report", "wgbs_report_preview_001", "file")

    assert not _has_edge(workflow, "r1_001", "file", "bismark_align_001", "r1")
    assert not _has_edge(workflow, "r2_001", "file", "bismark_align_001", "r2")
    assert not _has_edge(workflow, "bismark_align_001", "aligned_bam", "bismark_methylation_001", "bam")
    assert not _has_edge(workflow, "bismark_align_001", "aligned_bam", "methyldackel_001", "bam")


def test_wgbs_methylation_template_validates_inputs_and_core_outputs() -> None:
    workflow = _load_template("wgbs_methylation_pipeline.json")

    r1_validator = _node_by_id(workflow, "validate_r1_001")
    r2_validator = _node_by_id(workflow, "validate_r2_001")
    genome_validator = _node_by_id(workflow, "validate_genome_001")
    reference_validator = _node_by_id(workflow, "validate_reference_001")
    bam_gate = _node_by_id(workflow, "gate_bismark_bam_001")
    bismark_output_validator = _node_by_id(workflow, "validate_methylation_output_001")
    methyldackel_validator = _node_by_id(workflow, "validate_methyldackel_bedgraph_001")

    assert r1_validator["params"]["expected_format"] == "fastq"
    assert r1_validator["params"]["min_records"] >= 1
    assert r1_validator["params"]["fail_on_error"] is True
    assert r2_validator["params"]["expected_format"] == "fastq"
    assert r2_validator["params"]["min_records"] >= 1
    assert r2_validator["params"]["fail_on_error"] is True
    assert genome_validator["params"]["expected_format"] == "directory"
    assert genome_validator["params"]["min_size_bytes"] > 0
    assert genome_validator["params"]["fail_on_error"] is True
    assert reference_validator["params"]["expected_format"] == "fasta"
    assert reference_validator["params"]["min_records"] >= 1
    assert reference_validator["params"]["fail_on_error"] is True

    assert bam_gate["params"]["condition_mode"] == "file_exists"
    assert bam_gate["params"]["on_fail"] == "halt"
    assert "Bismark aligned BAM" in bam_gate["params"]["error_message"]
    assert bismark_output_validator["params"]["expected_format"] == "directory"
    assert bismark_output_validator["params"]["fail_on_error"] is True
    assert methyldackel_validator["params"]["expected_format"] == "text"
    assert methyldackel_validator["params"]["fail_on_error"] is True

    assert workflow["outputs"]["validated_r1"] == "validate_r1_001"
    assert workflow["outputs"]["validated_r2"] == "validate_r2_001"
    assert workflow["outputs"]["validated_genome_folder"] == "validate_genome_001"
    assert workflow["outputs"]["validated_reference"] == "validate_reference_001"
    assert workflow["outputs"]["aligned_bam_quality_gate"] == "gate_bismark_bam_001"
    assert workflow["outputs"]["aligned_bam"] == "bismark_align_001"
    assert workflow["outputs"]["bismark_methylation"] == "bismark_methylation_001"
    assert workflow["outputs"]["methyldackel_bedgraph"] == "methyldackel_001"
    assert workflow["outputs"]["methyldackel_mbias"] == "methyldackel_001"
    assert workflow["outputs"]["report"] == "wgbs_report_001"
    assert workflow["outputs"]["report_preview"] == "wgbs_report_preview_001"


def test_wgbs_methylation_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/wgbs_methylation_pipeline.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "wgbs_methylation_pipeline.json"
    )
    assert listed["name"] == "WGBS Methylation Profiling"
    assert listed["category"] == "Epigenomics"
    assert listed["node_count"] >= 14
    assert "bismark_align" in listed["tools"]
    assert "methyldackel" in listed["tools"]
    assert "Bismark Align" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "WGBS Methylation Profiling"
