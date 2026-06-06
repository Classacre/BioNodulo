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


def test_fastq_qc_template_aggregates_fastp_and_fastqc_reports_in_multiqc() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["fastp_001"] == "fastp"
    assert node_types["fastqc_001"] == "fastqc"
    assert node_types["multiqc_001"] == "multiqc"

    assert _has_edge(workflow, "fastp_001", "report", "multiqc_001", "reports")
    assert _has_edge(workflow, "fastqc_001", "report_dir", "multiqc_001", "reports")
    assert _has_edge(workflow, "multiqc_001", "report", "validate_multiqc_001", "input")


def test_fastq_qc_template_demonstrates_sample_sheet_input_validation() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["sample_sheet_001"] == "input_sample_sheet"
    assert node_types["validate_sample_sheet_001"] == "data_validator"

    sample_sheet = next(node for node in workflow["nodes"] if node["id"] == "sample_sheet_001")
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_sample_sheet_001")
    assert sample_sheet["params"]["sample_sheet"] == "templates/data/fastq_qc_sample_sheet.csv"
    assert validator["params"]["expected_format"] == "csv"
    assert validator["params"]["required_fields"] == "sample,fastq_1,fastq_2"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True

    assert _has_edge(workflow, "sample_sheet_001", "sample_sheet", "validate_sample_sheet_001", "input")
    assert workflow["outputs"]["sample_sheet"] == "sample_sheet_001"
    assert workflow["outputs"]["validated_sample_sheet"] == "validate_sample_sheet_001"
