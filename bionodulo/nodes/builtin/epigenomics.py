"""Epigenomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from ._bam_index import validate_colocated_bam_index

DSS_DMR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dss_dmr.R"


def _safe_output_stem(value: Any, default: str) -> str:
    stem = "_".join(str(value or "").strip().split())
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
    stem = stem.strip("._-")
    return stem or default


def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace("\n", ",").split(",") if part.strip()]


def _split_window_sizes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(",", " ").split() if part.strip()]


def _split_base_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    bases: list[str] = []
    for item in values:
        bases.extend(part.strip() for part in str(item).replace(",", " ").split() if part.strip())
    return bases


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


class BismarkGenomePreparationNode(CommandNode):
    """Build the Bismark bisulfite genome index from a reference folder.

    Bismark alignment needs a genome folder containing the reference FASTA plus a
    ``Bisulfite_Genome/`` index. This node copies the reference folder so the
    prepared index is a self-contained output, then builds the index in place.
    """
    NODE_ID = "bismark_genome_preparation"
    DISPLAY_NAME = "Bismark Genome Preparation"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Build the Bisulfite_Genome index that a genome folder must contain before Bismark alignment."
    SEARCH_ALIASES = ["bismark", "bisulfite", "genome preparation", "index", "wgbs", "prepare"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("genome_folder",)
    REQUIRED_EXECUTABLES = ["bismark_genome_preparation"]
    REQUIRED_CONDA_PACKAGES = ["bismark", "bowtie2"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/bismark/"
    VERSION = "0.24.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        genome_folder = str(inputs.get("genome_folder", ""))
        aligner = str(inputs.get("aligner", "bowtie2") or "bowtie2").strip().lower()
        flag = "--hisat2" if aligner == "hisat2" else "--bowtie2"
        prepared = f"{out_dir}/genome"
        return [
            "mkdir", "-p", prepared, "&&",
            "cp", "-rL", f"{genome_folder}/.", prepared, "&&",
            "bismark_genome_preparation", flag, prepared,
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome_folder": ("DIRECTORY", {"description": "Folder containing the reference FASTA"}),
            },
            "optional": {
                "aligner": ("STRING", {"default": "bowtie2", "options": ["bowtie2", "hisat2"], "description": "Index aligner", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "genome"]


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


class BismarkMethylationNode(BismarkMethylationExtractorNode):
    """Compatibility wrapper for the original Bismark methylation roadmap node ID."""

    NODE_ID = "bismark_methylation"
    DISPLAY_NAME = "Bismark Methylation"
    DESCRIPTION = "Extract methylation calls from Bismark-aligned BAM files."
    SEARCH_ALIASES = [
        "bismark methylation",
        "bismark",
        "methylation",
        "methylation extractor",
        "cpg",
        "cytosine",
        "bedgraph",
        "bisulfite",
    ]


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


class DSSDMRNode(CommandNode):
    """Detect differentially methylated regions with Bioconductor DSS."""

    NODE_ID = "dss_dmr"
    DISPLAY_NAME = "DSS DMR"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Detect differentially methylated regions from bisulfite methylation count tables using DSS."
    SEARCH_ALIASES = ["DSS", "DMR", "differential methylation", "bisulfite", "methylation", "epigenomics"]
    RETURN_TYPES = ("BED", "FILE")
    RETURN_NAMES = ("dmr", "dmr_stats")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-dss", "r-readr"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/DSS/"
    VERSION = "2.48.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "methylation_files": (
                    "STRING",
                    {"description": "Comma- or newline-separated DSS methylation count tables"},
                ),
                "sample_info": ("FILE", {"description": "Sample metadata table"}),
                "condition_column": ("STRING", {"default": "condition", "description": "Column in sample_info containing conditions"}),
                "sample_column": ("STRING", {"default": "sample", "description": "Column in sample_info containing sample IDs"}),
            },
            "optional": {
                "smoothing": ("BOOLEAN", {"default": True, "description": "Enable DSS smoothing"}),
                "delta": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "description": "Minimum methylation difference"}),
                "pvalue": ("FLOAT", {"default": 0.001, "min": 0.0, "max": 1.0, "description": "DMR p-value threshold"}),
                "minlen": ("INT", {"default": 50, "min": 1, "description": "Minimum DMR length"}),
                "mincg": ("INT", {"default": 3, "min": 1, "description": "Minimum CpG count"}),
                "output_prefix": ("STRING", {"default": "dss_dmr", "description": "Output filename stem"}),
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
        if len(_split_path_list(inputs.get("methylation_files"))) < 2:
            return "At least two methylation files are required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output_bed, output_stats = cls._output_paths(inputs, inputs.get("output", "."))
        cmd = [
            "Rscript",
            str(DSS_DMR_SCRIPT),
            "--methylation-files",
            ",".join(_split_path_list(inputs.get("methylation_files"))),
            "--sample-info",
            str(inputs.get("sample_info", "")),
            "--condition-column",
            str(inputs.get("condition_column", "condition")),
            "--sample-column",
            str(inputs.get("sample_column", "sample")),
            "--output-bed",
            str(output_bed),
            "--output-stats",
            str(output_stats),
            "--delta",
            str(inputs.get("delta", 0.1)),
            "--pvalue",
            str(inputs.get("pvalue", 0.001)),
            "--minlen",
            str(inputs.get("minlen", 50)),
            "--mincg",
            str(inputs.get("mincg", 3)),
        ]
        if inputs.get("smoothing", True):
            cmd.append("--smoothing")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._output_paths(inputs, node_out))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        stem = _safe_output_stem(inputs.get("output_prefix"), "dss_dmr")
        out_dir = Path(output_dir)
        return out_dir / f"{stem}.dmr.bed", out_dir / f"{stem}.dmr_stats.tsv"


class ModkitDMRNode(CommandNode):
    """Detect differentially methylated regions from modkit bedMethyl pileups."""

    NODE_ID = "modkit_dmr"
    DISPLAY_NAME = "Modkit DMR"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Detect differentially methylated regions between two modkit bedMethyl pileups."
    SEARCH_ALIASES = ["modkit", "dmr", "dmr pair", "differential methylation", "methylation", "bedmethyl"]
    RETURN_TYPES = ("BED", "FILE")
    RETURN_NAMES = ("dmr", "log")
    REQUIRED_EXECUTABLES = ["modkit"]
    REQUIRED_CONDA_PACKAGES = ["modkit"]
    DOCUMENTATION_URL = "https://nanoporetech.github.io/modkit/dmr.html"
    VERSION = "0.4.3"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sample_a": ("BED", {"description": "First bgzipped modkit bedMethyl pileup"}),
                "sample_b": ("BED", {"description": "Second bgzipped modkit bedMethyl pileup"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for the pileups"}),
                "base": ("STRING", {"default": "C", "description": "Canonical base(s), comma- or space-separated"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "optional": {
                "index_a": ("FILE", {"description": "Tabix index for sample_a"}),
                "index_b": ("FILE", {"description": "Tabix index for sample_b"}),
                "regions": ("BED", {"description": "Regions to test; omit for single-base analysis"}),
                "segment": ("BED", {"description": "Segments for region-free DMR segmentation"}),
                "fine_grained": ("BOOLEAN", {"default": False, "description": "Report fine-grained DMR scores"}),
                "output_prefix": ("STRING", {"default": "modkit_dmr", "description": "Output filename stem"}),
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
        for field in ("sample_a", "sample_b", "reference"):
            if not str(inputs.get(field, "")).strip():
                return f"{field} is required"
        if not _split_base_list(inputs.get("base")):
            return "At least one base is required"
        threads = inputs.get("threads", 1)
        if threads < 1:
            return "threads must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output_bed, output_log = cls._output_paths(inputs, inputs.get("output", "."))
        cmd = [
            "modkit",
            "dmr",
            "pair",
            "-a",
            str(inputs.get("sample_a", "")),
        ]
        if inputs.get("index_a"):
            cmd.extend(["--index-a", str(inputs["index_a"])])
        cmd.extend([
            "-b",
            str(inputs.get("sample_b", "")),
        ])
        if inputs.get("index_b"):
            cmd.extend(["--index-b", str(inputs["index_b"])])
        cmd.extend([
            "-o",
            str(output_bed),
            "--ref",
            str(inputs.get("reference", "")),
        ])
        for base in _split_base_list(inputs.get("base")):
            cmd.extend(["--base", base])
        cmd.extend([
            "--threads",
            str(inputs.get("threads", 4)),
            "--log-filepath",
            str(output_log),
        ])
        if inputs.get("regions"):
            cmd.extend(["-r", str(inputs["regions"])])
        if inputs.get("segment"):
            cmd.extend(["--segment", str(inputs["segment"])])
        if inputs.get("fine_grained"):
            cmd.append("--fine-grained")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._output_paths(inputs, node_out))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        stem = _safe_output_stem(inputs.get("output_prefix"), "modkit_dmr")
        out_dir = Path(output_dir)
        return out_dir / f"{stem}.dmr.bed", out_dir / f"{stem}.dmr.log"


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
                "bam_index": ("BAI", {"description": "BAI colocated with input BAM"}),
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

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return validate_colocated_bam_index(inputs)


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


class DeepToolsPlotProfileNode(CommandNode):
    """Generate average profile plots from deepTools matrix output."""
    NODE_ID = "deeptools_plot_profile"
    DISPLAY_NAME = "deepTools Plot Profile"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Plot average signal profiles from deepTools computeMatrix output."
    SEARCH_ALIASES = ["deeptools", "plotprofile", "profile plot", "average profile", "signal profile"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("profile",)
    REQUIRED_EXECUTABLES = ["plotProfile"]
    REQUIRED_CONDA_PACKAGES = ["deeptools"]
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/"
    VERSION = "3.5.6"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "plotProfile",
            "-m",
            str(inputs.get("matrix", "")),
            "--outFileName",
            f"{out_dir}/profile.png",
        ]
        plot_title = inputs.get("plot_title")
        if plot_title:
            cmd.extend(["--plotTitle", str(plot_title)])
        plot_type = inputs.get("plot_type", "lines")
        if plot_type:
            cmd.extend(["--plotType", str(plot_type)])
        if inputs.get("plot_height"):
            cmd.extend(["--plotHeight", str(inputs["plot_height"])])
        if inputs.get("plot_width"):
            cmd.extend(["--plotWidth", str(inputs["plot_width"])])
        if inputs.get("per_group"):
            cmd.append("--perGroup")
        for input_name, flag in (
            ("colors", "--colors"),
            ("samples_label", "--samplesLabel"),
            ("regions_label", "--regionsLabel"),
            ("y_axis_label", "--yAxisLabel"),
            ("start_label", "--startLabel"),
            ("end_label", "--endLabel"),
        ):
            value = inputs.get(input_name)
            if value:
                cmd.extend([flag, str(value)])
        legend_location = inputs.get("legend_location", "best")
        if legend_location:
            cmd.extend(["--legendLocation", str(legend_location)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "profile.png"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "matrix": ("FILE", {"description": "Matrix from computeMatrix"}),
            },
            "optional": {
                "plot_title": ("STRING", {"default": ""}),
                "plot_type": (
                    "STRING",
                    {"default": "lines", "options": ["lines", "fill", "se", "std", "overlapped_lines", "heatmap"]},
                ),
                "plot_height": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "plot_width": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "per_group": ("BOOLEAN", {"default": False}),
                "colors": ("STRING", {"default": "", "description": "Space-separated matplotlib color names"}),
                "samples_label": ("STRING", {"default": ""}),
                "regions_label": ("STRING", {"default": ""}),
                "y_axis_label": ("STRING", {"default": ""}),
                "start_label": ("STRING", {"default": ""}),
                "end_label": ("STRING", {"default": ""}),
                "legend_location": (
                    "STRING",
                    {
                        "default": "best",
                        "options": [
                            "best",
                            "upper-right",
                            "upper-left",
                            "lower-left",
                            "lower-right",
                            "none",
                        ],
                    },
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class HICProNode(CommandNode):
    """Run the HiC-Pro pipeline for Hi-C read processing."""
    NODE_ID = "hic_pro"
    DISPLAY_NAME = "HiC-Pro Pipeline"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Complete Hi-C processing: alignment, valid pairs, dedup, contact matrices, ICE normalization."
    SEARCH_ALIASES = ["hic-pro", "hic", "3d genome", "chromatin contacts", "contact matrix"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("hic_results",)
    REQUIRED_EXECUTABLES = ["HiC-Pro"]
    REQUIRED_CONDA_PACKAGES = ["hic-pro"]
    DOCUMENTATION_URL = "https://github.com/nservant/HiC-Pro"
    VERSION = "3.1.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get("output", "."))
        out_dir.mkdir(parents=True, exist_ok=True)
        config_file = out_dir / "hicpro_config.txt"
        config_file.write_text(
            "\n".join([
                f"N_CPU = {inputs.get('threads', 8)}",
                f"REFERENCE_GENOME = {inputs.get('genome_fasta', '')}",
                f"GENOME_SIZE = {inputs.get('chrom_sizes', '')}",
                f"BOWTIE2_IDX_PATH = {inputs.get('bowtie2_index_dir', '')}",
                "PAIR1_EXT = _R1",
                "PAIR2_EXT = _R2",
                f"MIN_MAPQ = {inputs.get('min_mapq', 10)}",
                f"BIN_SIZE = {inputs.get('bin_sizes', '5000 10000 20000 40000 100000 1000000')}",
                f"MAX_ITER = {inputs.get('max_iter', 100)}",
            ])
            + "\n"
        )
        return ["HiC-Pro", "-i", str(inputs.get("input_dir", "")), "-o", str(out_dir), "-c", str(config_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "hic_results"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_dir": ("DIRECTORY", {"description": "FASTQ directory (_R1/_R2 naming)"}),
                "genome_fasta": ("FASTA", {"description": "Reference FASTA"}),
                "bowtie2_index_dir": ("DIRECTORY", {"description": "Bowtie2 index directory"}),
                "chrom_sizes": ("FILE", {"description": "Chromosome sizes file"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
            },
            "optional": {
                "min_mapq": ("INT", {"default": 10, "min": 0}),
                "bin_sizes": ("STRING", {"default": "5000 10000 20000 40000 100000 1000000"}),
                "max_iter": ("INT", {"default": 100, "min": 1, "label": "ICE Max Iter"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class JuicerNode(CommandNode):
    """Run the Juicer Hi-C processing pipeline."""
    NODE_ID = "juicer"
    DISPLAY_NAME = "Juicer Pipeline"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Process Hi-C data with Juicer. Generates .hic files with HiCCUPS loop calling and Arrowhead TAD calling."
    SEARCH_ALIASES = ["juicer", "hic", "juicebox", "hiccups", "arrowhead", "tad", "loops"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("hic_file",)
    REQUIRED_EXECUTABLES = ["juicer.sh"]
    REQUIRED_CONDA_PACKAGES = ["juicer"]
    DOCUMENTATION_URL = "https://github.com/aidenlab/juicer"
    VERSION = "2.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "juicer.sh",
            "-g",
            str(inputs.get("genome_id", "")),
            "-d",
            str(inputs.get("fastq_dir", "")),
            "-s",
            str(inputs.get("restriction_site", "none")),
            "-p",
            str(inputs.get("chrom_sizes", "")),
            "-D",
            str(inputs.get("output", ".")),
        ]
        if inputs.get("restriction_sites_bed"):
            cmd.extend(["-y", str(inputs["restriction_sites_bed"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "hic_file.hic"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq_dir": ("DIRECTORY", {"description": "_R1.fastq.gz and _R2.fastq.gz files"}),
                "genome_id": ("STRING", {"description": "Genome ID (hg38, mm10)"}),
                "chrom_sizes": ("FILE", {"description": "Chromosome sizes"}),
                "restriction_site": ("STRING", {"default": "none", "description": "Enzyme site (e.g., GATC)"}),
            },
            "optional": {
                "restriction_sites_bed": ("BED", {"description": "Restriction sites BED"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CoolerNode(CommandNode):
    """Create and process Hi-C contact matrices with cooler."""
    NODE_ID = "cooler"
    DISPLAY_NAME = "Cooler Matrix"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Create, zoomify, and balance Hi-C contact matrices in cooler format."
    SEARCH_ALIASES = ["cooler", "hic", "contact matrix", "cool", "mcool", "ice normalization"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("mcool",)
    REQUIRED_EXECUTABLES = ["cooler"]
    REQUIRED_CONDA_PACKAGES = ["cooler", "cooltools"]
    DOCUMENTATION_URL = "https://cooler.readthedocs.io/"
    VERSION = "0.10.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        mode = inputs.get("mode", "cload")
        chrom_sizes = str(inputs.get("chrom_sizes", ""))
        bin_size = str(inputs.get("bin_size", 10000))
        input_data = str(inputs.get("input_data", ""))
        threads = str(inputs.get("threads", 4))
        out_cool = f"{out_dir}/matrix.cool"
        out_mcool = f"{out_dir}/mcool.mcool"

        if mode == "cload":
            cmd = ["cooler", "cload", "pairs", f"{chrom_sizes}:{bin_size}", input_data, out_cool]
            cmd.extend(["&&", "cooler", "zoomify", "-p", threads, "-o", out_mcool, out_cool])
            cmd.extend(["&&", "cooler", "balance", "-p", threads, out_mcool])
            return cmd
        if mode == "csort":
            return [
                "cooler",
                "csort",
                "-k2,2n",
                "-k4,4n",
                "-c1",
                "-c3",
                "-p",
                threads,
                chrom_sizes,
                input_data,
                f"{out_dir}/sorted.pairs.gz",
            ]
        return ["cooler", "balance", "--cis-only", "-p", threads, input_data]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "mcool.mcool"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": ("FILE", {"description": "Input depending on mode"}),
                "mode": ("STRING", {"default": "cload", "options": ["cload", "csort", "balance"]}),
            },
            "optional": {
                "chrom_sizes": ("FILE", {"description": "Chrom sizes (for cload/csort)"}),
                "bin_size": ("INT", {"default": 10000, "min": 100}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CooltoolsCompartmentsNode(CommandNode):
    """Call A/B compartments from balanced Hi-C contact matrices with cooltools."""

    NODE_ID = "cooltools_compartments"
    DISPLAY_NAME = "cooltools Compartments"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Call A/B compartments with cooltools eigs-cis from balanced Hi-C matrices."
    SEARCH_ALIASES = ["cooltools", "hic", "compartments", "eigs-cis", "eigenvector", "a/b compartments"]
    RETURN_TYPES = ("TSV", "FILE")
    RETURN_NAMES = ("compartment_track", "eigenvalues")
    REQUIRED_EXECUTABLES = ["cooltools"]
    REQUIRED_CONDA_PACKAGES = ["cooltools"]
    DOCUMENTATION_URL = "https://cooltools.readthedocs.io/en/latest/cli.html#eigs-cis"
    VERSION = "0.7.0"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        n_eigs = inputs.get("n_eigs", 3)
        if int(n_eigs if n_eigs is not None else 3) < 1:
            return "n_eigs must be at least 1."
        ignore_diags = inputs.get("ignore_diags", 0)
        if int(ignore_diags if ignore_diags is not None else 0) < 0:
            return "ignore_diags must be zero or greater."
        return True

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        return Path(output_dir) / _safe_output_stem(inputs.get("output_prefix"), "compartments")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_prefix = cls._out_prefix(inputs, inputs.get("output", "."))
        cmd = ["cooltools", "eigs-cis"]
        if inputs.get("phasing_track"):
            cmd.extend(["--phasing-track", str(inputs["phasing_track"])])
        if inputs.get("view_file"):
            cmd.extend(["--view", str(inputs["view_file"])])
        cmd.extend(["--n-eigs", str(inputs.get("n_eigs", 3))])
        if inputs.get("clr_weight_name"):
            cmd.extend(["--clr-weight-name", str(inputs["clr_weight_name"])])
        if inputs.get("ignore_diags"):
            cmd.extend(["--ignore-diags", str(inputs["ignore_diags"])])
        cmd.extend(["-o", str(out_prefix), str(inputs.get("cooler_uri", ""))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        out_prefix = cls._out_prefix(inputs, node_out)
        return [
            Path(f"{out_prefix}.cis.vecs.tsv"),
            Path(f"{out_prefix}.cis.lam.txt"),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cooler_uri": ("FILE", {"description": "Balanced .cool/.mcool URI, optionally with ::resolutions/bin"}),
            },
            "optional": {
                "phasing_track": ("TSV", {"description": "BedGraph-like phasing track, optionally path::column"}),
                "view_file": ("BED", {"description": "Optional genomic view BED"}),
                "n_eigs": ("INT", {"default": 3, "min": 1, "max": 10}),
                "clr_weight_name": ("STRING", {"default": "weight", "description": "Cooler balancing weight column"}),
                "ignore_diags": ("INT", {"default": 0, "min": 0}),
                "output_prefix": ("STRING", {"default": "compartments"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CooltoolsInsulationNode(CommandNode):
    """Calculate Hi-C insulation scores and boundaries with cooltools."""

    NODE_ID = "cooltools_insulation"
    DISPLAY_NAME = "cooltools Insulation"
    CATEGORY = "epigenomics"
    DESCRIPTION = "Calculate diamond insulation scores and call insulating boundaries with cooltools."
    SEARCH_ALIASES = ["cooltools", "hic", "insulation", "boundaries", "tad", "domains"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("insulation",)
    REQUIRED_EXECUTABLES = ["cooltools"]
    REQUIRED_CONDA_PACKAGES = ["cooltools"]
    DOCUMENTATION_URL = "https://cooltools.readthedocs.io/en/latest/cli.html#insulation"
    VERSION = "0.7.0"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        window_sizes = _split_window_sizes(inputs.get("window_sizes"))
        if not window_sizes:
            return "At least one window size is required."
        for window in window_sizes:
            if int(window) <= 0:
                return "window sizes must be positive integers."
        nproc = inputs.get("nproc", 1)
        if int(nproc if nproc is not None else 1) < 1:
            return "nproc must be at least 1."
        ignore_diags = inputs.get("ignore_diags", 0)
        if int(ignore_diags if ignore_diags is not None else 0) < 0:
            return "ignore_diags must be zero or greater."
        min_frac_valid_pixels = inputs.get("min_frac_valid_pixels", 0.66)
        if not 0 <= float(min_frac_valid_pixels if min_frac_valid_pixels is not None else 0.66) <= 1:
            return "min_frac_valid_pixels must be between 0 and 1."
        min_dist_bad_bin = inputs.get("min_dist_bad_bin", 0)
        if int(min_dist_bad_bin if min_dist_bad_bin is not None else 0) < 0:
            return "min_dist_bad_bin must be zero or greater."
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = inputs.get("output", ".")
        cmd = [
            "cooltools",
            "insulation",
            "-p",
            str(inputs.get("nproc", 1)),
            "-o",
            f"{out_dir}/insulation.tsv",
        ]
        if inputs.get("view_file"):
            cmd.extend(["--view", str(inputs["view_file"])])
        if inputs.get("clr_weight_name"):
            cmd.extend(["--clr-weight-name", str(inputs["clr_weight_name"])])
        if inputs.get("ignore_diags"):
            cmd.extend(["--ignore-diags", str(inputs["ignore_diags"])])
        if inputs.get("min_frac_valid_pixels") is not None:
            cmd.extend(["--min-frac-valid-pixels", str(inputs.get("min_frac_valid_pixels"))])
        if inputs.get("min_dist_bad_bin"):
            cmd.extend(["--min-dist-bad-bin", str(inputs["min_dist_bad_bin"])])
        if inputs.get("threshold"):
            cmd.extend(["--threshold", str(inputs["threshold"])])
        if inputs.get("window_pixels"):
            cmd.append("--window-pixels")
        if inputs.get("append_raw_scores"):
            cmd.append("--append-raw-scores")
        if inputs.get("chunksize"):
            cmd.extend(["--chunksize", str(inputs["chunksize"])])
        cmd.append(str(inputs.get("cooler_uri", "")))
        cmd.extend(_split_window_sizes(inputs.get("window_sizes")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "insulation.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cooler_uri": ("FILE", {"description": "Balanced .cool/.mcool URI, optionally with ::resolutions/bin"}),
                "window_sizes": ("STRING", {"default": "100000", "description": "Comma- or space-separated insulation windows"}),
            },
            "optional": {
                "view_file": ("BED", {"description": "Optional genomic view BED"}),
                "nproc": ("INT", {"default": 1, "min": 1, "max": 64}),
                "clr_weight_name": ("STRING", {"default": "weight", "description": "Cooler balancing weight column"}),
                "ignore_diags": ("INT", {"default": 0, "min": 0}),
                "min_frac_valid_pixels": ("FLOAT", {"default": 0.66, "min": 0.0, "max": 1.0}),
                "min_dist_bad_bin": ("INT", {"default": 0, "min": 0}),
                "threshold": ("STRING", {"default": "0", "description": "Boundary threshold: Li, Otsu, or numeric"}),
                "window_pixels": ("BOOLEAN", {"default": False}),
                "append_raw_scores": ("BOOLEAN", {"default": False}),
                "chunksize": ("INT", {"default": 20000000, "min": 1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
