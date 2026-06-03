"""Long-read sequencing nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class ModkitPileupNode(CommandNode):
    """Generate bedMethyl pileups from modified-base BAM files."""
    NODE_ID = "modkit_pileup"
    DISPLAY_NAME = "Modkit Pileup"
    CATEGORY = "long_read"
    DESCRIPTION = (
        "Generate bedMethyl pileup from ONT BAM with MM/ML modified base tags. "
        "Single-base methylation resolution."
    )
    SEARCH_ALIASES = ["modkit", "methylation", "modified bases", "pileup", "bedmethyl", "5mc", "6ma"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("bedmethyl",)
    REQUIRED_EXECUTABLES = ["modkit"]
    REQUIRED_CONDA_PACKAGES = ["modkit"]
    DOCUMENTATION_URL = "https://github.com/nanoporetech/modkit"
    VERSION = "0.4.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "modkit",
            "pileup",
            str(inputs.get("bam", "")),
            f"{out_dir}/bedmethyl.bed",
            "--ref",
            str(inputs.get("reference", "")),
            "--threads",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("combine_strands"):
            cmd.append("--combine-strands")
        if inputs.get("region"):
            cmd.extend(["--region", str(inputs["region"])])
        if inputs.get("bedgraph"):
            cmd.append("--bedgraph")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "BAM with MM/ML modified base tags"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "combine_strands": ("BOOLEAN", {"default": True, "description": "Combine methylation from both strands"}),
                "region": ("STRING", {"default": "", "description": "Region (e.g., chr1:1-1000000)"}),
                "bedgraph": ("BOOLEAN", {"default": False, "description": "Also output bedGraph"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class ChopperFilterNode(CommandNode):
    """Filter and trim Oxford Nanopore reads with Chopper."""
    NODE_ID = "chopper_filter"
    DISPLAY_NAME = "Chopper Filter"
    CATEGORY = "long_read"
    DESCRIPTION = "Filter and trim ONT reads by quality, length. Replaces NanoFilt."
    SEARCH_ALIASES = ["chopper", "nanopore", "filter", "trim", "quality filter"]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("filtered_reads",)
    REQUIRED_EXECUTABLES = ["chopper"]
    REQUIRED_CONDA_PACKAGES = ["chopper"]
    DOCUMENTATION_URL = "https://github.com/wdecoster/chopper"
    VERSION = "0.9.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = ["chopper", "-i", str(inputs.get("reads", ""))]
        if inputs.get("min_quality"):
            cmd.extend(["-q", str(inputs["min_quality"])])
        if inputs.get("min_length"):
            cmd.extend(["-l", str(inputs["min_length"])])
        if inputs.get("max_length") and int(inputs["max_length"]) > 0:
            cmd.extend(["--maxlength", str(inputs["max_length"])])
        if inputs.get("headcrop"):
            cmd.extend(["--headcrop", str(inputs["headcrop"])])
        if inputs.get("tailcrop"):
            cmd.extend(["--tailcrop", str(inputs["tailcrop"])])
        if inputs.get("threads"):
            cmd.extend(["-t", str(inputs["threads"])])
        cmd.extend([">", f"{out_dir}/filtered_reads.fastq.gz"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Input FASTQ (can be gzipped)"}),
            },
            "optional": {
                "min_quality": ("INT", {"default": 10, "min": 0, "max": 30, "label": "Min Quality"}),
                "min_length": ("INT", {"default": 1000, "min": 0, "label": "Min Read Length"}),
                "max_length": ("INT", {"default": 0, "min": 0, "label": "Max Length (0=off)"}),
                "headcrop": ("INT", {"default": 0, "min": 0, "label": "Head Crop (bp)"}),
                "tailcrop": ("INT", {"default": 0, "min": 0, "label": "Tail Crop (bp)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class NanoPlotQCNode(CommandNode):
    """Generate long-read QC plots and summary statistics with NanoPlot."""
    NODE_ID = "nanoplot"
    DISPLAY_NAME = "NanoPlot QC"
    CATEGORY = "long_read"
    DESCRIPTION = "QC plots for ONT and PacBio data. Length, quality, yield histograms."
    SEARCH_ALIASES = ["nanoplot", "qc", "nanopore", "quality control", "read stats"]
    RETURN_TYPES = ("HTML_REPORT", "STATS_FILE")
    RETURN_NAMES = ("qc_report", "qc_stats")
    REQUIRED_EXECUTABLES = ["NanoPlot"]
    REQUIRED_CONDA_PACKAGES = ["nanoplot"]
    DOCUMENTATION_URL = "https://github.com/wdecoster/NanoPlot"
    VERSION = "1.44.1"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out_dir = Path(output_dir) / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return [out_dir / "NanoPlot-report.html", out_dir / "NanoStats.txt"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "NanoPlot",
            "--outdir",
            str(out_dir),
            "--threads",
            str(inputs.get("threads", 4)),
            "--format",
            str(inputs.get("plot_format", "png")),
            "--N50",
        ]
        if inputs.get("fastq"):
            cmd.extend(["--fastq", str(inputs["fastq"])])
        elif inputs.get("bam"):
            cmd.extend(["--bam", str(inputs["bam"])])
        elif inputs.get("summary"):
            cmd.extend(["--summary", str(inputs["summary"])])
        if inputs.get("max_length") and int(inputs["max_length"]) > 0:
            cmd.extend(["--maxlength", str(inputs["max_length"])])
        if inputs.get("min_length") and int(inputs["min_length"]) > 0:
            cmd.extend(["--minlength", str(inputs["min_length"])])
        if inputs.get("loglength"):
            cmd.append("--loglength")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq": ("FASTQ", {"description": "Input FASTQ (or use bam/summary)"}),
            },
            "optional": {
                "bam": ("BAM", {"description": "Input BAM (alternative)"}),
                "summary": ("FILE", {"description": "Sequencing summary from MinKNOW"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "plot_format": ("STRING", {"default": "png", "options": ["png", "jpg", "pdf"]}),
                "max_length": ("INT", {"default": 0, "min": 0}),
                "min_length": ("INT", {"default": 0, "min": 0}),
                "loglength": ("BOOLEAN", {"default": False, "description": "Log scale for lengths"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
