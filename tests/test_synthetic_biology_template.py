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


def test_synthetic_biology_template_covers_biocad_design_and_simulation_workflow() -> None:
    workflow = _load_template("synthetic_biology_design_simulation.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Synthetic Biology Design and Simulation"
    assert workflow["category"] == "Synthetic Biology"
    assert {"synthetic-biology", "biocad", "sbol", "copasi", "ibiosim", "cello"}.issubset(
        set(workflow["tags"])
    )
    assert {
        "input_file",
        "input_directory",
        "data_validator",
        "sbol_design_import",
        "copasi_simulation",
        "ibiosim_model",
        "cello_circuit_design",
        "html_report",
        "html_preview",
    }.issubset(set(workflow["tools"]))

    assert node_types["sbol_design_001"] == "input_file"
    assert node_types["validate_sbol_design_001"] == "data_validator"
    assert node_types["sbol_import_001"] == "sbol_design_import"
    assert node_types["validate_sbol_summary_001"] == "data_validator"
    assert node_types["copasi_model_001"] == "input_file"
    assert node_types["validate_copasi_model_001"] == "data_validator"
    assert node_types["copasi_simulation_001"] == "copasi_simulation"
    assert node_types["validate_copasi_report_001"] == "data_validator"
    assert node_types["omex_archive_001"] == "input_file"
    assert node_types["validate_omex_archive_001"] == "data_validator"
    assert node_types["ibiosim_model_001"] == "ibiosim_model"
    assert node_types["validate_ibiosim_index_001"] == "data_validator"
    assert node_types["cello_netlist_001"] == "input_file"
    assert node_types["cello_ucf_001"] == "input_file"
    assert node_types["cello_options_001"] == "input_file"
    assert node_types["cello_exec_dir_001"] == "input_directory"
    assert node_types["validate_cello_netlist_001"] == "data_validator"
    assert node_types["validate_cello_ucf_001"] == "data_validator"
    assert node_types["validate_cello_options_001"] == "data_validator"
    assert node_types["validate_cello_exec_dir_001"] == "data_validator"
    assert node_types["cello_design_001"] == "cello_circuit_design"
    assert node_types["validate_cello_index_001"] == "data_validator"
    assert node_types["synthetic_biology_report_001"] == "html_report"
    assert node_types["synthetic_biology_report_preview_001"] == "html_preview"

    assert _has_edge(workflow, "sbol_design_001", "file", "validate_sbol_design_001", "input")
    assert _has_edge(workflow, "validate_sbol_design_001", "passthrough", "sbol_import_001", "sbol_file")
    assert _has_edge(workflow, "sbol_import_001", "summary", "validate_sbol_summary_001", "input")
    assert _has_edge(workflow, "copasi_model_001", "file", "validate_copasi_model_001", "input")
    assert _has_edge(workflow, "validate_copasi_model_001", "passthrough", "copasi_simulation_001", "model_file")
    assert _has_edge(workflow, "copasi_simulation_001", "report", "validate_copasi_report_001", "input")
    assert _has_edge(workflow, "omex_archive_001", "file", "validate_omex_archive_001", "input")
    assert _has_edge(workflow, "validate_omex_archive_001", "passthrough", "ibiosim_model_001", "archive_file")
    assert _has_edge(workflow, "ibiosim_model_001", "result_index", "validate_ibiosim_index_001", "input")
    assert _has_edge(workflow, "cello_netlist_001", "file", "validate_cello_netlist_001", "input")
    assert _has_edge(workflow, "cello_ucf_001", "file", "validate_cello_ucf_001", "input")
    assert _has_edge(workflow, "cello_options_001", "file", "validate_cello_options_001", "input")
    assert _has_edge(workflow, "cello_exec_dir_001", "directory", "validate_cello_exec_dir_001", "input")
    assert _has_edge(workflow, "validate_cello_netlist_001", "passthrough", "cello_design_001", "input_netlist")
    assert _has_edge(workflow, "validate_cello_ucf_001", "passthrough", "cello_design_001", "target_data_file")
    assert _has_edge(workflow, "validate_cello_options_001", "passthrough", "cello_design_001", "options_file")
    assert _has_edge(workflow, "validate_cello_exec_dir_001", "passthrough", "cello_design_001", "cello_exec_dir")
    assert _has_edge(workflow, "cello_design_001", "result_index", "validate_cello_index_001", "input")
    assert _has_edge(
        workflow,
        "synthetic_biology_report_001",
        "html_report",
        "synthetic_biology_report_preview_001",
        "file",
    )

    assert not _has_edge(workflow, "sbol_design_001", "file", "sbol_import_001", "sbol_file")
    assert not _has_edge(workflow, "copasi_model_001", "file", "copasi_simulation_001", "model_file")
    assert not _has_edge(workflow, "omex_archive_001", "file", "ibiosim_model_001", "archive_file")
    assert _target_input_count(workflow, "synthetic_biology_report_001", "tables") == 0


def test_synthetic_biology_template_validates_outputs_and_tool_parameters() -> None:
    workflow = _load_template("synthetic_biology_design_simulation.json")

    sbol_input = _node_by_id(workflow, "sbol_design_001")
    sbol_validator = _node_by_id(workflow, "validate_sbol_design_001")
    sbol_import = _node_by_id(workflow, "sbol_import_001")
    sbol_summary_validator = _node_by_id(workflow, "validate_sbol_summary_001")
    copasi_input = _node_by_id(workflow, "copasi_model_001")
    copasi_validator = _node_by_id(workflow, "validate_copasi_model_001")
    copasi = _node_by_id(workflow, "copasi_simulation_001")
    copasi_report_validator = _node_by_id(workflow, "validate_copasi_report_001")
    omex_input = _node_by_id(workflow, "omex_archive_001")
    ibiosim = _node_by_id(workflow, "ibiosim_model_001")
    ibiosim_index_validator = _node_by_id(workflow, "validate_ibiosim_index_001")
    cello = _node_by_id(workflow, "cello_design_001")
    cello_index_validator = _node_by_id(workflow, "validate_cello_index_001")
    report = _node_by_id(workflow, "synthetic_biology_report_001")

    assert sbol_input["params"]["file"] == "examples/data/synthetic_biology/toggle_switch.xml"
    assert sbol_validator["params"]["expected_format"] == "auto"
    assert sbol_validator["params"]["fail_on_error"] is True
    assert sbol_import["params"]["namespace"] == "https://bionodulo.local/synthetic-biology"
    assert sbol_import["params"]["validate"] is True
    assert sbol_import["params"]["output_format"] == "rdfxml"
    assert sbol_import["params"]["output_name"] == "toggle_switch"
    assert sbol_summary_validator["params"]["expected_format"] == "json"

    assert copasi_input["params"]["file"] == "examples/data/synthetic_biology/toggle_model.cps"
    assert copasi_validator["params"]["expected_format"] == "auto"
    assert copasi["params"]["copasi_executable"] == "CopasiSE"
    assert copasi["params"]["scheduled_task"] == "Time-Course"
    assert copasi["params"]["sedml_task"] == ""
    assert copasi["params"]["save_model"] is True
    assert copasi["params"]["validate_only"] is False
    assert copasi["params"]["verbose"] is False
    assert copasi["params"]["max_time"] == 600
    assert copasi["params"]["output_name"] == "toggle_simulation"
    assert copasi_report_validator["params"]["expected_format"] == "tsv"

    assert omex_input["params"]["file"] == "examples/data/synthetic_biology/toggle_study.omex"
    assert ibiosim["params"]["execution_mode"] == "cli"
    assert ibiosim["params"]["ibiosim_executable"] == "ibiosim"
    assert ibiosim["params"]["docker_image"] == "ghcr.io/biosimulators/ibiosim:latest"
    assert ibiosim["params"]["quiet"] is True
    assert ibiosim["params"]["debug"] is False
    assert ibiosim["params"]["output_name"] == "toggle_study"
    assert ibiosim_index_validator["params"]["expected_format"] == "tsv"

    assert cello["params"]["netlist_constraint_file"] == ""
    assert cello["params"]["java_args"] == "-Xms2G -Xmx5G"
    assert cello["params"]["application"] == "DNACompiler"
    assert cello["params"]["algo_name"] == ""
    assert cello["params"]["output_name"] == "toggle_circuit"
    assert cello_index_validator["params"]["expected_format"] == "tsv"

    assert report["params"]["title"] == "Synthetic Biology Design and Simulation Report"
    assert "SBOL" in report["params"]["text_sections"]
    assert "COPASI" in report["params"]["text_sections"]
    assert "Cello" in report["params"]["text_sections"]
    assert report["params"]["tables"] == (
        "copasi_simulation/toggle_simulation.report.tsv,"
        "ibiosim_model/toggle_study.result_index.tsv,"
        "cello_circuit_design/toggle_circuit.result_index.tsv"
    )
    assert report["params"]["section_names"] == (
        "COPASI report,iBioSim result index,Cello result index"
    )

    assert workflow["outputs"]["validated_sbol"] == "validate_sbol_design_001"
    assert workflow["outputs"]["sbol_summary"] == "validate_sbol_summary_001"
    assert workflow["outputs"]["copasi_report"] == "validate_copasi_report_001"
    assert workflow["outputs"]["ibiosim_index"] == "validate_ibiosim_index_001"
    assert workflow["outputs"]["cello_index"] == "validate_cello_index_001"
    assert workflow["outputs"]["report"] == "synthetic_biology_report_001"
    assert workflow["outputs"]["report_preview"] == "synthetic_biology_report_preview_001"


def test_synthetic_biology_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/synthetic_biology_design_simulation.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "synthetic_biology_design_simulation.json"
    )
    assert listed["name"] == "Synthetic Biology Design and Simulation"
    assert listed["category"] == "Synthetic Biology"
    assert listed["node_count"] >= 24
    assert "sbol_design_import" in listed["tools"]
    assert "cello_circuit_design" in listed["tools"]
    assert "SBOL Design Import" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Synthetic Biology Design and Simulation"
