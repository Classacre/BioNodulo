"""Pinned MEGAHIT 1.2.9 assembly contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._paths import normalize_paths


_DEFAULT_K_LIST = "21,29,39,59,79,99,119,141"


class MEGAHITNode(CommandNode):
    """Assemble one single-end or paired-end FASTQ library with MEGAHIT."""

    NODE_ID = "megahit"
    DISPLAY_NAME = "MEGAHIT"
    CATEGORY = "assembly"
    DESCRIPTION = "Memory-efficient de novo metagenome assembly with MEGAHIT"
    SEARCH_ALIASES = ["megahit", "assemble", "metagenome", "macro", "contigs"]
    RETURN_TYPES = ("CONTIGS",)
    RETURN_NAMES = ("contigs",)
    REQUIRED_EXECUTABLES = ["megahit"]
    REQUIRED_CONDA_PACKAGES = ["megahit"]
    DOCUMENTATION_URL = "https://github.com/voutcn/megahit/blob/v1.2.9/README.md"
    VERSION = "1.2.9"
    GIT_URL = "https://github.com/voutcn/megahit.git"
    GIT_COMMIT = "d729cca1e201ca16749b67f750b0bc5465c9a990"
    CITATION_DOIS = ["10.1093/bioinformatics/btv033"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btv033"]
    CITATION_TEXT = "MEGAHIT: an ultra-fast single-node solution for large and complex metagenomics assembly via succinct de Bruijn graph."
    BIOCONDA_VERSION = "1.2.9"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/megahit/files?version=1.2.9"
    UPSTREAM_README = "README.md"
    UPSTREAM_SOURCE = "src/megahit"
    OUTPUT_DIRECTORY = "megahit_out"
    OUTPUT_FILENAME = "final.contigs.fa"
    DEFAULT_K_LIST = _DEFAULT_K_LIST

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": ("One single-end FASTQ or ordered paired-end [R1, R2] reads")},
                ),
            },
            "optional": {
                "threads": (
                    "INT",
                    {
                        "min": 1,
                        "description": ("CPU threads; omitted uses the logical CPU count detected by MEGAHIT"),
                    },
                ),
                "min_contig_len": (
                    "INT",
                    {"default": 200, "min": 1, "description": "Minimum contig length to emit"},
                ),
                "k_list": (
                    "STRING",
                    {
                        "default": _DEFAULT_K_LIST,
                        "description": "Comma-separated odd k-mer sizes",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validate_k_list(cls, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return "k_list must be a non-empty comma-separated integer list"
        try:
            values = sorted(int(part.strip()) for part in value.split(","))
        except ValueError:
            return "k_list must contain only integers"
        if not values:
            return "k_list must contain at least one k-mer size"
        if values[0] < 15 or values[-1] > 255:
            return "k_list values must be between 15 and 255"
        if any(value % 2 == 0 for value in values):
            return "k_list values must be odd"
        if any(right - left > 28 for left, right in zip(values, values[1:])):
            return "adjacent k_list values must differ by at most 28"
        return None

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

        threads = inputs.get("threads")
        if threads is not None:
            if isinstance(threads, bool) or not isinstance(threads, int):
                return "threads must be an integer"
            if threads < 1:
                return "threads must be at least 1"
        min_len = inputs.get("min_contig_len", 200)
        if isinstance(min_len, bool) or not isinstance(min_len, int):
            return "min_contig_len must be an integer"
        if min_len < 1:
            return "min_contig_len must be at least 1"
        k_error = cls._validate_k_list(inputs.get("k_list", cls.DEFAULT_K_LIST))
        return k_error or True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        reads = normalize_paths(inputs.get("reads"), "reads")
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / cls.OUTPUT_DIRECTORY
        command = ["megahit"]
        if len(reads) == 1:
            command.extend(["-r", reads[0]])
        else:
            command.extend(["-1", reads[0], "-2", reads[1]])
        command.extend(
            [
                "-o",
                str(output),
                "--min-contig-len",
                str(inputs.get("min_contig_len", 200)),
                "--k-list",
                str(inputs.get("k_list", cls.DEFAULT_K_LIST)),
            ]
        )
        if inputs.get("threads") is not None:
            command.extend(["--num-cpu-threads", str(inputs["threads"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [Path(output_dir) / cls.NODE_ID / cls.OUTPUT_DIRECTORY / cls.OUTPUT_FILENAME]
