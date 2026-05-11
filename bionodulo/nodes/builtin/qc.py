"""Quality control nodes for BioNodulo.

Provides nodes for running FastQC, MultiQC, and QualiMap to assess
sequencing data and alignment quality.
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class FastQCNode(CommandNode):
    """Run FastQC quality control on FASTQ reads."""
    NODE_ID = "fastqc"
    DISPLAY_NAME = "FastQC"
    CATEGORY = "qc"
    DESCRIPTION = "Run FastQC to generate per-base quality plots and reports"
    SEARCH_ALIASES = ["fastqc", "quality control", "qc", "reads qc"]
    RETURN_TYPES = ("QC_REPORT_DIR",)
    RETURN_NAMES = ("report_dir",)
    REQUIRED_EXECUTABLES = ["fastqc"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/fastqc/"
    VERSION = "0.12.1"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "fastqc",
            "--threads", str(inputs.get("threads", 2)),
            "--outdir", str(inputs.get("output", inputs.get("output_dir", "."))),
        ]
        if inputs.get("nogroup"):
            cmd.append("--nogroup")
        if inputs.get("kmers"):
            cmd.extend(["--kmers", str(inputs["kmers"])])
        if inputs.get("extract") is not False:
            cmd.append("--extract")
        reads = inputs.get("reads", "")
        if isinstance(reads, list):
            cmd.extend(reads)
        else:
            cmd.append(str(reads))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "FASTQ read file(s)"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "nogroup": ("BOOLEAN", {"default": False, "description": "Disable grouping of bases", "advanced": True}),
                "kmers": ("INT", {"default": 7, "min": 2, "max": 10, "description": "K-mer length", "advanced": True}),
                "extract": ("BOOLEAN", {"default": True, "description": "Extract ZIP archive", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MultiQCNode(CommandNode):
    """Aggregate QC reports with MultiQC."""
    NODE_ID = "multiqc"
    DISPLAY_NAME = "MultiQC"
    CATEGORY = "qc"
    DESCRIPTION = "Aggregate multiple QC reports into a single HTML report"
    SEARCH_ALIASES = ["multiqc", "aggregate qc", "report", "summary"]
    RETURN_TYPES = ("MULTIQC_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["multiqc"]
    DOCUMENTATION_URL = "https://multiqc.info/"
    VERSION = "1.21"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "multiqc",
            str(inputs.get("reports", "")),
            "--outdir", str(inputs.get("output", inputs.get("output_dir", "."))),
            "--filename", "multiqc_report.html",
        ]
        if inputs.get("title"):
            cmd.extend(["--title", str(inputs["title"])])
        if inputs.get("comment"):
            cmd.extend(["--comment", str(inputs["comment"])])
        if inputs.get("force"):
            cmd.append("--force")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reports": ("DIRECTORY", {"description": "Directory containing QC report files"}),
            },
            "optional": {
                "title": ("STRING", {"default": "BioNodulo QC Report", "label": "Report Title"}),
                "comment": ("STRING", {"default": "", "multiline": True, "label": "Comment", "advanced": True}),
                "force": ("BOOLEAN", {"default": False, "label": "Overwrite", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class QualiMapNode(CommandNode):
    """Run QualiMap BAM QC analysis."""
    NODE_ID = "qualimap_bamqc"
    DISPLAY_NAME = "QualiMap BAM QC"
    CATEGORY = "qc"
    DESCRIPTION = "Comprehensive BAM quality analysis with QualiMap"
    SEARCH_ALIASES = ["qualimap", "bamqc", "bam qc", "alignment qc"]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["qualimap"]
    DOCUMENTATION_URL = "http://qualimap.conesalab.org/"
    VERSION = "2.3"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "qualimap", "bamqc",
            "-bam", str(inputs.get("bam", "")),
            "-outdir", str(inputs.get("output", inputs.get("output_dir", "."))),
            "-nt", str(inputs.get("threads", 2)),
        ]
        if inputs.get("feature_file"):
            cmd.extend(["-gff", str(inputs["feature_file"])])
        if inputs.get("paint_chromosome_limits"):
            cmd.append("--paint-chromosome-limits")
        if inputs.get("collect_overlap_pairs"):
            cmd.append("--collect-overlap-pairs")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM alignment file"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "feature_file": ("GFF_GTF", {"description": "Optional GFF/GTF for feature coverage", "advanced": True}),
                "paint_chromosome_limits": ("BOOLEAN", {"default": False, "advanced": True}),
                "collect_overlap_pairs": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
