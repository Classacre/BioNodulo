"""Read trimming and filtering nodes for BioNodulo.

Provides nodes for adapter trimming and quality filtering using
fastp, Trimmomatic, and Cutadapt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class FastpNode(CommandNode):
    """Adapter trimming and quality filtering with fastp."""
    NODE_ID = "fastp"
    DISPLAY_NAME = "fastp Trim"
    REQUIRED_CONDA_PACKAGES = ['fastp']
    CATEGORY = "trimming"
    DESCRIPTION = "Ultra-fast all-in-one FASTQ preprocessor: trim adapters, filter by quality"
    SEARCH_ALIASES = ["fastp", "trim", "adapter", "quality filter"]
    RETURN_TYPES = ("FASTQ_LIST", "HTML_REPORT",)
    RETURN_NAMES = ("trimmed_reads", "report",)
    REQUIRED_EXECUTABLES = ["fastp"]
    DOCUMENTATION_URL = "https://github.com/OpenGene/fastp"
    VERSION = "0.23.4"
    COMMAND = [
        "fastp",
        "-i", "{inputs.reads[0]}",
        "-I", "{inputs.reads[1]}",
        "-o", "{output}/trimmed_R1.fastq.gz",
        "-O", "{output}/trimmed_R2.fastq.gz",
        "-h", "{output}/fastp_report.html",
        "-j", "{output}/fastp_report.json",
        "-w", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "qualified_quality_phred": ("INT", {"default": 15, "min": 1, "max": 40}),
                "cut_front": ("BOOLEAN", {"default": True}),
                "cut_tail": ("BOOLEAN", {"default": True}),
                "length_required": ("INT", {"default": 20, "min": 1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run fastp and return paired trimmed reads as a list."""
        output_dir = kwargs.get("output_dir")
        ctx = kwargs.get("context")
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        raw = await super().run(**kwargs)
        out = Path(output_dir)
        return {
            "outputs": {
                "trimmed_reads": [
                    str(out / "trimmed_R1.fastq.gz"),
                    str(out / "trimmed_R2.fastq.gz"),
                ],
                "report": str(out / "fastp_report.html"),
            }
        }


class TrimmomaticNode(CommandNode):
    """Adapter trimming with Trimmomatic."""
    NODE_ID = "trimmomatic"
    DISPLAY_NAME = "Trimmomatic"
    REQUIRED_CONDA_PACKAGES = ['trimmomatic']
    CATEGORY = "trimming"
    DESCRIPTION = "Flexible read trimming tool for Illumina NGS data"
    SEARCH_ALIASES = ["trimmomatic", "trim", "adapter removal"]
    RETURN_TYPES = ("FASTQ_LIST",)
    RETURN_NAMES = ("trimmed_reads",)
    REQUIRED_EXECUTABLES = ["trimmomatic"]
    DOCUMENTATION_URL = "http://www.usadellab.org/cms/?page=trimmomatic"
    VERSION = "0.39"
    COMMAND = [
        "trimmomatic", "PE",
        "-threads", "{inputs.threads}",
        "{inputs.reads[0]}",
        "{inputs.reads[1]}",
        "{output}/trimmed_R1_paired.fastq.gz",
        "{output}/trimmed_R1_unpaired.fastq.gz",
        "{output}/trimmed_R2_paired.fastq.gz",
        "{output}/trimmed_R2_unpaired.fastq.gz",
        "ILLUMINACLIP:{inputs.adapters}:2:30:10",
        "LEADING:{inputs.leading}",
        "TRAILING:{inputs.trailing}",
        "SLIDINGWINDOW:4:{inputs.quality}",
        "MINLEN:{inputs.minlen}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "adapters": ("STRING", {"default": "TruSeq3-PE.fa"}),
            },
            "optional": {
                "leading": ("INT", {"default": 3, "min": 1, "max": 40}),
                "trailing": ("INT", {"default": 3, "min": 1, "max": 40}),
                "quality": ("INT", {"default": 15, "min": 1, "max": 40}),
                "minlen": ("INT", {"default": 36, "min": 1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CutadaptNode(CommandNode):
    """Adapter trimming with Cutadapt."""
    NODE_ID = "cutadapt"
    DISPLAY_NAME = "Cutadapt"
    CATEGORY = "trimming"
    DESCRIPTION = "Remove adapter sequences from high-throughput sequencing reads"
    SEARCH_ALIASES = ["cutadapt", "trim adapters", "adapter"]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("trimmed_reads",)
    REQUIRED_EXECUTABLES = ["cutadapt"]
    REQUIRED_CONDA_PACKAGES = ['cutadapt']
    DOCUMENTATION_URL = "https://cutadapt.readthedocs.io/"
    VERSION = "4.9"
    COMMAND = [
        "cutadapt",
        "-a", "{inputs.adapter_r1}",
        "-A", "{inputs.adapter_r2}",
        "-o", "{output}/trimmed_R1.fastq.gz",
        "-p", "{output}/trimmed_R2.fastq.gz",
        "-j", "{inputs.threads}",
        "{inputs.reads[0]}",
        "{inputs.reads[1]}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "adapter_r1": ("STRING", {"default": "AGATCGGAAGAGC"}),
            },
            "optional": {
                "adapter_r2": ("STRING", {"default": "AGATCGGAAGAGC"}),
                "minimum_length": ("INT", {"default": 20, "min": 1}),
                "quality_cutoff": ("INT", {"default": 20, "min": 1, "max": 40}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
