from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template() -> dict[str, Any]:
    return json.loads((ROOT / "templates" / "synthetic_biology_design_simulation.json").read_text())


def _node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, output: str, target: str, input_name: str) -> bool:
    return any(
        edge["from"] == {"node": source, "output": output}
        and edge["to"] == {"node": target, "input": input_name}
        for edge in workflow["edges"]
    )


def test_template_uses_the_four_focused_synthetic_biology_nodes() -> None:
    workflow = _load_template()
    node_types = {node["id"]: node["type"] for node in workflow["nodes"]}

    assert workflow["name"] == "Synthetic Biology Design and Simulation"
    assert set(workflow["tools"]) == {
        "input_file",
        "sbol_design_import",
        "copasi_simulation",
        "ibiosim_model",
        "cello_circuit_design",
    }
    assert node_types["sbol_import_001"] == "sbol_design_import"
    assert node_types["copasi_simulation_001"] == "copasi_simulation"
    assert node_types["ibiosim_model_001"] == "ibiosim_model"
    assert node_types["cello_design_001"] == "cello_circuit_design"
    assert "cello_exec_dir_001" not in node_types


def test_template_wires_every_required_cello_artifact_explicitly() -> None:
    workflow = _load_template()

    expected_edges = {
        ("cello_netlist_001", "input_netlist"),
        ("cello_ucf_001", "user_constraints_file"),
        ("cello_input_sensor_001", "input_sensor_file"),
        ("cello_output_device_001", "output_device_file"),
        ("cello_options_001", "options_file"),
        ("cello_jar_001", "cello_jar"),
    }
    for source, target_input in expected_edges:
        assert _has_edge(workflow, source, "file", "cello_design_001", target_input)
    assert not any(edge["to"].get("input") == "target_data_file" for edge in workflow["edges"])
    assert not any(edge["to"].get("input") == "cello_exec_dir" for edge in workflow["edges"])


def test_template_uses_corrected_parameters_and_native_outputs() -> None:
    workflow = _load_template()
    sbol = _node(workflow, "sbol_import_001")
    copasi = _node(workflow, "copasi_simulation_001")
    ibiosim = _node(workflow, "ibiosim_model_001")
    cello = _node(workflow, "cello_design_001")

    assert sbol["params"] == {
        "namespace": "https://bionodulo.local/synthetic-biology",
        "validate": True,
        "output_format": "xml",
    }
    assert copasi["params"] == {
        "input_format": "cps",
        "scheduled_task": "Time-Course",
        "sedml_task": "",
        "verbose": False,
        "max_time": 600,
    }
    assert ibiosim["params"] == {"quiet": True, "debug": False}
    assert cello["params"] == {"netlist_constraint_file": "", "python_executable": "python"}
    assert "results_dir" in ibiosim["ui"]["validation"]["outputs"]
    assert "design_dir" in cello["ui"]["validation"]["outputs"]
    assert "output_netlist" in cello["ui"]["validation"]["outputs"]
    assert workflow["outputs"] == {
        "source_sbol": "sbol_design_001",
        "sbol_summary": "sbol_import_001",
        "copasi_report": "copasi_simulation_001",
        "ibiosim_results": "ibiosim_model_001",
        "cello_design": "cello_design_001",
    }
