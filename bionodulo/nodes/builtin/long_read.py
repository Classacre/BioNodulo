"""Long-read sequencing nodes."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


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


class MedakaConsensusNode(CommandNode):
    """Polish Oxford Nanopore draft assemblies with Medaka."""
    NODE_ID = "medaka_consensus"
    DISPLAY_NAME = "Medaka Consensus"
    CATEGORY = "long_read"
    DESCRIPTION = "Neural network polishing of ONT assemblies. Corrects indel and substitution errors."
    SEARCH_ALIASES = ["medaka", "polish", "consensus", "nanopore", "assembly polish"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("polished_assembly",)
    REQUIRED_EXECUTABLES = ["medaka_consensus"]
    REQUIRED_CONDA_PACKAGES = ["medaka"]
    DOCUMENTATION_URL = "https://github.com/nanoporetech/medaka"
    VERSION = "2.0.1"
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out_dir = Path(output_dir) / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return [out_dir / "consensus.fasta"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "medaka_consensus",
            "-i",
            str(inputs.get("reads", "")),
            "-d",
            str(inputs.get("draft", "")),
            "-o",
            str(out_dir),
            "-t",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("model"):
            cmd.extend(["-m", str(inputs["model"])])
        if inputs.get("bam"):
            cmd.extend(["-b", str(inputs["bam"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Input FASTQ reads"}),
                "draft": ("FASTA", {"description": "Draft assembly to polish"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "model": ("STRING", {"default": "r1041_e82_400_sup_v5.0.0", "description": "Medaka model"}),
                "bam": ("BAM", {"description": "Pre-aligned BAM"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DoradoBasecallerNode(CommandNode):
    """Basecall Oxford Nanopore POD5 reads with Dorado."""
    NODE_ID = "dorado_basecaller"
    DISPLAY_NAME = "Dorado Basecaller"
    CATEGORY = "long_read"
    DESCRIPTION = (
        "Basecall ONT POD5 reads with Dorado. Supports simplex, modified base calling "
        "(5mC, 6mA). GPU-accelerated."
    )
    SEARCH_ALIASES = ["dorado", "basecaller", "ont", "nanopore", "modified bases", "methylation"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("basecalled_bam",)
    REQUIRED_EXECUTABLES = ["dorado"]
    REQUIRED_CONDA_PACKAGES = ["dorado"]
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado"
    VERSION = "0.9.6"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "dorado",
            "basecaller",
            str(inputs.get("model", "sup@latest")),
            str(inputs.get("pod5_dir", "")),
        ]
        if inputs.get("modified_bases"):
            cmd.extend(["--modified-bases", *str(inputs["modified_bases"]).split()])
        if inputs.get("kit_name"):
            cmd.extend(["--kit-name", str(inputs["kit_name"])])
        if inputs.get("trim"):
            cmd.extend(["--trim", str(inputs["trim"])])
        if inputs.get("min_qscore"):
            cmd.extend(["--min-qscore", str(inputs["min_qscore"])])
        if inputs.get("reference"):
            cmd.extend(["--reference", str(inputs["reference"])])
        cmd.extend([">", f"{out_dir}/basecalled_bam.bam"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pod5_dir": ("DIRECTORY", {"description": "Directory with POD5 signal files"}),
                "model": ("STRING", {"default": "sup@latest", "description": "Model (sup@latest, hac@latest, fast@latest)"}),
            },
            "optional": {
                "modified_bases": ("STRING", {"default": "", "description": "Modified bases to call (e.g., '5mC 6mA')"}),
                "kit_name": ("STRING", {"default": "", "description": "Barcoding kit for demux"}),
                "trim": ("STRING", {"default": "all", "options": ["all", "primers", "adapters", "none"]}),
                "min_qscore": ("INT", {"default": 0, "min": 0, "max": 30}),
                "reference": ("FASTA", {"description": "Reference for alignment during basecalling"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DoradoDemuxNode(CommandNode):
    """Demultiplex Oxford Nanopore reads by barcode with Dorado."""

    NODE_ID = "dorado_demux"
    DISPLAY_NAME = "Dorado Demux"
    CATEGORY = "long_read"
    DESCRIPTION = "Demultiplex ONT reads into per-barcode files with Dorado."
    SEARCH_ALIASES = ["dorado", "demux", "demultiplex", "barcoding", "barcode", "nanopore"]
    RETURN_TYPES = ("DIRECTORY", "TSV")
    RETURN_NAMES = ("demux_dir", "barcode_summary")
    REQUIRED_EXECUTABLES = ["dorado"]
    REQUIRED_CONDA_PACKAGES = ["dorado"]
    DOCUMENTATION_URL = "https://software-docs.nanoporetech.com/dorado/latest/barcoding/barcoding/"
    VERSION = "0.9.6"
    SHELL = True
    EXPERIMENTAL = True

    _MODES = {"classify", "split"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation

        mode = str(inputs.get("mode", "classify") or "classify")
        if mode not in cls._MODES:
            return f"Unsupported Dorado demux mode: {mode}"
        if int(inputs.get("threads", 0) or 0) < 0:
            return "threads must be zero or greater."

        kit_name = str(inputs.get("kit_name", "") or "").strip()
        sample_sheet = str(inputs.get("sample_sheet", "") or "").strip()
        barcode_arrangement = str(inputs.get("barcode_arrangement", "") or "").strip()
        barcode_sequences = str(inputs.get("barcode_sequences", "") or "").strip()

        if mode == "classify" and not kit_name and not barcode_arrangement:
            return "kit_name is required when mode is classify."
        if mode == "split":
            if kit_name:
                return "kit_name cannot be used when mode is split."
            if sample_sheet or barcode_arrangement or barcode_sequences:
                return "barcode classification options cannot be used when mode is split."
        if inputs.get("sort_bam") and not inputs.get("no_trim"):
            return "sort_bam requires no_trim so mapped reads remain valid."
        return True

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        node_out = Path(output_dir)
        fallback = f"{_safe_output_stem(inputs.get('reads'), 'dorado')}_demux"
        stem = _safe_output_stem(inputs.get("output_name"), fallback)
        demux_dir = node_out / stem
        return demux_dir, demux_dir / "barcode_summary.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        demux_dir, _summary = cls._planned_paths(inputs, out_dir)
        mode = str(inputs.get("mode", "classify") or "classify")
        threads = int(inputs.get("threads", 0) or 0)

        cmd = [
            "dorado",
            "demux",
            "--output-dir",
            str(demux_dir),
        ]
        if mode == "split":
            cmd.append("--no-classify")
        else:
            kit_name = str(inputs.get("kit_name", "") or "").strip()
            if kit_name:
                cmd.extend(["--kit-name", kit_name])
            if inputs.get("sample_sheet"):
                cmd.extend(["--sample-sheet", str(inputs["sample_sheet"])])
            if inputs.get("barcode_arrangement"):
                cmd.extend(["--barcode-arrangement", str(inputs["barcode_arrangement"])])
            if inputs.get("barcode_sequences"):
                cmd.extend(["--barcode-sequences", str(inputs["barcode_sequences"])])

        if inputs.get("emit_fastq"):
            cmd.append("--emit-fastq")
        if inputs.get("emit_summary"):
            cmd.append("--emit-summary")
        if inputs.get("no_trim"):
            cmd.append("--no-trim")
        if inputs.get("sort_bam"):
            cmd.append("--sort-bam")
        if inputs.get("recursive"):
            cmd.append("--recursive")
        if threads > 0:
            cmd.extend(["--threads", str(threads)])
        cmd.append(str(inputs.get("reads", "")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FILE", {"description": "Basecalled reads in BAM, FASTQ, or an input directory"}),
                "mode": ("STRING", {"default": "classify", "options": ["classify", "split"]}),
            },
            "optional": {
                "kit_name": ("STRING", {"default": "", "description": "Dorado barcode kit name for classification"}),
                "sample_sheet": ("FILE", {"description": "Optional Dorado sample sheet CSV"}),
                "barcode_arrangement": ("FILE", {"description": "Custom barcode arrangement TOML"}),
                "barcode_sequences": ("FASTA", {"description": "Custom barcode sequences FASTA"}),
                "emit_fastq": ("BOOLEAN", {"default": False, "description": "Emit demultiplexed FASTQ instead of BAM"}),
                "emit_summary": ("BOOLEAN", {"default": True, "description": "Emit per-read barcode summary"}),
                "no_trim": ("BOOLEAN", {"default": False, "description": "Preserve barcode sequence and mapping tags"}),
                "sort_bam": ("BOOLEAN", {"default": False, "description": "Sort and index mapped BAM outputs"}),
                "recursive": ("BOOLEAN", {"default": False, "description": "Search input folders recursively"}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 128}),
                "output_name": ("STRING", {"default": "", "description": "Optional output directory stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DoradoDuplexNode(CommandNode):
    """Run Dorado duplex basecalling for high-accuracy ONT reads."""
    NODE_ID = "dorado_duplex"
    DISPLAY_NAME = "Dorado Duplex"
    CATEGORY = "long_read"
    DESCRIPTION = "Duplex basecalling for Q30+ ONT accuracy. Both strands of same molecule sequenced."
    SEARCH_ALIASES = ["dorado", "duplex", "ont", "nanopore", "double-strand", "high accuracy"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("duplex_bam",)
    REQUIRED_EXECUTABLES = ["dorado"]
    REQUIRED_CONDA_PACKAGES = ["dorado"]
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado"
    VERSION = "0.9.6"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "dorado",
            "duplex",
            str(inputs.get("model", "sup@latest")),
            str(inputs.get("pod5_dir", "")),
            "-t",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("modified_bases"):
            cmd.extend(["--modified-bases", *str(inputs["modified_bases"]).split()])
        cmd.extend([">", f"{out_dir}/duplex_bam.bam"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pod5_dir": ("DIRECTORY", {"description": "POD5 signal files"}),
                "model": ("STRING", {"default": "sup@latest"}),
            },
            "optional": {
                "modified_bases": ("STRING", {"default": "", "description": "Modified bases"}),
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
