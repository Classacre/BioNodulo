"""Align one single-end or paired-end RNA-seq read set with STAR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .star_adapter import STAR_INDEX_MARKERS, STARCommandNode, path_value, read_paths


class STARAlignNode(STARCommandNode):
    NODE_ID = "star_align"
    DISPLAY_NAME = "STAR Align"
    DESCRIPTION = "Align single-end or paired-end RNA-seq reads with coordinate-sorted BAM output"
    SEARCH_ALIASES = ["star", "align", "rna-seq", "two-pass"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("alignment",)
    UPSTREAM_SOURCE = "source/Parameters.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "One FASTQ or an ordered R1/R2 pair"}),
                "index": ("INDEX_DIR", {"description": "Complete STAR genome index directory"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "two_pass": ("BOOLEAN", {"default": True, "advanced": True}),
                "chim_segment_min": ("INT", {"default": 0, "min": 0, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "Aligned.sortedByCoord.out.bam"]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        index_dir = Path(str(inputs.get("index", "")))
        if not index_dir.is_dir():
            raise FileNotFoundError(f"STAR index directory not found: {index_dir}")
        missing = [name for name in STAR_INDEX_MARKERS if not (index_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(f"STAR index is incomplete; missing: {', '.join(missing)}")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        reads = read_paths(inputs.get("reads"))
        if len(reads) not in (1, 2):
            return "reads must contain one FASTQ or one ordered R1/R2 pair"
        if path_value(inputs.get("index")) is None:
            return "index must be a non-empty path-like value"
        validation = cls.validate_threads(inputs)
        if validation is not True:
            return validation
        chim_segment_min = inputs.get("chim_segment_min", 0)
        if isinstance(chim_segment_min, bool) or not isinstance(chim_segment_min, int) or chim_segment_min < 0:
            return "chim_segment_min must be a non-negative integer"
        compressions = {
            ".gz" if read.endswith(".gz") else ".bz2" if read.endswith(".bz2") else "plain"
            for read in reads
        }
        if len(compressions) != 1:
            return "paired reads must use the same compression format"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reads = read_paths(inputs.get("reads"))
        command = [
            "STAR",
            "--genomeDir",
            str(inputs.get("index", "")),
            "--readFilesIn",
            *reads,
        ]
        if reads and reads[0].endswith(".gz"):
            command.extend(["--readFilesCommand", "zcat"])
        elif reads and reads[0].endswith(".bz2"):
            command.extend(["--readFilesCommand", "bzcat"])
        output_prefix = f"{cls.output_dir(inputs)}/"
        command.extend(
            [
                "--outFileNamePrefix",
                output_prefix,
                "--outSAMtype",
                "BAM",
                "SortedByCoordinate",
                "--runThreadN",
                str(inputs.get("threads", 8)),
            ]
        )
        if inputs.get("two_pass", True):
            command.extend(["--twopassMode", "Basic"])
        chim_segment_min = inputs.get("chim_segment_min", 0)
        if chim_segment_min:
            command.extend(["--chimSegmentMin", str(chim_segment_min)])
        return command


__all__ = ["STARAlignNode"]
