"""R 4.5.3 Rscript front-end contract."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import R_DOCUMENTATION_URL, R_GIT_COMMIT, R_GIT_URL, R_VERSION, path_value


class RScriptNode(CommandNode):
    """Run one caller-provided R script with separately tokenized arguments."""

    NODE_ID = "r_script"
    DISPLAY_NAME = "R Script"
    CATEGORY = "r"
    DESCRIPTION = "Execute an R script with Rscript --vanilla and expose its working directory."
    SEARCH_ALIASES = ["BioNodulo builtin", "R", "Rscript", "custom script"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base"]
    CONDA_PACKAGE_CONSTRAINTS = {"r-base": R_VERSION}
    REQUIRED_R_PACKAGES: list[str] = []
    VERSION = R_VERSION
    GIT_URL = R_GIT_URL
    GIT_COMMIT = R_GIT_COMMIT
    DOCUMENTATION_URL = R_DOCUMENTATION_URL
    UPSTREAM_SOURCE = "src/unix/Rscript.c; src/library/utils/man/Rscript.Rd"
    SHELL = False
    RUN_IN_NODE_OUTPUT_DIR = True
    EXIT_SEMANTICS = "The Rscript process exit status is preserved; any non-zero exit fails the node."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"script": ("FILE", {"description": "R source file passed as Rscript's file argument"})},
            "optional": {
                "args": (
                    "STRING",
                    {"default": "", "description": "Shell-style argument string passed after the script path"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir]

    @staticmethod
    def _arguments(value: Any) -> list[str]:
        return shlex.split(str(value or ""), posix=True)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("script")):
            return "Input 'script' must be a non-empty path-like value"
        try:
            cls._arguments(inputs.get("args", ""))
        except ValueError as exc:
            return f"Input 'args' is not valid shell-style syntax: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return [
            "Rscript",
            "--vanilla",
            path_value(inputs.get("script")),
            *cls._arguments(inputs.get("args", "")),
        ]
