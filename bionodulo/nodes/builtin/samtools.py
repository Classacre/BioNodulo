"""SAMtools nodes for BioNodulo.

Provides nodes for SAM/BAM file manipulation: sorting, indexing,
format conversion, merging, flagstat, and stats generation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class SamtoolsSortNode(CommandNode):
    """Sort BAM file by coordinate."""
    NODE_ID = "samtools_sort"
    DISPLAY_NAME = "Samtools Sort"
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = "samtools"
    DESCRIPTION = "Sort a SAM/BAM file by genomic coordinate"
    SEARCH_ALIASES = ["samtools", "sort", "bam sort", "coordinate"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("sorted_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-sort.html"
    VERSION = "1.23.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = [
            "samtools", "sort",
            "-@", str(inputs.get("threads", 4)),
            "-o", f"{output}/sorted.bam",
            "-T", f"{output}/tmp",
        ]
        if inputs.get("memory"):
            cmd.extend(["-m", str(inputs["memory"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "memory": ("STRING", {"default": "2G"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SamtoolsIndexNode(CommandNode):
    """Index a BAM file."""
    NODE_ID = "samtools_index"
    DISPLAY_NAME = "Samtools Index"
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = "samtools"
    DESCRIPTION = "Create a .bai index for a sorted BAM file"
    SEARCH_ALIASES = ["samtools", "index", "bai"]
    RETURN_TYPES = ("BAI",)
    RETURN_NAMES = ("bai",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-index.html"
    VERSION = "1.23.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        bam = str(inputs.get("bam", ""))
        output_path = inputs.get("output_path", "")
        cmd = [
            "samtools", "index",
            "-@", str(inputs.get("threads", 2)),
        ]
        if inputs.get("csi"):
            cmd.append("--csi")
        if output_path:
            cmd.extend(["-o", str(output_path)])
        cmd.append(bam)
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Sorted BAM file to index"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "csi": ("BOOLEAN", {"default": False, "description": "Create CSI index instead of BAI"}),
                "output_path": ("STRING", {"default": "", "description": "Output index path", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        await super().run(**kwargs)
        bam = kwargs.get("bam", "")
        output_path = kwargs.get("output_path", "")
        if output_path:
            return {"outputs": {"bai": str(output_path)}}
        if kwargs.get("csi"):
            return {"outputs": {"bai": str(Path(bam).with_suffix(".csi"))}}
        return {"outputs": {"bai": str(Path(bam).with_suffix(".bai"))}}


class SamtoolsFlagstatNode(CommandNode):
    """Generate flagstat statistics for a BAM file."""
    NODE_ID = "samtools_flagstat"
    DISPLAY_NAME = "Samtools Flagstat"
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = "samtools"
    DESCRIPTION = "Generate alignment statistics with samtools flagstat"
    SEARCH_ALIASES = ["samtools", "flagstat", "stats", "alignment stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-flagstat.html"
    VERSION = "1.23.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = [
            "samtools", "flagstat",
            "-@", str(inputs.get("threads", 2)),
        ]
        if inputs.get("output_format"):
            cmd.extend(["-O", str(inputs["output_format"])])
        cmd.extend([
            str(inputs.get("bam", "")),
            ">", f"{output}/flagstat.txt",
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "output_format": ("STRING", {"default": "", "description": "Output format (json, tsv)", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SamtoolsViewNode(CommandNode):
    """Convert SAM to BAM or filter alignments."""
    NODE_ID = "samtools_view"
    DISPLAY_NAME = "Samtools View"
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = "samtools"
    DESCRIPTION = "Convert SAM to BAM, filter by flags, or extract regions"
    SEARCH_ALIASES = ["samtools", "view", "sam to bam", "convert", "filter"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-view.html"
    VERSION = "1.23.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = [
            "samtools", "view",
            "-b",
            "-@", str(inputs.get("threads", 4)),
            "-o", f"{output}/output.bam",
        ]
        if inputs.get("f") is not None:
            cmd.extend(["-f", str(inputs["f"])])
        if inputs.get("F") is not None:
            cmd.extend(["-F", str(inputs["F"])])
        cmd.append(str(inputs.get("sam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sam": ("SAM", {"description": "Input SAM file"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "f": ("INT", {"default": None, "description": "Require ALL flags"}),
                "F": ("INT", {"default": None, "description": "Filter out ALL flags"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SamtoolsMergeNode(CommandNode):
    """Merge multiple BAM files."""
    NODE_ID = "samtools_merge"
    DISPLAY_NAME = "Samtools Merge"
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = "samtools"
    DESCRIPTION = "Merge multiple sorted BAM files into one"
    SEARCH_ALIASES = ["samtools", "merge", "combine", "bam"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("merged_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-merge.html"
    VERSION = "1.23.1"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bams": ("BAM", {"description": "List of BAM files to merge"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        """Override render to properly expand the bams list."""
        bams = inputs.get("bams", [])
        if isinstance(bams, str):
            bams = [bams]
        cmd = [
            "samtools", "merge",
            "-@", str(inputs.get("threads", 4)),
            f"{inputs.get('output', '.')}/merged.bam",
        ] + list(bams)
        return cmd


class SamtoolsStatsNode(CommandNode):
    """Generate comprehensive BAM statistics."""
    NODE_ID = "samtools_stats"
    DISPLAY_NAME = "Samtools Stats"
    CATEGORY = "samtools"
    DESCRIPTION = "Generate comprehensive statistics for a BAM file"
    SEARCH_ALIASES = ["samtools", "stats", "statistics", "bam stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["samtools"]
    REQUIRED_CONDA_PACKAGES = ['samtools']
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-stats.html"
    VERSION = "1.23.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = [
            "samtools", "stats",
            "-@", str(inputs.get("threads", 2)),
        ]
        if inputs.get("target_regions"):
            cmd.extend(["-t", str(inputs["target_regions"])])
        cmd.extend([
            str(inputs.get("bam", "")),
            ">", f"{output}/stats.txt",
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "target_regions": ("BED", {"description": "Optional target regions BED"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
