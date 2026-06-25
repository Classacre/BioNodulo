"""SAMtools nodes for BioNodulo.

Provides nodes for SAM/BAM file manipulation: sorting, indexing,
format conversion, merging, flagstat, and stats generation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


GALAXY_ALIAS = "Galaxy"
SAMTOOLS_CITATION_DOIS = ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btp352"]
SAMTOOLS_CITATION_URLS = [f"https://doi.org/{doi}" for doi in SAMTOOLS_CITATION_DOIS]
SAMTOOLS_CITATION_TEXT = (
    "Twelve years of SAMtools and BCFtools; "
    "The Sequence Alignment/Map format and SAMtools."
)
SAMTOOLS_GALAXY_CITATION_DOIS = ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btr076"]
SAMTOOLS_GALAXY_CITATION_URLS = [f"https://doi.org/{doi}" for doi in SAMTOOLS_GALAXY_CITATION_DOIS]
SAMTOOLS_GALAXY_CITATION_TEXT = (
    "Twelve years of SAMtools and BCFtools; "
    "Improving SNP discovery by Base Alignment Quality."
)


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


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != ""]
    return [str(value)]


def _flag_sum(value: Any) -> int:
    total = 0
    for item in _as_list(value):
        for part in item.split(","):
            if part.strip():
                total += int(part.strip())
    return total


def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != "":
        cmd.extend([flag, str(value)])


def _additional_threads(inputs: dict[str, Any], default: int = 1) -> int:
    return max(int(inputs.get("threads", default) or default) - 1, 0)


def _sort_memory(inputs: dict[str, Any], default_mb: int = 768) -> str:
    memory_mb = int(inputs.get("memory_mb", default_mb) or default_mb)
    return f"{max(memory_mb * 75 // 100, 1)}M"


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


class SamtoolsIdxstatsNode(CommandNode):
    """Report alignment counts per reference sequence from a BAM/CRAM index."""

    NODE_ID = "samtools_idxstats"
    DISPLAY_NAME = "Samtools Idxstats"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Report mapped and unmapped read counts per reference sequence from a BAM or CRAM index."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "idxstats", "index stats", "BAM index", "MultiQC"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("idxstats",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-idxstats.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        addthreads = max(int(inputs.get("threads", 1) or 1) - 1, 0)
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        return [
            "samtools",
            "idxstats",
            "-@",
            str(addthreads),
            str(inputs.get("input", inputs.get("bam", ""))),
            ">",
            f"{output}/idxstats.tsv",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "idxstats.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Indexed BAM or CRAM alignment file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsDepthNode(CommandNode):
    """Compute per-position read depth across one or more BAM files."""

    NODE_ID = "samtools_depth"
    DISPLAY_NAME = "Samtools Depth"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Compute per-position alignment depth for one or more BAM files, optionally restricted to regions."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "depth", "coverage depth", "per-base coverage", "BAM depth"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("depth",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-depth.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = ["samtools", "depth"]
        all_positions = str(inputs.get("all", ""))
        if all_positions:
            cmd.append(all_positions)
        if inputs.get("input_bed"):
            cmd.extend(["-b", str(inputs["input_bed"])])
        elif inputs.get("region"):
            cmd.extend(["-r", str(inputs["region"])])
        _add_if_value(cmd, "-l", inputs.get("minlength"))
        _add_if_value(cmd, "-m", inputs.get("maxdepth"))
        _add_if_value(cmd, "-q", inputs.get("basequality"))
        _add_if_value(cmd, "-Q", inputs.get("mapquality"))
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["-g", str(required_flags)])
        if skipped_flags:
            cmd.extend(["-G", str(skipped_flags)])
        if inputs.get("deletions"):
            cmd.append("-J")
        if inputs.get("single_read"):
            cmd.append("-s")
        if inputs.get("header"):
            cmd.append("-H")
        cmd.extend(_as_list(inputs.get("input_bams", inputs.get("bam"))))
        cmd.extend([">", f"{output}/depth.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "depth.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bams": ("BAM_LIST", {"description": "One or more indexed BAM files"}),
            },
            "optional": {
                "all": ("STRING", {"default": "", "options": ["", "-a", "-aa"], "description": "Emit zero-depth positions"}),
                "region": ("STRING", {"default": "", "description": "Manual region such as chr1:100-200"}),
                "input_bed": ("BED", {"description": "BED regions to restrict depth calculation"}),
                "minlength": ("INT", {"default": "", "min": 0, "description": "Ignore reads shorter than this length"}),
                "maxdepth": ("INT", {"default": "", "min": 0, "description": "Maximum read depth considered"}),
                "basequality": ("INT", {"default": "", "min": 0, "description": "Minimum base quality"}),
                "mapquality": ("INT", {"default": "", "min": 0, "description": "Minimum mapping quality"}),
                "required_flags": ("STRING", {"default": "", "description": "Comma-separated SAM flags that must be set", "advanced": True}),
                "skipped_flags": ("STRING", {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True}),
                "deletions": ("BOOLEAN", {"default": False, "description": "Include deletions in depth calculation"}),
                "single_read": ("BOOLEAN", {"default": False, "description": "Count only one read in overlapping pairs"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print a file header"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsFaidxNode(CommandNode):
    """Index FASTA or FASTQ sequences with samtools faidx."""

    NODE_ID = "samtools_faidx"
    DISPLAY_NAME = "Samtools Faidx"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Create a FASTA/FASTQ fai index, with fallback handling for gzip-compressed inputs."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "faidx", "FASTA index", "FASTQ index", "fai"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("fai_index",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-faidx.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        output_index = f"{output}/fai_index.tsv"
        input_path = str(inputs.get("input", ""))
        is_fastq = inputs.get("fastq", "fastq" in input_path.lower())
        is_compressed = inputs.get("compressed", input_path.lower().endswith((".gz", ".bgz")))
        if is_compressed:
            linked_input = f"{output}/input.gz"
            cmd = ["ln", "-sf", input_path, linked_input, "&&", "samtools", "faidx"]
            if is_fastq:
                cmd.append("--fastq")
            cmd.extend([linked_input, "--fai-idx", output_index, "--gzi-idx", f"{linked_input}.gzi"])
            cmd.extend([
                "||",
                "(",
                "echo",
                "Failed to index compressed reference. Trying decompressed ...",
                "1>&2",
                "&&",
                "gzip",
                "-dc",
                linked_input,
                ">",
                f"{output}/input.plain",
                "&&",
                "samtools",
                "faidx",
            ])
            if is_fastq:
                cmd.append("--fastq")
            cmd.extend([f"{output}/input.plain", "--fai-idx", output_index, ")"])
            return cmd

        linked_input = f"{output}/input"
        cmd = ["ln", "-sf", input_path, linked_input, "&&", "samtools", "faidx"]
        if is_fastq:
            cmd.append("--fastq")
        cmd.extend([linked_input, "--fai-idx", output_index])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "fai_index.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA or FASTQ sequence file"}),
            },
            "optional": {
                "fastq": ("BOOLEAN", {"default": False, "description": "Pass --fastq for FASTQ input"}),
                "compressed": ("BOOLEAN", {"default": False, "description": "Treat input as gzip/BGZF compressed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsCoverageNode(CommandNode):
    """Compute per-reference coverage summaries or ASCII histogram data."""

    NODE_ID = "samtools_coverage"
    DISPLAY_NAME = "Samtools Coverage"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Compute tabular or histogram coverage summaries per reference sequence using samtools coverage."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "coverage", "histogram", "BAM coverage", "chromosome coverage"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("coverage",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-coverage.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.22"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        input_bams = _as_list(inputs.get("input_bams"))
        if not input_bams:
            input_bams = _as_list(inputs.get("input", inputs.get("bam")))
        cmd = ["samtools", "coverage", *input_bams]
        cmd.extend(["-l", str(inputs.get("min_read_length", 0))])
        cmd.extend(["-q", str(inputs.get("min_mq", 0))])
        cmd.extend(["-Q", str(inputs.get("min_bq", 0))])
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["--rf", str(required_flags)])
        if skipped_flags:
            cmd.extend(["--ff", str(skipped_flags)])
        if inputs.get("region"):
            cmd.extend(["-r", str(inputs["region"])])
        if inputs.get("histogram"):
            cmd.extend(["-m", "-w", str(inputs.get("n_bins", 100))])
        cmd.extend(["-o", f"{output}/coverage.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "coverage.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Indexed BAM file"}),
            },
            "optional": {
                "input_bams": ("BAM_LIST", {"description": "Multiple BAM files to pool"}),
                "min_read_length": ("INT", {"default": 0, "min": 0}),
                "min_mq": ("INT", {"default": 0, "min": 0, "description": "Minimum mapping quality"}),
                "min_bq": ("INT", {"default": 0, "min": 0, "description": "Minimum base quality"}),
                "required_flags": ("STRING", {"default": "", "description": "Comma-separated SAM flags that must be set", "advanced": True}),
                "skipped_flags": ("STRING", {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True}),
                "region": ("STRING", {"default": "", "description": "Region such as chr1:100-200"}),
                "histogram": ("BOOLEAN", {"default": False, "description": "Emit histogram data"}),
                "n_bins": ("INT", {"default": 100, "min": 1, "description": "Number of histogram bins"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsBedcovNode(CommandNode):
    """Calculate read depth summaries for intervals in a BED file."""

    NODE_ID = "samtools_bedcov"
    DISPLAY_NAME = "Samtools Bedcov"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Calculate read depth totals for BED intervals across one or more BAM files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "bedcov", "interval coverage", "BED coverage", "depth threshold"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("interval_coverage",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-bedcov.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = ["samtools", "bedcov"]
        _add_if_value(cmd, "-Q", inputs.get("mapq"))
        if inputs.get("countdel"):
            cmd.append("-j")
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["-g", str(required_flags)])
        if skipped_flags:
            cmd.extend(["-G", str(skipped_flags)])
        _add_if_value(cmd, "-d", inputs.get("depth_thresh"))
        cmd.append(str(inputs.get("input_bed", "")))
        cmd.extend(_as_list(inputs.get("input_bams", inputs.get("bam"))))
        cmd.extend([">", f"{output}/interval_coverage.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "interval_coverage.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED intervals to summarize"}),
                "input_bams": ("BAM_LIST", {"description": "One or more indexed BAM files"}),
            },
            "optional": {
                "mapq": ("INT", {"default": "", "min": 0, "description": "Minimum mapping quality"}),
                "countdel": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude deletions and reference skips from coverage totals"},
                ),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags that must be set", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "depth_thresh": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Add a column counting bases with coverage at or above this threshold",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsCalmdNode(CommandNode):
    """Recalculate MD/NM tags and optional BAQ values in a BAM file."""

    NODE_ID = "samtools_calmd"
    DISPLAY_NAME = "Samtools Calmd"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Recalculate MD and NM tags against a reference FASTA, optionally adding BAQ-adjusted qualities."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "calmd", "MD tags", "NM tags", "BAQ", "Base Alignment Quality"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("calmd_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-calmd.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        cmd = ["samtools", "calmd"]
        if inputs.get("calculate_baq"):
            cmd.append("-r")
            if inputs.get("modify_quality"):
                cmd.append("-A")
            if inputs.get("extended_baq"):
                cmd.append("-E")
        if inputs.get("change_identical"):
            cmd.append("-e")
        adjust_mq = int(inputs.get("adjust_mq", 0) or 0)
        if adjust_mq:
            cmd.extend(["-C", str(adjust_mq)])
        cmd.extend([
            "-b",
            "-@",
            str(_additional_threads(inputs)),
            str(inputs.get("input", inputs.get("bam", ""))),
            str(inputs.get("reference", "")),
            ">",
            f"{output}/calmd.bam",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "calmd.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM file to recalculate"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for the alignment"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "calculate_baq": ("BOOLEAN", {"default": False, "description": "Calculate BAQ scores"}),
                "modify_quality": (
                    "BOOLEAN",
                    {"default": False, "description": "Use BAQ to cap read base qualities", "advanced": True},
                ),
                "extended_baq": (
                    "BOOLEAN",
                    {"default": False, "description": "Use extended BAQ calculation", "advanced": True},
                ),
                "change_identical": (
                    "BOOLEAN",
                    {"default": False, "description": "Change reference-identical bases to '='", "advanced": True},
                ),
                "adjust_mq": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 255,
                        "description": "Coefficient for capping mapping quality of poorly mapped reads",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsAmpliconclipNode(CommandNode):
    """Clip primer regions from amplicon-aligned BAM files."""

    NODE_ID = "samtools_ampliconclip"
    DISPLAY_NAME = "Samtools Ampliconclip"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Clip primer bases from amplicon BAM files and re-sort alignments for downstream analysis."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "ampliconclip", "primer trimming", "amplicon", "soft clip"]
    RETURN_TYPES = ("BAM", "BEDGRAPH")
    RETURN_NAMES = ("clipped_bam", "primer_counts")
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-ampliconclip.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        addthreads = str(_additional_threads(inputs))
        primer_counts = f"{output}/primer_counts.bedgraph"
        cmd = [
            "samtools",
            "ampliconclip",
            "--hard-clip" if inputs.get("hard_clip") else "--soft-clip",
        ]
        _add_if_value(cmd, "--fail-len", inputs.get("min_length"))
        cmd.extend(["--tolerance", str(inputs.get("tolerance", 5))])
        if inputs.get("strand"):
            cmd.append("--strand")
        cmd.extend(["-b", str(inputs.get("input_bed", "")), "-u"])
        if inputs.get("both_ends"):
            cmd.append("--both-ends")
        if inputs.get("no_excluded"):
            cmd.append("--no-excluded")
        if inputs.get("write_primer_counts"):
            cmd.extend(["--primer-counts", primer_counts])
        cmd.extend([
            "-@",
            addthreads,
            str(inputs.get("input_bam", inputs.get("bam", ""))),
            "|",
            "samtools",
            "collate",
            "-@",
            addthreads,
            "-O",
            "-u",
            "-",
            "|",
            "samtools",
            "fixmate",
            "-@",
            addthreads,
            "-u",
            "-",
            "-",
            "|",
            "samtools",
            "sort",
            "-@",
            addthreads,
            "-m",
            _sort_memory(inputs),
            "-T",
            f"{output}/tmp",
            "-o",
            f"{output}/clipped.bam",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "clipped.bam", node_out / "primer_counts.bedgraph"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED file defining primer or amplicon intervals"}),
                "input_bam": ("BAM", {"description": "BAM file to clip"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "hard_clip": (
                    "BOOLEAN",
                    {"default": False, "description": "Hard clip primer bases instead of soft clipping"},
                ),
                "strand": (
                    "BOOLEAN",
                    {"default": False, "description": "Only clip reads matching BED strand annotation"},
                ),
                "both_ends": (
                    "BOOLEAN",
                    {"default": False, "description": "Clip both read ends instead of the 5' end only"},
                ),
                "no_excluded": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not write excluded reads to output", "advanced": True},
                ),
                "min_length": (
                    "INT",
                    {"default": "", "min": 0, "description": "Mark reads QCFAIL at this length or shorter"},
                ),
                "tolerance": ("INT", {"default": 5, "min": 0, "description": "Primer match tolerance in bases"}),
                "write_primer_counts": (
                    "BOOLEAN",
                    {"default": False, "description": "Write per-primer clipping counts as bedGraph"},
                ),
                "memory_mb": (
                    "INT",
                    {"default": 768, "min": 1, "description": "Memory per sort thread in MB", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SamtoolsFastxNode(CommandNode):
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
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        input_path = str(inputs.get("input", ""))
        output_format = cls._output_format(inputs)
        extension = cls._output_extension(output_format)
        command = "fastq" if output_format == "fastq" else "fasta"
        input_alias = f"{output}/input"
        addthreads = str(_additional_threads(inputs))

        if inputs.get("name_sorted"):
            cmd = ["ln", "-sf", input_path, input_alias, "&&"]
        else:
            cmd = [
                "samtools",
                "sort",
                "-@",
                addthreads,
                "-m",
                _sort_memory(inputs),
                "-n",
                input_path,
                "-T",
                f"{output}/tmp",
                ">",
                input_alias,
                "&&",
            ]

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
            cmd.extend(["-0", f"{output}/nonspecific.{extension}"])
        if "read1" in outputs:
            cmd.extend(["-1", f"{output}/read1.{extension}"])
        if "read2" in outputs:
            cmd.extend(["-2", f"{output}/read2.{extension}"])
        if "singletons" in outputs:
            cmd.extend(["-s", f"{output}/singletons.{extension}"])

        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        skipped_flags_all = _flag_sum(inputs.get("skipped_flags_all"))
        if required_flags:
            cmd.extend(["-f", str(required_flags)])
        if skipped_flags:
            cmd.extend(["-F", str(skipped_flags)])
        if skipped_flags_all:
            cmd.extend(["-G", str(skipped_flags_all)])

        if inputs.get("write_index_reads"):
            if inputs.get("write_i1", True):
                cmd.extend(["--i1", f"{output}/i1.{extension}"])
            if inputs.get("write_i2", True):
                cmd.extend(["--i2", f"{output}/i2.{extension}"])
            _add_if_value(cmd, "--index-format", inputs.get("index_format"))
            _add_if_value(cmd, "--barcode-tag", inputs.get("barcode_tag"))
            _add_if_value(cmd, "--quality-tag", inputs.get("quality_tag"))

        cmd.extend([input_alias, ">", f"{output}/reads.{extension}"])
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
                "input": ("BAM", {"description": "SAM, BAM, or CRAM alignment file"}),
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
                    "STRING",
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
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "skipped_flags_all": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags that must not all be set", "advanced": True},
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
                    {"default": "", "description": "Barcode quality tag name, default QT in samtools", "advanced": True},
                ),
                "memory_mb": (
                    "INT",
                    {"default": 768, "min": 1, "description": "Memory per sort thread in MB", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
