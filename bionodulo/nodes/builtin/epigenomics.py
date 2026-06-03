"""Epigenomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class BismarkAlignNode(CommandNode):
    """Align bisulfite sequencing reads with Bismark."""
    NODE_ID = "bismark_align"
    DISPLAY_NAME = "Bismark Align"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Align bisulfite sequencing reads (WGBS, RRBS) to reference. Directional and non-directional."
    SEARCH_ALIASES = ["bismark", "bisulfite", "wgbs", "rrbs", "methylation", "align"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("aligned_bam",)
    REQUIRED_EXECUTABLES = ["bismark"]
    REQUIRED_CONDA_PACKAGES = ["bismark"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/bismark/"
    VERSION = "0.24.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        r1 = str(inputs.get("r1", ""))
        cmd = [
            "bismark",
            "--genome",
            str(inputs.get("genome_folder", "")),
            "-o",
            str(out_dir),
            "--parallel",
            str(inputs.get("parallel_instances", 1)),
            "-p",
        ]
        if inputs.get("r2"):
            cmd.extend(["-1", r1, "-2", str(inputs["r2"])])
        else:
            cmd.append(r1)
        if inputs.get("non_directional"):
            cmd.append("--non_directional")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward bisulfite reads (R1)"}),
                "genome_folder": ("DIRECTORY", {"description": "Bismark-prepared genome folder"}),
                "parallel_instances": ("INT", {"default": 1, "min": 1, "max": 16}),
            },
            "optional": {
                "r2": ("FASTQ", {"description": "Reverse reads (R2, paired)"}),
                "non_directional": ("BOOLEAN", {"default": False, "description": "Non-directional library (PBAT)"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BismarkMethylationExtractorNode(CommandNode):
    """Extract methylation calls from Bismark-aligned BAM files."""
    NODE_ID = "bismark_methylation_extractor"
    DISPLAY_NAME = "Bismark Methylation Extractor"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Extract methylation calls from Bismark BAM. Outputs CpG/CHG/CHH bedGraph and coverage."
    SEARCH_ALIASES = ["bismark", "methylation", "methylation extractor", "cpg", "cytosine", "bedgraph", "bisulfite"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("methylation_output",)
    REQUIRED_EXECUTABLES = ["bismark_methylation_extractor"]
    REQUIRED_CONDA_PACKAGES = ["bismark"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/bismark/"
    VERSION = "0.24.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bismark_methylation_extractor",
            "--bedGraph",
            "--comprehensive",
            "--gzip",
            "--multicore",
            str(inputs.get("multicore", 1)),
            "--output",
            str(inputs.get("output", ".")),
        ]
        if inputs.get("cytosine_report"):
            cmd.append("--cytosine_report")
            cmd.extend(["--genome_folder", str(inputs.get("genome_folder", ""))])
        if inputs.get("no_overlap"):
            cmd.append("--no_overlap")
        if inputs.get("merge_non_cpg"):
            cmd.append("--merge_non_CpG")
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "methylation_output"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Bismark-aligned BAM"}),
                "multicore": ("INT", {"default": 1, "min": 1, "max": 16}),
            },
            "optional": {
                "cytosine_report": ("BOOLEAN", {"default": True, "description": "Genome-wide cytosine report"}),
                "genome_folder": ("DIRECTORY", {"description": "Genome folder (for cytosine report)"}),
                "no_overlap": ("BOOLEAN", {"default": True}),
                "merge_non_cpg": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
