"""Align one single-end or paired-end read set with Bowtie2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .bowtie2_adapter import BOWTIE2_SUFFIX_FAMILIES, Bowtie2CommandNode
from .fm_index_bundle import find_index_bundle, path_value, planned_or_complete_prefix, read_paths


class Bowtie2AlignNode(Bowtie2CommandNode):
    """Align one single-end FASTQ or one ordered FASTQ pair to Bowtie2."""

    NODE_ID = "bowtie2_align"
    DISPLAY_NAME = "Bowtie2 Align"
    DESCRIPTION = "Align single-end or paired-end reads against a complete Bowtie2 index bundle"
    SEARCH_ALIASES = ["bowtie2", "align", "mapper", "map"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["bowtie2"]
    UPSTREAM_WRAPPER = "bowtie2"
    UPSTREAM_SOURCE = "bt2_search.cpp"
    OUTPUT_FILENAME = "alignment.sam"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": "One single-end FASTQ or an ordered [R1, R2] pair"},
                ),
                "index": (
                    "INDEX_DIR",
                    {"description": "Directory containing one complete Bowtie2 index prefix"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {
                "rg_id": (
                    "STRING",
                    {"default": "", "description": "SAM read-group ID; empty matches Bowtie2's default"},
                ),
                "rg_sample": (
                    "STRING",
                    {"default": "", "description": "SAM read-group sample (SM); requires rg_id"},
                ),
                "very_sensitive": (
                    "BOOLEAN",
                    {"default": False, "description": "Use Bowtie2's --very-sensitive preset"},
                ),
                "no_mixed": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable unpaired fallback for paired reads"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        reads = read_paths(inputs)
        if len(reads) not in (1, 2):
            return "reads must contain one single-end FASTQ or an ordered [R1, R2] pair"
        missing_read = next((read for read in reads if not Path(read).is_file()), None)
        if missing_read is not None:
            return f"Read file not found: {missing_read}"

        index = path_value(inputs.get("index"))
        if index is None:
            return "Input 'index' must be a non-empty path-like value"
        try:
            find_index_bundle(
                index,
                label="Bowtie2",
                suffix_families=BOWTIE2_SUFFIX_FAMILIES,
            )
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            return str(exc)

        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"

        rg_id = inputs.get("rg_id", "")
        rg_sample = inputs.get("rg_sample", "")
        if not isinstance(rg_id, str) or not isinstance(rg_sample, str):
            return "rg_id and rg_sample must be strings"
        if any(character in rg_id or character in rg_sample for character in "\t\r\n"):
            return "rg_id and rg_sample must not contain tabs or newlines"
        if rg_sample and not rg_id:
            return "rg_sample requires rg_id so Bowtie2 emits an @RG header"
        if inputs.get("no_mixed", False) and len(reads) != 2:
            return "no_mixed is only valid for paired-end reads"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prefix = planned_or_complete_prefix(
            str(inputs.get("index", "")),
            label="Bowtie2",
            suffix_families=BOWTIE2_SUFFIX_FAMILIES,
        )
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        reads = read_paths(inputs)
        command = ["bowtie2", "-p", str(inputs.get("threads", 1)), "-x", str(prefix)]
        if inputs.get("rg_id"):
            command.extend(["--rg-id", str(inputs["rg_id"])])
        if inputs.get("rg_sample"):
            command.extend(["--rg", f"SM:{inputs['rg_sample']}"])
        if inputs.get("very_sensitive", False):
            command.append("--very-sensitive")
        if inputs.get("no_mixed", False):
            command.append("--no-mixed")
        if len(reads) == 2:
            command.extend(["-1", reads[0], "-2", reads[1]])
        elif reads:
            command.extend(["-U", reads[0]])
        command.extend(["-S", str(output / cls.OUTPUT_FILENAME)])
        return command
