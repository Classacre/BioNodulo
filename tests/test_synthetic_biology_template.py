"""The synthetic-biology template carries only branches that can actually run.

Two of the four original branches were removed because neither tool can be
obtained by an automated pipeline:

* Cello publishes no release asset at all -- CIDARLAB/Cello-v2 v0.1 has an empty
  assets list, no ``cello-dnacompiler`` JAR is published anywhere, and neither
  bioconda nor conda-forge carries it. Docker is its only distribution.
* iBioSim ships ``iBioSim-linux64.zip``, but its launcher is a cwd-dependent
  shell script ending in ``exec java -jar iBioSim.jar`` with no arguments, i.e.
  the GUI. There is no headless CLI to drive.

These tests exist so the branches are not silently re-added as non-running
decoration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REMOVED_TOOLS = ("ibiosim_model", "cello_circuit_design")


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


def test_the_template_carries_only_the_two_runnable_branches() -> None:
    workflow = _load_template()
    node_types = {node["id"]: node["type"] for node in workflow["nodes"]}

    assert workflow["name"] == "Synthetic Biology Design and Simulation"
    assert set(workflow["tools"]) == {"copasi_simulation", "input_file", "note", "sbol_design_import"}
    assert node_types["sbol_import_001"] == "sbol_design_import"
    assert node_types["copasi_simulation_001"] == "copasi_simulation"


def test_the_undistributable_tools_stay_out() -> None:
    """Re-adding either branch makes the template fail at run time, not here."""
    workflow = _load_template()
    node_types = {node["type"] for node in workflow["nodes"]}

    for tool in REMOVED_TOOLS:
        assert tool not in node_types
        assert tool not in workflow["tools"]


def test_the_note_records_why_the_two_branches_are_gone() -> None:
    """Without the reason on the canvas the removal reads as an oversight."""
    text = _node(_load_template(), "note_synthetic_biology_pipeline")["params"]["text"]

    assert "Cello" in text and "no release asset" in text.lower()
    assert "iBioSim" in text and "GUI" in text


def test_both_branches_are_fed_by_real_public_data() -> None:
    workflow = _load_template()
    sbol_source = _node(workflow, "sbol_design_001")["params"]["file"]
    model_source = _node(workflow, "copasi_model_001")["params"]["file"]

    # Pinned to a commit, not a branch: SBOLTestSuite rewrites master.
    assert sbol_source.startswith("https://raw.githubusercontent.com/SynBioDex/SBOLTestSuite/")
    assert "/SBOL3/toggle_switch/toggle_switch.rdf" in sbol_source
    assert "/master/" not in sbol_source
    # BIOMD0000000012 is the Elowitz & Leibler repressilator.
    assert "biomodels" in model_source and "BIOMD0000000012" in model_source

    assert _has_edge(workflow, "sbol_design_001", "file", "sbol_import_001", "sbol_file")
    assert _has_edge(workflow, "copasi_model_001", "file", "copasi_simulation_001", "model_file")


def test_copasi_reads_sbml_and_is_given_a_task_to_schedule() -> None:
    """BioModels serves SBML, and a report only exists if a task is scheduled.

    An imported model defines no report output, so without --scheduled-task
    CopasiSE exits 0 having written nothing and the node fails on its planned
    outputs.
    """
    copasi = _node(_load_template(), "copasi_simulation_001")

    assert copasi["params"]["input_format"] == "sbml"
    assert copasi["params"]["scheduled_task"] == "Time-Course"


def test_every_declared_output_names_a_node_that_exists() -> None:
    workflow = _load_template()
    node_ids = {node["id"] for node in workflow["nodes"]}

    assert workflow["outputs"] == {
        "sbol_design": "sbol_design_001",
        "sbol_document": "sbol_import_001",
        "copasi_model": "copasi_model_001",
        "copasi_report": "copasi_simulation_001",
        "copasi_updated_model": "copasi_simulation_001",
        "copasi_log": "copasi_simulation_001",
    }
    assert set(workflow["outputs"].values()) <= node_ids


def test_no_edge_points_at_a_removed_node() -> None:
    workflow = _load_template()
    node_ids = {node["id"] for node in workflow["nodes"]}

    for edge in workflow["edges"]:
        assert edge["from"]["node"] in node_ids
        assert edge["to"]["node"] in node_ids
