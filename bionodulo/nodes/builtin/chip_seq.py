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
    REQUIRED_CONDA_PACKAGES = ['macs2']
    CATEGORY = "chip_seq"
    DESCRIPTION = "Model-based Analysis of ChIP-Seq: identify transcription factor binding sites"
    SEARCH_ALIASES = ["macs2", "peak calling", "chip-seq", "binding sites"]
    RETURN_TYPES = ("NARROW_PEAK", "BEDGRAPH")
    RETURN_NAMES = ("peaks", "signal")
    REQUIRED_EXECUTABLES = ["macs2"]
    DOCUMENTATION_URL = "https://github.com/macs3-project/MACS"
    VERSION = "2.2.9.2"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "macs2", "callpeak",
            "-t", str(inputs.get("treatment", "")),
            "-n", str(inputs.get("name", "peaks")),
            "--outdir", str(inputs.get("output", ".")),
            "-g", str(inputs.get("genome_size", "hs")),
            "--bdg",
        ]
        if inputs.get("control"):
            cmd.extend(["-c", str(inputs["control"])])
        fmt = inputs.get("format", "BAM")
        if fmt:
            cmd.extend(["-f", str(fmt)])
        if inputs.get("qvalue") is not None:
            cmd.extend(["-q", str(inputs["qvalue"])])
        if inputs.get("pvalue") is not None:
            cmd.extend(["-p", str(inputs["pvalue"])])
        if inputs.get("broad"):
            cmd.append("--broad")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "treatment": ("BAM", {"description": "Treatment/ChIP BAM file"}),
                "name": ("STRING", {"default": "peaks"}),
                "genome_size": ("STRING", {"default": "hs", "description": "hs, mm, dm, ce, or numeric bp"}),
            },
            "optional": {
                "control": ("BAM", {"description": "Control/input BAM file"}),
                "qvalue": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "format": ("STRING", {"default": "BAM"}),
                "pvalue": ("FLOAT", {"default": None, "min": 0.0, "max": 1.0, "label": "p-value", "advanced": True}),
                "broad": ("BOOLEAN", {"default": False, "label": "Broad Peaks", "advanced": True}),
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
    REQUIRED_CONDA_PACKAGES = ['bedtools']
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/"
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools", "intersect",
            "-a", str(inputs.get("a", "")),
            "-b", str(inputs.get("b", "")),
        ]
        if inputs.get("wa"):
            cmd.append("-wa")
        if inputs.get("wb"):
            cmd.append("-wb")
        if inputs.get("f") is not None:
            cmd.extend(["-f", str(inputs["f"])])
        if inputs.get("sorted"):
            cmd.append("-sorted")
        if inputs.get("v"):
            cmd.append("-v")
        if inputs.get("s"):
            cmd.append("-s")
        if inputs.get("wo"):
            cmd.append("-wo")
        cmd.extend([">", f"{inputs.get('output', '.')}/intersect.bed"])
        return cmd

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
                "sorted": ("BOOLEAN", {"default": False, "label": "Sorted", "advanced": True}),
                "v": ("BOOLEAN", {"default": False, "label": "Invert", "advanced": True}),
                "s": ("BOOLEAN", {"default": False, "label": "Strand", "advanced": True}),
                "wo": ("BOOLEAN", {"default": False, "label": "Write overlap", "advanced": True}),
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
    REQUIRED_CONDA_PACKAGES = ['bedtools']
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
    REQUIRED_CONDA_PACKAGES = ['deeptools']
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/"
    VERSION = "3.5.6"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bamCoverage",
            "-b", str(inputs.get("bam", "")),
            "-o", f"{inputs.get('output', '.')}/coverage.bw",
            "-p", str(inputs.get("threads", 8)),
            "--binSize", str(inputs.get("bin_size", 10)),
        ]
        norm = inputs.get("norm", "None")
        if norm and norm != "None":
            cmd.extend(["--normalizeUsing", str(norm)])
        egs = inputs.get("effective_genome_size")
        if egs is not None:
            cmd.extend(["--effectiveGenomeSize", str(egs)])
        if inputs.get("extendReads") is not None:
            cmd.extend(["--extendReads", str(inputs["extendReads"])])
        if inputs.get("ignoreDuplicates"):
            cmd.append("--ignoreDuplicates")
        if inputs.get("smoothLength") is not None:
            cmd.extend(["--smoothLength", str(inputs["smoothLength"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted, indexed)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "norm": ("STRING", {"default": "None", "description": "RPGC, CPM, BPM, RPKM, None"}),
                "bin_size": ("INT", {"default": 10, "min": 1}),
                "effective_genome_size": ("INT", {"default": 2913022398, "label": "Effective Genome Size", "advanced": True}),
                "extendReads": ("INT", {"default": None, "label": "Extend Reads", "advanced": True}),
                "ignoreDuplicates": ("BOOLEAN", {"default": False, "label": "Ignore Duplicates", "advanced": True}),
                "smoothLength": ("INT", {"default": None, "label": "Smooth Length", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
