"""Bismark methylation extraction with stable, documented report outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    BISMARK_VERSION,
    BismarkCommandNode,
    bismark_source_urls,
    discover_fasta_files,
    extractor_report_names,
    path_value,
)


class BismarkMethylationExtractorNode(BismarkCommandNode):
    """Extract methylation calls while exposing only unconditional artifacts."""

    LEGACY_NODE_ID = "bismark_methylation_extractor"
    DISPLAY_NAME = "Bismark Methylation Extractor"
    DESCRIPTION = "Extract methylation calls and guaranteed M-bias and splitting reports from a Bismark BAM"
    SEARCH_ALIASES = ["bismark", "methylation", "methylation extractor", "cpg", "cytosine", "bedgraph", "bisulfite"]
    RETURN_TYPES = ("DIRECTORY", "TXT", "TXT")
    RETURN_NAMES = ("methylation_output", "mbias_report", "splitting_report")
    REQUIRED_EXECUTABLES = ["bismark_methylation_extractor"]
    REQUIRED_CONDA_PACKAGES = ["bismark"]
    CONDA_PACKAGE_CONSTRAINTS = {"bismark": BISMARK_VERSION}
    PACKAGE_CONSTRAINTS = (f"bismark=={BISMARK_VERSION}",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    DOCUMENTATION_URL = "https://felixkrueger.github.io/Bismark/options/methylation-extraction/"
    UPSTREAM_SOURCE = "rust/bismark/src/extractor"
    SOURCE_PATHS = (
        "rust/bismark/src/extractor/cli.rs",
        "rust/bismark/src/extractor/pipeline.rs",
        "rust/bismark/src/extractor/mbias_writer.rs",
        "rust/bismark/src/extractor/downstream_filenames.rs",
    )
    SOURCE_URLS = bismark_source_urls(*SOURCE_PATHS)
    OUTPUT_DIRECTORY = "methylation_output"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Bismark-aligned BAM"}),
                "multicore": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Extraction worker count"},
                ),
            },
            "optional": {
                "cytosine_report": (
                    "BOOLEAN",
                    {"default": False, "description": "Produce a genome-wide CpG report"},
                ),
                "genome_folder": (
                    "DIRECTORY",
                    {"description": "Folder containing top-level FASTA for a cytosine report"},
                ),
                "no_overlap": (
                    "BOOLEAN",
                    {"default": True, "description": "Drop overlapping read-2 calls in paired-end BAMs"},
                ),
                "merge_non_cpg": (
                    "BOOLEAN",
                    {"default": False, "description": "Merge CHG and CHH split outputs"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output = node_out / cls.OUTPUT_DIRECTORY
        mbias, splitting = extractor_report_names(inputs.get("bam"))
        return [output, output / mbias, output / splitting]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        bam = path_value(inputs.get("bam"))
        if bam is None:
            return "Input 'bam' must be a non-empty path-like value"
        if not Path(bam).is_file():
            return f"Bismark BAM file not found: {bam}"

        multicore = inputs.get("multicore", 1)
        if isinstance(multicore, bool) or not isinstance(multicore, int):
            return "multicore must be an integer"
        if multicore < 1:
            return "multicore must be at least 1"

        if inputs.get("cytosine_report", False):
            genome_folder = path_value(inputs.get("genome_folder"))
            if genome_folder is None:
                return "genome_folder is required when cytosine_report is enabled"
            try:
                discover_fasta_files(genome_folder)
            except (OSError, ValueError) as exc:
                return str(exc)
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / cls.OUTPUT_DIRECTORY
        command = [
            "bismark_methylation_extractor",
            "--bedGraph",
            "--comprehensive",
            "--gzip",
            "--multicore",
            str(inputs.get("multicore", 1)),
            "--output_dir",
            str(output),
        ]
        if inputs.get("cytosine_report", False):
            command.extend(
                [
                    "--cytosine_report",
                    "--genome_folder",
                    str(inputs.get("genome_folder", "")),
                ]
            )
        if inputs.get("no_overlap", True) is False:
            command.extend(["--paired-end", "--include_overlap"])
        if inputs.get("merge_non_cpg", False):
            command.append("--merge_non_CpG")
        command.append(str(inputs.get("bam", "")))
        return command


class BismarkMethylationNode(BismarkMethylationExtractorNode):
    """Compatibility alias for the original Bismark methylation node ID."""

    LEGACY_NODE_ID = "bismark_methylation"
    DISPLAY_NAME = "Bismark Methylation"
    DESCRIPTION = "Extract methylation calls from a Bismark-aligned BAM"
