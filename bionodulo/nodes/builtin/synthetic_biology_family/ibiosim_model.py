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
    REQUIRED_EXECUTABLES = ["iBioSim"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRED_PATH_INPUTS = ("archive_file",)
    VERSION = "0.0.1"
    SIMULATOR_VERSION = "3.1.0"
    GIT_COMMIT = "905de27812f011dd63c37f41347ed89839936161"
    SOURCE_URL = "https://github.com/biosimulators/Biosimulators_iBioSim/tree/0.0.1"
    DOCUMENTATION_URL = "https://github.com/biosimulators/Biosimulators_iBioSim"
    UPSTREAM_SOURCE = "setup.py; biosimulators_ibiosim/__main__.py; biosimulators_ibiosim/core.py; Dockerfile"
    EXIT_SEMANTICS = (
        "The wrapper's non-zero exit is fatal; BioNodulo requires the requested results directory and captured log."
    )
    KNOWN_LIMITATION = (
        "No verified immutable public image or conda package is available; a worker must provision the exact iBioSim executable."
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
