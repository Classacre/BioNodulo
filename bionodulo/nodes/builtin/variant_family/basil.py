"""Focused basil node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class BasilNode(CommandNode):
    """Detect structural-variant breakpoints with BASIL."""

    NODE_ID = "basil"
    DISPLAY_NAME = "basil"
    REQUIRED_CONDA_PACKAGES = ["anise_basil"]
    CATEGORY = "variant"
    DESCRIPTION = "Detect structural-variant breakpoints, including large insertions, from BAM reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "basil",
        "BASIL",
        "anise_basil",
        "breakpoint detection",
        "structural variants",
        "large insertions",
        "insertion breakpoints",
        "one-end-anchor reads",
        "OEA",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["basil"]
    DOCUMENTATION_URL = f"{DOI_URL}{BASIL_CITATION_DOI}"
    CITATION_DOIS = [BASIL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BASIL_CITATION_DOI}"]
    CITATION_TEXT = BASIL_CITATION_TEXT
    VERSION = "1.2.0+galaxy2"
    SHELL = True

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", inputs.get("reference_source", "history")) or "history")

    @classmethod
    def _support_threshold(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("min_oea_each_side", 2)
        if value is None or str(value) == "":
            return 2
        return int(value)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.vcf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "ln",
            "-f",
            "-s",
            str(inputs.get("ref", "")),
            "ref.fa",
            "&&",
            "ln",
            "-s",
            str(inputs.get("bam", "")),
            "in.bam",
            "&&",
            "basil",
            "--input-reference",
            "ref.fa",
            "--input-mapping",
            "in.bam",
            "--out-vcf",
            cls._output_path(inputs),
            "--oea-min-support-each-side",
            str(cls._support_threshold(inputs)),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.vcf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("ref", "")).strip():
            return "ref is required"
        if not str(inputs.get("bam", "")).strip():
            return "bam is required"
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        try:
            min_oea_each_side = cls._support_threshold(inputs)
        except (TypeError, ValueError):
            return "min_oea_each_side must be an integer"
        if min_oea_each_side < 1:
            return "min_oea_each_side must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref": ("FASTA", {"description": "Reference genome FASTA from history or a built-in cached reference"}),
                "bam": ("BAM", {"description": "SAM/BAM alignments to scan for breakpoints"}),
            },
            "optional": {
                "reference_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a reference FASTA from history or a built-in cached reference",
                    },
                ),
                "min_oea_each_side": (
                    "INT",
                    {
                        "default": 2,
                        "min": 1,
                        "description": "Minimum OEA supporting reads on each side of an insertion breakpoint",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(BasilNode)

__all__ = ['BasilNode']
