"""ChIP-seq analysis nodes for BioNodulo.

Provides nodes for peak calling (MACS2), BEDTools manipulation,
and coverage track generation (deepTools).
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class MACS2CallpeakNode(CommandNode):
    """Call peaks from ChIP-seq data with MACS2."""
    NODE_ID = "macs2_callpeak"
    DISPLAY_NAME = "MACS2 Callpeak"
    CATEGORY = "chip_seq"
    DESCRIPTION = "Model-based Analysis of ChIP-Seq: identify transcription factor binding sites"
    SEARCH_ALIASES = ["macs2", "peak calling", "chip-seq", "binding sites"]
    RETURN_TYPES = ("NARROW_PEAK", "BIGWIG")
    RETURN_NAMES = ("peaks", "signal")
    REQUIRED_EXECUTABLES = ["macs2"]
    DOCUMENTATION_URL = "https://github.com/macs3-project/MACS"
    VERSION = "2.2.9.1"
    COMMAND = [
        "macs2", "callpeak",
        "-t", "{inputs.treatment}",
        "-c", "{inputs.control}",
        "-n", "{inputs.name}",
        "--outdir", "{output}",
        "-f", "BAM",
        "-g", "{inputs.genome_size}",
        "--bdg",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "treatment": ("BAM", {"description": "Treatment/ChIP BAM file"}),
                "control": ("BAM", {"description": "Control/input BAM file"}),
                "name": ("STRING", {"default": "peaks"}),
                "genome_size": ("STRING", {"default": "hs", "description": "hs, mm, dm, ce, or numeric bp"}),
            },
            "optional": {
                "qvalue": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "format": ("STRING", {"default": "BAM"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BEDToolsIntersectNode(CommandNode):
    """Intersect two BED/BAM files."""
    NODE_ID = "bedtools_intersect"
    DISPLAY_NAME = "BEDTools Intersect"
    CATEGORY = "chip_seq"
    DESCRIPTION = "Find overlapping intervals between two BED files"
    SEARCH_ALIASES = ["bedtools", "intersect", "overlap", "bed"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("intersection",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/"
    VERSION = "2.31.1"
    SHELL = True
    COMMAND = [
        "bedtools", "intersect",
        "-a", "{inputs.a}",
        "-b", "{inputs.b}",
        ">", "{output}/intersect.bed",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "a": ("BED", {"description": "First BED/BAM/VCF/GFF file"}),
                "b": ("BED", {"description": "Second BED/BAM/VCF/GFF file"}),
            },
            "optional": {
                "wa": ("BOOLEAN", {"default": False}),
                "wb": ("BOOLEAN", {"default": False}),
                "f": ("FLOAT", {"default": 1e-09, "min": 0.0, "max": 1.0, "description": "Minimum overlap fraction"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BEDToolsCoverageNode(CommandNode):
    """Compute coverage of BED intervals."""
    NODE_ID = "bedtools_coverage"
    DISPLAY_NAME = "BEDTools Coverage"
    CATEGORY = "chip_seq"
    DESCRIPTION = "Compute read coverage over BED intervals"
    SEARCH_ALIASES = ["bedtools", "coverage", "depth", "intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("coverage",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/"
    VERSION = "2.31.1"
    SHELL = True
    COMMAND = [
        "bedtools", "coverage",
        "-a", "{inputs.a}",
        "-b", "{inputs.b}",
        ">", "{output}/coverage.bed",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "a": ("BED", {"description": "Intervals BED file"}),
                "b": ("BAM", {"description": "Reads BAM file"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DeepToolsBamCoverageNode(CommandNode):
    """Generate coverage tracks with deepTools bamCoverage."""
    NODE_ID = "deeptools_bamcoverage"
    DISPLAY_NAME = "deepTools bamCoverage"
    CATEGORY = "chip_seq"
    DESCRIPTION = "Generate BigWig coverage tracks from a BAM file"
    SEARCH_ALIASES = ["deeptools", "bamcoverage", "bigwig", "coverage track"]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("bigwig",)
    REQUIRED_EXECUTABLES = ["bamCoverage"]
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/"
    VERSION = "3.5.4"
    COMMAND = [
        "bamCoverage",
        "-b", "{inputs.bam}",
        "-o", "{output}/coverage.bw",
        "-p", "{inputs.threads}",
        "--normalizeUsing", "{inputs.norm}",
        "--binSize", "{inputs.bin_size}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted, indexed)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "norm": ("STRING", {"default": "RPGC", "description": "RPGC, CPM, BPM, RPKM, None"}),
                "bin_size": ("INT", {"default": 10, "min": 1}),
                "effective_genome_size": ("INT", {"default": 2913022398}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
