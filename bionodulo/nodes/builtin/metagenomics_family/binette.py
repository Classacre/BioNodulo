"""Focused binette node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class BinetteNode(CommandNode):
    """Refine metagenomic binning outputs into high-quality MAGs with Binette."""

    NODE_ID = "binette"
    DISPLAY_NAME = "Binette"
    REQUIRED_CONDA_PACKAGES = ["binette"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Refine multiple contig-to-bin tables into high-quality metagenome-assembled genomes with quality reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Binette",
        "Binette binning refinement",
        "binning refinement",
        "metagenomic binning",
        "MAG refinement",
        "CheckM2 database",
        "contig-to-bin tables",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "TSV")
    RETURN_NAMES = ("bins", "quality_reports", "final_quality_report")
    REQUIRED_EXECUTABLES = ["binette"]
    DOCUMENTATION_URL = "https://github.com/genotoul-bioinfo/Binette"
    CITATION_DOIS = ["10.21105/joss.06782"]
    CITATION_URLS = [f"{DOI_URL}10.21105/joss.06782"]
    CITATION_TEXT = "Binette: a fast and accurate binning refinement tool to construct high-quality MAGs."
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _checkm2_db(cls, inputs: dict[str, Any], out: str) -> str:
        if str(inputs.get("database_type", "cached")) == "his":
            return f"{out}/input_database.dmnd"
        return str(inputs.get("checkm2_db_path", inputs.get("datamanager", inputs.get("database_path", ""))))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input"
        output_dir = f"{out}/output"
        cmd = ["mkdir", "-p", input_dir, output_dir]
        for index, table in enumerate(_as_list(inputs.get("contig2bin_tables", inputs.get("bins")))):
            cmd.extend(["&&", "ln", "-s", table, f"{input_dir}/bin_table_{index}.tsv"])
        cmd.extend(["&&", "ln", "-s", str(inputs.get("contigs", "")), f"{out}/input_contigs.fasta"])
        if str(inputs.get("database_type", "cached")) == "his":
            cmd.extend(["&&", "ln", "-s", str(inputs.get("checkm2_db", "")), f"{out}/input_database.dmnd"])
        if inputs.get("proteins"):
            cmd.extend(["&&", "ln", "-s", str(inputs.get("proteins")), f"{out}/input_proteins.fasta"])
        cmd.extend(
            [
                "&&",
                "binette",
                "-b",
                f"{input_dir}/*.tsv",
                "-c",
                f"{out}/input_contigs.fasta",
            ]
        )
        if inputs.get("proteins"):
            cmd.extend(["-p", f"{out}/input_proteins.fasta"])
        cmd.extend(
            [
                "--min_completeness",
                str(inputs.get("min_completeness", 40)),
                "-t",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
                "-o",
                f"{output_dir}/",
                "-w",
                str(inputs.get("contamination_weight", 2)),
                "--checkm2_db",
                cls._checkm2_db(inputs, out),
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        bins = out / "final_bins"
        quality_reports = out / "input_bins_quality_reports"
        bins.mkdir(parents=True, exist_ok=True)
        quality_reports.mkdir(parents=True, exist_ok=True)
        return [bins, quality_reports, out / "final_bins_quality_reports.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contig2bin_tables": (
                    "TSV",
                    {
                        "multiple": True,
                        "min_items": 2,
                        "description": "At least two contig-to-bin tables from independent binning tools",
                    },
                ),
                "contigs": ("FASTA", {"description": "Assembly contigs used to generate the binning tables"}),
            },
            "optional": {
                "proteins": (
                    "FASTA",
                    {"default": "", "description": "Optional Prodigal-format predicted protein FASTA"},
                ),
                "min_completeness": (
                    "INT",
                    {"default": 40, "min": 0, "max": 100, "description": "Minimum completeness threshold for final bins"},
                ),
                "contamination_weight": (
                    "INT",
                    {"default": 2, "description": "Weight applied to contamination in the bin selection score"},
                ),
                "database_type": (
                    "STRING",
                    {
                        "default": "cached",
                        "options": ["cached", "his"],
                        "description": "Use a cached CheckM2 DIAMOND database or a database from workflow history",
                    },
                ),
                "checkm2_db": (
                    "FILE",
                    {"default": "", "description": "History CheckM2 DIAMOND database for database_type=his"},
                ),
                "checkm2_db_path": (
                    "FILE",
                    {"default": "", "description": "Cached CheckM2 DIAMOND database path for database_type=cached"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        tables = _as_list(inputs.get("contig2bin_tables", inputs.get("bins")))
        if len(tables) < 2:
            return "at least two contig-to-bin tables are required"
        if not str(inputs.get("contigs", "")).strip():
            return "contigs FASTA is required"
        if str(inputs.get("database_type", "cached")) == "his":
            if not str(inputs.get("checkm2_db", "")).strip():
                return "CheckM2 DIAMOND database is required for history database mode"
        elif not str(cls._checkm2_db(inputs, _out(inputs))).strip():
            return "cached CheckM2 DIAMOND database path is required"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(BinetteNode)

__all__ = ['BinetteNode']
