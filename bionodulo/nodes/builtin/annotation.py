"""Genome annotation nodes for BioNodulo.

Provides nodes for prokaryotic genome annotation with Prokka and Bakta,
and functional annotation with eggNOG-mapper.
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class ProkkaNode(CommandNode):
    """Prokaryotic genome annotation with Prokka."""
    NODE_ID = "prokka"
    DISPLAY_NAME = "Prokka"
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid prokaryotic genome annotation"
    SEARCH_ALIASES = ["prokka", "annotate", "bacteria", "archaea", "genome"]
    RETURN_TYPES = ("GFF", "GBK", "FAA")
    RETURN_NAMES = ("gff", "genbank", "proteins")
    REQUIRED_EXECUTABLES = ["prokka"]
    DOCUMENTATION_URL = "https://github.com/tseemann/prokka"
    VERSION = "1.14.6"
    COMMAND = [
        "prokka",
        "--outdir", "{output}",
        "--prefix", "{inputs.prefix}",
        "--cpus", "{inputs.threads}",
        "--kingdom", "{inputs.kingdom}",
        "{inputs.assembly}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Genome assembly FASTA"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "genome"}),
            },
            "optional": {
                "kingdom": ("STRING", {"default": "Bacteria"}),
                "genus": ("STRING", {"default": ""}),
                "species": ("STRING", {"default": ""}),
                "strain": ("STRING", {"default": ""}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        prefix = inputs.get("prefix", "genome")
        od = Path(output_dir) / cls.NODE_ID
        return [
            od / f"{prefix}.gff",
            od / f"{prefix}.gbk",
            od / f"{prefix}.faa",
        ]


class BaktaNode(CommandNode):
    """Prokaryotic annotation with Bakta (Prokka successor)."""
    NODE_ID = "bakta"
    DISPLAY_NAME = "Bakta"
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid & standardized annotation of bacterial genomes"
    SEARCH_ALIASES = ["bakta", "annotate", "bacteria", "annotation"]
    RETURN_TYPES = ("GFF", "FAA")
    RETURN_NAMES = ("gff", "proteins")
    REQUIRED_EXECUTABLES = ["bakta"]
    DOCUMENTATION_URL = "https://github.com/oschwengers/bakta"
    VERSION = "1.9.3"
    COMMAND = [
        "bakta",
        "--output", "{output}",
        "--prefix", "{inputs.prefix}",
        "--threads", "{inputs.threads}",
        "{inputs.assembly}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Genome assembly FASTA"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "genome"}),
            },
            "optional": {
                "db": ("DIRECTORY", {"description": "Bakta DB path"}),
                "translation_table": ("INT", {"default": 11}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
        prefix = inputs.get("prefix", "genome")
        od = Path(output_dir) / cls.NODE_ID
        return [
            od / f"{prefix}.gff3",
            od / f"{prefix}.faa",
        ]


class EggNOGMapperNode(CommandNode):
    """Functional annotation with eggNOG-mapper."""
    NODE_ID = "eggnog_mapper"
    DISPLAY_NAME = "eggNOG-mapper"
    CATEGORY = "annotation"
    DESCRIPTION = "Fast genome-wide functional annotation via orthology"
    SEARCH_ALIASES = ["eggnog", "emapper", "functional", "cog", "go"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("annotations",)
    REQUIRED_EXECUTABLES = ["emapper.py"]
    DOCUMENTATION_URL = "https://github.com/eggnogdb/eggnog-mapper"
    VERSION = "2.1.12"
    COMMAND = [
        "emapper.py",
        "-i", "{inputs.proteins}",
        "--output", "{inputs.prefix}",
        "--output_dir", "{output}",
        "-m", "{inputs.mode}",
        "--cpu", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "proteins": ("FASTA", {"description": "Protein FASTA file (.faa)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "annotations"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "diamond", "description": "Search mode: diamond, mmseqs, or hmmer"}),
                "data_dir": ("DIRECTORY", {"description": "eggNOG data directory"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
