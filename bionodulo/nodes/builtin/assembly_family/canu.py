"""Pinned Canu 2.3 long-read assembly contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._paths import normalize_paths


class CanuNode(CommandNode):
    """Assemble PacBio or Oxford Nanopore reads with Canu."""

    NODE_ID = "canu"
    DISPLAY_NAME = "Canu"
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble long reads with Canu and return its native contigs, unassembled reads, and report."
    SEARCH_ALIASES = ["canu", "assemble", "long reads", "pacbio", "nanopore", "hifi"]
    RETURN_TYPES = ("ASSEMBLY", "FASTA", "STATS_FILE")
    RETURN_NAMES = ("assembly", "unassembled_reads", "report")
    REQUIRED_EXECUTABLES = ["canu"]
    REQUIRED_CONDA_PACKAGES = ["canu"]
    PACKAGE_CONSTRAINTS = ("canu==2.3",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "2.3"
    GIT_URL = "https://github.com/marbl/canu.git"
    GIT_COMMIT = "d2ec645cf89a7fc862dcfdf2dea5a547eba15376"
    DOCUMENTATION_URL = "https://github.com/marbl/canu/tree/v2.3"
    CITATION_DOIS = ["10.1101/gr.215087.116"]
    CITATION_URLS = ["https://doi.org/10.1101/gr.215087.116"]
    CITATION_TEXT = "Canu: scalable and accurate long-read assembly via adaptive k-mer weighting and repeat separation."
    BIOCONDA_VERSION = "2.3"
    UPSTREAM_OPTIONS_SOURCE = "src/pipelines/canu/Defaults.pm"
    UPSTREAM_OUTPUT_SOURCE = "src/pipelines/canu/Output.pm"
    READ_TYPES = ("pacbio", "nanopore", "pacbio-hifi")
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FILE_LIST", {"description": "One or more FASTA/FASTQ long-read files"}),
                "genome_size": (
                    "STRING",
                    {"description": "Estimated haploid genome size, for example 5m or 3.2g"},
                ),
            },
            "optional": {
                "prefix": ("STRING", {"default": "assembly", "description": "Native Canu output prefix"}),
                "threads": (
                    "INT",
                    {"min": 1, "description": "Maximum threads; omitted lets Canu configure local resources"},
                ),
                "read_type": (
                    "STRING",
                    {"default": "pacbio-hifi", "options": list(cls.READ_TYPES)},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _prefix(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("prefix", "assembly") or "assembly")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        try:
            reads = normalize_paths(inputs.get("reads"), "reads")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if not reads:
            return "reads must contain at least one FASTA/FASTQ path"
        genome_size = inputs.get("genome_size")
        if not isinstance(genome_size, str) or not genome_size.strip():
            return "genome_size must be a non-empty string"
        prefix = cls._prefix(inputs)
        if prefix in {".", ".."} or Path(prefix).name != prefix or any(character.isspace() for character in prefix):
            return "prefix must be a filename-safe value without directory components or whitespace"
        read_type = str(inputs.get("read_type", "pacbio-hifi") or "pacbio-hifi")
        if read_type not in cls.READ_TYPES:
            return f"read_type must be one of: {', '.join(cls.READ_TYPES)}"
        threads = inputs.get("threads")
        if threads is not None:
            if isinstance(threads, bool) or not isinstance(threads, int):
                return "threads must be an integer"
            if threads < 1:
                return "threads must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = [
            "canu",
            "-p",
            cls._prefix(inputs),
            "-d",
            str(inputs.get("output", inputs.get("output_dir", "."))),
            f"genomeSize={str(inputs['genome_size']).strip()}",
            f"-{str(inputs.get('read_type', 'pacbio-hifi') or 'pacbio-hifi')}",
            *normalize_paths(inputs.get("reads"), "reads"),
            "useGrid=false",
        ]
        if inputs.get("threads") is not None:
            command.append(f"maxThreads={inputs['threads']}")
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        prefix = cls._prefix(inputs)
        return [
            node_out / f"{prefix}.contigs.fasta",
            node_out / f"{prefix}.unassembled.fasta",
            node_out / f"{prefix}.report",
        ]
