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


def test_proteomics_sage_percolator_template_wires_search_to_fdr_validation() -> None:
    workflow = _load_template("proteomics_sage_percolator_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Proteomics Sage-Percolator Search"
    assert workflow["category"] == "Proteomics"
    assert {"proteomics", "sage", "percolator", "fdr"}.issubset(set(workflow["tags"]))
    assert {"sage_search", "percolator"}.issubset(set(workflow["tools"]))

    assert node_types["spectra_001"] == "input_file"
    assert node_types["fasta_001"] == "input_fasta"
    assert "validate_spectra_001" not in node_types
    assert "validate_fasta_001" not in node_types
    assert node_types["sage_search_001"] == "sage_search"
    assert "validate_sage_pin_001" not in node_types
    assert node_types["percolator_001"] == "percolator"
    assert "validate_percolator_psms_001" not in node_types
    assert node_types["render_percolator_tab_0"] == "table_preview"
    assert node_types["render_percolator_tab_1"] == "table_preview"
    assert node_types["render_sage_search_tab_2"] == "table_preview"

    sage = _node_by_id(workflow, "sage_search_001")
    note = _node_by_id(workflow, "note_proteomics_pipeline")
    percolator = _node_by_id(workflow, "percolator_001")
    pin_validator = _output_validation(workflow, "sage_search_001", "pin_file")

    assert sage["params"]["batch_size"] == 1
    # The BSA-matched database is TARGET-ONLY (18,878 entries, 0 decoys), so
    # Sage reverses its own using its default rev_ prefix. Searching those
    # spectra against the old phospho-pool FASTA found 0 PSMs and wrote no .pin.
    assert sage["params"]["decoy_tag"] == "rev_"
    assert sage["params"]["generate_decoys"] is True
    assert "mzXML" not in note["params"]["text"]
    assert "flanking syntax" in note["params"]["text"]
    assert percolator["params"]["pin_dialect"] == "sage_0_14_7_full_digest"
    assert percolator["params"]["search_input"] == "concatenated"
    assert percolator["params"]["test_fdr"] == 0.01
    assert percolator["params"]["train_fdr"] == 0.01
    assert percolator["params"]["protein_enzyme"] == "trypsin"
    assert pin_validator["expected_format"] == "text"
    assert pin_validator["fail_on_error"] is True

    assert not _has_edge(workflow, "spectra_001", "file", "validate_spectra_001", "input")
    assert not _has_edge(workflow, "fasta_001", "reference", "validate_fasta_001", "input")
    assert _has_edge(workflow, "spectra_001", "file", "sage_search_001", "spectra_files")
    assert _has_edge(workflow, "fasta_001", "reference", "sage_search_001", "fasta_db")
    assert not _has_edge(workflow, "sage_search_001", "pin_file", "validate_sage_pin_001", "input")
    assert _has_edge(workflow, "sage_search_001", "pin_file", "percolator_001", "pin_file")
    assert _has_edge(workflow, "fasta_001", "reference", "percolator_001", "fasta_db")
    assert not _has_edge(workflow, "percolator_001", "percolator_psms", "validate_percolator_psms_001", "input")
    assert _has_edge(workflow, "percolator_001", "percolator_psms", "render_percolator_tab_0", "file")
    assert _has_edge(workflow, "percolator_001", "percolator_proteins", "render_percolator_tab_1", "file")
    assert _has_edge(workflow, "sage_search_001", "results_tsv", "render_sage_search_tab_2", "file")

    assert not _has_edge(workflow, "sage_search_001", "results_tsv", "percolator_001", "pin_file")
    assert _has_edge(workflow, "sage_search_001", "pin_file", "percolator_001", "pin_file")

    assert workflow["outputs"]["validated_spectra"] == "spectra_001"
    assert workflow["outputs"]["validated_fasta"] == "fasta_001"
    assert workflow["outputs"]["sage_results"] == "sage_search_001"
    assert workflow["outputs"]["sage_pin"] == "sage_search_001"
    assert workflow["outputs"]["validated_sage_pin"] == "sage_search_001"
    assert workflow["outputs"]["percolator_psms"] == "percolator_001"
    assert workflow["outputs"]["percolator_proteins"] == "percolator_001"


def test_proteomics_sage_percolator_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/proteomics_sage_percolator_pipeline.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "proteomics_sage_percolator_pipeline.json"
    )
    assert listed["name"] == "Proteomics Sage-Percolator Search"
    assert listed["category"] == "Proteomics"
    assert listed["node_count"] >= 6
    assert "sage_search" in listed["tools"]
    assert "percolator" in listed["tools"]
    assert "Sage Search" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Proteomics Sage-Percolator Search"
