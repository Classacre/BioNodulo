"""Read trimming and filtering nodes for BioNodulo.

Provides nodes for adapter trimming and quality filtering using
fastp, Trimmomatic, and Cutadapt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _read_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    return [text] if text else []


def _fastq_stem(value: Any, default: str) -> str:
    name = Path(str(value or default)).name
    for suffix in (".fastq.gz", ".fq.gz", ".fastq", ".fq", ".gz"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name or default


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
    VERSION = "0.24.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        cmd = [
            "fastp",
            "-i", str(reads[0]) if len(reads) > 0 else "",
            "-I", str(reads[1]) if len(reads) > 1 else "",
            "-o", f"{output}/trimmed_reads.fastq.gz",
            "-O", f"{output}/trimmed_reads_2.fastq.gz",
            "-h", f"{output}/report.html",
            "-j", f"{output}/report.json",
            "-w", str(inputs.get("threads", 4)),
        ]
        if inputs.get("qualified_quality_phred") is not None:
            cmd.extend(["-q", str(inputs["qualified_quality_phred"])])
        if inputs.get("cut_front"):
            cmd.append("--cut_front")
        if inputs.get("cut_tail"):
            cmd.append("--cut_tail")
        if inputs.get("length_required") is not None:
            cmd.extend(["--length_required", str(inputs["length_required"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "qualified_quality_phred": ("INT", {"default": 15, "min": 1, "max": 40, "description": "Quality threshold for trimming (fastp default: 15)"}),
                "cut_front": ("BOOLEAN", {"default": False, "description": "Trim low-quality bases from 5' end (fastp default: OFF)"}),
                "cut_tail": ("BOOLEAN", {"default": False, "description": "Trim low-quality bases from 3' end (fastp default: OFF)"}),
                "length_required": ("INT", {"default": 15, "min": 1, "description": "Discard reads shorter than this (fastp default: 15)"}),
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
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {
            "outputs": {
                "trimmed_reads": [
                    str(out / "trimmed_reads.fastq.gz"),
                    str(out / "trimmed_reads_2.fastq.gz"),
                ],
                "report": str(out / "report.html"),
            }
        }


class TrimGaloreNode(CommandNode):
    """Bisulfite-aware FASTQ trimming with Trim Galore."""

    NODE_ID = "trim_galore"
    DISPLAY_NAME = "Trim Galore"
    REQUIRED_CONDA_PACKAGES = ["trim-galore"]
    CATEGORY = "trimming"
    DESCRIPTION = "Adapter and quality trimming for FASTQ reads with bisulfite-aware Trim Galore modes."
    SEARCH_ALIASES = ["trim galore", "trim_galore", "bisulfite", "rrbs", "cutadapt", "adapter", "quality trim"]
    RETURN_TYPES = ("FASTQ_LIST", "HTML_REPORT")
    RETURN_NAMES = ("trimmed_reads", "fastqc_report")
    REQUIRED_EXECUTABLES = ["trim_galore"]
    DOCUMENTATION_URL = "https://github.com/FelixKrueger/TrimGalore"
    VERSION = "0.6.10"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        reads = _read_list(inputs.get("reads"))
        paired = bool(inputs.get("paired", True))
        if paired and len(reads) != 2:
            return "paired mode requires exactly two reads."
        if not paired and len(reads) != 1:
            return "single-end mode requires exactly one read."
        if int(inputs.get("threads", 1)) < 1:
            return "threads must be at least 1."
        for field in ("quality", "length", "clip_r1", "clip_r2", "three_prime_clip_r1", "three_prime_clip_r2"):
            if int(inputs.get(field, 0) or 0) < 0:
                return f"{field} must be zero or greater."
        return True

    @classmethod
    def _trimmed_read_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        reads = _read_list(inputs.get("reads"))
        out_dir = Path(output_dir)
        paired = bool(inputs.get("paired", True))
        if paired:
            r1 = _fastq_stem(reads[0] if reads else "R1", "R1")
            r2 = _fastq_stem(reads[1] if len(reads) > 1 else "R2", "R2")
            return [out_dir / f"{r1}_val_1.fq.gz", out_dir / f"{r2}_val_2.fq.gz"]
        stem = _fastq_stem(reads[0] if reads else "reads", "reads")
        return [out_dir / f"{stem}_trimmed.fq.gz"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        reads = _read_list(inputs.get("reads"))
        cmd = ["trim_galore"]
        if inputs.get("paired", True):
            cmd.append("--paired")
        cmd.extend(["--cores", str(inputs.get("threads", 1))])

        for field, flag in (
            ("quality", "--quality"),
            ("length", "--length"),
            ("clip_r1", "--clip_R1"),
            ("clip_r2", "--clip_R2"),
            ("three_prime_clip_r1", "--three_prime_clip_R1"),
            ("three_prime_clip_r2", "--three_prime_clip_R2"),
        ):
            value = int(inputs.get(field, 0) or 0)
            if value > 0:
                cmd.extend([flag, str(value)])
        if inputs.get("rrbs"):
            cmd.append("--rrbs")
        if inputs.get("non_directional"):
            cmd.append("--non_directional")
        if inputs.get("gzip", True):
            cmd.append("--gzip")
        if inputs.get("fastqc", True):
            cmd.append("--fastqc")
        cmd.extend(["-o", output])
        cmd.extend(reads)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return cls._trimmed_read_paths(inputs, node_out) + [node_out / "fastqc_report.html"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Input FASTQ read(s); paired mode expects [R1, R2]"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 8, "display": "slider"}),
            },
            "optional": {
                "paired": ("BOOLEAN", {"default": True, "description": "Run paired-end trimming"}),
                "quality": ("INT", {"default": 20, "min": 0, "max": 40}),
                "length": ("INT", {"default": 20, "min": 0}),
                "clip_r1": ("INT", {"default": 0, "min": 0}),
                "clip_r2": ("INT", {"default": 0, "min": 0}),
                "three_prime_clip_r1": ("INT", {"default": 0, "min": 0}),
                "three_prime_clip_r2": ("INT", {"default": 0, "min": 0}),
                "rrbs": ("BOOLEAN", {"default": False, "description": "Enable RRBS mode"}),
                "non_directional": ("BOOLEAN", {"default": False, "description": "Enable non-directional RRBS libraries"}),
                "gzip": ("BOOLEAN", {"default": True, "description": "Compress FASTQ outputs"}),
                "fastqc": ("BOOLEAN", {"default": True, "description": "Run FastQC after trimming"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run Trim Galore and return grouped trimmed FASTQ paths."""
        output_dir = kwargs.get("output_dir")
        ctx = kwargs.get("context")
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {
            "outputs": {
                "trimmed_reads": [str(path) for path in self.__class__._trimmed_read_paths(kwargs, out)],
                "fastqc_report": str(out / "fastqc_report.html"),
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
    RETURN_TYPES = ("FASTQ_LIST", "FASTQ_LIST", "FASTQ_LIST", "FASTQ_LIST")
    RETURN_NAMES = ("R1_paired", "R1_unpaired", "R2_paired", "R2_unpaired")
    REQUIRED_EXECUTABLES = ["trimmomatic"]
    DOCUMENTATION_URL = "http://www.usadellab.org/cms/?page=trimmomatic"
    VERSION = "0.40"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        cmd = [
            "trimmomatic", "PE",
            "-threads", str(inputs.get("threads", 4)),
            str(reads[0]) if len(reads) > 0 else "",
            str(reads[1]) if len(reads) > 1 else "",
            f"{output}/R1_paired.fastq.gz",
            f"{output}/R1_unpaired.fastq.gz",
            f"{output}/R2_paired.fastq.gz",
            f"{output}/R2_unpaired.fastq.gz",
            f"ILLUMINACLIP:{inputs.get('adapters', 'TruSeq3-PE.fa')}:2:30:10",
            f"LEADING:{inputs.get('leading', 3)}",
            f"TRAILING:{inputs.get('trailing', 3)}",
            f"SLIDINGWINDOW:4:{inputs.get('quality', 15)}",
            f"MINLEN:{inputs.get('minlen', 36)}",
        ]
        return cmd

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

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run Trimmomatic and return all four outputs."""
        output_dir = kwargs.get("output_dir")
        ctx = kwargs.get("context")
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {
            "outputs": {
                "R1_paired": [str(out / "R1_paired.fastq.gz")],
                "R1_unpaired": [str(out / "R1_unpaired.fastq.gz")],
                "R2_paired": [str(out / "R2_paired.fastq.gz")],
                "R2_unpaired": [str(out / "R2_unpaired.fastq.gz")],
            }
        }


class CutadaptNode(CommandNode):
    """Adapter trimming with Cutadapt."""
    NODE_ID = "cutadapt"
    DISPLAY_NAME = "Cutadapt"
    CATEGORY = "trimming"
    DESCRIPTION = "Remove adapter sequences from high-throughput sequencing reads"
    SEARCH_ALIASES = ["cutadapt", "trim adapters", "adapter"]
    RETURN_TYPES = ("FASTQ_LIST",)
    RETURN_NAMES = ("trimmed_reads",)
    REQUIRED_EXECUTABLES = ["cutadapt"]
    REQUIRED_CONDA_PACKAGES = ['cutadapt']
    DOCUMENTATION_URL = "https://cutadapt.readthedocs.io/"
    VERSION = "5.2"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        cmd = [
            "cutadapt",
            "-a", str(inputs.get("adapter_r1", "AGATCGGAAGAGC")),
            "-A", str(inputs.get("adapter_r2", "AGATCGGAAGAGC")),
            "-o", f"{output}/trimmed_reads.fastq.gz",
            "-p", f"{output}/trimmed_reads_2.fastq.gz",
            "-j", str(inputs.get("threads", 4)),
        ]
        if inputs.get("minimum_length") is not None:
            cmd.extend(["-m", str(inputs["minimum_length"])])
        if inputs.get("quality_cutoff") is not None:
            cmd.extend(["-q", str(inputs["quality_cutoff"])])
        if len(reads) > 0:
            cmd.append(str(reads[0]))
        if len(reads) > 1:
            cmd.append(str(reads[1]))
        return cmd

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

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run Cutadapt and return paired trimmed reads."""
        output_dir = kwargs.get("output_dir")
        ctx = kwargs.get("context")
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {
            "outputs": {
                "trimmed_reads": [
                    str(out / "trimmed_reads.fastq.gz"),
                    str(out / "trimmed_reads_2.fastq.gz"),
                ],
            }
        }
