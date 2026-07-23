"""Focused VSEARCH shuffling node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

from .adapter import VSearchNodeBase


class VSearchShufflingNode(VSearchNodeBase):
    """Shuffle FASTA sequence order with VSEARCH."""

    NODE_ID = "vsearch_shuffling"
    DISPLAY_NAME = "VSEARCH Shuffling"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Shuffle FASTA sequence order pseudo-randomly with VSEARCH, using an explicit random seed and optional top-N limit."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "shuffling",
        "shuffle",
        "random sequence order",
        "randseed",
        "topn",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("shuffled_sequences",)
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        cmd.extend([
            "--output",
            f"{_out(inputs)}/shuffled.fasta",
            "--randseed",
            str(inputs.get("randseed", 0)),
            "--shuffle",
            str(inputs.get("infile", inputs.get("sequences", ""))),
        ])
        _add_if_value(cmd, "--topn", inputs.get("topn"))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "shuffled.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("infile", inputs.get("sequences", ""))).strip():
            return "infile is required"
        try:
            int(inputs.get("randseed", 0))
        except (TypeError, ValueError):
            return "randseed must be an integer"
        topn = inputs.get("topn")
        if topn is not None and str(topn) != "":
            try:
                if int(topn) < 1:
                    return "topn must be at least 1"
            except (TypeError, ValueError):
                return "topn must be an integer"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"infile": ("FASTA", {"description": "FASTA sequences to shuffle"})},
            "optional": {
                "randseed": ("INT", {"default": 0, "min": 0, "description": "Random seed; zero uses a random data source"}),
                "topn": ("INT", {"default": "", "min": 1, "description": "Output only the first n sequences after shuffling"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchShufflingNode)
