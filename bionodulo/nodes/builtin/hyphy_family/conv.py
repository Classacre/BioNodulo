"""Focused owner for ``hyphy_conv``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract
from .absrel import HyPhyABSRELNode

class HyPhyCONVNode(ToolsIUCCommandContract):
    """Translate in-frame codon alignments to protein alignments with HyPhy CONV."""

    NODE_ID = "hyphy_conv"
    DISPLAY_NAME = "HyPhy-Conv"
    REQUIRED_CONDA_PACKAGES = ["hyphy"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Translate an in-frame codon alignment to proteins with HyPhy CONV."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HyPhy",
        "CONV",
        "CodonToProtein",
        "codon to protein",
        "translate codon alignment",
        "amino acid translation",
        "CodonToProtein amino acid translation",
        "protein alignment",
        "keep deletions",
        "skip deletions",
        "phylogenetics",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("proteins",)
    REQUIRED_EXECUTABLES = ["hyphy"]
    DOCUMENTATION_URL = "https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/CodonToProtein.bf"
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{HYPHY_CITATION_DOI}"]
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = "2.5.96"
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    DELETION_MODES = ["Keep Deletions", "Skip Deletions"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        deletions = str(inputs.get("deletions", "Skip Deletions") or "Skip Deletions")
        commands = [_shell_join(["cp", str(inputs.get("input_file", "")), "conv_input.fa"])]
        cmd = [
            "hyphy",
            "conv",
            str(inputs.get("gencodeid", "Universal") or "Universal"),
            deletions,
            "conv_input.fa",
            f"{out}/proteins.nex",
        ]
        commands.append("ENV='TOLERATE_NUMERICAL_ERRORS=1;' " + _shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "proteins.nex"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "HyPhy-Conv codon alignment input is required"
        gencodeid = str(inputs.get("gencodeid", "Universal") or "Universal")
        if gencodeid not in cls.GENETIC_CODES:
            return f"Unsupported HyPhy genetic code: {gencodeid}"
        deletions = str(inputs.get("deletions", "Skip Deletions") or "Skip Deletions")
        if deletions not in cls.DELETION_MODES:
            return f"Unsupported HyPhy-Conv deletion handling: {deletions}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {"description": "In-frame codon alignment in FASTA format"},
                ),
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
                "deletions": (
                    "STRING",
                    {
                        "default": "Skip Deletions",
                        "options": cls.DELETION_MODES,
                        "description": "Whether translated deletion sites are retained in the protein alignment",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
