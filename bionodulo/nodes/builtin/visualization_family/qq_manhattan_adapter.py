"""QQ/Manhattan plotting node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    QQMAN_GIT_COMMIT,
    QQMAN_GIT_URL,
    ASSET_SHA256,
    asset_path,
    pin_contract,
)

class QQManhattanNode(CommandNode):
    """Create a GWAS Manhattan plot with qqman."""

    LEGACY_NODE_ID = "qq_manhattan"
    DISPLAY_NAME = "Manhattan Plots"
    REQUIRED_CONDA_PACKAGES = ["r-qqman", "r-optparse"]
    CATEGORY = "visualization"
    DESCRIPTION = "Create a GWAS Manhattan plot PDF from a tabular association-results file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "qqman",
        "qq_manhattan",
        "Manhattan Plots",
        "GWAS Manhattan plot",
        "association results",
        "genome-wide association study",
        "SNP p-values",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("manhattan",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://cran.r-project.org/package=qqman"
    CITATION_DOIS = QQMAN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in QQMAN_CITATION_DOIS]
    CITATION_TEXT = QQMAN_CITATION_TEXT
    VERSION = "0.1.0"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    COLUMN_DEFAULTS = {
        "pval": "P",
        "chr": "CHR",
        "bp": "BP",
        "snp": "SNP",
        "name": "Manhattan Plot",
    }

    @classmethod
    def _param(cls, inputs: dict[str, Any], name: str) -> str:
        return str(inputs.get(name, cls.COLUMN_DEFAULTS[name]) or cls.COLUMN_DEFAULTS[name])

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/manhattan.pdf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "Rscript",
            str(inputs.get("script_path") or asset_path("manhattan.R")),
            "--file",
            str(inputs.get("data", "")),
            "--pval",
            cls._param(inputs, "pval"),
            "--chr",
            cls._param(inputs, "chr"),
            "--bp",
            cls._param(inputs, "bp"),
            "--snp",
            cls._param(inputs, "snp"),
            "--name",
            cls._param(inputs, "name"),
        ]
        return f"{_shell_join(cmd)} && {_shell_join(['mv', 'manhattan.pdf', cls._output_path(inputs)])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "manhattan.pdf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, label in (
            ("pval", "pval column name"),
            ("chr", "chr column name"),
            ("bp", "bp column name"),
            ("snp", "snp column name"),
            ("name", "plot title"),
        ):
            if name in inputs and not str(inputs.get(name, "")).strip():
                return f"{label} is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("TSV", {"description": "Tabular GWAS association results with SNP, chromosome, position, and p-value columns"}),
            },
            "optional": {
                "pval": (
                    "STRING",
                    {"default": "P", "description": "P-value column name in the input file"},
                ),
                "chr": (
                    "STRING",
                    {"default": "CHR", "description": "Chromosome column name in the input file"},
                ),
                "bp": (
                    "STRING",
                    {"default": "BP", "description": "Base-pair coordinate column name in the input file"},
                ),
                "snp": (
                    "STRING",
                    {"default": "SNP", "description": "SNP identifier column name in the input file"},
                ),
                "name": (
                    "STRING",
                    {"default": "Manhattan Plot", "description": "Plot title"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional override; blank uses the pinned bundled Galaxy qqman script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(
    [QQManhattanNode],
    runtime_version="0.1.4",
    runtime_git_url=QQMAN_GIT_URL,
    runtime_git_commit=QQMAN_GIT_COMMIT,
    package_constraint="r-qqman==0.1.4; r-optparse==1.6.4",
)
QQManhattanNode.WRAPPER_ASSET_SHA256 = ASSET_SHA256["manhattan.R"]
