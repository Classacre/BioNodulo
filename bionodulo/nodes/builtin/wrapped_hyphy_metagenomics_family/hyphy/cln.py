"""Focused owner for ``hyphy_cln``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyCLNNode(ToolsIUCCommandContract):
    """Clean and normalize codon alignments with HyPhy CLN."""

    NODE_ID = "hyphy_cln"
    DISPLAY_NAME = "HyPhy-CLN"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Clean and normalize codon alignments with HyPhy CLN."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "CLN",
        "CleanStopCodons",
        "CleanStopCodons duplicate sequences",
        "clean alignment",
        "normalize alignment",
        "duplicate sequences",
        "gap-only sites",
        "stop codons",
        "sequence identifiers",
        "phylogenetics",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("cleaned_alignment",)
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/CleanStopCodons.bf"
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{HYPHY_CITATION_DOI}"]
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = ["fasta", "fasta.gz", "nex", "nexus", "phylip", "mega"]
    FILTERING_METHODS = ["No/No", "No/Yes", "Yes/No", "Yes/Yes", "Disallow stops"]

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta")).strip().lstrip(".") or "fasta"
        return f"input.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands = [_shell_join(["ln", "-s", str(inputs.get("input_file", "")), input_name])]
        cmd = [
            "hyphy",
            f"CPU={inputs.get('threads', 4)}",
            "cln",
            "--alignment",
            input_name,
            "--code",
            str(inputs.get("gencodeid", "Universal") or "Universal"),
            "--filtering-method",
            str(inputs.get("filtering_method", "No/No") or "No/No"),
            "--output",
            f"{out}/cleaned_alignment.fasta",
        ]
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "cleaned_alignment.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-CLN alignment input is required"
        input_ext = str(inputs.get("input_ext", "fasta") or "fasta").strip().lstrip(".")
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f"Unsupported HyPhy-CLN input extension: {input_ext}"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        filtering_method = str(inputs.get("filtering_method", "No/No") or "No/No")
        if filtering_method not in cls.FILTERING_METHODS:
            return f"Unsupported HyPhy-CLN filtering method: {filtering_method}"
        try:
            threads = int(inputs.get("threads", 4))
        except (TypeError, ValueError):
            return "HyPhy-CLN threads must be a positive integer"
        if threads < 1:
            return "HyPhy-CLN threads must be a positive integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {
                        "description": (
                            "In-frame codon alignment in FASTA, compressed FASTA, NEXUS, PHYLIP, or MEGA format"
                        )
                    },
                ),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {"default": "fasta", "options": cls.INPUT_EXTENSIONS, "advanced": True},
                ),
                "gencodeid": (
                    "STRING",
                    {
                        "default": "Universal",
                        "options": cls.GENETIC_CODES,
                        "description": "HyPhy genetic code for codon interpretation",
                    },
                ),
                "filtering_method": (
                    "STRING",
                    {
                        "default": "No/No",
                        "options": cls.FILTERING_METHODS,
                        "description": "How to filter duplicate sequences, gap-only sites, and stop codons",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }
