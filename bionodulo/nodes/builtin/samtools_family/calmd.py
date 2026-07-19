"""Focused Samtools 1.23.1 owner: Recalculate MD/NM tags and optional BAQ values in a BAM file."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _additional_threads,
)


class SamtoolsCalmdNode(SamtoolsCommandNode):
    """Recalculate MD/NM tags and optional BAQ values in a BAM file."""

    NODE_ID = "samtools_calmd"
    DISPLAY_NAME = "Samtools Calmd"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Recalculate MD and NM tags against a reference FASTA, optionally adding BAQ-adjusted qualities."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "calmd", "MD tags", "NM tags", "BAQ", "Base Alignment Quality"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("calmd_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-calmd.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("calmd.bam",)
    SHELL = True
    UPSTREAM_MANPAGE = "doc/samtools-calmd.1"
    UPSTREAM_SOURCE = "bam_md.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["samtools", "calmd"]
        if inputs.get("calculate_baq"):
            cmd.append("-r")
            if inputs.get("modify_quality"):
                cmd.append("-A")
            if inputs.get("extended_baq"):
                cmd.append("-E")
        if inputs.get("change_identical"):
            cmd.append("-e")
        adjust_mq = int(inputs.get("adjust_mq", 0) or 0)
        if adjust_mq:
            cmd.extend(["-C", str(adjust_mq)])
        cmd.extend(
            [
                "-b",
                "-@",
                str(_additional_threads(inputs)),
                str(inputs.get("input", inputs.get("bam", ""))),
                str(inputs.get("reference", "")),
                ">",
                str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            ]
        )
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_colocated_reference_index(inputs)
        if validation is not True:
            return validation
        if inputs.get("modify_quality") and not inputs.get("calculate_baq"):
            return "modify_quality requires calculate_baq"
        if inputs.get("extended_baq") and not inputs.get("calculate_baq"):
            return "extended_baq requires calculate_baq"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM file to recalculate"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for the alignment"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated <reference>.fai index consumed by calmd"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "calculate_baq": ("BOOLEAN", {"default": False, "description": "Calculate BAQ scores"}),
                "modify_quality": (
                    "BOOLEAN",
                    {"default": False, "description": "Use BAQ to cap read base qualities", "advanced": True},
                ),
                "extended_baq": (
                    "BOOLEAN",
                    {"default": False, "description": "Use extended BAQ calculation", "advanced": True},
                ),
                "change_identical": (
                    "BOOLEAN",
                    {"default": False, "description": "Change reference-identical bases to '='", "advanced": True},
                ),
                "adjust_mq": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 255,
                        "description": "Coefficient for capping mapping quality of poorly mapped reads",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
