"""Pinned QUAST 5.3.0 assembly-quality contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._paths import normalize_paths


class QuastNode(CommandNode):
    """Assess one or more assembly FASTA files with QUAST."""

    NODE_ID = "quast"
    DISPLAY_NAME = "QUAST"
    CATEGORY = "assembly"
    DESCRIPTION = "Assess assembly quality and produce the QUAST HTML report"
    SEARCH_ALIASES = ["quast", "quality", "assembly qc", "assess", "report"]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["quast"]
    REQUIRED_CONDA_PACKAGES = ["quast"]
    DOCUMENTATION_URL = "https://github.com/ablab/quast/tree/quast_5.3.0"
    VERSION = "5.3.0"
    GIT_URL = "https://github.com/ablab/quast.git"
    GIT_COMMIT = "c3eb988a2fa8a815e1b0bfff55a58cb8d6ff0152"
    CITATION_DOIS = ["10.1093/bioinformatics/btt086"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btt086"]
    CITATION_TEXT = "QUAST: quality assessment tool for genome assemblies."
    BIOCONDA_VERSION = "5.3.0"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/quast/files?version=5.3.0"
    UPSTREAM_README = "README.md"
    UPSTREAM_SOURCE = "quast.py"
    UPSTREAM_OPTIONS_SOURCE = "quast_libs/options_parser.py"
    OUTPUT_DIRECTORY = "report_dir.out"
    OUTPUT_FILENAME = "report.html"

    @classmethod
    def _optional_path(cls, inputs: dict[str, Any], name: str) -> str | None:
        value = inputs.get(name)
        if value is None or value == "":
            return None
        paths = normalize_paths(value, name)
        if len(paths) != 1:
            raise ValueError(f"{name} must contain exactly one path")
        return paths[0]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": (
                    "ASSEMBLY",
                    {"description": "One assembly FASTA or an ordered assembly collection"},
                ),
            },
            "optional": {
                "threads": (
                    "INT",
                    {
                        "min": 1,
                        "description": ("Maximum threads; omitted uses QUAST's 25%-of-CPUs default (fallback 4)"),
                    },
                ),
                "reference": ("FASTA", {"description": "Optional reference FASTA"}),
                "gff": (
                    "GFF",
                    {"description": ("Optional genomic features file (GFF/BED/NCBI/TXT)")},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        try:
            assemblies = normalize_paths(inputs.get("assembly"), "assembly")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if not assemblies:
            return "assembly must contain at least one FASTA path"
        threads = inputs.get("threads")
        if threads is not None:
            if isinstance(threads, bool) or not isinstance(threads, int):
                return "threads must be an integer"
            if threads < 1:
                return "threads must be at least 1"
        for name in ("reference", "gff"):
            try:
                cls._optional_path(inputs, name)
            except (TypeError, ValueError) as exc:
                return str(exc)
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        assemblies = normalize_paths(inputs.get("assembly"), "assembly")
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / cls.OUTPUT_DIRECTORY
        command = ["quast", *assemblies, "--output-dir", str(output)]
        if inputs.get("threads") is not None:
            command.extend(["--threads", str(inputs["threads"])])
        reference = cls._optional_path(inputs, "reference")
        if reference is not None:
            command.extend(["--reference", reference])
        gff = cls._optional_path(inputs, "gff")
        if gff is not None:
            command.extend(["--features", gff])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [Path(output_dir) / cls.NODE_ID / cls.OUTPUT_DIRECTORY / cls.OUTPUT_FILENAME]
