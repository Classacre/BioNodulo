"""MZmine 4.7.29 headless batch processing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    path_value,
    safe_output_stem,
    split_paths,
    validate_choice,
    validate_number,
)


class MZmineBatchProcessingNode(MetabolomicsCommandNode):
    """Run one MZmine batch file with explicit staged inputs and user state."""

    NODE_ID = "mzmine_batch_processing"
    DISPLAY_NAME = "MZmine Batch Processing"
    DESCRIPTION = "Run an MZmine 4.7.29 .mzbatch workflow in headless mode."
    SEARCH_ALIASES = ["BioNodulo builtin", "MZmine", "mzbatch", "LC-MS", "batch", "metabolomics"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("results_dir",)
    OUTPUT_SUFFIXES = ("",)
    REQUIRED_EXECUTABLES = ["mzmine"]
    REQUIRED_CONDA_PACKAGES = ["mzmine"]
    CONDA_PACKAGE_CONSTRAINTS = {"mzmine": "4.7.29"}
    VERSION = "4.7.29"
    GIT_URL = "https://github.com/mzmine/mzmine.git"
    GIT_COMMIT = "d780c98fd0689fea47839d0a7975f259a80e5634"
    SOURCE_SHA256 = "d2c2a7037e7f4c333efad77aaa835830cabdda156769e95a4d613d2af145ca16"
    DOCUMENTATION_URL = "https://mzmine.github.io/mzmine_documentation/commandline_tool.html"
    SOURCE_URL = GIT_URL
    UPSTREAM_SOURCE = (
        "command-line argument table; mzmine-community/.../MZmineCore.java; Bioconda mzmine 4.7.29 recipe"
    )
    CREDENTIAL_SEMANTICS = (
        "MZmine CLI requires a valid .mzuser file; the staged user file may expire and must be handled as sensitive input."
    )
    EXIT_SEMANTICS = (
        "MZmine returns zero only for a finished batch. BioNodulo also requires at least one native result file."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "batch_file": ("FILE", {"description": "MZmine .mzbatch workflow"}),
                "user_file": ("FILE", {"description": "Valid staged MZmine .mzuser file"}),
            },
            "optional": {
                "input_files": (
                    "FILE_LIST",
                    {"default": [], "multiple": True, "description": "Files overriding batch import steps"},
                ),
                "preferences_file": ("FILE", {"default": "", "description": "Optional .mzconfig preferences"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 256}),
                "memory_mode": (
                    "STRING",
                    {
                        "default": "none",
                        "options": ["none", "all", "features", "centroids", "raw", "masses_features"],
                    },
                ),
                "temp_dir": ("DIRECTORY", {"default": ""}),
                "ignore_parameter_warnings": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("batch_file", "user_file"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        validation = validate_number(inputs.get("threads", 1), "threads", minimum=1, maximum=256, integer=True)
        if validation is not True:
            return validation
        return validate_choice(
            inputs.get("memory_mode", "none"),
            "memory_mode",
            ("none", "all", "features", "centroids", "raw", "masses_features"),
        )

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        batch_stem = safe_output_stem(inputs.get("batch_file"), "mzmine")
        return safe_output_stem(inputs.get("output_name"), batch_stem)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        stem = cls.output_stem(inputs, "mzmine")
        results_dir = output / stem
        results_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "mzmine",
            "-user",
            path_value(inputs.get("user_file")),
            "-batch",
            path_value(inputs.get("batch_file")),
        ]
        input_files = split_paths(inputs.get("input_files"))
        if input_files:
            input_list = output / f"{stem}.input_files.txt"
            input_list.write_text("\n".join(input_files) + "\n", encoding="utf-8")
            command.extend(["-input", str(input_list)])
        command.extend(["-output", str(results_dir / stem)])
        temp_dir = path_value(inputs.get("temp_dir"))
        if temp_dir:
            command.extend(["-temp", temp_dir])
        preferences = path_value(inputs.get("preferences_file"))
        if preferences:
            command.extend(["-pref", preferences])
        command.extend(
            [
                "-memory",
                str(inputs.get("memory_mode", "none")),
                "-threads",
                str(inputs.get("threads", 1)),
            ]
        )
        if inputs.get("ignore_parameter_warnings", False):
            command.append("-ignore-parameter-warnings")
        return command

    async def run(self, **kwargs: Any) -> tuple[str]:
        outputs = await super().run(**kwargs)
        results_dir = Path(outputs[0])
        if not any(path.is_file() for path in results_dir.rglob("*")):
            raise RuntimeError("MZmine completed without creating a native result file")
        return outputs
