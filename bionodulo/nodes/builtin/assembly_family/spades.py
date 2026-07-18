"""Pinned SPAdes 4.2.0 assembly contract.

The wrapper maps one FASTQ to SPAdes' documented ``-s`` input and an ordered
R1/R2 pair to ``-1``/``-2``.  It returns the native ``scaffolds.fasta`` and
``contigs.fasta`` files directly; no post-run filename synthesis or copy is
needed.  SPAdes' optional mode-specific inputs are intentionally not exposed
by the ordinary isolate contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._paths import normalize_paths


class SPAdesNode(CommandNode):
    """Assemble one single-end FASTQ or one paired-end FASTQ library."""

    NODE_ID = "spades"
    DISPLAY_NAME = "SPAdes"
    CATEGORY = "assembly"
    DESCRIPTION = "De novo assembly of single-end or paired-end reads with SPAdes"
    SEARCH_ALIASES = ["spades", "assemble", "de novo", "genome", "scaffolds"]
    RETURN_TYPES = ("ASSEMBLY", "CONTIGS")
    RETURN_NAMES = ("assembly", "contigs")
    REQUIRED_EXECUTABLES = ["spades.py"]
    REQUIRED_CONDA_PACKAGES = ["spades"]
    DOCUMENTATION_URL = "https://github.com/ablab/spades/tree/v4.2.0"
    VERSION = "4.2.0"
    GIT_URL = "https://github.com/ablab/spades.git"
    GIT_COMMIT = "7fee3c1050a732faef8a0d93d70861015a96f44e"
    CITATION_DOIS = ["10.1089/cmb.2012.0021"]
    CITATION_URLS = ["https://doi.org/10.1089/cmb.2012.0021"]
    CITATION_TEXT = "SPAdes: A New Genome Assembly Algorithm and Its Applications to Single-Cell Sequencing."
    BIOCONDA_VERSION = "4.2.0"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/spades/files?version=4.2.0"
    UPSTREAM_README = "README.md"
    UPSTREAM_INPUT_DOC = "docs/input.md"
    UPSTREAM_OUTPUT_DOC = "docs/output.md"
    UPSTREAM_OPTIONS_DOC = "docs/running.md"
    OUTPUT_FILENAMES = ("scaffolds.fasta", "contigs.fasta")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": ("One FASTQ for single-end assembly or ordered [R1, R2] paired-end reads")},
                ),
                "threads": (
                    "INT",
                    {
                        "default": 16,
                        "min": 1,
                        "description": "SPAdes worker threads (upstream default: 16)",
                    },
                ),
            },
            "optional": {
                "memory": (
                    "INT",
                    {
                        "min": 1,
                        "description": (
                            "RAM limit in GB; omitted uses SPAdes' available-memory "
                            "default (upstream default: 250 GB cap)"
                        ),
                        "advanced": True,
                    },
                ),
                "careful": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Enable mismatch/short-indel reduction",
                        "advanced": True,
                    },
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
        if len(reads) not in (1, 2):
            return "reads must contain exactly one or two FASTQ paths"

        threads = inputs.get("threads", 16)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"

        memory = inputs.get("memory")
        if memory is not None:
            if isinstance(memory, bool) or not isinstance(memory, int):
                return "memory must be an integer number of GB"
            if memory < 1:
                return "memory must be at least 1 GB"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        reads = normalize_paths(inputs.get("reads"), "reads")
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        command = ["spades.py"]
        if len(reads) == 1:
            command.extend(["-s", reads[0]])
        else:
            command.extend(["-1", reads[0], "-2", reads[1]])
        command.extend(["-o", output, "-t", str(inputs.get("threads", 16))])
        if inputs.get("memory") is not None:
            command.extend(["-m", str(inputs["memory"])])
        if inputs.get("careful", False):
            command.append("--careful")
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]
