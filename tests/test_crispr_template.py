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


def test_crispr_template_covers_editing_design_and_screen_analysis() -> None:
    workflow = _load_template("crispr_editing_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "CRISPR Editing and Screen Analysis"
    assert workflow["category"] == "CRISPR"
    assert {"crispr", "guide-rna", "crispresso2", "mageck", "cas-offinder"}.issubset(set(workflow["tags"]))
    assert {
        "guide_rna_design",
        "cas_offinder",
        "crispresso2",
        "mageck_count",
        "mageck_test",
    }.issubset(set(workflow["tools"]))

    assert node_types["genome_001"] == "input_fasta"
    assert node_types["amplicon_r1_001"] == "input_file"
    assert node_types["amplicon_r2_001"] == "input_file"
    assert node_types["screen_reads_001"] == "input_fastq"
    assert node_types["library_001"] == "input_file"
    assert node_types["validate_genome_001"] == "data_validator"
    assert node_types["validate_amplicon_r1_001"] == "data_validator"
    assert node_types["validate_amplicon_r2_001"] == "data_validator"
    assert node_types["validate_screen_reads_001"] == "data_validator"
    assert node_types["validate_library_001"] == "data_validator"
    assert node_types["guide_design_001"] == "guide_rna_design"
    assert node_types["cas_offinder_001"] == "cas_offinder"
    assert node_types["crispresso2_001"] == "crispresso2"
    assert node_types["gate_crispresso_report_001"] == "gate"
    assert node_types["mageck_count_001"] == "mageck_count"
    assert node_types["validate_mageck_count_001"] == "data_validator"
    assert node_types["mageck_test_001"] == "mageck_test"
    assert node_types["validate_mageck_gene_summary_001"] == "data_validator"
    assert node_types["validate_guides_001"] == "data_validator"
    assert node_types["validate_offtargets_001"] == "data_validator"
    assert node_types["validate_cas_offinder_001"] == "data_validator"
    assert node_types["crispr_report_001"] == "html_report"
    assert node_types["crispr_report_preview_001"] == "html_preview"

    assert _has_edge(workflow, "genome_001", "reference", "validate_genome_001", "input")
    assert _has_edge(workflow, "amplicon_r1_001", "file", "validate_amplicon_r1_001", "input")
    assert _has_edge(workflow, "amplicon_r2_001", "file", "validate_amplicon_r2_001", "input")
    assert _has_edge(workflow, "screen_reads_001", "reads", "validate_screen_reads_001", "input")
    assert _has_edge(workflow, "library_001", "file", "validate_library_001", "input")
    assert _has_edge(workflow, "validate_genome_001", "passthrough", "guide_design_001", "genome")
    assert _has_edge(workflow, "validate_genome_001", "passthrough", "cas_offinder_001", "genome_fasta")
    assert _has_edge(workflow, "guide_design_001", "guides", "validate_guides_001", "input")
    assert _has_edge(workflow, "guide_design_001", "off_targets", "validate_offtargets_001", "input")
    assert _has_edge(workflow, "cas_offinder_001", "offtarget_sites", "validate_cas_offinder_001", "input")
    assert _has_edge(workflow, "validate_amplicon_r1_001", "passthrough", "crispresso2_001", "r1")
    assert _has_edge(workflow, "validate_amplicon_r2_001", "passthrough", "crispresso2_001", "r2")
    assert _has_edge(workflow, "crispresso2_001", "report", "gate_crispresso_report_001", "value")
    assert _has_edge(workflow, "validate_screen_reads_001", "passthrough", "mageck_count_001", "fastq_files")
    assert _has_edge(workflow, "validate_library_001", "passthrough", "mageck_count_001", "library_file")
    assert _has_edge(workflow, "mageck_count_001", "count_table", "validate_mageck_count_001", "input")
    assert _has_edge(workflow, "validate_mageck_count_001", "passthrough", "mageck_test_001", "count_table")
    assert _has_edge(workflow, "mageck_test_001", "gene_summary", "validate_mageck_gene_summary_001", "input")
    assert _has_edge(workflow, "validate_guides_001", "passthrough", "crispr_report_001", "tables")
    assert _has_edge(workflow, "validate_offtargets_001", "passthrough", "crispr_report_001", "tables")
    assert _has_edge(workflow, "validate_cas_offinder_001", "passthrough", "crispr_report_001", "tables")
    assert _has_edge(workflow, "gate_crispresso_report_001", "output", "crispr_report_001", "tables")
    assert _has_edge(workflow, "validate_mageck_gene_summary_001", "passthrough", "crispr_report_001", "tables")
    assert _has_edge(workflow, "crispr_report_001", "html_report", "crispr_report_preview_001", "file")

    assert not _has_edge(workflow, "genome_001", "reference", "guide_design_001", "genome")
    assert not _has_edge(workflow, "amplicon_r1_001", "file", "crispresso2_001", "r1")
    assert not _has_edge(workflow, "library_001", "file", "mageck_count_001", "library_file")
    assert not _has_edge(workflow, "crispresso2_001", "report", "crispr_report_preview_001", "file")


def test_crispr_template_validates_inputs_outputs_and_quality_gates() -> None:
    workflow = _load_template("crispr_editing_pipeline.json")

    genome_validator = _node_by_id(workflow, "validate_genome_001")
    r1_validator = _node_by_id(workflow, "validate_amplicon_r1_001")
    r2_validator = _node_by_id(workflow, "validate_amplicon_r2_001")
    screen_reads_validator = _node_by_id(workflow, "validate_screen_reads_001")
    library_validator = _node_by_id(workflow, "validate_library_001")
    guides_validator = _node_by_id(workflow, "validate_guides_001")
    mageck_count_validator = _node_by_id(workflow, "validate_mageck_count_001")
    crispresso_gate = _node_by_id(workflow, "gate_crispresso_report_001")
    guide_design = _node_by_id(workflow, "guide_design_001")
    cas_offinder = _node_by_id(workflow, "cas_offinder_001")
    crispresso2 = _node_by_id(workflow, "crispresso2_001")
    mageck_test = _node_by_id(workflow, "mageck_test_001")

    assert genome_validator["params"]["expected_format"] == "fasta"
    assert genome_validator["params"]["min_records"] >= 1
    assert genome_validator["params"]["fail_on_error"] is True
    assert r1_validator["params"]["expected_format"] == "fastq"
    assert r1_validator["params"]["min_records"] >= 1
    assert r2_validator["params"]["expected_format"] == "fastq"
    assert r2_validator["params"]["min_records"] >= 1
    assert screen_reads_validator["params"]["expected_format"] == "fastq"
    assert screen_reads_validator["params"]["min_records"] >= 1
    assert library_validator["params"]["expected_format"] == "tsv"
    assert library_validator["params"]["required_fields"] == "sgRNA,sequence,gene"
    assert guides_validator["params"]["expected_format"] == "tsv"
    assert mageck_count_validator["params"]["expected_format"] == "tsv"

    assert crispresso_gate["params"]["condition_mode"] == "file_exists"
    assert crispresso_gate["params"]["on_fail"] == "halt"
    assert "CRISPResso2 HTML report" in crispresso_gate["params"]["error_message"]

    assert guide_design["params"]["target"] == "chr1:1-1000"
    assert guide_design["params"]["pam"] == "NGG"
    assert guide_design["params"]["guide_length"] == 20
    assert guide_design["params"]["mismatches"] == 3
    assert cas_offinder["params"]["guide_seq"] == "ACGTACGTACGTACGTACGT"
    assert cas_offinder["params"]["pam_sequence"] == "NNG"
    assert crispresso2["params"]["name"] == "edited_locus"
    assert crispresso2["params"]["guide_seq"] == "ACGTACGTACGTACGTACGT"
    assert mageck_test["params"]["treatment_labels"] == "treated"
    assert mageck_test["params"]["control_labels"] == "control"

    assert workflow["outputs"]["validated_genome"] == "validate_genome_001"
    assert workflow["outputs"]["designed_guides"] == "guide_design_001"
    assert workflow["outputs"]["cas_offinder_sites"] == "cas_offinder_001"
    assert workflow["outputs"]["crispresso_report_gate"] == "gate_crispresso_report_001"
    assert workflow["outputs"]["mageck_counts"] == "mageck_count_001"
    assert workflow["outputs"]["mageck_gene_summary"] == "mageck_test_001"
    assert workflow["outputs"]["report"] == "crispr_report_001"
    assert workflow["outputs"]["report_preview"] == "crispr_report_preview_001"


def test_crispr_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/crispr_editing_pipeline.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "crispr_editing_pipeline.json"
    )
    assert listed["name"] == "CRISPR Editing and Screen Analysis"
    assert listed["category"] == "CRISPR"
    assert listed["node_count"] >= 18
    assert "guide_rna_design" in listed["tools"]
    assert "mageck_test" in listed["tools"]
    assert "Guide RNA Design" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "CRISPR Editing and Screen Analysis"
