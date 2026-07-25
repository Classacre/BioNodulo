"""Focused VSEARCH masking node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

from .adapter import VSearchNodeBase


class VSearchMaskingNode(VSearchNodeBase):
    """Mask FASTA sequences with VSEARCH."""

    NODE_ID = "vsearch_masking"
    DISPLAY_NAME = "VSEARCH Masking"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Mask FASTA sequences with VSEARCH maskfasta using dust, soft, or no qmask modes and optional hard masking."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "masking",
        "maskfasta",
        "qmask",
        "hardmask",
        "soft masking",
        "dust masking",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("masked_sequences",)
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        cmd.extend(["--qmask", str(inputs.get("qmask", "dust") or "dust")])
        if inputs.get("hardmask"):
            cmd.append("--hardmask")
        cmd.extend([
            "--maskfasta",
            str(inputs.get("infile", inputs.get("sequences", ""))),
            "--output",
            f"{_out(inputs)}/masked.fasta",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "masked.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("infile", inputs.get("sequences", ""))).strip():
            return "infile is required"
        if str(inputs.get("qmask", "dust")) not in {"none", "dust", "soft"}:
            return "qmask must be one of: none, dust, soft"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"infile": ("FASTA", {"description": "FASTA sequences to mask"})},
            "optional": {
                "qmask": ("STRING", {"default": "dust", "options": ["none", "dust", "soft"], "description": "Masking mode"}),
                "hardmask": ("BOOLEAN", {"default": False, "description": "Replace masked bases with N instead of lowercase"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchMaskingNode)
