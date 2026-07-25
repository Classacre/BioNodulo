"""MS-DIAL 4.92 console processing with a staged executable."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    path_value,
    safe_output_stem,
    validate_choice,
    validate_number,
)


ANALYSIS_TYPES = ("gcms", "lcmsdda", "lcmsdia", "lcimmsdda", "lcimmsdia")


class MSDIALProcessingNode(MetabolomicsCommandNode):
    """Run the source-documented MS-DIAL 4.92 console contract."""

    NODE_ID = "msdial_processing"
    DISPLAY_NAME = "MS-DIAL Processing"
    DESCRIPTION = "Run a staged MS-DIAL 4.92 console executable with a parameter file."
    SEARCH_ALIASES = ["BioNodulo builtin", "MS-DIAL", "MSDIAL", "LC-MS", "GC-MS", "ion mobility"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("results_dir",)
    OUTPUT_SUFFIXES = ("",)
    REQUIRED_EXECUTABLES = ["mono"]
    REQUIRED_CONDA_PACKAGES = ["mono"]
    CONDA_PACKAGE_CONSTRAINTS = {"mono": "6.12.*"}
    VERSION = "4.92"
    GIT_URL = "https://github.com/systemsomicslab/MsdialWorkbench.git"
    GIT_COMMIT = "dd3a03f6fca266978211eb96aef4332744819568"
    DOCUMENTATION_URL = (
        "https://github.com/systemsomicslab/MsdialWorkbench/blob/"
        "dd3a03f6fca266978211eb96aef4332744819568/MsdialConsoleAppCore/Program.cs"
    )
    SOURCE_URL = GIT_URL
    UPSTREAM_SOURCE = "MsdialConsoleAppCore/Program.cs; MsdialConsoleAppCore/Process/MainProcess.cs"
    EXTERNAL_INSTALLATION = (
        "MS-DIAL 4.92 is not a Conda package; stage MsdialConsoleApp.exe as the required file input."
    )
    EXIT_SEMANTICS = (
        "MS-DIAL returns a non-zero integer for invalid arguments or caught processing errors; "
        "BioNodulo also requires at least one native result file."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "msdial_executable": ("FILE", {"description": "Staged MsdialConsoleApp.exe"}),
                "input_dir": ("DIRECTORY", {"description": "Directory containing files to process"}),
                "parameter_file": ("FILE", {"description": "MS-DIAL 4.92 method/parameter file"}),
            },
            "optional": {
                "analysis_type": ("STRING", {"default": "lcmsdda", "options": list(ANALYSIS_TYPES)}),
                "use_mono": ("BOOLEAN", {"default": True}),
                "keep_project_file": ("BOOLEAN", {"default": False, "description": "Pass -p"}),
                "multi_collision_energy": (
                    "BOOLEAN",
                    {"default": False, "description": "Pass -mCE for LC-MS DIA multi-collision-energy mode"},
                ),
                "target_mz": ("FLOAT", {"default": 0.0, "min": 0.0, "description": "Optional -target m/z"}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("msdial_executable", "input_dir", "parameter_file"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        analysis_type = str(inputs.get("analysis_type", "lcmsdda"))
        validation = validate_choice(analysis_type, "analysis_type", ANALYSIS_TYPES)
        if validation is not True:
            return validation
        validation = validate_number(inputs.get("target_mz", 0.0), "target_mz", minimum=0)
        if validation is not True:
            return validation
        if inputs.get("multi_collision_energy", False) and analysis_type != "lcmsdia":
            return "Input 'multi_collision_energy' is supported only for analysis_type='lcmsdia'"
        return True

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        return safe_output_stem(inputs.get("output_name"), str(inputs.get("analysis_type", "lcmsdda")))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        results_dir = output / cls.output_stem(inputs, "lcmsdda")
        command: list[str] = []
        if inputs.get("use_mono", True):
            command.append("mono")
        command.extend(
            [
                path_value(inputs.get("msdial_executable")),
                str(inputs.get("analysis_type", "lcmsdda")),
                "-i",
                path_value(inputs.get("input_dir")),
                "-o",
                str(results_dir),
                "-m",
                path_value(inputs.get("parameter_file")),
            ]
        )
        if inputs.get("keep_project_file", False):
            command.append("-p")
        if inputs.get("multi_collision_energy", False):
            command.append("-mCE")
        target_mz = float(inputs.get("target_mz", 0.0) or 0.0)
        if target_mz > 0:
            command.extend(["-target", str(inputs.get("target_mz"))])
        return command

    async def run(self, **kwargs: Any) -> tuple[str]:
        outputs = await super().run(**kwargs)
        results_dir = Path(outputs[0])
        if not any(path.is_file() for path in results_dir.rglob("*")):
            raise RuntimeError("MS-DIAL completed without creating a native result file")
        return outputs
