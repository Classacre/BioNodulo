"""Epigenomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

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


from bionodulo.nodes.builtin.bismark_family.align import BismarkAlignNode  # noqa: E402,F401
from bionodulo.nodes.builtin.bismark_family.genome_preparation import (  # noqa: E402,F401
    BismarkGenomePreparationNode,
)
from bionodulo.nodes.builtin.bismark_family.methylation_extractor import (  # noqa: E402,F401
    BismarkMethylationExtractorNode,
    BismarkMethylationNode,
)


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


from bionodulo.nodes.builtin.deeptools_family.bam_coverage import (  # noqa: E402,F401
    DeepToolsBamCoverageNode,
)
from bionodulo.nodes.builtin.deeptools_family.compute_matrix import (  # noqa: E402,F401
    DeepToolsComputeMatrixNode,
)
from bionodulo.nodes.builtin.deeptools_family.plot_heatmap import (  # noqa: E402,F401
    DeepToolsPlotHeatmapNode,
)
from bionodulo.nodes.builtin.deeptools_family.plot_profile import (  # noqa: E402,F401
    DeepToolsPlotProfileNode,
)


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
