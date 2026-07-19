from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
)
from bionodulo.nodes.builtin.synthetic_biology_family.cello_circuit_design import (
    CelloCircuitDesignNode,
)
from bionodulo.nodes.builtin.synthetic_biology_family.copasi_simulation import (
    COPASISimulationNode,
)
from bionodulo.nodes.builtin.synthetic_biology_family.ibiosim_model import iBioSimModelNode
from bionodulo.nodes.builtin.synthetic_biology_family.sbol_design_import import (
    SBOLDesignImportNode,
)
from bionodulo.nodes.registry import NodeRegistry


def test_focused_synthetic_biology_nodes_are_source_pinned_and_discoverable() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    expected = {
        "sbol_design_import": (SBOLDesignImportNode, "1.1", "c84ccd16028821f8668473758031e1b6dcdcd628"),
        "copasi_simulation": (COPASISimulationNode, "4.46.300", "e9c47d912b55eccd56f70b72e52f19d61f5ab2e2"),
        "ibiosim_model": (iBioSimModelNode, "0.0.1", "905de27812f011dd63c37f41347ed89839936161"),
        "cello_circuit_design": (CelloCircuitDesignNode, "0.1", "e5fed2256089f5defe3afd0c90eafea2fa1e13f0"),
    }
    for node_id, (node_class, version, commit) in expected.items():
        assert registry.get(node_id) is node_class
        assert node_class.VERSION == version
        assert node_class.GIT_COMMIT == commit
        assert node_class.SOURCE_URL.endswith(commit)
        assert node_class.SOURCE_AUTHORITIES
        assert "no-" in node_class.AUDIT_STATUS
        assert node_class.QUARANTINE_STATUS
        assert node_class.__module__.startswith("bionodulo.nodes.builtin.synthetic_biology_family.")


def test_synthetic_biology_environment_contracts_are_exact() -> None:
    assert PACKAGE_MIN_VERSIONS["pysbol3"] == "1.1"
    assert SBOLDesignImportNode.CONDA_PACKAGE_CONSTRAINTS == {"pysbol3": "1.1"}
    assert EXECUTABLE_TO_CONDA_PACKAGE["iBioSim"] == ""
    assert EXECUTABLE_TO_CONDA_PACKAGE["dot"] == "graphviz"


def test_sbol_uses_official_format_constants_and_plans_native_files(tmp_path: Path) -> None:
    inputs = {
        "sbol_file": "design.ttl",
        "namespace": "https://example.org/designs",
        "validate": True,
        "output_format": "json-ld",
        "output": "/work/sbol_design_import",
    }
    command = SBOLDesignImportNode.render_command(inputs)

    assert command[:2] == ["python", "-c"]
    assert command[-6:] == [
        "design.ttl",
        "/work/sbol_design_import/normalized.json",
        "/work/sbol_design_import/summary.json",
        "json-ld",
        "https://example.org/designs",
        "true",
    ]
    assert "document.validate()" in command[2]
    assert "document.write(output_path, file_format=output_format)" in command[2]
    assert SBOLDesignImportNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "sbol_design_import" / "normalized.json",
        tmp_path / "sbol_design_import" / "summary.json",
    ]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"sbol_file": "", "validate": True, "output_format": "xml"}, "sbol_file"),
        ({"sbol_file": "a.xml", "validate": True, "output_format": "rdfxml"}, "output_format"),
        ({"sbol_file": "a.xml", "validate": "yes", "output_format": "xml"}, "boolean"),
        (
            {
                "sbol_file": "a.xml",
                "namespace": "example.org/designs",
                "validate": True,
                "output_format": "xml",
            },
            "absolute URL",
        ),
    ],
)
def test_sbol_rejects_values_outside_pysbol3_contract(inputs: dict[str, Any], message: str) -> None:
    assert message in str(SBOLDesignImportNode.VALIDATE_INPUTS(inputs))


def test_copasi_renders_cps_task_override_and_required_outputs(tmp_path: Path) -> None:
    inputs = {
        "model_file": "toggle.cps",
        "input_format": "cps",
        "scheduled_task": "Time-Course",
        "sedml_task": "",
        "verbose": True,
        "max_time": 600,
        "output": "/work/copasi_simulation",
    }
    assert COPASISimulationNode.render_command(inputs) == [
        "CopasiSE",
        "--nologo",
        "--verbose",
        "toggle.cps",
        "--save",
        "/work/copasi_simulation/updated.cps",
        "--report-file",
        "/work/copasi_simulation/report.txt",
        "--scheduled-task",
        "Time-Course",
        "--maxTime",
        "600",
        ">",
        "/work/copasi_simulation/copasi.log",
        "2>&1",
    ]
    assert COPASISimulationNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "copasi_simulation" / "report.txt",
        tmp_path / "copasi_simulation" / "updated.cps",
        tmp_path / "copasi_simulation" / "copasi.log",
    ]


@pytest.mark.parametrize(
    ("input_format", "flag"),
    [("sbml", "--importSBML"), ("sedml", "--importSEDML"), ("omex", "--importCA")],
)
def test_copasi_selects_documented_import_flag(input_format: str, flag: str) -> None:
    command = COPASISimulationNode.render_command(
        {
            "model_file": "study.input",
            "input_format": input_format,
            "scheduled_task": "",
            "sedml_task": "task-1" if input_format in {"sedml", "omex"} else "",
            "verbose": False,
            "max_time": 0,
            "output": "/work/copasi_simulation",
        }
    )
    assert command[2:4] == [flag, "study.input"]
    assert command.count("study.input") == 1


def test_copasi_accepts_separate_sedml_selection_and_scheduled_task_override() -> None:
    inputs = {
        "model_file": "study.omex",
        "input_format": "omex",
        "scheduled_task": "Time-Course",
        "sedml_task": "task-1",
        "output": "/work/copasi_simulation",
    }
    assert COPASISimulationNode.VALIDATE_INPUTS(inputs) is True

    command = COPASISimulationNode.render_command(inputs)
    assert command[command.index("--scheduled-task") : command.index("--scheduled-task") + 2] == [
        "--scheduled-task",
        "Time-Course",
    ]
    assert command[command.index("--sedmlTask") : command.index("--sedmlTask") + 2] == [
        "--sedmlTask",
        "task-1",
    ]


def test_copasi_rejects_sedml_task_for_non_sedml_input() -> None:
    wrong_format = COPASISimulationNode.VALIDATE_INPUTS(
        {"model_file": "study.cps", "input_format": "cps", "sedml_task": "task-1"}
    )
    assert "requires input_format" in str(wrong_format)


def test_ibiosim_uses_case_sensitive_official_wrapper_and_native_directory(tmp_path: Path) -> None:
    inputs = {
        "archive_file": "study.omex",
        "quiet": True,
        "debug": True,
        "output": "/work/ibiosim_model",
    }
    assert iBioSimModelNode.render_command(inputs) == [
        "iBioSim",
        "-d",
        "-q",
        "-i",
        "study.omex",
        "-o",
        "/work/ibiosim_model/results",
        ">",
        "/work/ibiosim_model/ibiosim.log",
        "2>&1",
    ]
    assert iBioSimModelNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "ibiosim_model" / "results",
        tmp_path / "ibiosim_model" / "ibiosim.log",
    ]
    assert iBioSimModelNode.REQUIRED_EXECUTABLES == ["iBioSim", "java"]
    assert iBioSimModelNode.UPSTREAM_EXECUTION_STATUS == "incomplete-at-pinned-tag"
    assert "never uses out_dir" in iBioSimModelNode.KNOWN_LIMITATION
    assert "Method not yet implemented" in iBioSimModelNode.KNOWN_LIMITATION


def test_cello_renders_official_dna_compiler_artifact_contract(tmp_path: Path) -> None:
    inputs = {
        "input_netlist": "toggle.v",
        "user_constraints_file": "Eco.UCF.json",
        "input_sensor_file": "Eco.input.json",
        "output_device_file": "Eco.output.json",
        "cello_jar": "cello-dnacompiler.jar",
        "options_file": "options.csv",
        "netlist_constraint_file": "constraints.json",
        "python_executable": "python3",
        "output": "/work/cello_circuit_design",
    }
    assert CelloCircuitDesignNode.render_command(inputs) == [
        "java",
        "-classpath",
        "cello-dnacompiler.jar",
        "org.cellocad.v2.DNACompiler.runtime.Main",
        "-inputNetlist",
        "toggle.v",
        "-options",
        "options.csv",
        "-userConstraintsFile",
        "Eco.UCF.json",
        "-inputSensorFile",
        "Eco.input.json",
        "-outputDeviceFile",
        "Eco.output.json",
        "-netlistConstraintFile",
        "constraints.json",
        "-pythonEnv",
        "python3",
        "-outputDir",
        "/work/cello_circuit_design/design",
        ">",
        "/work/cello_circuit_design/cello.log",
        "2>&1",
    ]
    assert CelloCircuitDesignNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "cello_circuit_design" / "design",
        tmp_path / "cello_circuit_design" / "design" / "toggle_outputNetlist.json",
        tmp_path / "cello_circuit_design" / "cello.log",
    ]


def test_cello_requires_each_documented_design_artifact() -> None:
    inputs = {
        "input_netlist": "toggle.v",
        "user_constraints_file": "Eco.UCF.json",
        "input_sensor_file": "",
        "output_device_file": "Eco.output.json",
        "cello_jar": "cello.jar",
    }
    assert "input_sensor_file" in str(CelloCircuitDesignNode.VALIDATE_INPUTS(inputs))
    assert set(CelloCircuitDesignNode.INPUT_TYPES()["required"]) == {
        "input_netlist",
        "user_constraints_file",
        "input_sensor_file",
        "output_device_file",
        "cello_jar",
    }
