"""Cello-v2 v0.1 DNACompiler circuit design."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SyntheticBiologyCommandNode, path_value


class CelloCircuitDesignNode(SyntheticBiologyCommandNode):
    """Compile a Verilog circuit using the official Cello v2 DNACompiler CLI."""

    NODE_ID = "cello_circuit_design"
    DISPLAY_NAME = "Cello Circuit Design"
    DESCRIPTION = "Compile a Verilog genetic circuit with Cello-v2 v0.1 DNACompiler."
    SEARCH_ALIASES = ["BioNodulo builtin", "Cello", "DNACompiler", "Verilog", "UCF", "genetic circuit"]
    RETURN_TYPES = ("DIRECTORY", "JSON", "LOG")
    RETURN_NAMES = ("design_dir", "output_netlist", "log")
    REQUIRED_EXECUTABLES = ["java", "python", "yosys", "dot"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRED_PATH_INPUTS = (
        "input_netlist",
        "user_constraints_file",
        "input_sensor_file",
        "output_device_file",
        "cello_jar",
    )
    OPTIONAL_PATH_INPUTS = ("options_file", "netlist_constraint_file")
    VERSION = "0.1"
    GIT_COMMIT = "e5fed2256089f5defe3afd0c90eafea2fa1e13f0"
    SOURCE_URL = "https://github.com/CIDARLAB/Cello-v2/tree/v0.1"
    DOCUMENTATION_URL = "https://github.com/CIDARLAB/Cello-v2/tree/v0.1#option-2-prepackaged-jar-file"
    UPSTREAM_SOURCE = (
        "README.md; cello/cello-common/src/main/java/org/cellocad/v2/common/runtime/environment/RuntimeEnv.java; "
        "cello/cello-dnacompiler/src/main/java/org/cellocad/v2/DNACompiler/runtime/Main.java"
    )
    EXIT_SEMANTICS = (
        "A non-zero Java exit is fatal; BioNodulo requires the DNACompiler output directory and captured log."
    )
    KNOWN_LIMITATION = "The Cello JAR is an explicit staged input because no verified conda package is available."
    EXPERIMENTAL = True
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_netlist": ("FILE", {"description": "Verilog input netlist"}),
                "user_constraints_file": ("FILE", {"description": "Cello UCF user-constraints JSON"}),
                "input_sensor_file": ("FILE", {"description": "Cello input-sensor JSON"}),
                "output_device_file": ("FILE", {"description": "Cello output-device JSON"}),
                "cello_jar": ("FILE", {"description": "Pinned Cello DNACompiler JAR"}),
            },
            "optional": {
                "options_file": ("FILE", {"default": "", "description": "Application options CSV"}),
                "netlist_constraint_file": (
                    "FILE",
                    {"default": "", "description": "Optional netlist-constraints JSON"},
                ),
                "python_executable": (
                    "STRING",
                    {"default": "python", "description": "Python executable passed through -pythonEnv"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("python_executable", "python") or "").strip():
            return "Input 'python_executable' must be non-empty"
        return True

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], node_dir: Path) -> tuple[Path, Path, Path]:
        stem = Path(path_value(inputs.get("input_netlist")) or "design").stem or "design"
        design_dir = node_dir / "design"
        return design_dir, design_dir / f"{stem}_outputNetlist.json", node_dir / "cello.log"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        outputs = cls._output_paths(inputs, cls.node_output_dir(output_dir))
        outputs[0].mkdir(parents=True, exist_ok=True)
        return list(outputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        design_dir, _, log = cls._output_paths(inputs, Path(str(inputs.get("output", "."))))
        command = [
            "java",
            "-classpath",
            path_value(inputs["cello_jar"]),
            "org.cellocad.v2.DNACompiler.runtime.Main",
            "-inputNetlist",
            path_value(inputs["input_netlist"]),
        ]
        options_file = path_value(inputs.get("options_file"))
        if options_file:
            command.extend(["-options", options_file])
        command.extend(
            [
                "-userConstraintsFile",
                path_value(inputs["user_constraints_file"]),
                "-inputSensorFile",
                path_value(inputs["input_sensor_file"]),
                "-outputDeviceFile",
                path_value(inputs["output_device_file"]),
            ]
        )
        netlist_constraint_file = path_value(inputs.get("netlist_constraint_file"))
        if netlist_constraint_file:
            command.extend(["-netlistConstraintFile", netlist_constraint_file])
        command.extend(
            [
                "-pythonEnv",
                str(inputs.get("python_executable", "python")),
                "-outputDir",
                str(design_dir),
                ">",
                str(log),
                "2>&1",
            ]
        )
        return command
