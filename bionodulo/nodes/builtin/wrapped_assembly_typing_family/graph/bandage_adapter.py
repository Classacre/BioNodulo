"""Shared Bandage contracts for focused graph utility owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_assembly_typing_family.contracts import (
    TOOLS_IUC_GIT_COMMIT,
    ToolsIUCCommandContract,
)


class BandageContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/bandage"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    PACKAGE_CONSTRAINT = "bandage_ng==2022.09"
    GALAXY_WRAPPER_VERSIONS = {
        "bandage_info": "2022.09+galaxy2",
        "bandage_image": "2022.09+galaxy4",
    }


class _BandageInfoContract(BandageContractNode):
    """Summarize de novo assembly graph statistics with Bandage info."""

    LEGACY_NODE_ID = "bandage_info"
    DISPLAY_NAME = "Bandage Info"
    REQUIRED_CONDA_PACKAGES = ["bandage_ng"]
    CATEGORY = "assembly"
    DESCRIPTION = "Determine node, edge, length, connectivity, and N50 statistics for de novo assembly graphs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bandage",
        "bandage info",
        "assembly graph",
        "GFA statistics",
        "FASTG statistics",
        "de novo assembly graph",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["Bandage"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Bandage/wiki/Command-line-options#info"
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BANDAGE_CITATION_DOI}"]
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = "2022.09"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(["Bandage", "info", f"{out}/input.gfa"])
        if inputs.get("tsv"):
            cmd.append("--tsv")
        cmd.extend(["|", "sed", r"s/:\s\+/:\t/g", ">", f"{out}/out.tab"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.tab"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "GFA",
                    {
                        "description": (
                            "Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format"
                        ),
                    },
                ),
            },
            "optional": {
                "tsv": (
                    "BOOLEAN",
                    {"default": False, "description": "Output information as a single tab-delimited line"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BandageImageContract(BandageContractNode):
    """Render de novo assembly graph images with Bandage image."""

    LEGACY_NODE_ID = "bandage_image"
    DISPLAY_NAME = "Bandage Image"
    REQUIRED_CONDA_PACKAGES = ["bandage_ng"]
    CATEGORY = "visualization"
    DESCRIPTION = "Visualize de novo assembly graphs as JPG, PNG, or SVG images using Bandage."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bandage",
        "bandage image",
        "assembly graph image",
        "GFA visualization",
        "FASTG visualization",
        "de novo assembly graph",
    ]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["Bandage"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Bandage/wiki/Command-line-options#image"
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BANDAGE_CITATION_DOI}"]
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = "2022.09"
    SHELL = True

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("output_format", "jpg") or "jpg").lower()
        return output_format if output_format in {"jpg", "png", "svg"} else "jpg"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = cls._output_format(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(["Bandage", "image", f"{out}/input.gfa", f"{out}/out.{output_format}"])
        _add_if_value(cmd, "--height", inputs.get("height"))
        _add_if_value(cmd, "--width", inputs.get("width"))
        _add_if_value(cmd, "--fontsize", inputs.get("fontsize"))
        _add_if_value(cmd, "--nodewidth", inputs.get("nodewidth"))
        if inputs.get("names"):
            cmd.append("--names")
        if inputs.get("lengths"):
            cmd.append("--lengths")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"out.{cls._output_format(inputs)}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "GFA",
                    {
                        "description": (
                            "Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format"
                        ),
                    },
                ),
            },
            "optional": {
                "height": ("INT", {"default": 1000, "min": 1, "description": "Image height in pixels"}),
                "width": ("INT", {"default": "", "min": 1, "description": "Image width in pixels"}),
                "names": ("BOOLEAN", {"default": False, "description": "Show node name labels"}),
                "lengths": ("BOOLEAN", {"default": False, "description": "Show node length labels"}),
                "fontsize": ("INT", {"default": "", "min": 5, "description": "Node label font size"}),
                "nodewidth": ("FLOAT", {"default": "", "min": 5, "description": "Node width for graph image"}),
                "output_format": (
                    "STRING",
                    {"default": "jpg", "options": ["jpg", "png", "svg"], "description": "Output image format"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
