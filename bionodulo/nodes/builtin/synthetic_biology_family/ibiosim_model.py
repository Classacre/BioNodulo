"""BioSimulators-iBioSim 0.0.1 COMBINE archive execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SyntheticBiologyCommandNode, path_value, validate_bool


class iBioSimModelNode(SyntheticBiologyCommandNode):
    """Execute a COMBINE archive through the official BioSimulators wrapper."""

    NODE_ID = "ibiosim_model"
    DISPLAY_NAME = "iBioSim Model"
    DESCRIPTION = "Execute a COMBINE/OMEX archive with BioSimulators-iBioSim 0.0.1."
    SEARCH_ALIASES = ["BioNodulo builtin", "iBioSim", "BioSimulators", "COMBINE", "OMEX", "SED-ML"]
    RETURN_TYPES = ("DIRECTORY", "LOG")
    RETURN_NAMES = ("results_dir", "log")
    REQUIRED_EXECUTABLES = ["iBioSim", "java"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRED_PATH_INPUTS = ("archive_file",)
    VERSION = "0.0.1"
    SIMULATOR_VERSION = "3.1.0"
    GIT_COMMIT = "905de27812f011dd63c37f41347ed89839936161"
    GIT_URL = "https://github.com/biosimulators/Biosimulators_iBioSim.git"
    SOURCE_URL = f"https://github.com/biosimulators/Biosimulators_iBioSim/tree/{GIT_COMMIT}"
    RELEASE_TAG_URL = "https://github.com/biosimulators/Biosimulators_iBioSim/tree/0.0.1"
    DOCUMENTATION_URL = "https://github.com/biosimulators/Biosimulators_iBioSim"
    LICENSE = "Apache-2.0"
    LICENSE_URL = f"https://github.com/biosimulators/Biosimulators_iBioSim/blob/{GIT_COMMIT}/LICENSE"
    UPSTREAM_SOURCE = (
        "README.md; setup.py; biosimulators_ibiosim/__main__.py; "
        "biosimulators_ibiosim/core.py; tests/test_all.py; Dockerfile"
    )
    SOURCE_AUTHORITIES = {
        "cli": "README.md; biosimulators_ibiosim/__main__.py",
        "execution_callback": "biosimulators_ibiosim/core.py:exec_sedml_docs_in_combine_archive",
        "known_skipped_execution": "tests/test_all.py",
        "simulator_and_image_recipe": "Dockerfile; biosimulators.json",
        "license": LICENSE_URL,
    }
    PACKAGE_CONSTRAINT = "external BioSimulators-iBioSim 0.0.1 with iBioSim 3.1.0"
    ACCESS_CONSTRAINTS = (
        "worker-provisioned case-sensitive iBioSim wrapper executable",
        "worker-provisioned Java runtime and IBIOSIM_PATH JAR",
        "patched immutable runtime required before promotion",
    )
    QUARANTINE_STATUS = "blocked-upstream-incomplete-no-binary-execution"
    AUDIT_STATUS = "contract-checked-upstream-incomplete-no-binary-execution"
    UPSTREAM_EXECUTION_STATUS = "incomplete-at-pinned-tag"
    EXIT_SEMANTICS = (
        "A missing archive raises FileNotFoundError and a non-zero Java exit propagates through "
        "subprocess.check_call. Exit zero does not prove result placement in upstream 0.0.1, so "
        "BioNodulo also requires the requested results directory and captured log."
    )
    KNOWN_LIMITATION = (
        "Upstream 0.0.1 is incomplete: core.py accepts but never uses out_dir, its execution test is "
        "skipped as 'Method not yet implemented', its container test is skipped as 'Docker image not "
        "yet built', and the release commit says the Dockerfile does not succeed. No verified immutable "
        "image or Conda package is available."
    )
    EXPERIMENTAL = True
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "archive_file": ("FILE", {"description": "COMBINE/OMEX archive containing SED-ML experiments"}),
            },
            "optional": {
                "quiet": ("BOOLEAN", {"default": False, "description": "Suppress wrapper console output"}),
                "debug": ("BOOLEAN", {"default": False, "description": "Enable wrapper debug output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("quiet", "debug"):
            validation = validate_bool(inputs.get(key, False), key)
            if validation is not True:
                return validation
        return True

    @classmethod
    def _output_paths(cls, node_dir: Path) -> tuple[Path, Path]:
        return node_dir / "results", node_dir / "ibiosim.log"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return list(cls._output_paths(cls.node_output_dir(output_dir)))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        results_dir, log = cls._output_paths(Path(str(inputs.get("output", "."))))
        command = ["iBioSim"]
        if inputs.get("debug", False):
            command.append("-d")
        if inputs.get("quiet", False):
            command.append("-q")
        command.extend(["-i", path_value(inputs["archive_file"]), "-o", str(results_dir)])
        command.extend([">", str(log), "2>&1"])
        return command
