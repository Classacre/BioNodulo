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


class MethylDackelNode(CommandNode):
    """Extract per-base methylation from alignments with MethylDackel."""
    NODE_ID = "methyldackel"
    DISPLAY_NAME = "MethylDackel"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Extract per-base methylation from alignments. Handles directional and non-directional protocols."
    SEARCH_ALIASES = ["methyldackel", "pileometh", "methylation", "bisulfite", "cpg", "extract"]
    RETURN_TYPES = ("BED", "BED")
    RETURN_NAMES = ("methylation_bedgraph", "mbias_report")
    REQUIRED_EXECUTABLES = ["MethylDackel"]
    REQUIRED_CONDA_PACKAGES = ["methyldackel"]
    DOCUMENTATION_URL = "https://github.com/dpryan79/MethylDackel"
    VERSION = "0.6.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        prefix = str(inputs.get("output_prefix", "methyldackel"))
        output_prefix = f"{out_dir}/{prefix}"
        reference = str(inputs.get("reference", ""))
        bam = str(inputs.get("bam", ""))
        cmd = [
            "MethylDackel",
            "mbias",
            reference,
            bam,
            output_prefix,
            "&&",
            "MethylDackel",
            "extract",
            reference,
            bam,
            "-o",
            output_prefix,
            "--bedGraph",
        ]
        if inputs.get("merge_context"):
            cmd.append("--mergeContext")
        if inputs.get("min_depth"):
            cmd.extend(["--minDepth", str(inputs["min_depth"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Sorted, indexed BAM from bisulfite aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "output_prefix": ("STRING", {"default": "methyldackel"}),
            },
            "optional": {
                "merge_context": ("BOOLEAN", {"default": True, "description": "Merge strands into CpG"}),
                "min_depth": ("INT", {"default": 1, "min": 1, "label": "Min Coverage"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DeepToolsBamCoverageNode(CommandNode):
    """Convert BAM alignments to bigWig coverage tracks with deepTools."""
    NODE_ID = "deeptools_bamcoverage"
    DISPLAY_NAME = "deepTools bamCoverage"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Convert BAM to bigWig coverage tracks. Supports CPM, RPGC, BPM normalization."
    SEARCH_ALIASES = ["deeptools", "bamcoverage", "bigwig", "coverage", "chip-seq", "atac-seq"]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("coverage_bw",)
    REQUIRED_EXECUTABLES = ["bamCoverage"]
    REQUIRED_CONDA_PACKAGES = ["deeptools"]
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/"
    VERSION = "3.5.6"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = inputs.get("output", ".")
        cmd = [
            "bamCoverage",
            "-b",
            str(inputs.get("bam", "")),
            "-o",
            f"{output}/coverage_bw.bw",
            "-p",
            str(inputs.get("threads", 4)),
            "--binSize",
            str(inputs.get("bin_size", 10)),
        ]
        normalize_using = inputs.get("normalize_using", "CPM")
        if normalize_using and normalize_using != "None":
            cmd.extend(["--normalizeUsing", str(normalize_using)])
        if inputs.get("effective_genome_size"):
            cmd.extend(["--effectiveGenomeSize", str(inputs["effective_genome_size"])])
        if inputs.get("center_reads"):
            cmd.append("--centerReads")
        if inputs.get("ignore_duplicates"):
            cmd.append("--ignoreDuplicates")
        if inputs.get("extend_reads"):
            cmd.extend(["--extendReads", str(inputs["extend_reads"])])
        if inputs.get("blacklist"):
            cmd.extend(["--blackListFileName", str(inputs["blacklist"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Sorted, indexed BAM"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "normalize_using": (
                    "STRING",
                    {"default": "CPM", "options": ["CPM", "BPM", "RPGC", "RPKM", "None"]},
                ),
            },
            "optional": {
                "bin_size": ("INT", {"default": 10, "min": 1}),
                "effective_genome_size": (
                    "INT",
                    {"default": 0, "min": 0, "label": "Eff. Genome Size (0=auto)"},
                ),
                "center_reads": ("BOOLEAN", {"default": False}),
                "ignore_duplicates": ("BOOLEAN", {"default": True}),
                "extend_reads": ("INT", {"default": 0, "min": 0, "label": "Extend Reads (0=auto)"}),
                "blacklist": ("BED", {"description": "Blacklist regions"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DeepToolsComputeMatrixNode(CommandNode):
    """Prepare signal matrices around genomic features for deepTools plots."""
    NODE_ID = "deeptools_compute_matrix"
    DISPLAY_NAME = "deepTools computeMatrix"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Prepare signal matrices around genomic features for heatmap/profile plots."
    SEARCH_ALIASES = ["deeptools", "computematrix", "heatmap matrix", "signal profile"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("matrix",)
    REQUIRED_EXECUTABLES = ["computeMatrix"]
    REQUIRED_CONDA_PACKAGES = ["deeptools"]
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/"
    VERSION = "3.5.6"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        mode = str(inputs.get("mode", "reference-point"))
        cmd = [
            "computeMatrix",
            mode,
            "-S",
            str(inputs.get("bigwig", "")),
            "-R",
            str(inputs.get("regions", "")),
            "-o",
            f"{out_dir}/matrix.gz",
            "-p",
            str(inputs.get("threads", 4)),
            "--binSize",
            str(inputs.get("bin_size", 10)),
        ]
        if mode == "reference-point":
            cmd.extend([
                "--referencePoint",
                str(inputs.get("reference_point", "TSS")),
                "-b",
                str(inputs.get("before_region", 3000)),
                "-a",
                str(inputs.get("after_region", 3000)),
            ])
        else:
            cmd.extend([
                "-b",
                str(inputs.get("before_region", 3000)),
                "-a",
                str(inputs.get("after_region", 3000)),
                "--regionBodyLength",
                str(inputs.get("region_body_length", 5000)),
            ])
        if inputs.get("skip_zeros"):
            cmd.append("--skipZeros")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bigwig": ("BIGWIG", {"description": "bigWig file(s)"}),
                "regions": ("BED", {"description": "Regions BED"}),
                "mode": (
                    "STRING",
                    {"default": "reference-point", "options": ["reference-point", "scale-regions"]},
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "reference_point": ("STRING", {"default": "TSS", "options": ["TSS", "TES", "center"]}),
                "before_region": ("INT", {"default": 3000, "min": 0}),
                "after_region": ("INT", {"default": 3000, "min": 0}),
                "region_body_length": ("INT", {"default": 5000, "min": 0}),
                "skip_zeros": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DeepToolsPlotHeatmapNode(CommandNode):
    """Generate heatmap and profile images from deepTools matrix output."""
    NODE_ID = "deeptools_plot_heatmap"
    DISPLAY_NAME = "deepTools Plot Heatmap"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Publication-quality heatmaps and profile plots from computeMatrix output."
    SEARCH_ALIASES = ["deeptools", "plotheatmap", "heatmap", "profile plot"]
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("heatmap", "profile_plot")
    REQUIRED_EXECUTABLES = ["plotHeatmap"]
    REQUIRED_CONDA_PACKAGES = ["deeptools"]
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/"
    VERSION = "3.5.6"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        matrix = str(inputs.get("matrix", ""))
        heatmap = [
            "plotHeatmap",
            "-m",
            matrix,
            "--heatmapHeight",
            str(inputs.get("heatmap_height", 25)),
            "--heatmapWidth",
            str(inputs.get("heatmap_width", 15)),
            "--colorMap",
            str(inputs.get("colormap", "RdBu_r")),
            "--outFileName",
            f"{out_dir}/heatmap.png",
        ]
        sort_regions = inputs.get("sort_regions")
        if sort_regions and sort_regions != "no":
            heatmap.extend(["--sortRegions", str(sort_regions)])
        if inputs.get("kmeans") and int(inputs["kmeans"]) > 0:
            heatmap.extend(["--kmeans", str(inputs["kmeans"])])
        plot_title = inputs.get("plot_title")
        if plot_title:
            heatmap.extend(["--plotTitle", str(plot_title)])
        profile = [
            "plotProfile",
            "-m",
            matrix,
            "--outFileName",
            f"{out_dir}/profile_plot.png",
        ]
        if plot_title:
            profile.extend(["--plotTitle", str(plot_title)])
        return heatmap + ["&&"] + profile

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "heatmap.png", node_out / "profile_plot.png"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "matrix": ("FILE", {"description": "Matrix from computeMatrix"}),
            },
            "optional": {
                "heatmap_height": ("INT", {"default": 25, "min": 5}),
                "heatmap_width": ("INT", {"default": 15, "min": 5}),
                "colormap": (
                    "STRING",
                    {"default": "RdBu_r", "options": ["RdBu_r", "hot", "coolwarm", "viridis"]},
                ),
                "sort_regions": (
                    "STRING",
                    {"default": "no", "options": ["no", "descend", "ascend", "mean"]},
                ),
                "kmeans": ("INT", {"default": 0, "min": 0, "max": 20, "label": "K-means (0=off)"}),
                "plot_title": ("STRING", {"default": ""}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
