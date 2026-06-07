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


def _target_input_count(workflow: dict[str, Any], target: str, target_input: str) -> int:
    return sum(
        edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_protein_structure_template_covers_uniprot_alphafold_and_rcsb_workflow() -> None:
    workflow = _load_template("protein_structure_database_workflow.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Protein Structure Database Workflow"
    assert workflow["category"] == "Protein Structure"
    assert {
        "protein-structure",
        "uniprot",
        "alphafold",
        "rcsb",
        "pdb",
        "mmcif",
        "database",
        "report",
    }.issubset(set(workflow["tags"]))
    assert {
        "uniprot_search",
        "uniprot_retrieve",
        "alphafold_db",
        "pdb_download",
        "data_validator",
        "html_report",
        "html_preview",
    }.issubset(set(workflow["tools"]))

    assert node_types["uniprot_search_001"] == "uniprot_search"
    assert node_types["validate_uniprot_table_001"] == "data_validator"
    assert node_types["uniprot_retrieve_001"] == "uniprot_retrieve"
    assert node_types["validate_uniprot_fasta_001"] == "data_validator"
    assert node_types["alphafold_db_001"] == "alphafold_db"
    assert node_types["validate_alphafold_structure_001"] == "data_validator"
    assert node_types["pdb_download_001"] == "pdb_download"
    assert node_types["validate_pdb_structure_001"] == "data_validator"
    assert node_types["protein_structure_report_001"] == "html_report"
    assert node_types["protein_structure_report_preview_001"] == "html_preview"

    assert _has_edge(workflow, "uniprot_search_001", "results_table", "validate_uniprot_table_001", "input")
    assert _has_edge(workflow, "uniprot_retrieve_001", "sequence", "validate_uniprot_fasta_001", "input")
    assert _has_edge(workflow, "alphafold_db_001", "structure_mmcif", "validate_alphafold_structure_001", "input")
    assert _has_edge(workflow, "pdb_download_001", "structure_file", "validate_pdb_structure_001", "input")
    assert _has_edge(workflow, "validate_uniprot_table_001", "passthrough", "protein_structure_report_001", "tables")
    assert _has_edge(
        workflow,
        "protein_structure_report_001",
        "html_report",
        "protein_structure_report_preview_001",
        "file",
    )

    assert not _has_edge(workflow, "uniprot_search_001", "results_data", "protein_structure_report_001", "tables")
    assert not _has_edge(workflow, "alphafold_db_001", "structure_metadata", "protein_structure_report_001", "tables")
    assert not _has_edge(workflow, "pdb_download_001", "pdb_metadata", "protein_structure_report_001", "tables")
    assert _target_input_count(workflow, "protein_structure_report_001", "tables") == 1


def test_protein_structure_template_validates_outputs_and_database_parameters() -> None:
    workflow = _load_template("protein_structure_database_workflow.json")

    uniprot_search = _node_by_id(workflow, "uniprot_search_001")
    uniprot_table_validator = _node_by_id(workflow, "validate_uniprot_table_001")
    uniprot_retrieve = _node_by_id(workflow, "uniprot_retrieve_001")
    uniprot_fasta_validator = _node_by_id(workflow, "validate_uniprot_fasta_001")
    alphafold = _node_by_id(workflow, "alphafold_db_001")
    alphafold_validator = _node_by_id(workflow, "validate_alphafold_structure_001")
    pdb = _node_by_id(workflow, "pdb_download_001")
    pdb_validator = _node_by_id(workflow, "validate_pdb_structure_001")
    report = _node_by_id(workflow, "protein_structure_report_001")

    assert uniprot_search["params"]["query"] == "gene:TP53 AND organism_id:9606"
    assert uniprot_search["params"]["max_results"] == 10
    assert uniprot_search["params"]["reviewed_only"] is True
    assert uniprot_search["params"]["output_name"] == "tp53_uniprot"
    assert uniprot_table_validator["params"]["expected_format"] == "tsv"
    assert uniprot_table_validator["params"]["min_size_bytes"] > 0
    assert uniprot_table_validator["params"]["fail_on_error"] is True

    assert uniprot_retrieve["params"]["accession"] == "P04637"
    assert uniprot_retrieve["params"]["include_fasta"] is True
    assert uniprot_retrieve["params"]["output_name"] == "tp53"
    assert uniprot_fasta_validator["params"]["expected_format"] == "fasta"
    assert uniprot_fasta_validator["params"]["fail_on_error"] is True

    assert alphafold["params"]["uniprot_ids"] == "P04637"
    assert alphafold["params"]["structure_format"] == "mmcif"
    assert alphafold["params"]["model_version"] == ""
    assert alphafold["params"]["download_pae"] is True
    assert alphafold_validator["params"]["expected_format"] == "auto"
    assert alphafold_validator["params"]["fail_on_error"] is True

    assert pdb["params"]["pdb_ids"] == "4HHB"
    assert pdb["params"]["format"] == "cif"
    assert pdb["params"]["fetch_metadata"] is True
    assert pdb["params"]["download_density"] is False
    assert pdb_validator["params"]["expected_format"] == "auto"
    assert pdb_validator["params"]["fail_on_error"] is True

    assert report["params"]["title"] == "Protein Structure Database Report"
    assert "UniProt" in report["params"]["text_sections"]
    assert "AlphaFold" in report["params"]["text_sections"]
    assert "RCSB" in report["params"]["text_sections"]
    assert report["params"]["section_names"] == "UniProt search results"

    assert workflow["outputs"]["uniprot_search_results"] == "validate_uniprot_table_001"
    assert workflow["outputs"]["uniprot_sequence"] == "validate_uniprot_fasta_001"
    assert workflow["outputs"]["alphafold_structure"] == "validate_alphafold_structure_001"
    assert workflow["outputs"]["alphafold_metadata"] == "alphafold_db_001"
    assert workflow["outputs"]["pdb_structure"] == "validate_pdb_structure_001"
    assert workflow["outputs"]["pdb_metadata"] == "pdb_download_001"
    assert workflow["outputs"]["report"] == "protein_structure_report_001"
    assert workflow["outputs"]["report_preview"] == "protein_structure_report_preview_001"


def test_protein_structure_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/protein_structure_database_workflow.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "protein_structure_database_workflow.json"
    )
    assert listed["name"] == "Protein Structure Database Workflow"
    assert listed["category"] == "Protein Structure"
    assert listed["node_count"] >= 10
    assert "uniprot_search" in listed["tools"]
    assert "alphafold_db" in listed["tools"]
    assert "UniProt Search" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Protein Structure Database Workflow"
