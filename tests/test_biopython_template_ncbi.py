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


def test_biopython_template_fetches_ncbi_fasta_before_sequence_analysis() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["seqs_001"] == "input_fasta"
    assert node_types["ncbi_efetch_001"] == "ncbi_efetch"
    assert node_types["validate_sequences_001"] == "data_validator"

    efetch = _node(workflow, "ncbi_efetch_001")
    validator = _node(workflow, "validate_sequences_001")
    assert efetch["params"]["database"] == "nuccore"
    assert efetch["params"]["rettype"] == "fasta"
    assert efetch["params"]["retmode"] == "text"
    assert efetch["params"]["id_list"] == "NR_024570.1,NR_027552.1,NR_036781.1,NR_026078.1,NR_028747.1"
    assert efetch["params"]["output_name"] == "16s_sequences.fasta"
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 2
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True

    assert _has_edge(workflow, "ncbi_efetch_001", "records", "validate_sequences_001", "input")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "seqio_read_001", "input_file")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "seq_stats_001", "input_file")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "blast_001", "query")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "blast_001", "subject")
    assert not _has_edge(workflow, "seqs_001", "reference", "validate_sequences_001", "input")
    assert workflow["outputs"]["fetched_fasta"] == "ncbi_efetch_001"
    assert workflow["outputs"]["validated_sequences"] == "validate_sequences_001"


def test_biopython_template_previews_sequence_report() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["sequence_report_001"] == "html_report"
    assert node_types["sequence_report_preview_001"] == "html_preview"

    report = _node(workflow, "sequence_report_001")
    assert report["params"]["section_names"] == (
        "Sequence length chart,Sequence statistics,AI sequence classifications"
    )

    assert _has_edge(workflow, "seq_length_chart_001", "chart_image", "sequence_report_001", "images")
    assert _has_edge(workflow, "seq_stats_001", "stats_tsv", "sequence_report_001", "tables")
    assert _has_edge(workflow, "sequence_report_001", "html_report", "sequence_report_preview_001", "file")
    assert workflow["outputs"]["sequence_report_preview"] == "sequence_report_preview_001"


def test_biopython_template_runs_ai_sequence_classification_on_validated_coding_sequences() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["sequence_classification_001"] == "ai_sequence_classification"

    classifier = _node(workflow, "sequence_classification_001")
    report = _node(workflow, "sequence_report_001")
    assert classifier["params"]["classifier"] == "deeploc"
    assert classifier["params"]["fallback_backend"] == "deterministic"
    assert classifier["params"]["confidence_threshold"] == 0.0
    assert classifier["params"]["top_k"] == 3
    assert report["params"]["section_names"] == (
        "Sequence length chart,Sequence statistics,AI sequence classifications"
    )

    assert _has_edge(workflow, "validate_coding_001", "passthrough", "sequence_classification_001", "input_fasta")
    assert _has_edge(workflow, "sequence_classification_001", "classifications_csv", "sequence_report_001", "tables")
    assert workflow["outputs"]["sequence_classifications"] == "sequence_classification_001"
    assert workflow["outputs"]["sequence_classifications_csv"] == "sequence_classification_001"
