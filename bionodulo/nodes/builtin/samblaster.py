"""Source-pinned samblaster 0.1.26 contract using Samtools 1.23.1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def _enabled(inputs: dict[str, Any], name: str, default: bool = False) -> bool:
    return bool(inputs.get(name, default))


def _validate_int(value: Any, name: str, *, minimum: int, maximum: int | None = None) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if value < minimum:
        return f"{name} must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"{name} must be at most {maximum}"
    return True


class SamblasterNode(CommandNode):
    """Mark duplicates and optionally extract discordant, split, and clipped reads."""

    NODE_ID = "samblaster"
    DISPLAY_NAME = "samblaster"
    CATEGORY = "alignment"
    DESCRIPTION = "Query-name group alignments, mark duplicates, and emit indexed BAM side outputs with samblaster."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "samblaster",
        "duplicate marking",
        "split reads",
        "discordant read pairs",
        "structural variant extraction",
    ]
    RETURN_TYPES = ("BAM", "BAI", "BAM", "BAI", "BAM", "BAI", "FILE")
    RETURN_NAMES = (
        "alignments",
        "alignments_index",
        "discordant_alignments",
        "discordant_alignments_index",
        "split_alignments",
        "split_alignments_index",
        "unmapped_reads",
    )
    REQUIRED_EXECUTABLES = ["samblaster", "samtools"]
    REQUIRED_CONDA_PACKAGES = ["samblaster", "samtools"]
    PACKAGE_CONSTRAINTS = ("samblaster==0.1.26", "samtools==1.23.1")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    VERSION = "0.1.26"
    GIT_URL = "https://github.com/GregoryFaust/samblaster.git"
    GIT_COMMIT = "b642639117eafedc760d8b84c0d2c4872b0da084"
    DOCUMENTATION_URL = "https://github.com/GregoryFaust/samblaster/tree/v.0.1.26"
    CITATION_DOIS = ["10.1093/bioinformatics/btu314"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btu314"]
    CITATION_TEXT = "SAMBLASTER: fast duplicate marking and structural variant read extraction."
    UPSTREAM_SOURCE = "samblaster.cpp"
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("SAM,BAM", {"description": "Input SAM or BAM alignment file"}),
            },
            "optional": {
                "output_bam": ("BOOLEAN", {"default": True}),
                "discordantFile": ("BOOLEAN", {"default": False}),
                "splitterFile": ("BOOLEAN", {"default": False}),
                "unmappedFile": (
                    "BOOLEAN",
                    {"default": False, "description": "Output clipped/unmapped FASTQ or FASTA as a generic file"},
                ),
                "acceptDupMarks": ("BOOLEAN", {"default": False}),
                "excludeDups": ("BOOLEAN", {"default": False}),
                "removeDups": ("BOOLEAN", {"default": False}),
                "addMateTags": ("BOOLEAN", {"default": False}),
                "compatibility_mode": ("BOOLEAN", {"default": False}),
                "maxSplitCount": ("INT", {"default": 2, "min": 2}),
                "maxUnmappedBases": ("INT", {"default": 50, "min": 0}),
                "minIndelSize": ("INT", {"default": 50, "min": 1}),
                "minNonOverlap": ("INT", {"default": 20, "min": 1}),
                "minClipSize": ("INT", {"default": 20, "min": 1}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if _path_value(inputs.get("input")) is None:
            return "input must be a non-empty SAM/BAM path"
        if not any(
            _enabled(inputs, name, name == "output_bam")
            for name in ("output_bam", "discordantFile", "splitterFile", "unmappedFile")
        ):
            return "at least one output must be enabled"
        validation = _validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        if _enabled(inputs, "splitterFile"):
            for name, default, minimum in (
                ("maxSplitCount", 2, 2),
                ("maxUnmappedBases", 50, 0),
                ("minIndelSize", 50, 1),
                ("minNonOverlap", 20, 1),
            ):
                validation = _validate_int(inputs.get(name, default), name, minimum=minimum)
                if validation is not True:
                    return validation
        if _enabled(inputs, "unmappedFile"):
            validation = _validate_int(inputs.get("minClipSize", 20), "minClipSize", minimum=1)
            if validation is not True:
                return validation
        return True

    @classmethod
    def _append_sorted_bam(cls, command: list[str], output_dir: Path, stem: str, threads: int) -> None:
        bam = output_dir / f"{stem}.bam"
        command.extend(
            [
                "&&",
                "samtools",
                "sort",
                "--no-PG",
                "-@",
                str(threads),
                "-O",
                "bam",
                "-o",
                str(bam),
                str(output_dir / f"{stem}.sam"),
                "&&",
                "samtools",
                "index",
                "-o",
                str(output_dir / f"{stem}.bam.bai"),
                str(bam),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        threads = int(inputs.get("threads", 4))
        grouped_sam = output_dir / "queryname_grouped.sam"
        command = [
            "set",
            "-o",
            "pipefail",
            "&&",
            "samtools",
            "sort",
            "-n",
            "--no-PG",
            "-@",
            str(threads),
            "-O",
            "sam",
            "-o",
            str(grouped_sam),
            str(inputs.get("input", "")),
            "&&",
            "samblaster",
            "--input",
            str(grouped_sam),
            "--output",
            str(output_dir / "output.sam") if _enabled(inputs, "output_bam", True) else "/dev/null",
        ]
        if _enabled(inputs, "discordantFile"):
            command.extend(["--discordantFile", str(output_dir / "discordant.sam")])
        if _enabled(inputs, "splitterFile"):
            command.extend(
                [
                    "--splitterFile",
                    str(output_dir / "splitter.sam"),
                    "--maxSplitCount",
                    str(inputs.get("maxSplitCount", 2)),
                    "--maxUnmappedBases",
                    str(inputs.get("maxUnmappedBases", 50)),
                    "--minIndelSize",
                    str(inputs.get("minIndelSize", 50)),
                    "--minNonOverlap",
                    str(inputs.get("minNonOverlap", 20)),
                ]
            )
        if _enabled(inputs, "unmappedFile"):
            command.extend(
                [
                    "--unmappedFile",
                    str(output_dir / "unmapped_reads.fastx"),
                    "--minClipSize",
                    str(inputs.get("minClipSize", 20)),
                ]
            )
        if _enabled(inputs, "acceptDupMarks"):
            command.append("--acceptDupMarks")
        if _enabled(inputs, "excludeDups"):
            command.append("--excludeDups")
        if _enabled(inputs, "removeDups"):
            command.append("--removeDups")
        if _enabled(inputs, "addMateTags"):
            command.append("--addMateTags")
        if _enabled(inputs, "compatibility_mode"):
            command.append("-M")
        if _enabled(inputs, "output_bam", True):
            cls._append_sorted_bam(command, output_dir, "output", threads)
        if _enabled(inputs, "discordantFile"):
            cls._append_sorted_bam(command, output_dir, "discordant", threads)
        if _enabled(inputs, "splitterFile"):
            cls._append_sorted_bam(command, output_dir, "splitter", threads)
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if _enabled(inputs, "output_bam", True):
            outputs.extend([node_out / "output.bam", node_out / "output.bam.bai"])
        if _enabled(inputs, "discordantFile"):
            outputs.extend([node_out / "discordant.bam", node_out / "discordant.bam.bai"])
        if _enabled(inputs, "splitterFile"):
            outputs.extend([node_out / "splitter.bam", node_out / "splitter.bam.bai"])
        if _enabled(inputs, "unmappedFile"):
            outputs.append(node_out / "unmapped_reads.fastx")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        names = {
            "output.bam": "alignments",
            "output.bam.bai": "alignments_index",
            "discordant.bam": "discordant_alignments",
            "discordant.bam.bai": "discordant_alignments_index",
            "splitter.bam": "split_alignments",
            "splitter.bam.bai": "split_alignments_index",
            "unmapped_reads.fastx": "unmapped_reads",
        }
        return {names[path.name]: path for path in planned_paths}

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
