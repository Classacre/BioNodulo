"""Pinned Unicycler 0.5.1 bacterial assembly contract."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._paths import normalize_paths


def _optional_path(value: Any, label: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError as exc:
        raise TypeError(f"{label} must be path-like") from exc
    if not path.strip():
        raise ValueError(f"{label} must be a non-empty path")
    return path


class UnicyclerNode(CommandNode):
    """Run short-read, long-read, or hybrid bacterial assembly."""

    NODE_ID = "unicycler"
    DISPLAY_NAME = "Unicycler"
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble bacterial genomes from paired, unpaired, and/or long reads with Unicycler."
    SEARCH_ALIASES = ["unicycler", "assemble", "bacteria", "hybrid", "short reads", "long reads"]
    RETURN_TYPES = ("ASSEMBLY", "GFA", "STATS_FILE")
    RETURN_NAMES = ("assembly", "assembly_graph", "log")
    REQUIRED_EXECUTABLES = ["unicycler"]
    REQUIRED_CONDA_PACKAGES = ["unicycler"]
    PACKAGE_CONSTRAINTS = ("unicycler==0.5.1",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "0.5.1"
    GIT_URL = "https://github.com/rrwick/Unicycler.git"
    GIT_COMMIT = "d153f67d6f626176c100724600104ade4f6d7a2e"
    DOCUMENTATION_URL = "https://github.com/rrwick/Unicycler/tree/v0.5.1"
    CITATION_DOIS = ["10.1371/journal.pcbi.1005595"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pcbi.1005595"]
    CITATION_TEXT = "Unicycler: resolving bacterial genome assemblies from short and long sequencing reads."
    BIOCONDA_VERSION = "0.5.1"
    UPSTREAM_OPTIONS_SOURCE = "unicycler/unicycler.py"
    UPSTREAM_OUTPUT_DOC = "README.md"
    MODES = ("conservative", "normal", "bold")
    OUTPUT_FILENAMES = ("assembly.fasta", "assembly.gfa", "unicycler.log")
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "reads": ("FASTQ_LIST", {"default": "", "description": "Ordered paired reads [R1, R2]"}),
                "r1": ("FASTQ", {"default": "", "description": "Compatibility forward-read port"}),
                "r2": ("FASTQ", {"default": "", "description": "Compatibility reverse-read port"}),
                "unpaired": ("FASTQ", {"default": "", "description": "Unpaired short reads"}),
                "long_reads": ("FILE", {"default": "", "description": "Long-read FASTA/FASTQ"}),
                "threads": (
                    "INT",
                    {"min": 1, "description": "Threads; omitted uses Unicycler's CPU-count default capped at 8"},
                ),
                "mode": ("STRING", {"default": "normal", "options": list(cls.MODES)}),
                "min_fasta_length": ("INT", {"default": 100, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _paired_reads(cls, inputs: dict[str, Any]) -> list[str]:
        reads_value = inputs.get("reads")
        if reads_value not in (None, ""):
            return normalize_paths(reads_value, "reads")
        r1 = _optional_path(inputs.get("r1"), "r1")
        r2 = _optional_path(inputs.get("r2"), "r2")
        return [path for path in (r1, r2) if path is not None]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("reads") not in (None, "") and (
            inputs.get("r1") not in (None, "") or inputs.get("r2") not in (None, "")
        ):
            return "use either reads or r1/r2, not both"
        try:
            paired = cls._paired_reads(inputs)
            unpaired = _optional_path(inputs.get("unpaired"), "unpaired")
            long_reads = _optional_path(inputs.get("long_reads"), "long_reads")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if paired and len(paired) != 2:
            return "paired short reads require exactly two paths"
        if not paired and unpaired is None and long_reads is None:
            return "at least one paired, unpaired, or long-read input is required"
        mode = str(inputs.get("mode", "normal") or "normal")
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        threads = inputs.get("threads")
        if threads is not None:
            if isinstance(threads, bool) or not isinstance(threads, int):
                return "threads must be an integer"
            if threads < 1:
                return "threads must be at least 1"
        min_length = inputs.get("min_fasta_length", 100)
        if isinstance(min_length, bool) or not isinstance(min_length, int):
            return "min_fasta_length must be an integer"
        if min_length < 1:
            return "min_fasta_length must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["unicycler"]
        paired = cls._paired_reads(inputs)
        if paired:
            command.extend(["-1", paired[0], "-2", paired[1]])
        unpaired = _optional_path(inputs.get("unpaired"), "unpaired")
        if unpaired is not None:
            command.extend(["-s", unpaired])
        long_reads = _optional_path(inputs.get("long_reads"), "long_reads")
        if long_reads is not None:
            command.extend(["-l", long_reads])
        command.extend(["-o", str(inputs.get("output", inputs.get("output_dir", ".")))])
        if inputs.get("threads") is not None:
            command.extend(["-t", str(inputs["threads"])])
        command.extend(
            [
                "--mode",
                str(inputs.get("mode", "normal") or "normal"),
                "--min_fasta_length",
                str(inputs.get("min_fasta_length", 100)),
                "--keep",
                "0",
            ]
        )
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]
