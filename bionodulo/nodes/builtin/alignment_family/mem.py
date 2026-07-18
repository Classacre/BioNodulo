"""BWA-MEM alignment against a validated BWA index bundle."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adapter import BWA_INDEX_FASTA, BwaCommandNode, find_index_prefix, path_value


def _reads(inputs: dict[str, Any]) -> list[str]:
    value = inputs.get("reads", [])
    if isinstance(value, (str, os.PathLike)):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    reads: list[str] = []
    for item in value:
        path = path_value(item)
        if path is None:
            return []
        reads.append(path)
    return reads


def _read_group(inputs: dict[str, Any]) -> str:
    read_group = str(inputs.get("read_group", "") or "")
    if read_group:
        return read_group

    # Render legacy workflow parameters when present, without advertising them
    # as upstream BWA ports or synthesizing a read group by default.
    rg_id = str(inputs.get("rg_id", "") or "")
    if not rg_id:
        return ""
    sample = str(inputs.get("rg_sample", "") or "")
    platform = str(inputs.get("rg_platform", "") or "")
    fields = ["@RG", f"ID:{rg_id}"]
    if sample:
        fields.append(f"SM:{sample}")
    if platform:
        fields.append(f"PL:{platform}")
    return "\\t".join(fields)


class BWAMemNode(BwaCommandNode):
    """Align one single-end or paired-end FASTQ set with BWA-MEM."""

    NODE_ID = "bwa_mem"
    DISPLAY_NAME = "BWA-MEM Align"
    DESCRIPTION = "Align single-end or paired-end reads against a complete BWA index bundle"
    SEARCH_ALIASES = ["bwa", "mem", "align", "mapper", "map"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    OUTPUT_FILENAME = "alignment.sam"
    DOCUMENTATION_URL = "https://github.com/lh3/bwa/blob/v0.7.19/bwa.1"
    UPSTREAM_SOURCE = "fastmap.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": "One single-end FASTQ or an ordered [R1, R2] pair"},
                ),
                "reference": (
                    "INDEX_DIR",
                    {"description": "Directory containing one staged FASTA and its complete BWA index siblings"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {
                "read_group": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Complete @RG line with escaped \\t separators; empty matches BWA's default",
                    },
                ),
                "mark_shorter_splits": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Use -M to mark shorter split hits as secondary",
                    },
                ),
                "min_score": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "description": "Minimum alignment score to output (-T)",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        reads = _reads(inputs)
        if len(reads) not in (1, 2):
            return "reads must contain one single-end FASTQ or an ordered [R1, R2] pair"

        reference = path_value(inputs.get("reference"))
        if reference is None:
            return "Input 'reference' must be a non-empty path-like value"
        try:
            find_index_prefix(reference)
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            return str(exc)

        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"

        read_group = _read_group(inputs)
        if read_group:
            if not read_group.startswith("@RG"):
                return "read_group must start with @RG"
            if "\t" in read_group:
                return "read_group must use escaped \\t separators, not literal tabs"
            if "\\tID:" not in read_group:
                return "read_group must contain an ID field separated by escaped \\t"

        mark_splits = inputs.get("mark_shorter_splits", False)
        if not isinstance(mark_splits, bool):
            return "mark_shorter_splits must be a boolean"
        min_score = inputs.get("min_score", 30)
        if isinstance(min_score, bool) or not isinstance(min_score, int):
            return "min_score must be an integer"
        if min_score < 0:
            return "min_score must be at least 0"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reference = path_value(inputs.get("reference"))
        if reference is None:
            raise ValueError("Input 'reference' must be a non-empty path-like value")
        index_dir = Path(reference)
        prefix = find_index_prefix(index_dir) if index_dir.exists() else index_dir / BWA_INDEX_FASTA
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["bwa", "mem", "-t", str(inputs.get("threads", 1))]
        read_group = _read_group(inputs)
        if read_group:
            command.extend(["-R", read_group])
        command.extend(["-T", str(inputs.get("min_score", 30))])
        if inputs.get("mark_shorter_splits", False):
            command.append("-M")
        command.extend(["-o", str(output / cls.OUTPUT_FILENAME), str(prefix)])
        command.extend(_reads(inputs))
        return command
