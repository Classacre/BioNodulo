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


def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node(workflow, node_id)
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


def test_biopython_template_fetches_ncbi_fasta_before_sequence_analysis() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert "seqs_001" not in node_types
    assert node_types["ncbi_efetch_001"] == "ncbi_efetch"
    assert "validate_sequences_001" not in node_types

    efetch = _node(workflow, "ncbi_efetch_001")
    validator = _output_validation(workflow, "ncbi_efetch_001", "records")
    assert efetch["params"]["database"] == "nuccore"
    assert efetch["params"]["rettype"] == "fasta"
    assert efetch["params"]["retmode"] == "text"
    assert efetch["params"]["id_list"] == "NR_024570.1,NR_027552.1,NR_036781.1,NR_026078.1,NR_028747.1"
    assert efetch["params"]["output_name"] == "16s_sequences.fasta"
    assert validator["expected_format"] == "fasta"
    assert validator["min_records"] >= 2
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True

    assert not _has_edge(workflow, "ncbi_efetch_001", "records", "validate_sequences_001", "input")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "seqio_read_001", "input_file")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "seq_stats_001", "input_file")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "blast_001", "query")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "blast_001", "subject")
    assert workflow["outputs"]["fetched_fasta"] == "ncbi_efetch_001"
    assert workflow["outputs"]["validated_sequences"] == "ncbi_efetch_001"


def test_biopython_template_previews_sequence_report() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    # The sequence_report_001 html_report and its html_preview were removed by design;
    # each feeder now renders into a dedicated preview node.
    assert "sequence_report_001" not in node_types
    assert "sequence_report_preview_001" not in node_types
    assert node_types["render_seq_length_chart_ima_2"] == "image_preview"
    assert node_types["render_sequence_classification_tab_1"] == "table_preview"
    assert node_types["table_preview_001"] == "table_preview"

    assert _has_edge(workflow, "seq_length_chart_001", "chart_image", "render_seq_length_chart_ima_2", "file")
    assert _has_edge(workflow, "seq_stats_001", "stats_tsv", "table_preview_001", "file")
    assert "sequence_report_preview" not in workflow["outputs"]


def test_biopython_template_runs_ai_sequence_classification_on_validated_coding_sequences() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["sequence_classification_001"] == "ai_sequence_classification"

    classifier = _node(workflow, "sequence_classification_001")
    assert classifier["params"]["classifier"] == "deeploc"
    assert classifier["params"]["fallback_backend"] == "deterministic"
    assert classifier["params"]["confidence_threshold"] == 0.0
    assert classifier["params"]["top_k"] == 3

    assert _has_edge(workflow, "coding_001", "reference", "sequence_classification_001", "input_fasta")
    assert _has_edge(workflow, "sequence_classification_001", "classifications_csv", "render_sequence_classification_tab_1", "file")
    assert workflow["outputs"]["sequence_classifications"] == "sequence_classification_001"
    assert workflow["outputs"]["sequence_classifications_csv"] == "sequence_classification_001"


def test_biopython_template_demonstrates_generic_http_api_lookup() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    # The http_gene_lookup_001 demo node was removed from the template by design.
    assert "http_gene_lookup_001" not in node_types
    assert "api_gene_lookup" not in workflow["outputs"]
