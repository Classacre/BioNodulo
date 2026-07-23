"""Focused owner for ``hyphy_strike_ambigs``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyStrikeAmbigsNode(ToolsIUCCommandContract):
    """Replace ambiguous codons in a FASTA alignment with gap codons."""

    NODE_ID = "hyphy_strike_ambigs"
    DISPLAY_NAME = "Replace ambiguous codons"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Replace ambiguous codons in an in-frame alignment using HyPhy."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "Strike-Ambigs",
        "Replace ambiguous codons",
        "ambiguous codons",
        "codon alignment",
        "FASTA",
        "gap codons",
        "sequencing ambiguity",
        "phylogenetics",
    ]
    RETURN_TYPES = ("FASTA", "TEXT")
    RETURN_NAMES = ("output", "strike_ambigs_md_report")
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles"
    CITATION_DOIS = HYPHY_STRIKE_AMBIGS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HYPHY_STRIKE_AMBIGS_CITATION_DOIS]
    CITATION_TEXT = HYPHY_STRIKE_AMBIGS_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES

    @classmethod
    def _batch_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("batch_file", "${HYPHY_STRIKE_AMBIGS_BF:-strike-ambigs.bf}") or "strike-ambigs.bf")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        batch_file = cls._batch_file(inputs)
        batch_file_arg = batch_file if batch_file.startswith("${") else shlex.quote(batch_file)
        cmd = [
            "--alignment",
            str(inputs.get("alignment", "")),
            "--code",
            str(inputs.get("gencodeid", "Universal") or "Universal"),
            "--output",
            f"{out}/output.fasta",
            ">",
            f"{out}/strike_ambigs_stdout.md",
        ]
        return f"hyphy {batch_file_arg} {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta", out / "strike_ambigs_stdout.md"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignment", "")).strip():
            return "HyPhy Strike-Ambigs alignment input is required"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("FASTA", {"description": "In-frame codon alignment in FASTA format"}),
            },
            "optional": {
                "gencodeid": (
                    "STRING",
                    {
                        "default": "Universal",
                        "options": cls.GENETIC_CODES,
                        "description": "HyPhy genetic code for codon interpretation",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
