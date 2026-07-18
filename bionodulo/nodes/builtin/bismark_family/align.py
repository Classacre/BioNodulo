"""Bismark short-read alignment against a prepared Bowtie2 genome bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BismarkCommandNode, path_value, validate_prepared_genome


class BismarkAlignNode(BismarkCommandNode):
    """Align one single-end read file or one ordered paired-end read set."""

    NODE_ID = "bismark_align"
    DISPLAY_NAME = "Bismark Align"
    DESCRIPTION = "Align single-end or paired-end bisulfite reads to a prepared Bowtie2 genome"
    SEARCH_ALIASES = ["bismark", "bisulfite", "wgbs", "rrbs", "methylation", "align"]
    RETURN_TYPES = ("BAM", "TXT")
    RETURN_NAMES = ("aligned_bam", "alignment_report")
    REQUIRED_EXECUTABLES = ["bismark", "bowtie2"]
    DOCUMENTATION_URL = "https://felixkrueger.github.io/Bismark/options/alignment/"
    UPSTREAM_SOURCE = "rust/bismark/src/aligner"
    OUTPUT_BASENAME = "aligned_bam"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Single-end reads or paired-end mate 1"}),
                "genome_folder": (
                    "DIRECTORY",
                    {"description": "Prepared genome with raw FASTA and complete CT/GA Bowtie2 indexes"},
                ),
                "parallel_instances": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Concurrent Bismark instances"},
                ),
            },
            "optional": {
                "r2": ("FASTQ", {"description": "Paired-end mate 2"}),
                "non_directional": (
                    "BOOLEAN",
                    {"default": False, "description": "Use all four bisulfite strands"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _paired(cls, inputs: dict[str, Any]) -> bool:
        return path_value(inputs.get("r2")) is not None

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if cls._paired(inputs):
            return [
                node_out / f"{cls.OUTPUT_BASENAME}_pe.bam",
                node_out / f"{cls.OUTPUT_BASENAME}_PE_report.txt",
            ]
        return [
            node_out / f"{cls.OUTPUT_BASENAME}.bam",
            node_out / f"{cls.OUTPUT_BASENAME}_SE_report.txt",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ("r1", "r2"):
            if name == "r2" and not inputs.get(name):
                continue
            value = path_value(inputs.get(name))
            if value is None:
                return f"Input '{name}' must be a non-empty path-like value"
            if not Path(value).is_file():
                return f"Bismark read file not found: {value}"

        genome_folder = path_value(inputs.get("genome_folder"))
        if genome_folder is None:
            return "Input 'genome_folder' must be a non-empty path-like value"
        try:
            validate_prepared_genome(genome_folder)
        except (OSError, ValueError) as exc:
            return str(exc)

        parallel = inputs.get("parallel_instances", 1)
        if isinstance(parallel, bool) or not isinstance(parallel, int):
            return "parallel_instances must be an integer"
        if parallel < 1:
            return "parallel_instances must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "bismark",
            "--genome",
            str(inputs.get("genome_folder", "")),
            "--output_dir",
            str(output),
            "--basename",
            cls.OUTPUT_BASENAME,
            "--parallel",
            str(inputs.get("parallel_instances", 1)),
        ]
        if inputs.get("non_directional", False):
            command.append("--non_directional")
        if cls._paired(inputs):
            command.extend(["-1", str(inputs.get("r1", "")), "-2", str(inputs.get("r2", ""))])
        else:
            command.append(str(inputs.get("r1", "")))
        return command
