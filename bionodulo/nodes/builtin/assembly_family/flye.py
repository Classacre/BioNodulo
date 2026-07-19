"""Pinned Flye 2.9.6 long-read assembly contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._paths import normalize_paths


class FlyeNode(CommandNode):
    """Assemble long reads with one of Flye's six documented read modes."""

    NODE_ID = "flye"
    DISPLAY_NAME = "Flye"
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble long reads with Flye and expose its native assembly, graph, statistics, and log files."
    SEARCH_ALIASES = ["flye", "assemble", "long reads", "nanopore", "pacbio", "repeat graph"]
    RETURN_TYPES = ("ASSEMBLY", "GFA", "FILE", "TSV", "STATS_FILE")
    RETURN_NAMES = ("assembly", "assembly_graph", "assembly_graph_visualization", "assembly_info", "log")
    REQUIRED_EXECUTABLES = ["flye"]
    REQUIRED_CONDA_PACKAGES = ["flye"]
    PACKAGE_CONSTRAINTS = ("flye==2.9.6",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "2.9.6"
    GIT_URL = "https://github.com/mikolmogorov/Flye.git"
    GIT_COMMIT = "886b8c17412cdf3a2868a28237bca6c5ad1da156"
    DOCUMENTATION_URL = "https://github.com/mikolmogorov/Flye/blob/2.9.6/docs/USAGE.md"
    CITATION_DOIS = ["10.1038/s41587-019-0072-8"]
    CITATION_URLS = ["https://doi.org/10.1038/s41587-019-0072-8"]
    CITATION_TEXT = "Assembly of long, error-prone reads using repeat graphs."
    BIOCONDA_VERSION = "2.9.6"
    UPSTREAM_OPTIONS_SOURCE = "flye/main.py"
    UPSTREAM_OUTPUT_DOC = "docs/USAGE.md"
    READ_TYPES = ("pacbio-raw", "pacbio-corr", "pacbio-hifi", "nano-raw", "nano-corr", "nano-hq")
    OUTPUT_FILENAMES = (
        "assembly.fasta",
        "assembly_graph.gfa",
        "assembly_graph.gv",
        "assembly_info.txt",
        "flye.log",
    )
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FILE_LIST", {"description": "One or more long-read FASTA/FASTQ files"}),
                "read_type": (
                    "STRING",
                    {"default": "nano-hq", "options": list(cls.READ_TYPES)},
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 128}),
                "genome_size": (
                    "STRING",
                    {"default": "", "description": "Optional estimated genome size, for example 5m"},
                ),
                "iterations": (
                    "INT",
                    {"default": 1, "min": 0, "max": 10, "description": "Polishing iterations"},
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
            reads = normalize_paths(inputs.get("reads"), "reads")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if not reads:
            return "reads must contain at least one long-read path"
        read_type = str(inputs.get("read_type", "nano-hq") or "nano-hq")
        if read_type not in cls.READ_TYPES:
            return f"read_type must be one of: {', '.join(cls.READ_TYPES)}"
        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 128:
            return "threads must be between 1 and 128"
        genome_size = inputs.get("genome_size", "")
        if genome_size not in (None, "") and (not isinstance(genome_size, str) or not genome_size.strip()):
            return "genome_size must be a non-empty string when supplied"
        iterations = inputs.get("iterations", 1)
        if isinstance(iterations, bool) or not isinstance(iterations, int):
            return "iterations must be an integer"
        if not 0 <= iterations <= 10:
            return "iterations must be between 0 and 10"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = [
            "flye",
            f"--{str(inputs.get('read_type', 'nano-hq') or 'nano-hq')}",
            *normalize_paths(inputs.get("reads"), "reads"),
            "--out-dir",
            str(inputs.get("output", inputs.get("output_dir", "."))),
            "--threads",
            str(inputs.get("threads", 1)),
        ]
        if inputs.get("genome_size") not in (None, ""):
            command.extend(["--genome-size", str(inputs["genome_size"])])
        command.extend(["--iterations", str(inputs.get("iterations", 1))])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]
