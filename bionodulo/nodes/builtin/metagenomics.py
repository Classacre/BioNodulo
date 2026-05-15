"""Metagenomics analysis nodes for BioNodulo.

Provides nodes for taxonomic classification (Kraken2, Bracken, MetaPhlAn),
functional profiling (HUMAnN), binning (MaxBin), and quality assessment (CheckM).
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class Kraken2Node(CommandNode):
    """Taxonomic classification with Kraken2."""
    NODE_ID = "kraken2"
    DISPLAY_NAME = "Kraken2"
    REQUIRED_CONDA_PACKAGES = ['kraken2']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Ultra-fast taxonomic classification of metagenomic reads"
    SEARCH_ALIASES = ["kraken2", "classify", "taxonomy", "metagenomics"]
    RETURN_TYPES = ("KRAKEN_OUTPUT", "KRAKEN_REPORT")
    RETURN_NAMES = ("output", "report")
    REQUIRED_EXECUTABLES = ["kraken2"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/kraken2/"
    VERSION = "2.1.3"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "kraken2",
            "--db", str(inputs.get("db", "")),
            "--output", f"{inputs.get('output', '.')}/kraken2.output",
            "--report", f"{inputs.get('output', '.')}/kraken2.report",
            "--threads", str(inputs.get("threads", 8)),
        ]
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        r1 = reads[0] if len(reads) > 0 else inputs.get("r1", "")
        r2 = reads[1] if len(reads) > 1 else inputs.get("r2", "")
        if r1 and r2:
            cmd.append("--paired")
            cmd.extend([str(r1), str(r2)])
        elif r1:
            cmd.append(str(r1))
        if inputs.get("confidence"):
            cmd.extend(["--confidence", str(inputs["confidence"])])
        if inputs.get("minimum_hit_groups") is not None:
            cmd.extend(["--minimum-hit-groups", str(inputs["minimum_hit_groups"])])
        if inputs.get("memory_mapping"):
            cmd.append("--memory-mapping")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "db": ("DIRECTORY", {"description": "Kraken2 database directory"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "confidence": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Confidence", "advanced": True}),
                "minimum_hit_groups": ("INT", {"default": 2, "label": "Min Hit Groups", "advanced": True}),
                "memory_mapping": ("BOOLEAN", {"default": False, "label": "Memory Mapping", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Kraken2BuildNode(CommandNode):
    """Build Kraken2 database."""
    NODE_ID = "kraken2_build"
    DISPLAY_NAME = "Kraken2 Build DB"
    CATEGORY = "metagenomics"
    DESCRIPTION = "Build a Kraken2 database from reference sequences"
    SEARCH_ALIASES = ["kraken2", "build", "database", "custom db"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("db",)
    REQUIRED_EXECUTABLES = ["kraken2-build"]
    REQUIRED_CONDA_PACKAGES = ['kraken2']
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/kraken2/"
    VERSION = "2.1.3"
    COMMAND = [
        "kraken2-build",
        "--db", "{inputs.db}",
        "--threads", "{inputs.threads}",
        "--download-library", "{inputs.library}",
        "--download-taxonomy",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "db": ("DIRECTORY", {"description": "Output database directory"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "library": ("STRING", {"default": "bacteria", "description": "RefSeq library to download"}),
            },
            "optional": {},
            "hidden": {},
        }


class BrackenNode(CommandNode):
    """Abundance estimation with Bracken."""
    NODE_ID = "bracken"
    DISPLAY_NAME = "Bracken"
    REQUIRED_CONDA_PACKAGES = ['bracken']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Bayesian Re-estimation of Abundance after classification with Kraken"
    SEARCH_ALIASES = ["bracken", "abundance", "kraken", "metagenomics"]
    RETURN_TYPES = ("KRAKEN_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["bracken"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/bracken/"
    VERSION = "2.9"
    COMMAND = [
        "bracken",
        "-d", "{inputs.db}",
        "-i", "{inputs.report}",
        "-o", "{output}/bracken.txt",
        "-w", "{output}/bracken_kreport.txt",
        "-r", "{inputs.read_length}",
        "-l", "{inputs.level}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("KRAKEN_REPORT", {"description": "Kraken2 report file"}),
                "db": ("DIRECTORY", {"description": "Kraken2 database directory"}),
                "read_length": ("STRING", {"default": "100", "description": "Read length (35, 50, 75, 100, 150, 200, 250, 300)"}),
                "level": ("STRING", {"default": "S", "description": "Taxonomic level: D, P, C, O, F, G, S"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MetaPhlAnNode(CommandNode):
    """Taxonomic profiling with MetaPhlAn."""
    NODE_ID = "metaphlan"
    DISPLAY_NAME = "MetaPhlAn"
    REQUIRED_CONDA_PACKAGES = ['metaphlan']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Metagenomic Phylogenetic Analysis for taxonomic profiling"
    SEARCH_ALIASES = ["metaphlan", "profile", "taxonomy", "metagenomics"]
    RETURN_TYPES = ("METAPHLAN_PROFILE",)
    RETURN_NAMES = ("profile",)
    REQUIRED_EXECUTABLES = ["metaphlan"]
    DOCUMENTATION_URL = "https://github.com/biobakery/MetaPhlAn"
    VERSION = "4.1.1"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "metaphlan",
            str(inputs.get("reads", "")),
            "--input_type", "fastq",
            "--nproc", str(inputs.get("threads", 8)),
            "--bowtie2db", str(inputs.get("bt2_db", "")),
            "--index", str(inputs.get("index", "mpa_vOct22_CHOCOPhlAnSGB_202212")),
            "-o", f"{inputs.get('output', '.')}/metaphlan_profile.txt",
            "--bowtie2out", f"{inputs.get('output', '.')}/metaphlan.bowtie2.bz2",
        ]
        if inputs.get("analysis_type"):
            cmd.extend(["-t", str(inputs["analysis_type"])])
        if inputs.get("tax_lev"):
            cmd.extend(["--tax_lev", str(inputs["tax_lev"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Metagenomic reads (single file, concatenated)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "bt2_db": ("DIRECTORY", {"description": "MetaPhlAn Bowtie2 database directory"}),
                "index": ("STRING", {"default": "mpa_vOct22_CHOCOPhlAnSGB_202212"}),
            },
            "optional": {
                "analysis_type": ("STRING", {"default": "rel_ab", "options": ["rel_ab", "rel_ab_w_read_stats", "reads_map", "clade_profiles", "marker_ab_table", "marker_counts"], "label": "Analysis Type", "advanced": True}),
                "tax_lev": ("STRING", {"default": "a", "label": "Taxonomic Level", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class HUMAnNNode(CommandNode):
    """Functional profiling with HUMAnN."""
    NODE_ID = "humann"
    DISPLAY_NAME = "HUMAnN"
    REQUIRED_CONDA_PACKAGES = ['humann']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Functional profiling of microbial communities"
    SEARCH_ALIASES = ["humann", "functional", "pathway", "gene family"]
    RETURN_TYPES = ("HUMANN_OUTPUT",)
    RETURN_NAMES = ("output_dir",)
    REQUIRED_EXECUTABLES = ["humann"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    VERSION = "3.8"
    COMMAND = [
        "humann",
        "--input", "{inputs.reads}",
        "--output", "{output}",
        "--threads", "{inputs.threads}",
        "--nucleotide-database", "{inputs.nuc_db}",
        "--protein-database", "{inputs.prot_db}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Quality-controlled metagenomic reads"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "nuc_db": ("DIRECTORY", {"description": "ChocoPhlAn nucleotide database"}),
                "prot_db": ("DIRECTORY", {"description": "UniRef protein database"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MaxBinNode(CommandNode):
    """Metagenomic binning with MaxBin."""
    NODE_ID = "maxbin"
    DISPLAY_NAME = "MaxBin2"
    CATEGORY = "metagenomics"
    DESCRIPTION = "Unsupervised metagenomic binning using expectation maximization"
    SEARCH_ALIASES = ["maxbin", "binning", "metagenome", "mags"]
    RETURN_TYPES = ("BINS",)
    RETURN_NAMES = ("bins",)
    REQUIRED_EXECUTABLES = ["run_MaxBin.pl"]
    REQUIRED_CONDA_PACKAGES = ['maxbin2']
    DOCUMENTATION_URL = "https://sourceforge.net/projects/maxbin/"
    VERSION = "2.2.7"
    COMMAND = [
        "run_MaxBin.pl",
        "-contig", "{inputs.contigs}",
        "-out", "{output}/maxbin",
        "-reads", "{inputs.reads}",
        "-thread", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("CONTIGS", {"description": "Metagenomic contigs FASTA"}),
                "reads": ("FASTQ", {"description": "Metagenomic reads FASTQ"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "abund": ("FILE", {"description": "Optional abundance file"}),
                "min_prob": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CheckMNode(CommandNode):
    """Assess metagenomic bin quality with CheckM."""
    NODE_ID = "checkm"
    DISPLAY_NAME = "CheckM"
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assess the quality of microbial genomes recovered from metagenomes"
    SEARCH_ALIASES = ["checkm", "bin quality", "completeness", "contamination"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("quality_report",)
    REQUIRED_EXECUTABLES = ["checkm"]
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    VERSION = "1.2.2"
    COMMAND = [
        "checkm", "lineage_wf",
        "-x", "fa",
        "-t", "{inputs.threads}",
        "{inputs.bins}",
        "{output}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bins": ("BINS", {"description": "Directory with MAG bins (.fa files)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }
