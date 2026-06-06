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
