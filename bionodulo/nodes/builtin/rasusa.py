"""BioNodulo built-in Rasusa node."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


RASUSA_READS_DOI = "10.21105/joss.03941"
RASUSA_ALN_DOI = "10.46471/gigabyte.180"
RASUSA_CITATION_TEXT = (
    "Rasusa: Randomly subsample sequencing reads to a specified coverage; "
    "Efficient downsampling of genome alignments with Rasusa."
)


def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get("output", inputs.get("output_dir", ".")))


def _has_value(value: Any) -> bool:
    return value is not None and str(value) != ""


def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if _has_value(value):
        cmd.extend([flag, str(value)])


def _selector(inputs: dict[str, Any]) -> str:
    selector = str(inputs.get("input_selector", "single"))
    return selector if selector in {"single", "paired", "paired_collection", "aligned"} else "single"


def _read_pair(inputs: dict[str, Any]) -> tuple[str, str]:
    reads = inputs.get("reads")
    if isinstance(reads, (list, tuple)) and len(reads) >= 2:
        return str(reads[0]), str(reads[1])
    if inputs.get("collection_forward") or inputs.get("collection_reverse"):
        return str(inputs.get("collection_forward", "")), str(inputs.get("collection_reverse", ""))
    return str(inputs.get("reads1", "")), str(inputs.get("reads2", ""))


def _single_read(inputs: dict[str, Any]) -> str:
    reads = inputs.get("reads")
    if isinstance(reads, (list, tuple)):
        return str(reads[0] if reads else "")
    return str(reads or inputs.get("read", ""))


def _clean_output_ext(value: Any) -> str:
    ext = str(value or "fastq.gz").strip().lstrip(".")
    return ext or "fastq.gz"


def _compression_from_ext(ext: str) -> str:
    if ext.endswith(".gz") or ext == "gz" or ext.endswith("fastq.gz") or ext.endswith("fasta.gz"):
        return "g"
    if ext.endswith(".bz") or ext.endswith(".bz2"):
        return "b"
    if ext.endswith(".xz") or ext.endswith(".lzma"):
        return "x"
    if ext.endswith(".zst"):
        return "z"
    return "u"


def _compress_type(inputs: dict[str, Any], ext: str) -> str:
    return str(inputs.get("compress_type") or _compression_from_ext(ext))


def _format_size(value: Any, unit: Any) -> str:
    return f"{value}{unit}"


class RasusaNode(CommandNode):
    """Randomly subsample FASTA/FASTQ reads or downsample BAM alignments."""

    NODE_ID = "rasusa"
    DISPLAY_NAME = "Rasusa"
    REQUIRED_CONDA_PACKAGES = ["rasusa", "samtools"]
    CATEGORY = "qc"
    DESCRIPTION = "Randomly subsample FASTA/FASTQ reads to coverage, bases, read count, or fraction; optionally downsample BAM alignments."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "rasusa",
        "subsample reads",
        "downsample reads",
        "coverage subsampling",
        "alignment downsampling",
        "FASTQ subsampling",
    ]
    RETURN_TYPES = ("FASTQ_LIST", "FASTQ", "BAM")
    RETURN_NAMES = ("paired_reads", "single_reads", "subsampled_bam")
    REQUIRED_EXECUTABLES = ["rasusa", "samtools"]
    DOCUMENTATION_URL = "https://github.com/mbhall88/rasusa"
    CITATION_DOIS = [RASUSA_READS_DOI, RASUSA_ALN_DOI]
    CITATION_URLS = [f"https://doi.org/{RASUSA_READS_DOI}", f"https://doi.org/{RASUSA_ALN_DOI}"]
    CITATION_TEXT = RASUSA_CITATION_TEXT
    VERSION = "4.1.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        selector = _selector(inputs)
        if selector == "aligned":
            return cls._render_aligned_command(inputs)
        return cls._render_reads_command(inputs)

    @classmethod
    def _render_reads_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        ext = _clean_output_ext(inputs.get("output_ext"))
        selector = _selector(inputs)
        cmd = ["rasusa", "reads"]
        _add_if_value(cmd, "-s", inputs.get("seed"))
        if inputs.get("strict"):
            cmd.append("--strict")
        if inputs.get("verbose"):
            cmd.append("-v")
        _add_if_value(cmd, "--output-format", inputs.get("output_format"))
        _add_if_value(cmd, "--compress-level", inputs.get("compress_level"))

        if selector in {"paired", "paired_collection"}:
            r1, r2 = _read_pair(inputs)
            cmd.extend(["-o", f"{out}/paired_R1.{ext}", "-o", f"{out}/paired_R2.{ext}"])
            cls._append_reads_subsample_args(cmd, inputs)
            cmd.extend(["--compress-type", _compress_type(inputs, ext), r1, r2])
            return cmd

        cmd.extend(["-o", f"{out}/single.{ext}"])
        cls._append_reads_subsample_args(cmd, inputs)
        cmd.extend(["--compress-type", _compress_type(inputs, ext), _single_read(inputs)])
        return cmd

    @classmethod
    def _append_reads_subsample_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        subsample_type = str(inputs.get("subsample_type", "frac_reads"))
        if subsample_type == "coverage":
            cmd.extend([
                "--genome-size",
                _format_size(inputs.get("genome_size", ""), inputs.get("genome_size_unit", "b")),
                "--coverage",
                str(inputs.get("coverage", "")),
            ])
        elif subsample_type == "num_bases":
            cmd.extend(["--bases", _format_size(inputs.get("bases", ""), inputs.get("num_bases_unit", "b"))])
        elif subsample_type == "num_reads":
            cmd.extend(["--num", str(inputs.get("num", ""))])
        elif subsample_type == "frac_reads":
            cmd.extend(["--frac", str(inputs.get("frac", 0.1))])

    @classmethod
    def _render_aligned_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["rasusa", "aln"]
        _add_if_value(cmd, "-s", inputs.get("seed"))
        cmd.extend(["--coverage", str(inputs.get("coverage", ""))])
        strategy = str(inputs.get("strategy", "stream"))
        if strategy in {"stream", "fetch"}:
            cmd.extend(["--strategy", strategy])
        _add_if_value(cmd, "--step-size", inputs.get("step_size"))
        _add_if_value(cmd, "--batch-size", inputs.get("batch_size"))
        _add_if_value(cmd, "--swap-distance", inputs.get("swap_distance"))
        cmd.extend([
            "--output-format",
            "bam",
            str(inputs.get("aligned_input", "")),
            "|",
            "samtools",
            "sort",
            "--no-PG",
            "-@",
            "1",
            "-T",
            f"{out}/tmp",
            "-O",
            "bam",
            "-o",
            f"{out}/subsampled.bam",
            "-",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        ext = _clean_output_ext(inputs.get("output_ext"))
        selector = _selector(inputs)
        if selector in {"paired", "paired_collection"}:
            return [out / f"paired_R1.{ext}", out / f"paired_R2.{ext}"]
        if selector == "aligned":
            return [out / "subsampled.bam"]
        return [out / f"single.{ext}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_selector": (
                    "STRING",
                    {"default": "single", "options": ["single", "paired", "paired_collection", "aligned"], "description": "Input mode matching the Galaxy Rasusa wrapper"},
                ),
            },
            "optional": {
                "reads": ("FASTQ_LIST", {"default": "", "description": "Single read file or FASTQ/FASTA pair"}),
                "reads1": ("FASTQ", {"default": "", "description": "Forward reads for paired mode"}),
                "reads2": ("FASTQ", {"default": "", "description": "Reverse reads for paired mode"}),
                "collection_forward": ("FASTQ", {"default": "", "description": "Forward reads from a paired collection", "advanced": True}),
                "collection_reverse": ("FASTQ", {"default": "", "description": "Reverse reads from a paired collection", "advanced": True}),
                "aligned_input": ("BAM", {"default": "", "description": "Coordinate-sorted BAM alignment for alignment downsampling"}),
                "subsample_type": (
                    "STRING",
                    {"default": "frac_reads", "options": ["coverage", "num_bases", "num_reads", "frac_reads"], "description": "Subsampling target for reads mode"},
                ),
                "genome_size": ("FLOAT", {"default": "", "min": 0, "description": "Genome size value for coverage-based read subsampling"}),
                "genome_size_unit": ("STRING", {"default": "b", "options": ["b", "k", "m", "g", "t"], "description": "Genome size unit"}),
                "coverage": ("FLOAT", {"default": "", "min": 0, "description": "Desired read coverage or BAM depth"}),
                "bases": ("FLOAT", {"default": "", "min": 0, "description": "Target number of bases"}),
                "num_bases_unit": ("STRING", {"default": "b", "options": ["b", "k", "m", "g", "t"], "description": "Target bases unit"}),
                "num": ("INT", {"default": "", "min": 1, "description": "Target number of reads"}),
                "frac": ("FLOAT", {"default": 0.1, "min": 0, "max": 1, "description": "Fraction of reads to keep"}),
                "seed": ("INT", {"default": "", "description": "Random seed for reproducible subsampling"}),
                "strict": ("BOOLEAN", {"default": False, "description": "Exit if the requested subsample cannot be met", "advanced": True}),
                "verbose": ("BOOLEAN", {"default": False, "description": "Enable verbose Rasusa logging", "advanced": True}),
                "output_ext": ("STRING", {"default": "fastq.gz", "options": ["fastq.gz", "fastq", "fasta.gz", "fasta"], "description": "Read output extension"}),
                "compress_type": ("STRING", {"default": "", "options": ["", "u", "g", "b", "x", "z"], "description": "Override FASTA/FASTQ output compression", "advanced": True}),
                "compress_level": ("INT", {"default": "", "min": 1, "max": 21, "description": "Compression level for compressed reads output", "advanced": True}),
                "output_format": ("STRING", {"default": "", "options": ["", "fasta", "fastq", "sam", "bam", "cram"], "description": "Override Rasusa reads output format", "advanced": True}),
                "strategy": ("STRING", {"default": "stream", "options": ["stream", "fetch"], "description": "Alignment downsampling strategy", "advanced": True}),
                "swap_distance": ("INT", {"default": "", "min": 0, "description": "Stream strategy swap distance", "advanced": True}),
                "step_size": ("INT", {"default": 100, "min": 1, "description": "Fetch strategy step size", "advanced": True}),
                "batch_size": ("INT", {"default": "", "min": 1000, "description": "Fetch strategy batch size", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }
