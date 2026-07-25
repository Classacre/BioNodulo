"""Focused VSEARCH sorting node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

from .adapter import VSearchNodeBase


class VSearchSortingNode(VSearchNodeBase):
    """Sort FASTA sequences by length or abundance with VSEARCH."""

    NODE_ID = "vsearch_sorting"
    DISPLAY_NAME = "VSEARCH Sorting"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Sort FASTA sequences by length or abundance with VSEARCH, with optional abundance filters, relabeling, size annotations, and top-N output."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "sorting",
        "sortbylength",
        "sortbysize",
        "sort by abundance",
        "sizeout",
        "relabel",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("sorted_sequences",)
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        sorting_mode = str(inputs.get("sorting_mode", inputs.get("sorting_mode_select", "sortbylength")))
        if sorting_mode == "sortbylength":
            cmd.extend(["--sortbylength", str(inputs.get("infile", inputs.get("sequences", "")))])
        else:
            cmd.extend(["--sortbysize", str(inputs.get("infile", inputs.get("sequences", "")))])
            _add_if_value(cmd, "--minsize", inputs.get("minsize"))
            _add_if_value(cmd, "--maxsize", inputs.get("maxsize"))
        cmd.extend(["--output", f"{_out(inputs)}/sorted.fasta"])
        _add_if_value(cmd, "--relabel", inputs.get("relabel"))
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        _add_if_value(cmd, "--topn", inputs.get("topn"))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sorted.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("infile", inputs.get("sequences", ""))).strip():
            return "infile is required"
        sorting_mode = str(inputs.get("sorting_mode", inputs.get("sorting_mode_select", "sortbylength")))
        if sorting_mode not in {"sortbylength", "sortbyabundance"}:
            return "sorting_mode must be one of: sortbylength, sortbyabundance"
        numeric_values: dict[str, int] = {}
        for name in ("minsize", "maxsize", "topn"):
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be at least 1"
            numeric_values[name] = value
        if (
            "minsize" in numeric_values
            and "maxsize" in numeric_values
            and numeric_values["minsize"] > numeric_values["maxsize"]
        ):
            return "minsize must be <= maxsize"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "FASTA sequences to sort"}),
            },
            "optional": {
                "sorting_mode": ("STRING", {"default": "sortbylength", "options": ["sortbylength", "sortbyabundance"]}),
                "minsize": ("INT", {"default": "", "min": 1, "description": "Minimum abundance for sort-by-size mode"}),
                "maxsize": ("INT", {"default": "", "min": 1, "description": "Maximum abundance for sort-by-size mode"}),
                "relabel": ("STRING", {"default": "", "description": "Prefix used to relabel sequences after sorting"}),
                "sizeout": ("BOOLEAN", {"default": False, "description": "Add abundance annotations to output"}),
                "topn": ("INT", {"default": "", "min": 1, "description": "Output only the top n sorted sequences"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchSortingNode)
