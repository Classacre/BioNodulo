"""Focused Samtools 1.23.1 owner: Generate pileup text from one or more BAM files."""

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
    _add_if_value,
    _as_list,
    _flag_sum,
    TOOLS_IUC_GIT_COMMIT,
    validate_index_pairs,
)


class SamtoolsMpileupNode(SamtoolsCommandNode):
    """Generate pileup text from one or more BAM files."""

    NODE_ID = "samtools_mpileup"
    DISPLAY_NAME = "Samtools Mpileup"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Generate pileup format text for one or more BAM files using samtools mpileup."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "mpileup", "pileup", "BAQ", "Base Alignment Quality"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("pileup",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-mpileup.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("pileup.pileup",)
    UPSTREAM_MANPAGE = "doc/samtools-mpileup.1"
    UPSTREAM_SOURCE = "bam_plcmd.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_mpileup/samtools_mpileup.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["samtools", "mpileup"]
        if inputs.get("reference"):
            cmd.extend(["-f", str(inputs["reference"])])
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["--rf", str(required_flags)])
        if skipped_flags:
            cmd.extend(["--ff", str(skipped_flags)])
        _add_if_value(cmd, "-r", inputs.get("region"))
        _add_if_value(cmd, "-l", inputs.get("positions_bed"))
        _add_if_value(cmd, "-G", inputs.get("exclude_read_groups"))
        if inputs.get("ignore_overlaps"):
            cmd.append("-x")
        if inputs.get("count_orphans"):
            cmd.append("-A")
        if inputs.get("disable_baq"):
            cmd.append("-B")
        if inputs.get("adjust_mq") is not None:
            cmd.extend(["-C", str(inputs.get("adjust_mq", 0))])
        if inputs.get("max_depth") is not None:
            cmd.extend(["-d", str(inputs.get("max_depth", 8000))])
        if inputs.get("redo_baq"):
            cmd.append("-E")
        if inputs.get("min_mq") is not None:
            cmd.extend(["-q", str(inputs.get("min_mq", 0))])
        if inputs.get("min_bq") is not None:
            cmd.extend(["-Q", str(inputs.get("min_bq", 13))])
        if inputs.get("illumina13"):
            cmd.append("-6")
        if inputs.get("output_bp"):
            cmd.append("-O")
        if inputs.get("output_mq"):
            cmd.append("-s")
        if inputs.get("output_qname"):
            cmd.append("--output-QNAME")
        if inputs.get("ignore_read_groups"):
            cmd.append("-R")
        if inputs.get("all_positions"):
            cmd.append(str(inputs["all_positions"]))
        _add_if_value(cmd, "--output-extra", inputs.get("output_extra"))
        cmd.extend(["--output", str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0])])
        bams = _as_list(inputs.get("input_bams", inputs.get("input", inputs.get("bam"))))
        indexes = _as_list(inputs.get("bam_indexes"))
        if indexes:
            cmd.append("-X")
        cmd.extend(bams)
        cmd.extend(indexes)
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("reference") or inputs.get("reference_index"):
            validation = validate_colocated_reference_index(inputs)
            if validation is not True:
                return validation
        has_reference = bool(inputs.get("reference"))
        if inputs.get("disable_baq") and not has_reference:
            return "disable_baq requires reference; BAQ is not active without -f"
        if inputs.get("redo_baq") and not has_reference:
            return "redo_baq requires reference"
        if inputs.get("disable_baq") and inputs.get("redo_baq"):
            return "disable_baq and redo_baq are mutually exclusive"
        adjust_mq = inputs.get("adjust_mq", 0)
        if isinstance(adjust_mq, int) and 0 < adjust_mq <= 10:
            return "adjust_mq must be 0 (disabled) or greater than 10; mpileup ignores -C values from 1 through 10"
        if isinstance(adjust_mq, int) and adjust_mq > 10 and not has_reference:
            return "adjust_mq requires reference"
        return validate_index_pairs(
            inputs,
            data_key="input_bams",
            index_key="bam_indexes",
            required=bool(inputs.get("region")),
        )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bams": ("BAM_LIST", {"description": "One or more indexed BAM files"}),
            },
            "optional": {
                "reference": ("FASTA", {"description": "Optional reference FASTA; enables BAQ"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated <reference>.fai index when a reference is supplied"},
                ),
                "bam_indexes": (
                    "FILE_LIST",
                    {"description": "One BAI or CSI index per BAM; required for region queries"},
                ),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Include reads with at least one listed SAM flag", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "region": ("STRING", {"default": "", "description": "Region such as chr17:100-150"}),
                "positions_bed": ("BED", {"description": "BED or positions file restricting pileup positions"}),
                "exclude_read_groups": (
                    "FILE",
                    {"description": "Read-group exclusion list", "advanced": True},
                ),
                "ignore_overlaps": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable read-pair overlap detection"},
                ),
                "count_orphans": ("BOOLEAN", {"default": False, "description": "Do not discard anomalous read pairs"}),
                "disable_baq": ("BOOLEAN", {"default": False, "description": "Disable BAQ computation"}),
                "adjust_mq": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Coefficient for downgrading mapping qualities"},
                ),
                "max_depth": ("INT", {"default": 8000, "min": 0, "description": "Maximum per-file depth"}),
                "redo_baq": ("BOOLEAN", {"default": False, "description": "Recalculate BAQ on the fly"}),
                "min_mq": ("INT", {"default": 0, "min": 0, "description": "Minimum mapping quality"}),
                "min_bq": ("INT", {"default": 13, "min": 0, "description": "Minimum base quality"}),
                "illumina13": (
                    "BOOLEAN",
                    {"default": False, "description": "Input quality is Illumina 1.3+ encoded", "advanced": True},
                ),
                "output_bp": (
                    "BOOLEAN",
                    {"default": False, "description": "Output base positions on reads", "advanced": True},
                ),
                "output_mq": (
                    "BOOLEAN",
                    {"default": False, "description": "Output mapping qualities", "advanced": True},
                ),
                "output_qname": (
                    "BOOLEAN",
                    {"default": False, "description": "Output read names", "advanced": True},
                ),
                "ignore_read_groups": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat all reads in each BAM as one sample", "advanced": True},
                ),
                "all_positions": (
                    "STRING",
                    {"default": "", "options": ["", "-a", "-aa"], "description": "Emit zero-depth positions"},
                ),
                "output_extra": (
                    "STRING",
                    {"default": "", "description": "Comma-separated extra tags to output", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
