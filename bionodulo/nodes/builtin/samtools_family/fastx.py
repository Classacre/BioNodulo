"""Focused Samtools 1.23.1 owner: Extract FASTA or FASTQ reads from SAM/BAM/CRAM alignment files."""

from __future__ import annotations

import re
from pathlib import Path

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _add_if_value,
    _additional_threads,
    _as_list,
    _flag_sum,
    TOOLS_IUC_GIT_COMMIT,
)


class SamtoolsFastxNode(SamtoolsCommandNode):
    """Extract FASTA or FASTQ reads from SAM/BAM/CRAM alignment files."""

    NODE_ID = "samtools_fastx"
    DISPLAY_NAME = "Samtools Fastx"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Extract FASTA or FASTQ reads from alignment files, with optional read-pair and index-read outputs."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "fastx", "bam2fq", "FASTQ extraction", "FASTA extraction"]
    RETURN_TYPES = ("FILE", "FILE", "FILE", "FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("reads", "read1", "read2", "singletons", "nonspecific", "index1", "index2")
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-fasta.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    SHELL = True
    OUTPUT_FILENAMES = (
        "reads.fasta",
        "read1.fasta",
        "read2.fasta",
        "singletons.fasta",
        "nonspecific.fasta",
        "index1.fasta",
        "index2.fasta",
    )
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-fasta.1"
    UPSTREAM_SOURCE = "bam_fastq.c"
    UPSTREAM_COLLATE_MANPAGE = "doc/samtools-collate.1"
    UPSTREAM_COLLATE_SOURCE = "bamshuf.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_fastx/samtools_fastx.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        input_path = str(inputs.get("input", ""))
        output_format = cls._output_format(inputs)
        extension = cls._output_extension(output_format)
        command = "fastq" if output_format == "fastq" else "fasta"
        addthreads = str(_additional_threads(inputs))

        if inputs.get("name_sorted"):
            cmd: list[str] = []
            fastx_input = input_path
        else:
            cmd = [
                "samtools",
                "collate",
                "-@",
                addthreads,
                "-O",
                "-u",
                input_path,
                "|",
            ]
            fastx_input = "-"

        cmd.extend(["samtools", command, "-@", addthreads])
        if command == "fastq":
            _add_if_value(cmd, "-v", inputs.get("default_quality"))
            if inputs.get("output_quality"):
                cmd.append("-O")
            if inputs.get("illumina_casava"):
                cmd.append("-i")
        if inputs.get("copy_tags"):
            cmd.append("-t")
        _add_if_value(cmd, "-T", inputs.get("copy_arbitrary_tags"))
        if inputs.get("read_numbering"):
            cmd.append(str(inputs["read_numbering"]))

        outputs = set(_as_list(inputs.get("outputs", ["other"])))
        if "nonspecific" in outputs:
            cmd.extend(["-0", str(output / f"nonspecific.{extension}")])
        if "read1" in outputs:
            cmd.extend(["-1", str(output / f"read1.{extension}")])
        if "read2" in outputs:
            cmd.extend(["-2", str(output / f"read2.{extension}")])
        if "singletons" in outputs:
            cmd.extend(["-s", str(output / f"singletons.{extension}")])

        required_flags = _flag_sum(inputs.get("required_flags"))
        include_any_flags = _flag_sum(inputs.get("include_any_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        skipped_flags_all = _flag_sum(inputs.get("skipped_flags_all"))
        if required_flags:
            cmd.extend(["-f", str(required_flags)])
        if include_any_flags:
            cmd.extend(["--rf", str(include_any_flags)])
        if skipped_flags:
            cmd.extend(["-F", str(skipped_flags)])
        if skipped_flags_all:
            cmd.extend(["-G", str(skipped_flags_all)])

        index_options_active = bool(
            inputs.get("write_index_reads") or inputs.get("illumina_casava")
        )
        if inputs.get("write_index_reads"):
            if inputs.get("write_i1", True):
                cmd.extend(["--i1", str(output / f"index1.{extension}")])
            if inputs.get("write_i2", True):
                cmd.extend(["--i2", str(output / f"index2.{extension}")])
        if index_options_active:
            _add_if_value(cmd, "--index-format", inputs.get("index_format"))
            _add_if_value(cmd, "--barcode-tag", inputs.get("barcode_tag"))
            _add_if_value(cmd, "--quality-tag", inputs.get("quality_tag"))

        cmd.append(fastx_input)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        extension = cls._output_extension(cls._output_format(inputs))
        return [
            node_out / f"reads.{extension}",
            node_out / f"read1.{extension}",
            node_out / f"read2.{extension}",
            node_out / f"singletons.{extension}",
            node_out / f"nonspecific.{extension}",
            node_out / f"index1.{extension}",
            node_out / f"index2.{extension}",
        ]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        for output in outputs:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.touch()

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        output_format = cls._output_format(inputs)
        default_quality = inputs.get("default_quality")
        if default_quality not in (None, "") and not 0 <= default_quality <= 93:
            return "default_quality must be between 0 and 93"
        has_fastq_only_option = bool(inputs.get("output_quality")) or any(
            inputs.get(key) not in (None, "") for key in ("default_quality", "quality_tag")
        )
        if output_format != "fastq" and has_fastq_only_option:
            return "FASTQ quality options require output_format=fastq"
        index_format = str(inputs.get("index_format", "") or "").strip()
        index_options_active = bool(
            inputs.get("write_index_reads") or inputs.get("illumina_casava")
        )
        if index_options_active and not index_format:
            return "index_format is required for index-read or Illumina Casava output"
        if not index_options_active and any(
            inputs.get(key) not in (None, "")
            for key in ("index_format", "barcode_tag", "quality_tag")
        ):
            return "index_format, barcode_tag, and quality_tag require index-read or Illumina Casava output"
        if index_options_active:
            if re.fullmatch(r"(?:[in](?:[1-9][0-9]*|\*))+", index_format) is None:
                return "index_format must contain documented i/n segments with a positive length or '*'"
            index_count = index_format.count("i")
            if index_count not in (1, 2):
                return "index_format must define one or two index reads"
            if inputs.get("write_index_reads"):
                write_i1 = bool(inputs.get("write_i1", True))
                write_i2 = bool(inputs.get("write_i2", True))
                if not write_i1 and not write_i2:
                    return "write_index_reads requires at least one selected index output"
                if write_i2 and index_count < 2:
                    return "write_i2 requires index_format to define two index reads"
        if inputs.get("write_i2", True) and not inputs.get("write_i1", True):
            return "write_i2 requires write_i1"
        return True

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        raw_format = str(inputs.get("output_format", inputs.get("output_fmt_select", "fasta")) or "fasta").lower()
        if raw_format in {"fastq", "fastqsanger", "fastqsanger.gz", "fastq.gz"}:
            return "fastq"
        return "fasta"

    @classmethod
    def _output_extension(cls, output_format: str) -> str:
        return "fastq" if output_format == "fastq" else "fasta"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (("SAM", "BAM", "CRAM"), {"description": "SAM, BAM, or CRAM alignment file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "name_sorted": (
                    "BOOLEAN",
                    {"default": False, "description": "Input is already query-name sorted"},
                ),
                "output_format": (
                    "STRING",
                    {"default": "fasta", "options": ["fasta", "fastq"], "description": "Extract FASTA or FASTQ"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": ["other"],
                        "options": ["other", "read1", "read2", "singletons", "nonspecific"],
                        "description": "Read subsets to split into dedicated files",
                    },
                ),
                "default_quality": (
                    "INT",
                    {"default": "", "min": 0, "description": "Default FASTQ quality if none is present"},
                ),
                "output_quality": (
                    "BOOLEAN",
                    {"default": False, "description": "Use OQ tag quality values when available", "advanced": True},
                ),
                "illumina_casava": (
                    "BOOLEAN",
                    {"default": False, "description": "Add Illumina Casava 1.8 header fields", "advanced": True},
                ),
                "copy_tags": (
                    "BOOLEAN",
                    {"default": False, "description": "Copy RG, BC, and QT tags to sequence headers"},
                ),
                "copy_arbitrary_tags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated tags to copy to FASTA headers", "advanced": True},
                ),
                "read_numbering": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "-n", "-N"],
                        "description": "Control /1 and /2 read-name suffixes",
                        "advanced": True,
                    },
                ),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags that must be set", "advanced": True},
                ),
                "include_any_flags": (
                    "STRING",
                    {"default": "", "description": "Require at least one listed SAM flag", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "skipped_flags_all": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Comma-separated SAM flags that must not all be set",
                        "advanced": True,
                    },
                ),
                "write_index_reads": (
                    "BOOLEAN",
                    {"default": False, "description": "Write index reads from barcode tags", "advanced": True},
                ),
                "write_i1": (
                    "BOOLEAN",
                    {"default": True, "description": "Write first index read output", "advanced": True},
                ),
                "write_i2": (
                    "BOOLEAN",
                    {"default": True, "description": "Write second index read output", "advanced": True},
                ),
                "index_format": (
                    "STRING",
                    {"default": "", "description": "Index-format string for parsing barcode tags", "advanced": True},
                ),
                "barcode_tag": (
                    "STRING",
                    {"default": "", "description": "Barcode tag name, default BC in samtools", "advanced": True},
                ),
                "quality_tag": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Barcode quality tag name, default QT in samtools",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
