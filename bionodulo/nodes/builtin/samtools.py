"""SAMtools nodes for BioNodulo.

Provides nodes for SAM/BAM file manipulation: sorting, indexing,
format conversion, merging, flagstat, and stats generation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _safe_stem(value: str, default: str) -> str:
    stem = "_".join(str(value or "").strip().split())
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
    stem = stem.strip("._-")
    return stem or default


def _bam_output_stem(inputs: dict[str, Any], default: str) -> str:
    if inputs.get("output_name"):
        return _safe_stem(str(inputs["output_name"]), default)
    bam = str(inputs.get("bam", "") or "")
    if not bam:
        return default
    stem = Path(bam).name
    for suffix in (".bam", ".sam", ".cram"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    processing_suffixes = (".markdup", ".dedup", ".sorted", ".coordinate", ".fixmate", ".name_collated", ".collated")
    changed = True
    while changed:
        changed = False
        for suffix in processing_suffixes:
            if stem.lower().endswith(suffix):
                stem = stem[: -len(suffix)]
                changed = True
                break
    return _safe_stem(stem, default)


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
            "-o", f"{output}/sorted_bam.bam",
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
    RETURN_NAMES = ("index",)
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

    async def run(self, **kwargs):
        import shutil
        result = await super().run(**kwargs)
        bam = kwargs.get("bam", "")
        output_dir = kwargs.get("output_dir") or (kwargs.get("context") and getattr(kwargs["context"], "node_dir", "."))
        if bam and output_dir:
            bam_path = Path(bam)
            bai_path = Path(str(bam) + ".bai")
            if not bai_path.exists():
                bai_path = bam_path.with_suffix(bam_path.suffix + ".bai")
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if bai_path.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(bai_path), str(target))
        return result


class SamtoolsCollateNode(CommandNode):
    """Name-collate alignments before mate fixing."""

    NODE_ID = "samtools_collate"
    DISPLAY_NAME = "Samtools Collate"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Name-collate a BAM before samtools fixmate and duplicate marking"
    SEARCH_ALIASES = ["samtools", "collate", "name collate", "queryname", "fixmate", "markdup prerequisite"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("name_collated_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-collate.html"
    VERSION = "1.23.1"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
                "temp_prefix": ("STRING", {"default": "", "description": "Temporary file prefix", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        output_bam = output / f"{cls._output_stem(inputs)}.name_collated.bam"
        cmd = [
            "samtools",
            "collate",
            "-@",
            str(inputs.get("threads", 4)),
            "-o",
            str(output_bam),
        ]
        if inputs.get("temp_prefix"):
            cmd.extend(["-T", str(inputs["temp_prefix"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f"{cls._output_stem(inputs)}.name_collated.bam"]

    @classmethod
    def _output_stem(cls, inputs: dict[str, Any]) -> str:
        return _bam_output_stem(inputs, "collated")


class SamtoolsFixmateNode(CommandNode):
    """Add mate-coordinate and mate-score tags before duplicate marking."""

    NODE_ID = "samtools_fixmate"
    DISPLAY_NAME = "Samtools Fixmate"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Add mate coordinates and duplicate-marking tags to a name-collated BAM"
    SEARCH_ALIASES = ["samtools", "fixmate", "mate coordinates", "ms tag", "mc tag", "markdup prerequisite"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("fixmate_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-fixmate.html"
    VERSION = "1.23.1"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Name-collated BAM from samtools collate"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "add_markdup_tags": ("BOOLEAN", {"default": True, "description": "Add ms tags required by samtools markdup"}),
                "remove_secondary_and_unmapped": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove secondary and unmapped alignments", "advanced": True},
                ),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        output_bam = output / f"{cls._output_stem(inputs)}.fixmate.bam"
        cmd = [
            "samtools",
            "fixmate",
            "-@",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("add_markdup_tags", True):
            cmd.append("-m")
        if inputs.get("remove_secondary_and_unmapped"):
            cmd.append("-r")
        cmd.extend([str(inputs.get("bam", "")), str(output_bam)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f"{cls._output_stem(inputs)}.fixmate.bam"]

    @classmethod
    def _output_stem(cls, inputs: dict[str, Any]) -> str:
        return _bam_output_stem(inputs, "fixmate")


class SamtoolsMarkdupNode(CommandNode):
    """Mark or remove duplicate alignments in a coordinate-sorted BAM file."""

    NODE_ID = "samtools_markdup"
    DISPLAY_NAME = "Samtools Markdup"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = (
        "Mark or remove duplicate alignments from coordinate-sorted BAM files "
        "prepared with samtools fixmate -m"
    )
    SEARCH_ALIASES = [
        "samtools",
        "markdup",
        "mark duplicates",
        "remove duplicates",
        "duplicate marking",
        "picard equivalent",
        "variant preprocessing",
    ]
    RETURN_TYPES = ("BAM", "STATS_FILE")
    RETURN_NAMES = ("marked_bam", "duplicate_stats")
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-markdup.html"
    VERSION = "1.23.1"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted BAM prepared with samtools fixmate -m"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "remove_duplicates": ("BOOLEAN", {"default": False, "description": "Remove duplicates instead of only marking them"}),
                "mark_supplementary": ("BOOLEAN", {"default": False, "description": "Mark supplementary duplicate alignments", "advanced": True}),
                "mark_optical_duplicates": ("BOOLEAN", {"default": False, "description": "Use optical duplicate distance tagging", "advanced": True}),
                "optical_distance": ("INT", {"default": 100, "min": 0, "advanced": True}),
                "read_name_regex": ("STRING", {"default": "", "description": "Regex for extracting read coordinates", "advanced": True}),
                "clear_existing_duplicate_flags": ("BOOLEAN", {"default": False, "description": "Clear existing duplicate flags before marking", "advanced": True}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        raw_threads = inputs.get("threads", 4)
        threads = 4 if raw_threads is None else int(raw_threads)
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"
        optical_distance = int(inputs.get("optical_distance", 100) or 0)
        if optical_distance < 0:
            return "optical_distance must be non-negative"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        output_name = cls._output_stem(inputs)
        output_bam = output / f"{output_name}.markdup.bam"
        duplicate_stats = output / f"{output_name}.duplicate_stats.txt"

        cmd = [
            "samtools",
            "markdup",
            "-@",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("remove_duplicates"):
            cmd.append("-r")
        if inputs.get("mark_supplementary"):
            cmd.append("-S")
        if inputs.get("mark_optical_duplicates"):
            cmd.extend(["-d", str(inputs.get("optical_distance", 100))])
            if inputs.get("read_name_regex"):
                cmd.extend(["--read-coords", str(inputs["read_name_regex"])])
        if inputs.get("clear_existing_duplicate_flags"):
            cmd.append("-c")
        cmd.extend(["-f", str(duplicate_stats), str(inputs.get("bam", "")), str(output_bam)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output_name = cls._output_stem(inputs)
        return [
            node_out / f"{output_name}.markdup.bam",
            node_out / f"{output_name}.duplicate_stats.txt",
        ]

    @classmethod
    def _output_stem(cls, inputs: dict[str, Any]) -> str:
        return _bam_output_stem(inputs, "markdup")


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
            ">", f"{output}/stats.stats.txt",
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
            "-o", f"{output}/bam.bam",
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
            f"{inputs.get('output', '.')}/merged_bam.bam",
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
            ">", f"{output}/stats.stats.txt",
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
