"""COPASI 4.46 Build 300 batch simulation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    SyntheticBiologyCommandNode,
    path_value,
    validate_bool,
    validate_choice,
    validate_int,
)


class COPASISimulationNode(SyntheticBiologyCommandNode):
    """Run configured COPASI tasks from CPS, SBML, SED-ML, or COMBINE input."""

    NODE_ID = "copasi_simulation"
    DISPLAY_NAME = "COPASI Simulation"
    DESCRIPTION = "Run configured model tasks with CopasiSE 4.46 Build 300."
    SEARCH_ALIASES = ["BioNodulo builtin", "COPASI", "CopasiSE", "SBML", "SED-ML", "OMEX"]
    RETURN_TYPES = ("FILE", "CPS", "LOG")
    RETURN_NAMES = ("report", "updated_model", "log")
    REQUIRED_EXECUTABLES = ["CopasiSE"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRED_PATH_INPUTS = ("model_file",)
    VERSION = "4.46.300"
    GIT_COMMIT = "e9c47d912b55eccd56f70b72e52f19d61f5ab2e2"
    GIT_URL = "https://github.com/copasi/COPASI.git"
    SOURCE_URL = f"https://github.com/copasi/COPASI/tree/{GIT_COMMIT}"
    RELEASE_TAG_URL = "https://github.com/copasi/COPASI/tree/Build-300"
    DOCUMENTATION_URL = "https://copasi.org/Support/User_Manual/Model_Creation/Commandline_Version_and_Commandline_Options/"
    LICENSE = "Artistic-2.0"
    LICENSE_URL = f"https://github.com/copasi/COPASI/blob/{GIT_COMMIT}/license.txt"
    UPSTREAM_SOURCE = "copasi/commandline/COptionParser.cpp; copasi/CopasiSE/CopasiSE.cpp"
    SOURCE_AUTHORITIES = {
        "cli_parser_and_help": "copasi/commandline/COptionParser.cpp",
        "import_task_output_and_exit_behavior": "copasi/CopasiSE/CopasiSE.cpp",
        "manual": DOCUMENTATION_URL,
        "license": LICENSE_URL,
    }
    PACKAGE_CONSTRAINT = "external BYOL CopasiSE 4.46 Build 300"
    ACCESS_CONSTRAINTS = (
        "worker-provisioned CopasiSE built from COPASI Build-300",
        "Artistic License 2.0 terms apply",
    )
    QUARANTINE_STATUS = "byol-evidence-only-no-binary-execution"
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    KNOWN_LIMITATION = "No verified Conda package or immutable CopasiSE binary is provisioned by this node."
    REPORT_SEMANTICS = (
        "--report-file overrides the target of each task that actually runs. The report is only "
        "materialized when the CPS task or selected SED-ML task defines report output."
    )
    EXIT_SEMANTICS = (
        "A non-zero CopasiSE exit is fatal. Build 300 catches some CCopasiException paths without "
        "changing the return code, so BioNodulo additionally requires the configured report, saved "
        "CPS, and captured log to exist."
    )
    EXPERIMENTAL = True
    SHELL = True
    INPUT_FORMATS = ("cps", "sbml", "sedml", "omex")
    IMPORT_FLAGS = {
        "sbml": "--importSBML",
        "sedml": "--importSEDML",
        "omex": "--importCA",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "model_file": ("FILE", {"description": "COPASI CPS, SBML, SED-ML, or COMBINE archive"}),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "cps",
                        "options": list(cls.INPUT_FORMATS),
                        "description": "Explicit input contract; non-CPS inputs use the matching import flag",
                    },
                ),
                "scheduled_task": (
                    "STRING",
                    {"default": "", "description": "Override the COPASI task marked executable"},
                ),
                "sedml_task": (
                    "STRING",
                    {"default": "", "description": "SED-ML task id for SED-ML or COMBINE imports"},
                ),
                "verbose": ("BOOLEAN", {"default": False}),
                "max_time": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Maximum runtime in seconds; 0 disables"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        input_format = str(inputs.get("input_format", "cps"))
        validation = validate_choice(input_format, "input_format", cls.INPUT_FORMATS)
        if validation is not True:
            return validation
        validation = validate_bool(inputs.get("verbose", False), "verbose")
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("max_time", 0), "max_time", minimum=0)
        if validation is not True:
            return validation
        sedml_task = str(inputs.get("sedml_task", "") or "").strip()
        if sedml_task and input_format not in {"sedml", "omex"}:
            return "Input 'sedml_task' requires input_format sedml or omex"
        return True

    @classmethod
    def _output_paths(cls, node_dir: Path) -> tuple[Path, Path, Path]:
        return node_dir / "report.txt", node_dir / "updated.cps", node_dir / "copasi.log"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return list(cls._output_paths(cls.node_output_dir(output_dir)))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        report, updated_model, log = cls._output_paths(Path(str(inputs.get("output", "."))))
        input_format = str(inputs.get("input_format", "cps"))
        model_file = path_value(inputs["model_file"])
        scheduled_task = str(inputs.get("scheduled_task", "") or "").strip()
        sedml_task = str(inputs.get("sedml_task", "") or "").strip()
        max_time = int(inputs.get("max_time", 0))

        command = ["CopasiSE", "--nologo"]
        if inputs.get("verbose", False):
            command.append("--verbose")
        if input_format == "cps":
            command.append(model_file)
        else:
            command.extend([cls.IMPORT_FLAGS[input_format], model_file])
        command.extend(["--save", str(updated_model), "--report-file", str(report)])
        if scheduled_task:
            command.extend(["--scheduled-task", scheduled_task])
        if sedml_task:
            command.extend(["--sedmlTask", sedml_task])
        if max_time:
            command.extend(["--maxTime", str(max_time)])
        command.extend([">", str(log), "2>&1"])
        return command
