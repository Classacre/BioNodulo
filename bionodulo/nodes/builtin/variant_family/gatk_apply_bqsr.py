"""GATK 4.6.2.0 ApplyBQSR node."""

from __future__ import annotations

from typing import Any

from .gatk_adapter import (
    GATKCommandNode,
    validate_gatk_bam_index,
    validate_path_input,
    validate_reference_bundle,
)


class GatkApplyBQSRNode(GATKCommandNode):
    """Apply a BQSR table and retain GATK's source-generated BAM index."""

    NODE_ID = "gatk_apply_bqsr"
    DISPLAY_NAME = "GATK ApplyBQSR"
    DESCRIPTION = "Apply base-quality recalibration to a coordinate-sorted BAM"
    SEARCH_ALIASES = ["gatk", "apply bqsr", "recalibrate", "base quality"]
    RETURN_TYPES = ("BAM", "BAI")
    RETURN_NAMES = ("bam", "bam_index")
    OUTPUT_FILENAMES = ("recalibrated.bam", "recalibrated.bai")
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037055952-ApplyBQSR"
    UPSTREAM_SOURCE = "src/main/java/org/broadinstitute/hellbender/tools/walkers/bqsr/ApplyBQSR.java"
    UPSTREAM_WRITER_SOURCE = "src/main/java/org/broadinstitute/hellbender/utils/read/ReadUtils.java"
    UPSTREAM_INDEX_SOURCE = (
        "htsjdk 4.2.0:src/main/java/htsjdk/samtools/BAMFileWriter.java"
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted BAM used to build the BQSR table"}),
                "bam_index": (
                    "BAI",
                    {"description": "Exact colocated <stem>.bai or <bam>.bai index"},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with colocated FAI and sequence dictionary"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai sidecar"},
                ),
                "sequence_dictionary": (
                    "SEQUENCE_DICTIONARY",
                    {"description": "Exact extension-replaced <reference>.dict sidecar"},
                ),
                "recal_table": (
                    ("TABLE", "FILE"),
                    {"description": "Recalibration table produced from this BAM"},
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_gatk_bam_index(inputs)
        if validation is not True:
            return validation
        validation = validate_reference_bundle(inputs)
        if validation is not True:
            return validation
        return validate_path_input(inputs, key="recal_table")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "ApplyBQSR")
        command.extend(
            [
                "-R",
                str(inputs["reference"]),
                "-I",
                str(inputs["bam"]),
                "--bqsr-recal-file",
                str(inputs["recal_table"]),
                "-O",
                str(cls.output_path(inputs)),
                "--create-output-bam-index",
                "true",
            ]
        )
        return command
