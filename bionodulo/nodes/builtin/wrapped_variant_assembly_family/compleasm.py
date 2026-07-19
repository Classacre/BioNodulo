"""Focused compleasm node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class CompleasmNode(CommandNode):
    """Assess genome assembly completeness with compleasm."""

    NODE_ID = "compleasm"
    DISPLAY_NAME = "compleasm"
    REQUIRED_CONDA_PACKAGES = ["compleasm"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assess genome assembly completeness with compleasm using cached BUSCO lineage data."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "compleasm",
        "compleasm genome completeness",
        "BUSCO lineage",
        "assembly completeness",
        "miniprot",
        "single-copy orthologs",
    ]
    RETURN_TYPES = ("TSV", "TSV", "GFF", "FASTA", "TXT")
    RETURN_NAMES = ("full_table_busco", "full_table", "miniprot", "translated_protein", "summary")
    REQUIRED_EXECUTABLES = ["compleasm"]
    DOCUMENTATION_URL = "https://github.com/huangnengCSU/compleasm"
    CITATION_DOIS = ["10.1101/2023.06.03.543588"]
    CITATION_URLS = [f"{DOI_URL}10.1101/2023.06.03.543588"]
    CITATION_TEXT = "Compleasm: a faster and more accurate reimplementation of the BUSCO lineage assessment."
    VERSION = "0.2.6"
    SHELL = True

    OUTPUT_FILES = {
        "full_table_busco": ("full_table_busco_format.tsv", "full_table_busco.tsv"),
        "full_table": ("full_table.tsv", "full_table.tsv"),
        "miniprot": ("miniprot_output.gff", "miniprot.gff"),
        "translated_protein": ("translated_protein.fasta", "translated_protein.fasta"),
        "summary": ("summary.txt", "summary.txt"),
    }
    OUTPUT_ORDER = ["full_table_busco", "full_table", "miniprot", "translated_protein", "summary"]

    @classmethod
    def _outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("outputs"))
        return outputs or ["full_table_busco"]

    @classmethod
    def _database_path(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("busco_database_path", inputs.get("busco_database", inputs.get("database_path", ""))) or "")

    @classmethod
    def _lineage(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("lineage_dataset", inputs.get("lineage", "")) or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        lineage = cls._lineage(inputs)
        galaxy_db = f"{out}/galaxy_db"
        galaxy_output = f"{out}/galaxy_output"
        lineage_output = f"{galaxy_output}/{lineage}"
        cmd = [
            "mkdir",
            "-p",
            galaxy_db,
            "&&",
            "ln",
            "-s",
            f"{cls._database_path(inputs)}/lineages/{lineage}",
            f"{galaxy_db}/{lineage}",
            "&&",
            "touch",
            f"{galaxy_db}/{lineage}.done",
            "&&",
            "compleasm",
            "run",
            "-a",
            str(inputs.get("input", "")),
            "-o",
            galaxy_output,
            "--mode",
            str(inputs.get("mode", "busco")),
            "-L",
            galaxy_db,
            "-l",
            lineage,
            "-t",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
        ]
        if inputs.get("specified_contigs"):
            cmd.extend(["--specified_contigs", str(inputs.get("specified_contigs"))])
        selected = set(cls._outputs(inputs))
        for name in cls.OUTPUT_ORDER:
            if name not in selected:
                continue
            source, target = cls.OUTPUT_FILES[name]
            source_path = f"{galaxy_output}/{source}" if name == "summary" else f"{lineage_output}/{source}"
            cmd.extend(["&&", "cp", source_path, f"{out}/{target}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(cls._outputs(inputs))
        return [out / cls.OUTPUT_FILES[name][1] for name in cls.OUTPUT_ORDER if name in selected]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input genome assembly FASTA"}),
                "busco_database_path": ("DIRECTORY", {"description": "Cached BUSCO database root containing lineage directories"}),
                "lineage_dataset": ("STRING", {"description": "BUSCO lineage dataset name"}),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {"default": "busco", "options": ["busco", "lite"], "description": "Use BUSCO/hmmsearch mode or lite mode"},
                ),
                "specified_contigs": (
                    "STRING",
                    {"default": "", "description": "Optional space-separated contig names to evaluate"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": ["full_table_busco"],
                        "options": cls.OUTPUT_ORDER,
                        "description": "Compleasm outputs to copy from Galaxy work directory",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input genome FASTA is required"
        if not cls._database_path(inputs).strip():
            return "BUSCO database path is required"
        if not cls._lineage(inputs).strip():
            return "lineage_dataset is required"
        for output in cls._outputs(inputs):
            if output not in cls.OUTPUT_FILES:
                return f"unknown compleasm output: {output}"
        specified_contigs = str(inputs.get("specified_contigs", "") or "")
        if specified_contigs and not re.fullmatch(r"[0-9A-Za-z_ ]+", specified_contigs):
            return "specified_contigs may contain only letters, numbers, underscores, and spaces"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(CompleasmNode)

__all__ = ['CompleasmNode']
