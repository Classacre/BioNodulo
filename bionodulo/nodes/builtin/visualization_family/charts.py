"""Focused charts node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class ChartsNode(CommandNode):
    """Generate tabular chart data with Galaxy Charts R modules."""

    NODE_ID = "charts"
    DISPLAY_NAME = "Charts"
    REQUIRED_CONDA_PACKAGES = ["r-getopt", "r-matrix"]
    CATEGORY = "visualization"
    DESCRIPTION = "Generate tabular chart data from tabular inputs with Galaxy Charts R modules."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Charts",
        "charts",
        "Chart Utilities",
        "boxplot",
        "heatmap",
        "histogram",
        "histogramdiscrete",
        "R chart modules",
        "tabular visualization",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = CHARTS_CITATION_URL
    CITATION_URLS = [CHARTS_CITATION_URL]
    CITATION_TEXT = CHARTS_CITATION_TEXT
    VERSION = "1.0.1"
    SHELL = True

    MODULES = ["boxplot", "heatmap", "histogram", "histogramdiscrete"]

    @classmethod
    def _module(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("module", "boxplot") or "boxplot")

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("charts_script", "charts.r") or "charts.r")

    @classmethod
    def _workdir(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("charts_workdir", "./") or "./")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "Rscript",
            cls._script(inputs),
            "-w",
            cls._workdir(inputs),
            "-m",
            cls._module(inputs),
            "-i",
            str(inputs.get("input", "")),
            "-c",
            str(inputs.get("columns", "")),
            "-s",
            str(inputs.get("settings", "")),
            "-o",
            cls._output_path(inputs),
        ]
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if cls._module(inputs) not in cls.MODULES:
            return f"module must be one of: {', '.join(cls.MODULES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Input tabular dataset"}),
            },
            "optional": {
                "module": ("STRING", {"default": "boxplot", "options": cls.MODULES}),
                "columns": (
                    "STRING",
                    {"default": "", "description": "Column mapping string, such as key1: 2, key2: 3"},
                ),
                "settings": (
                    "STRING",
                    {"default": "", "description": "Options string, such as key1: value, key2: value"},
                ),
                "charts_script": ("FILE", {"default": "charts.r", "advanced": True}),
                "charts_workdir": ("STRING", {"default": "./", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(ChartsNode)

__all__ = ['ChartsNode']
