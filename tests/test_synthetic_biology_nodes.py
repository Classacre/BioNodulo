from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_sbol_design_import_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["sbol_design_import"]
    assert node_info["display_name"] == "SBOL Design Import"
    assert node_info["category"] == "synthetic_biology"
    assert node_info["description"].startswith("Import and summarize")
    assert node_info["output"] == ["SBOL", "JSON"]
    assert node_info["output_name"] == ["normalized_sbol", "summary"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["pysbol3"]
    assert "sbol" in node_info["search_aliases"]
    assert "synthetic biology" in node_info["search_aliases"]
    assert "biocad" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sbol_file"}
    assert set(inputs["optional"]) == {"namespace", "validate", "output_format", "output_name"}


def test_sbol_design_import_writes_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("sbol_design_import")
    output_dir = tmp_path / "sbol_design_import"

    cmd = node_class.render_command({
        "sbol_file": "design.xml",
        "namespace": "https://example.org/designs",
        "validate": True,
        "output_format": "rdfxml",
        "output_name": "toggle switch",
        "output": str(output_dir),
    })

    script_file = output_dir / "sbol_design_import.py"
    assert cmd == ["python", str(script_file)]
    script = script_file.read_text()
    assert "import sbol3" in script
    assert "doc = sbol3.Document()" in script
    assert "sbol3.set_namespace('https://example.org/designs')" in script
    assert "doc.read('design.xml')" in script
    assert "report = doc.validate()" in script
    assert f"doc.write('{output_dir}/toggle_switch.xml', file_format='rdfxml')" in script
    assert f"summary_path = Path('{output_dir}/toggle_switch.summary.json')" in script
    assert "\"components\"" in script
    assert "\"sequences\"" in script
    assert "\"interactions\"" in script


def test_sbol_design_import_accepts_default_output_name_and_skips_validation(tmp_path: Path) -> None:
    node_class = _node_class("sbol_design_import")
    output_dir = tmp_path / "sbol_design_import"

    cmd = node_class.render_command({
        "sbol_file": "/data/plasmid_design.nt",
        "namespace": "",
        "validate": False,
        "output_format": "ntriples",
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == ["python", str(output_dir / "sbol_design_import.py")]
    script = (output_dir / "sbol_design_import.py").read_text()
    assert "sbol3.set_namespace" not in script
    assert "report = doc.validate()" not in script
    assert "doc.read('/data/plasmid_design.nt')" in script
    assert f"doc.write('{output_dir}/plasmid_design.nt', file_format='ntriples')" in script
    assert f"summary_path = Path('{output_dir}/plasmid_design.summary.json')" in script


def test_sbol_design_import_plans_outputs() -> None:
    node_class = _node_class("sbol_design_import")

    outputs = node_class.PLAN_OUTPUTS({"sbol_file": "toggle.xml", "output_name": "toggle switch"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/sbol_design_import/toggle_switch.xml",
        "/tmp/run/sbol_design_import/toggle_switch.summary.json",
    ]


def test_sbol_design_import_environment_metadata_is_declared() -> None:
    assert PACKAGE_MIN_VERSIONS["pysbol3"] == ">=1.1"


def test_copasi_simulation_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["copasi_simulation"]
    assert node_info["display_name"] == "COPASI Simulation"
    assert node_info["category"] == "synthetic_biology"
    assert node_info["description"].startswith("Run COPASI batch simulations")
    assert node_info["output"] == ["TSV", "CPS", "LOG", "JSON"]
    assert node_info["output_name"] == ["report", "updated_model", "log", "metadata"]
    assert node_info["required_executables"] == ["CopasiSE", "python"]
    assert node_info["required_conda_packages"] == []
    assert node_info["experimental"] is True
    assert "copasi" in node_info["search_aliases"]
    assert "CopasiSE" in node_info["search_aliases"]
    assert "kinetic model" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"model_file"}
    assert set(inputs["optional"]) == {
        "copasi_executable",
        "scheduled_task",
        "sedml_task",
        "save_model",
        "validate_only",
        "verbose",
        "max_time",
        "output_name",
    }


def test_copasi_simulation_renders_batch_command_with_task_override() -> None:
    node_class = _node_class("copasi_simulation")

    cmd = node_class.render_command({
        "model_file": "/models/glycolysis.cps",
        "copasi_executable": "CopasiSE",
        "scheduled_task": "Time-Course",
        "sedml_task": "",
        "save_model": True,
        "validate_only": False,
        "verbose": True,
        "max_time": 600,
        "output_name": "glycolysis run",
        "output": "/tmp/run/copasi_simulation",
    })

    assert cmd == [
        "CopasiSE",
        "--nologo",
        "--verbose",
        "/models/glycolysis.cps",
        "-s",
        "/tmp/run/copasi_simulation/glycolysis_run.updated.cps",
        "--report-file",
        "/tmp/run/copasi_simulation/glycolysis_run.report.tsv",
        "--scheduled-task",
        "Time-Course",
        "--maxTime",
        "600",
        ">",
        "/tmp/run/copasi_simulation/glycolysis_run.log",
        "2>&1",
        "&&",
        "python",
        "-c",
        node_class.METADATA_SCRIPT,
        "/tmp/run/copasi_simulation/glycolysis_run.metadata.json",
        "/models/glycolysis.cps",
        "/tmp/run/copasi_simulation/glycolysis_run.report.tsv",
        "/tmp/run/copasi_simulation/glycolysis_run.updated.cps",
        "/tmp/run/copasi_simulation/glycolysis_run.log",
        "CopasiSE",
        "Time-Course",
        "",
        "false",
        "true",
        "true",
        "600",
    ]


def test_copasi_simulation_renders_sedml_validation_command_without_save() -> None:
    node_class = _node_class("copasi_simulation")

    cmd = node_class.render_command({
        "model_file": "/models/study.omex",
        "copasi_executable": "/opt/copasi/CopasiSE",
        "scheduled_task": "",
        "sedml_task": "repTsk_0_0_0",
        "save_model": False,
        "validate_only": True,
        "verbose": False,
        "max_time": 0,
        "output_name": "",
        "output": "/tmp/run/copasi_simulation",
    })

    assert cmd == [
        "/opt/copasi/CopasiSE",
        "--nologo",
        "--validate",
        "/models/study.omex",
        "--report-file",
        "/tmp/run/copasi_simulation/study.report.tsv",
        "--sedmlTask",
        "repTsk_0_0_0",
        ">",
        "/tmp/run/copasi_simulation/study.log",
        "2>&1",
        "&&",
        "python",
        "-c",
        node_class.METADATA_SCRIPT,
        "/tmp/run/copasi_simulation/study.metadata.json",
        "/models/study.omex",
        "/tmp/run/copasi_simulation/study.report.tsv",
        "/tmp/run/copasi_simulation/study.updated.cps",
        "/tmp/run/copasi_simulation/study.log",
        "/opt/copasi/CopasiSE",
        "",
        "repTsk_0_0_0",
        "true",
        "false",
        "false",
        "0",
    ]
    assert "-s" not in cmd
    assert "--maxTime" not in cmd


def test_copasi_simulation_rejects_conflicting_task_overrides() -> None:
    node_class = _node_class("copasi_simulation")

    try:
        node_class.render_command({
            "model_file": "/models/study.omex",
            "scheduled_task": "Time-Course",
            "sedml_task": "repTsk_0_0_0",
            "output": "/tmp/run/copasi_simulation",
        })
    except ValueError as exc:
        assert "scheduled_task" in str(exc)
        assert "sedml_task" in str(exc)
    else:
        raise AssertionError("Expected ValueError for conflicting COPASI task overrides")


def test_copasi_simulation_plans_outputs() -> None:
    node_class = _node_class("copasi_simulation")

    outputs = node_class.PLAN_OUTPUTS(
        {"model_file": "/models/glycolysis.cps", "output_name": "glycolysis run"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/copasi_simulation/glycolysis_run.report.tsv",
        "/tmp/run/copasi_simulation/glycolysis_run.updated.cps",
        "/tmp/run/copasi_simulation/glycolysis_run.log",
        "/tmp/run/copasi_simulation/glycolysis_run.metadata.json",
    ]


def test_copasi_simulation_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["CopasiSE"] == ""
    assert EXECUTABLE_TO_CONDA_PACKAGE["python"] == "python"
    assert "copasi" not in PACKAGE_MIN_VERSIONS
    packages = workflow_to_packages({"nodes": [{"id": "copasi", "type": "copasi_simulation"}]}, registry)

    assert packages == ["python"]
    assert "CopasiSE" not in packages


def test_ibiosim_model_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["ibiosim_model"]
    assert node_info["display_name"] == "iBioSim Model"
    assert node_info["category"] == "synthetic_biology"
    assert node_info["description"].startswith("Execute iBioSim COMBINE/OMEX")
    assert node_info["output"] == ["DIRECTORY", "TSV", "JSON", "LOG"]
    assert node_info["output_name"] == ["results_dir", "result_index", "metadata", "log"]
    assert node_info["required_executables"] == ["ibiosim", "python"]
    assert node_info["required_conda_packages"] == []
    assert node_info["experimental"] is True
    assert "ibiosim" in node_info["search_aliases"]
    assert "combine archive" in node_info["search_aliases"]
    assert "sed-ml" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"archive_file"}
    assert set(inputs["optional"]) == {
        "execution_mode",
        "ibiosim_executable",
        "docker_image",
        "quiet",
        "debug",
        "output_name",
    }


def test_ibiosim_model_renders_direct_cli_command() -> None:
    node_class = _node_class("ibiosim_model")

    cmd = node_class.render_command({
        "archive_file": "/models/toggle.omex",
        "execution_mode": "cli",
        "ibiosim_executable": "ibiosim",
        "docker_image": "ghcr.io/biosimulators/ibiosim:latest",
        "quiet": True,
        "debug": False,
        "output_name": "toggle study",
        "output": "/tmp/run/ibiosim_model",
    })

    assert cmd == [
        "ibiosim",
        "-q",
        "-i",
        "/models/toggle.omex",
        "-o",
        "/tmp/run/ibiosim_model/toggle_study",
        ">",
        "/tmp/run/ibiosim_model/toggle_study.log",
        "2>&1",
        "&&",
        "python",
        "-c",
        node_class.INDEX_SCRIPT,
        "/tmp/run/ibiosim_model/toggle_study",
        "/tmp/run/ibiosim_model/toggle_study.result_index.tsv",
        "/tmp/run/ibiosim_model/toggle_study.metadata.json",
        "/tmp/run/ibiosim_model/toggle_study.log",
        "/models/toggle.omex",
        "cli",
        "ibiosim",
        "ghcr.io/biosimulators/ibiosim:latest",
        "true",
        "false",
    ]


def test_ibiosim_model_renders_docker_command_with_default_stem() -> None:
    node_class = _node_class("ibiosim_model")

    cmd = node_class.render_command({
        "archive_file": "/models/repressilator.omex",
        "execution_mode": "docker",
        "ibiosim_executable": "ibiosim",
        "docker_image": "ghcr.io/biosimulators/ibiosim:v0.0.1",
        "quiet": False,
        "debug": True,
        "output_name": "",
        "output": "/tmp/run/ibiosim_model",
    })

    assert cmd == [
        "docker",
        "run",
        "--rm",
        "--mount",
        "type=bind,source=/models,target=/tmp/ibiosim-input,readonly",
        "--mount",
        "type=bind,source=/tmp/run/ibiosim_model/repressilator,target=/tmp/ibiosim-output",
        "ghcr.io/biosimulators/ibiosim:v0.0.1",
        "-d",
        "-i",
        "/tmp/ibiosim-input/repressilator.omex",
        "-o",
        "/tmp/ibiosim-output",
        ">",
        "/tmp/run/ibiosim_model/repressilator.log",
        "2>&1",
        "&&",
        "python",
        "-c",
        node_class.INDEX_SCRIPT,
        "/tmp/run/ibiosim_model/repressilator",
        "/tmp/run/ibiosim_model/repressilator.result_index.tsv",
        "/tmp/run/ibiosim_model/repressilator.metadata.json",
        "/tmp/run/ibiosim_model/repressilator.log",
        "/models/repressilator.omex",
        "docker",
        "ibiosim",
        "ghcr.io/biosimulators/ibiosim:v0.0.1",
        "false",
        "true",
    ]


def test_ibiosim_model_rejects_unknown_execution_mode() -> None:
    node_class = _node_class("ibiosim_model")

    try:
        node_class.render_command({
            "archive_file": "/models/toggle.omex",
            "execution_mode": "singularity",
            "output": "/tmp/run/ibiosim_model",
        })
    except ValueError as exc:
        assert "execution_mode" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported iBioSim execution mode")


def test_ibiosim_model_plans_outputs() -> None:
    node_class = _node_class("ibiosim_model")

    outputs = node_class.PLAN_OUTPUTS(
        {"archive_file": "/models/toggle.omex", "output_name": "toggle study"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/ibiosim_model/toggle_study",
        "/tmp/run/ibiosim_model/toggle_study.result_index.tsv",
        "/tmp/run/ibiosim_model/toggle_study.metadata.json",
        "/tmp/run/ibiosim_model/toggle_study.log",
    ]


def test_ibiosim_model_environment_metadata_avoids_fake_conda_package() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["ibiosim"] == ""
    assert EXECUTABLE_TO_CONDA_PACKAGE["python"] == "python"
    packages = workflow_to_packages({"nodes": [{"id": "ibiosim", "type": "ibiosim_model"}]}, registry)

    assert packages == ["python"]
    assert "ibiosim" not in packages
    assert "biosimulators-ibiosim" not in packages
