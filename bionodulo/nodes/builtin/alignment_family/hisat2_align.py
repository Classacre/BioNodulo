"""Align one single-end or paired-end RNA-seq read set with HISAT2."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .fm_index_bundle import (
    find_index_bundle,
    path_value,
    planned_or_complete_prefix,
    read_paths,
    stage_bundle,
    stage_file,
)
from .hisat2_adapter import HISAT2_SUFFIX_FAMILIES, HISAT2CommandNode, hisat2_source_urls


class HISAT2AlignNode(HISAT2CommandNode):
    """Align one single-end FASTQ or one ordered FASTQ pair to HISAT2."""

    NODE_ID = "hisat2_align"
    DISPLAY_NAME = "HISAT2 Align"
    DESCRIPTION = "Align single-end or paired-end reads against a complete HISAT2 index bundle"
    SEARCH_ALIASES = ["hisat2", "align", "rna-seq", "spliced", "mapper"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["hisat2"]
    UPSTREAM_WRAPPER = "hisat2"
    UPSTREAM_SOURCE = "hisat2.cpp"
    OUTPUT_FILENAME = "alignment.sam"
    SOURCE_PATHS = ("docs/_pages/manual.md", "hisat2", "hisat2.cpp")
    SOURCE_URLS = hisat2_source_urls(*SOURCE_PATHS)

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
                    {"description": "Directory containing one complete HISAT2 index prefix"},
                ),
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "optional": {
                "rg_id": (
                    "STRING",
                    {"default": "", "description": "SAM read-group ID; empty matches HISAT2's default"},
                ),
                "rg_sample": (
                    "STRING",
                    {"default": "", "description": "SAM read-group sample (SM); requires rg_id"},
                ),
                "dta": (
                    "BOOLEAN",
                    {"default": False, "description": "Tailor alignments for transcript assemblers (--dta)"},
                ),
                "no_softclip": (
                    "BOOLEAN",
                    {"default": False, "description": "Disallow soft clipping (--no-softclip)"},
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
                label="HISAT2",
                suffix_families=HISAT2_SUFFIX_FAMILIES,
            )
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            return str(exc)

        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be a positive integer"

        rg_id = inputs.get("rg_id", "")
        rg_sample = inputs.get("rg_sample", "")
        if not isinstance(rg_id, str) or not isinstance(rg_sample, str):
            return "rg_id and rg_sample must be strings"
        if any(character in rg_id or character in rg_sample for character in "\t\r\n"):
            return "rg_id and rg_sample must not contain tabs or newlines"
        if rg_sample and not rg_id:
            return "rg_sample requires rg_id so HISAT2 emits an @RG header"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        bundle = find_index_bundle(
            str(inputs["index"]),
            label="HISAT2",
            suffix_families=HISAT2_SUFFIX_FAMILIES,
        )
        safe_root = outputs[0].parent / "_inputs"
        if safe_root.exists():
            shutil.rmtree(safe_root)

        safe_index_dir = safe_root / "index"
        safe_prefix = safe_index_dir / "index"
        stage_bundle(bundle, safe_prefix)

        staged_reads: list[str] = []
        for number, read in enumerate(read_paths(inputs), start=1):
            source = Path(read)
            compression = source.suffix.lower() if source.suffix.lower() in {".gz", ".bz2"} else ""
            target = safe_root / "reads" / f"read_{number}.fastq{compression}"
            stage_file(source, target)
            staged_reads.append(str(target))

        inputs["index"] = str(safe_index_dir)
        inputs["reads"] = staged_reads

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prefix = planned_or_complete_prefix(
            str(inputs.get("index", "")),
            label="HISAT2",
            suffix_families=HISAT2_SUFFIX_FAMILIES,
        )
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        reads = read_paths(inputs)
        command = ["hisat2", "-p", str(inputs.get("threads", 1)), "-x", str(prefix)]
        if inputs.get("rg_id"):
            command.extend(["--rg-id", str(inputs["rg_id"])])
        if inputs.get("rg_sample"):
            command.extend(["--rg", f"SM:{inputs['rg_sample']}"])
        if inputs.get("dta", False):
            command.append("--dta")
        if inputs.get("no_softclip", False):
            command.append("--no-softclip")
        if len(reads) == 2:
            command.extend(["-1", reads[0], "-2", reads[1]])
        elif reads:
            command.extend(["-U", reads[0]])
        command.extend(["-S", str(output / cls.OUTPUT_FILENAME)])
        return command
