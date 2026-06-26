"""Galaxy IUC parity nodes with DOI-backed citation metadata."""
from __future__ import annotations

from pathlib import Path
from re import sub
from typing import Any

from bionodulo.nodes.command_node import CommandNode


GALAXY_ALIAS = "Galaxy"
DOI_URL = "https://doi.org/"


def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get("output", inputs.get("output_dir", ".")))


def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != "":
        cmd.extend([flag, str(value)])


def _add_shell_redirect(cmd: list[str], output_path: str) -> None:
    cmd.extend([">", output_path])


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != ""]
    return [str(value)]


def _safe_name(value: str) -> str:
    return sub(r"[^\w\-.]", "_", Path(value).name)


def _safe_label(value: str) -> str:
    return sub(r"[^\w\-.]", "_", value)


def _safe_identifier(value: str) -> str:
    return sub(r"[^\w\-.]", "_", value.strip())


def _bedtools_ext(path: Any, default: str = "bed") -> str:
    suffixes = Path(str(path or "")).suffixes
    if not suffixes:
        return default
    if len(suffixes) >= 2 and suffixes[-2:] == [".gff", ".gz"]:
        return "gff"
    ext = suffixes[-1].lstrip(".").lower()
    return {"gff3": "gff", "bg": "bedgraph"}.get(ext, ext or default)


BEDTOOLS_CITATION_DOI = "10.1093/bioinformatics/btq033"
BEDTOOLS_CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
BCFTOOLS_CITATION_DOIS = ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btp352"]
BCFTOOLS_CITATION_URLS = [f"{DOI_URL}{doi}" for doi in BCFTOOLS_CITATION_DOIS]
BCFTOOLS_CITATION_TEXT = (
    "Twelve years of SAMtools and BCFtools; "
    "The Sequence Alignment/Map format and SAMtools."
)


def _bedtools_common_output(node_id: str, filename: str, output_dir: str | Path) -> Path:
    out = Path(output_dir) / node_id
    out.mkdir(parents=True, exist_ok=True)
    return out / filename


def _bedtools_add_genome(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "-g", inputs.get("genome"))


def _bedtools_add_lr_or_b(cmd: list[str], inputs: dict[str, Any]) -> None:
    mode = str(inputs.get("addition_mode", inputs.get("addition_select", "b")))
    if mode == "lr":
        cmd.extend(["-l", str(inputs.get("left", inputs.get("l", 0)))])
        cmd.extend(["-r", str(inputs.get("right", inputs.get("r", 0)))])
    else:
        cmd.extend(["-b", str(inputs.get("both", inputs.get("b", 1)))])


def _bedtools_strand_flag(value: Any, *, same: str = "-s", opposite: str = "-S") -> str:
    strand = str(value or "")
    return {
        "same": same,
        "opposite": opposite,
        "-s": same,
        "-S": opposite,
        same: same,
        opposite: opposite,
    }.get(strand, "")


def _bcftools_common_output(node_id: str, filename: str, output_dir: str | Path) -> Path:
    out = Path(output_dir) / node_id
    out.mkdir(parents=True, exist_ok=True)
    return out / filename


def _bcftools_add_output_type(cmd: list[str], inputs: dict[str, Any]) -> None:
    output_type = str(inputs.get("output_type", "z"))
    if output_type and output_type != "__none__":
        cmd.extend(["--output-type", output_type])


def _bcftools_variant_suffix(inputs: dict[str, Any], default: str = ".vcf.gz") -> str:
    output_type = str(inputs.get("output_type", "z"))
    return {"b": ".bcf", "u": ".bcf", "z": ".vcf.gz", "v": ".vcf"}.get(output_type, default)


def _bcftools_add_restrict(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--collapse", inputs.get("collapse"))
    _add_if_value(cmd, "--regions", inputs.get("regions"))
    if not inputs.get("_skip_samples_restrict"):
        _add_if_value(cmd, "--samples", inputs.get("samples"))
    _add_if_value(cmd, "--targets", inputs.get("targets"))
    _add_if_value(cmd, "--include", inputs.get("include"))
    _add_if_value(cmd, "--exclude", inputs.get("exclude"))


def _bcftools_add_apply_filters(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--apply-filters", inputs.get("apply_filters"))


def _bcftools_add_region_targets(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--regions", inputs.get("regions"))
    _add_if_value(cmd, "--regions-overlap", inputs.get("regions_overlap"))
    _add_if_value(cmd, "--targets", inputs.get("targets"))
    _add_if_value(cmd, "--targets-overlap", inputs.get("targets_overlap"))


def _bcftools_add_af_file(cmd: list[str], inputs: dict[str, Any]) -> None:
    _add_if_value(cmd, "--AF-file", inputs.get("AF_file", inputs.get("af_file")))


def _bcftools_plugin_base_cmd(plugin: str, inputs: dict[str, Any]) -> list[str]:
    cmd = ["bcftools", "plugin", plugin]
    _add_if_value(cmd, "--include", inputs.get("include"))
    _add_if_value(cmd, "--exclude", inputs.get("exclude"))
    _bcftools_add_region_targets(cmd, inputs)
    return cmd


def _bcftools_add_plugin_separator(cmd: list[str], plugin_args: list[str]) -> None:
    if plugin_args:
        cmd.append("--")
        cmd.extend(plugin_args)


def _bcftools_add_plugin_vcf_output(cmd: list[str], inputs: dict[str, Any]) -> None:
    cmd.extend(["--output-type", "z"])
    _add_if_value(cmd, "--threads", inputs.get("threads"))


def _bcftools_join_mode(value: Any, default: str = "a") -> str:
    parts = _as_list(value)
    if not parts:
        return default
    return "".join(str(part).replace(",", "") for part in parts)


def _bcftools_convert_from_outputs(inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
    out = Path(output_dir) / "bcftools_convert_from_vcf"
    out.mkdir(parents=True, exist_ok=True)
    mode = str(inputs.get("convert_to", "gen_sample"))
    if mode == "hap_legend_sample":
        return [out / "converted.hap", out / "converted.legend", out / "converted.samples"]
    if mode == "hap_sample":
        return [out / "converted.hap", out / "converted.samples"]
    return [out / "converted.gen", out / "converted.samples"]


class BUSCONode(CommandNode):
    """Assess genome, transcriptome, or proteome completeness with BUSCO."""

    NODE_ID = "busco"
    DISPLAY_NAME = "BUSCO"
    REQUIRED_CONDA_PACKAGES = ["busco"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assess assembly or annotation completeness using BUSCO lineage orthologs."
    SEARCH_ALIASES = [GALAXY_ALIAS, "busco", "completeness", "orthologs", "assembly qc", "annotation qc"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "IMAGE")
    RETURN_NAMES = ("short_summary", "full_table", "missing_buscos", "summary_image")
    REQUIRED_EXECUTABLES = ["busco"]
    DOCUMENTATION_URL = "https://busco.ezlab.org/"
    CITATION_DOIS = ["10.1093/bioinformatics/btv351"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btv351"]
    CITATION_TEXT = "BUSCO: assessing genome assembly and annotation completeness with single-copy orthologs."
    VERSION = "5.8.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get("mode", "genome"))
        mode_aliases = {
            "genome": "genome",
            "geno": "genome",
            "transcriptome": "transcriptome",
            "tran": "transcriptome",
            "proteins": "proteins",
            "prot": "proteins",
        }
        galaxy_mode = mode_aliases.get(mode, mode)
        cmd = [
            "busco",
            "--in",
            str(inputs.get("input", "")),
            "--mode",
            galaxy_mode,
            "--out",
            "busco_galaxy",
            "--out_path",
            _out(inputs),
            "--cpu",
            str(inputs.get("threads", 4)),
            "--evalue",
            str(inputs.get("evalue", 0.001)),
            "--limit",
            str(inputs.get("limit", 3)),
            "--contig_break",
            str(inputs.get("contig_break", 10)),
        ]
        if inputs.get("offline", True):
            cmd.append("--offline")
        _add_if_value(cmd, "--download_path", inputs.get("download_path"))

        lineage_mode = str(inputs.get("lineage_mode", "select_lineage"))
        if lineage_mode == "auto_detect":
            cmd.append(str(inputs.get("auto_lineage", "--auto-lineage")))
        else:
            _add_if_value(cmd, "--lineage_dataset", inputs.get("lineage_dataset"))

        predictor = str(inputs.get("gene_predictor", "miniprot"))
        if galaxy_mode == "genome" and predictor in {"miniprot", "augustus", "metaeuk"}:
            cmd.append(f"--{predictor}")
        _add_if_value(cmd, "--augustus_species", inputs.get("augustus_species"))
        if inputs.get("long"):
            cmd.append("--long")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "short_summary.txt",
            out / "full_table.tsv",
            out / "missing_buscos.tsv",
            out / "summary.png",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Assembly, transcriptome, or protein FASTA to analyse"}),
                "mode": ("STRING", {"default": "genome", "options": ["genome", "transcriptome", "proteins"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "lineage_mode": ("STRING", {"default": "select_lineage", "options": ["select_lineage", "auto_detect"]}),
                "lineage_dataset": ("STRING", {"default": "bacteria_odb10", "description": "BUSCO lineage dataset such as bacteria_odb10"}),
                "auto_lineage": ("STRING", {"default": "--auto-lineage", "options": ["--auto-lineage", "--auto-lineage-prok", "--auto-lineage-euk"]}),
                "gene_predictor": ("STRING", {"default": "miniprot", "options": ["miniprot", "augustus", "metaeuk"], "advanced": True}),
                "augustus_species": ("STRING", {"default": "", "advanced": True}),
                "download_path": ("DIRECTORY", {"description": "Cached BUSCO download directory", "advanced": True}),
                "offline": ("BOOLEAN", {"default": True, "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0, "max": 1, "advanced": True}),
                "limit": ("INT", {"default": 3, "min": 1, "advanced": True}),
                "contig_break": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "long": ("BOOLEAN", {"default": False, "description": "Enable Augustus self-training optimization", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class HTSeqCountNode(CommandNode):
    """Count reads overlapping genomic features with HTSeq-count."""

    NODE_ID = "htseq_count"
    DISPLAY_NAME = "HTSeq-count"
    REQUIRED_CONDA_PACKAGES = ["htseq", "samtools"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Count aligned reads in SAM/BAM files that overlap GFF/GTF features."
    SEARCH_ALIASES = [GALAXY_ALIAS, "htseq-count", "htseq", "gene counts", "rna-seq counts"]
    RETURN_TYPES = ("COUNTS",)
    RETURN_NAMES = ("counts",)
    REQUIRED_EXECUTABLES = ["htseq-count", "samtools"]
    DOCUMENTATION_URL = "https://htseq.readthedocs.io/en/latest/htseqcount.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btu638"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btu638"]
    CITATION_TEXT = "HTSeq: a Python framework to work with high-throughput sequencing data."
    VERSION = "2.1.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        samfile = str(inputs.get("samfile", ""))
        if inputs.get("sort_bam"):
            samfile = f"{_out(inputs)}/name_sorted.bam"
            cmd = ["samtools", "sort", "-n", "-o", samfile, str(inputs.get("samfile", "")), "&&"]
        else:
            cmd = []
        cmd.extend([
            "htseq-count",
            "--format=bam" if str(inputs.get("samfile", "")).lower().endswith(".bam") else "--format=sam",
            f"--mode={inputs.get('mode', 'union')}",
            f"--stranded={inputs.get('stranded', 'yes')}",
            f"--minaqual={inputs.get('minaqual', 0)}",
            f"--type={inputs.get('featuretype', 'exon')}",
            f"--idattr={inputs.get('idattr', 'gene_id')}",
            f"--nonunique={inputs.get('nonunique', 'none')}",
            f"--secondary-alignments={inputs.get('secondary_alignments', 'score')}",
            f"--supplementary-alignments={inputs.get('supplementary_alignments', 'score')}",
            f"--order={inputs.get('order', 'pos')}",
            samfile,
            str(inputs.get("gfffile", "")),
        ])
        _add_shell_redirect(cmd, f"{_out(inputs)}/counts.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "counts.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "samfile": ("BAM", {"description": "Aligned SAM/BAM file"}),
                "gfffile": ("GFF_GTF", {"description": "GFF/GTF feature annotation"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "union", "options": ["union", "intersection-strict", "intersection-nonempty"]}),
                "stranded": ("STRING", {"default": "yes", "options": ["yes", "no", "reverse"]}),
                "minaqual": ("INT", {"default": 0, "min": 0}),
                "featuretype": ("STRING", {"default": "exon"}),
                "idattr": ("STRING", {"default": "gene_id"}),
                "nonunique": ("STRING", {"default": "none", "options": ["none", "all", "fraction", "random"]}),
                "secondary_alignments": ("STRING", {"default": "score", "options": ["score", "ignore"], "advanced": True}),
                "supplementary_alignments": ("STRING", {"default": "score", "options": ["score", "ignore"], "advanced": True}),
                "order": ("STRING", {"default": "pos", "options": ["pos", "name"], "advanced": True}),
                "sort_bam": ("BOOLEAN", {"default": False, "description": "Name-sort BAM with samtools before counting", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SeqKitStatsNode(CommandNode):
    """Compute FASTA/Q summary statistics with SeqKit."""

    NODE_ID = "seqkit_stats"
    DISPLAY_NAME = "SeqKit Stats"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "qc"
    DESCRIPTION = "Compute sequence counts, length summaries, N50, and FASTQ quality statistics."
    SEARCH_ALIASES = [GALAXY_ALIAS, "seqkit", "stats", "fasta statistics", "fastq statistics", "n50"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#stats"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["seqkit", "stats", str(inputs.get("input", ""))]
        if inputs.get("all"):
            cmd.append("--all")
        if inputs.get("basename"):
            cmd.append("--basename")
        if inputs.get("skip_err"):
            cmd.append("--skip-err")
        if inputs.get("tabular", True):
            cmd.append("--tabular")
        _add_shell_redirect(cmd, f"{_out(inputs)}/stats.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "stats.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FASTQ_LIST", {"description": "FASTA or FASTQ file"})},
            "optional": {
                "all": ("BOOLEAN", {"default": False, "description": "Output all statistics"}),
                "basename": ("BOOLEAN", {"default": False, "description": "Report input basename only"}),
                "skip_err": ("BOOLEAN", {"default": False, "description": "Skip errors and show warnings"}),
                "tabular": ("BOOLEAN", {"default": True, "description": "Output tabular format"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class SeqKitGrepNode(CommandNode):
    """Search FASTA/Q records by ID, name, or sequence with SeqKit grep."""

    NODE_ID = "seqkit_grep"
    DISPLAY_NAME = "SeqKit Grep"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Filter FASTA or FASTQ records by ID, full name, sequence motif, or a file of patterns using SeqKit grep."
    SEARCH_ALIASES = [GALAXY_ALIAS, "seqkit", "grep", "seqkit grep", "FASTA grep", "FASTQ grep", "motif search", "sequence filter"]
    RETURN_TYPES = ("FASTQ", "FASTA", "STATS_FILE")
    RETURN_NAMES = ("fastq_output", "fasta_output", "count")
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#grep"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("count"):
            return "count.txt"
        ext = str(inputs.get("output_ext", "fasta.gz")).strip().lstrip(".") or "fasta.gz"
        return f"grep.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["seqkit", "grep", "--threads", str(inputs.get("threads", 4))]
        pattern_mode = str(inputs.get("pattern_mode", "expression"))
        if pattern_mode == "file":
            cmd.extend(["--pattern-file", str(inputs.get("pattern_file", ""))])
        else:
            cmd.extend(["--pattern", str(inputs.get("pattern", ""))])
            if inputs.get("use_regexp"):
                cmd.append("--use-regexp")
        for key, flag in (
            ("allow_duplicated_patterns", "--allow-duplicated-patterns"),
            ("by_name", "--by-name"),
            ("by_seq", "--by-seq"),
            ("circular", "--circular"),
            ("count", "--count"),
            ("degenerate", "--degenerate"),
            ("delete_matched", "--delete-matched"),
            ("ignore_case", "--ignore-case"),
            ("invert_match", "--invert-match"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        if inputs.get("by_seq") and not inputs.get("degenerate"):
            cmd.extend(["--max-mismatch", str(inputs.get("max_mismatch", 0))])
        if inputs.get("only_positive_strand"):
            cmd.append("--only-positive-strand")
        if inputs.get("region"):
            cmd.extend(["--region", str(inputs.get("region"))])
        cmd.extend([str(inputs.get("input", "")), ">", f"{_out(inputs)}/{cls._output_name(inputs)}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ_LIST", {"description": "Input FASTA/FASTQ file"}),
                "pattern_mode": ("STRING", {"default": "expression", "options": ["expression", "file"], "description": "Pattern source"}),
            },
            "optional": {
                "pattern": ("STRING", {"default": "", "description": "Pattern or motif sequence"}),
                "pattern_file": ("FILE", {"description": "Text file with one pattern per line"}),
                "use_regexp": ("BOOLEAN", {"default": False, "description": "Interpret expression pattern as a regular expression"}),
                "allow_duplicated_patterns": ("BOOLEAN", {"default": False, "advanced": True}),
                "by_name": ("BOOLEAN", {"default": False, "description": "Match against full sequence name/header"}),
                "by_seq": ("BOOLEAN", {"default": False, "description": "Search sequence content"}),
                "circular": ("BOOLEAN", {"default": False, "description": "Treat sequences as circular", "advanced": True}),
                "count": ("BOOLEAN", {"default": False, "description": "Print only the count of matching records"}),
                "degenerate": ("BOOLEAN", {"default": False, "description": "Pattern contains degenerate bases"}),
                "delete_matched": ("BOOLEAN", {"default": False, "advanced": True}),
                "ignore_case": ("BOOLEAN", {"default": False, "description": "Ignore case"}),
                "invert_match": ("BOOLEAN", {"default": False, "description": "Select non-matching records"}),
                "max_mismatch": ("INT", {"default": 0, "min": 0, "description": "Allowed mismatches for sequence search"}),
                "only_positive_strand": ("BOOLEAN", {"default": False, "description": "Search only the positive strand"}),
                "region": ("STRING", {"default": "", "description": "Sequence region such as 1:30, :100, or -12:-1"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "output_ext": ("STRING", {"default": "fasta.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"], "description": "Sequence output extension"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


AMRFINDERPLUS_ORGANISMS = [
    "Acinetobacter_baumannii",
    "Burkholderia_cepacia",
    "Burkholderia_pseudomallei",
    "Campylobacter",
    "Citrobacter_freundii",
    "Clostridioides_difficile",
    "Enterobacter_cloacae",
    "Enterococcus_faecalis",
    "Enterococcus_faecium",
    "Escherichia",
    "Klebsiella_aerogenes",
    "Klebsiella_oxytoca",
    "Klebsiella_pneumoniae",
    "Neisseria_gonorrhoeae",
    "Neisseria_meningitidis",
    "Pseudomonas_aeruginosa",
    "Salmonella",
    "Serratia_marcescens",
    "Staphylococcus_aureus",
    "Staphylococcus_pseudintermedius",
    "Streptococcus_agalactiae",
    "Streptococcus_pneumoniae",
    "Streptococcus_pyogenes",
    "Vibrio_cholerae",
]

AMRFINDERPLUS_ANNOTATION_FORMATS = [
    "bakta",
    "genbank",
    "microscope",
    "patric",
    "prokka",
    "pseudomonasdb",
    "rast",
    "standard",
    "prodigal",
]

AMRFINDERPLUS_TRANSLATION_TABLES = [
    "",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "16",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "33",
]


def _amrfinderplus_out(output_dir: str | Path, filename: str) -> Path:
    out = Path(output_dir) / "amrfinderplus"
    out.mkdir(parents=True, exist_ok=True)
    return out / filename


class AMRFinderPlusNode(CommandNode):
    """Find AMR genes, point mutations, and plus genes with NCBI AMRFinderPlus."""

    NODE_ID = "amrfinderplus"
    DISPLAY_NAME = "AMRFinderPlus"
    REQUIRED_CONDA_PACKAGES = ["ncbi-amrfinderplus"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find acquired antimicrobial resistance genes, point mutations, stress response, biocide, and virulence genes in nucleotide and/or protein sequences."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "amrfinder",
        "amrfinderplus",
        "NCBI AMRFinderPlus",
        "antimicrobial resistance",
        "AMR genes",
        "point mutations",
        "virulence genes",
    ]
    RETURN_TYPES = ("TSV", "TSV", "FASTA", "FASTA", "FASTA")
    RETURN_NAMES = (
        "amrfinderplus_report",
        "mutation_all_report",
        "protein_output",
        "nucleotide_output",
        "nucleotide_flank5_output",
    )
    REQUIRED_EXECUTABLES = ["amrfinder"]
    DOCUMENTATION_URL = "https://github.com/ncbi/amr/wiki"
    CITATION_DOIS = ["10.1038/s41598-021-91456-0"]
    CITATION_URLS = ["https://doi.org/10.1038/s41598-021-91456-0"]
    CITATION_TEXT = "AMRFinderPlus and the Reference Gene Catalog facilitate examination of the genomic links among antimicrobial resistance, stress response, and virulence."
    VERSION = "4.2.7"
    SHELL = True

    @classmethod
    def _report_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _has_organism(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get("organism_select", "")) == "add_organism" or bool(inputs.get("organism"))

    @classmethod
    def _flank5_size(cls, inputs: dict[str, Any]) -> int:
        try:
            return int(inputs.get("nucleotide_flank5_size", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _add_nucleotide_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--nucleotide", str(inputs.get("nucleotide_input", ""))])
        if cls._flank5_size(inputs) > 0:
            cmd.extend([
                "--nucleotide_flank5_size",
                str(cls._flank5_size(inputs)),
                "--nucleotide_flank5_output",
                cls._report_path(inputs, "amrfinderplus_flanking_sequence_output.fasta"),
            ])
        cmd.extend(["--nucleotide_output", cls._report_path(inputs, "amrfinderplus_nucleotide_output.fasta")])

    @classmethod
    def _add_protein_inputs(cls, cmd: list[str], inputs: dict[str, Any], *, require_annotation: bool = False) -> None:
        cmd.extend(["--protein", str(inputs.get("protein_input", ""))])
        gff = inputs.get("gff_annotation")
        if require_annotation or gff:
            cmd.extend(["--gff", str(gff or "")])
        annotation_format = inputs.get("annotation_format")
        if require_annotation or annotation_format:
            cmd.extend(["--annotation_format", str(annotation_format or "genbank")])
        cmd.extend(["--protein_output", cls._report_path(inputs, "amrfinderplus_protein_output.fasta")])

    @classmethod
    def _add_version_columns_command(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        database = str(inputs.get("database", ""))
        database_name = str(inputs.get("database_name", Path(database).name or "amrfinderplus_database"))
        report_path = cls._report_path(inputs, "amrfinderplus_report.tsv")
        mutation_path = cls._report_path(inputs, "mutation_all_report.tsv")
        script = (
            "from pathlib import Path\n"
            f"tool_version = '{cls.VERSION}'\n"
            f"database = Path('{database}')\n"
            f"database_version = (database / 'version.txt').read_text().strip() if (database / 'version.txt').is_file() else '{database_name}'\n"
            f"for report in [Path('{report_path}'), Path('{mutation_path}')]:\n"
            "    if not report.is_file() or report.stat().st_size == 0:\n"
            "        continue\n"
            "    lines = report.read_text().splitlines()\n"
            "    if not lines:\n"
            "        continue\n"
            "    updated = [lines[0] + '\\tDatabase version\\tTool version']\n"
            "    updated.extend(line + '\\t' + database_version + '\\t' + tool_version for line in lines[1:])\n"
            "    report.write_text('\\n'.join(updated) + '\\n')\n"
        )
        cmd.extend([
            "&&",
            "python",
            "-c",
            script,
        ])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "amrfinder",
            "--threads",
            str(inputs.get("threads", 1)),
            "--database",
            str(inputs.get("database", "")),
        ]
        input_select = str(inputs.get("input_select", "nucleotide"))
        if input_select == "protein":
            cls._add_protein_inputs(cmd, inputs)
        elif input_select == "nucl_prot":
            cmd.extend(["--nucleotide", str(inputs.get("nucleotide_input", ""))])
            if cls._flank5_size(inputs) > 0:
                cmd.extend([
                    "--nucleotide_flank5_size",
                    str(cls._flank5_size(inputs)),
                    "--nucleotide_flank5_output",
                    cls._report_path(inputs, "amrfinderplus_flanking_sequence_output.fasta"),
                ])
            cmd.extend([
                "--protein",
                str(inputs.get("protein_input", "")),
                "--gff",
                str(inputs.get("gff_annotation", "")),
                "--annotation_format",
                str(inputs.get("annotation_format", "genbank")),
                "--nucleotide_output",
                cls._report_path(inputs, "amrfinderplus_nucleotide_output.fasta"),
                "--protein_output",
                cls._report_path(inputs, "amrfinderplus_protein_output.fasta"),
            ])
        else:
            cls._add_nucleotide_inputs(cmd, inputs)

        if cls._has_organism(inputs):
            cmd.extend(["--organism", str(inputs.get("organism", ""))])
            if inputs.get("mutation_all"):
                cmd.extend(["--mutation_all", cls._report_path(inputs, "mutation_all_report.tsv")])
            if inputs.get("plus") and inputs.get("report_common"):
                cmd.append("--report_common")

        cmd.extend(["--ident_min", str(inputs.get("ident_min", -1))])
        cmd.extend(["--coverage_min", str(inputs.get("coverage_min", 0.5))])
        _add_if_value(cmd, "--translation_table", inputs.get("translation_table"))
        _add_if_value(cmd, "--name", inputs.get("name"))
        for key, flag in (
            ("plus", "--plus"),
            ("report_all_equal", "--report_all_equal"),
            ("print_node", "--print_node"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(["--output", cls._report_path(inputs, "amrfinderplus_report.tsv")])
        if inputs.get("add_version_columns"):
            cls._add_version_columns_command(cmd, inputs)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        input_select = str(inputs.get("input_select", "nucleotide"))
        outputs = [_amrfinderplus_out(output_dir, "amrfinderplus_report.tsv")]
        if cls._has_organism(inputs) and inputs.get("mutation_all"):
            outputs.append(_amrfinderplus_out(output_dir, "mutation_all_report.tsv"))
        if input_select in {"protein", "nucl_prot"}:
            outputs.append(_amrfinderplus_out(output_dir, "amrfinderplus_protein_output.fasta"))
        if input_select in {"nucleotide", "nucl_prot"}:
            outputs.append(_amrfinderplus_out(output_dir, "amrfinderplus_nucleotide_output.fasta"))
        if input_select in {"nucleotide", "nucl_prot"} and cls._flank5_size(inputs) > 0:
            outputs.append(_amrfinderplus_out(output_dir, "amrfinderplus_flanking_sequence_output.fasta"))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "database": ("DIRECTORY", {"description": "AMRFinderPlus database directory, matching Galaxy's amrfinderplus versioned database"}),
                "input_select": ("STRING", {"default": "nucleotide", "options": ["nucleotide", "protein", "nucl_prot"], "description": "Analyze nucleotide, protein, or paired nucleotide and protein files"}),
            },
            "optional": {
                "nucleotide_input": ("FASTA", {"default": "", "description": "Input nucleotide sequence file"}),
                "protein_input": ("FASTA", {"default": "", "description": "Input protein sequence file"}),
                "gff_annotation": ("GFF", {"default": "", "description": "GFF3 annotation file for protein locations"}),
                "annotation_format": ("STRING", {"default": "genbank", "options": AMRFINDERPLUS_ANNOTATION_FORMATS, "description": "Annotation format such as bakta, prokka, rast, or genbank"}),
                "nucleotide_flank5_size": ("INT", {"default": 0, "min": 0, "description": "5' flanking sequence size added to nucleotide matches"}),
                "organism_select": ("STRING", {"default": "", "options": ["", "add_organism"], "description": "Enable organism-specific point mutation screening"}),
                "organism": ("STRING", {"default": "", "options": AMRFINDERPLUS_ORGANISMS, "description": "Taxonomic group for point mutation screening"}),
                "mutation_all": ("BOOLEAN", {"default": False, "description": "Report genotypes at all screened point mutation locations"}),
                "report_common": ("BOOLEAN", {"default": False, "description": "Report proteins common to the taxonomy group when plus and organism options are enabled"}),
                "ident_min": ("FLOAT", {"default": -1, "min": -1, "max": 1, "description": "Minimum amino acid identity; -1 uses curated thresholds"}),
                "coverage_min": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "description": "Minimum coverage of the reference protein"}),
                "translation_table": ("STRING", {"default": "11", "options": AMRFINDERPLUS_TRANSLATION_TABLES, "description": "NCBI genetic code for translated BLAST"}),
                "plus": ("BOOLEAN", {"default": False, "description": "Include stress response, biocide, virulence, and other plus genes"}),
                "report_all_equal": ("BOOLEAN", {"default": False, "description": "Report all equally scoring BLAST and HMM matches"}),
                "print_node": ("BOOLEAN", {"default": False, "description": "Print hierarchy node or family"}),
                "name": ("STRING", {"default": "", "description": "Value to add as the report's first-column sample name"}),
                "add_version_columns": ("BOOLEAN", {"default": False, "description": "Append database and tool version columns to tabular reports"}),
                "database_name": ("STRING", {"default": "", "description": "Fallback database label when database/version.txt is unavailable", "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


CHECKM2_TRANSLATION_TABLES = [
    "",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "16",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "33",
]


class CheckM2Node(CommandNode):
    """Assess MAG, SAG, or isolate genome quality with CheckM2."""

    NODE_ID = "checkm2"
    DISPLAY_NAME = "CheckM2"
    REQUIRED_CONDA_PACKAGES = ["checkm2"]
    CATEGORY = "qc"
    DESCRIPTION = "Rapidly predict genome bin completeness and contamination for MAGs, SAGs, and isolate genomes using CheckM2 machine-learning models."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "checkm2",
        "CheckM2",
        "genome quality",
        "MAG quality",
        "SAG quality",
        "completeness contamination",
        "bin quality",
    ]
    RETURN_TYPES = ("TSV", "FASTA_LIST", "TSV_LIST")
    RETURN_NAMES = ("quality", "protein_files", "diamond_files")
    REQUIRED_EXECUTABLES = ["checkm2"]
    DOCUMENTATION_URL = "https://github.com/chklovski/CheckM2"
    CITATION_DOIS = ["10.1038/s41592-023-01940-w"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-023-01940-w"]
    CITATION_TEXT = "CheckM2: a rapid, scalable and accurate tool for assessing microbial genome quality using machine learning."
    VERSION = "1.1.0"
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input", inputs.get("inputs")))

    @classmethod
    def _link_name(cls, path: str) -> str:
        return f"{_safe_name(path)}.dat"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input_dir"
        output_dir = f"{out}/output"
        cmd = ["mkdir", "-p", input_dir, output_dir]
        for input_file in cls._input_files(inputs):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{input_dir}/{cls._link_name(input_file)}"])
        cmd.extend(["&&", "checkm2", "predict", "--input", input_dir])
        model = str(inputs.get("model", ""))
        if model:
            cmd.append(model)
        if inputs.get("genes"):
            cmd.append("--genes")
        _add_if_value(cmd, "--ttable", inputs.get("ttable"))
        cmd.extend([
            "-x",
            ".dat",
            "--threads",
            str(inputs.get("threads", 1)),
            "--database_path",
            str(inputs.get("database_path", inputs.get("database", ""))),
            "--output-directory",
            output_dir,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        protein_out = out / "protein_files"
        diamond_out = out / "diamond_output"
        protein_out.mkdir(parents=True, exist_ok=True)
        diamond_out.mkdir(parents=True, exist_ok=True)
        return [out / "quality_report.tsv", protein_out, diamond_out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA_LIST", {"description": "Input MAG, SAG, isolate genome, or predicted protein FASTA files"}),
                "database_path": ("FILE", {"description": "CheckM2 DIAMOND database path, such as uniref100.KO.1.dmnd"}),
            },
            "optional": {
                "genes": ("BOOLEAN", {"default": False, "description": "Treat input files as predicted protein FASTA files"}),
                "model": ("STRING", {"default": "", "options": ["", "--general", "--specific", "--allmodels"], "description": "Force general, specific, or both quality prediction models"}),
                "ttable": ("STRING", {"default": "", "options": CHECKM2_TRANSLATION_TABLES, "description": "Prodigal translation table for nucleotide inputs"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class DASToolNode(CommandNode):
    """Integrate metagenomic binning predictions with DAS Tool."""

    NODE_ID = "das_tool"
    DISPLAY_NAME = "DAS Tool"
    REQUIRED_CONDA_PACKAGES = ["das_tool"]
    CATEGORY = "metagenomics"
    DESCRIPTION = (
        "Integrate multiple metagenomic binning predictions into an optimized, non-redundant set of genome bins."
    )
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "das tool",
        "DAS Tool",
        "DAS_Tool",
        "dastool",
        "genome-resolved metagenomics",
        "bin dereplication",
        "bin aggregation",
        "metagenome binning",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TEXT", "TSV", "FASTA_LIST", "FASTA", "FASTA")
    RETURN_NAMES = ("summary", "contigs2bin", "log", "eval", "bins", "unbinned_contigs", "proteins")
    REQUIRED_EXECUTABLES = ["DAS_Tool"]
    DOCUMENTATION_URL = "https://github.com/cmks/DAS_Tool"
    CITATION_DOIS = ["10.1038/s41564-018-0171-1"]
    CITATION_URLS = ["https://doi.org/10.1038/s41564-018-0171-1"]
    CITATION_TEXT = "Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy."
    VERSION = "1.1.7"
    SHELL = True

    @classmethod
    def _binning_entries(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        repeat = inputs.get("binning")
        if isinstance(repeat, (list, tuple)):
            entries: list[tuple[str, str]] = []
            for item in repeat:
                if isinstance(item, dict):
                    bin_file = str(item.get("bins", ""))
                    label = str(item.get("labels", item.get("label", "")))
                else:
                    bin_file = str(item)
                    label = ""
                if bin_file:
                    entries.append((bin_file, label))
            if entries:
                return entries

        bins = _as_list(inputs.get("bins"))
        raw_labels = inputs.get("labels", inputs.get("bin_labels"))
        if isinstance(raw_labels, (list, tuple)):
            labels = [str(label) if label is not None else "" for label in raw_labels]
        elif raw_labels is None or raw_labels == "":
            labels = []
        else:
            labels = [str(raw_labels)]
        return [(bin_file, labels[index] if index < len(labels) else "") for index, bin_file in enumerate(bins)]

    @classmethod
    def _labels(cls, entries: list[tuple[str, str]]) -> list[str]:
        return [_safe_label(label) if label else _safe_name(bin_file) for bin_file, label in entries]

    @classmethod
    def _write_bins_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("write_bins")
        if isinstance(value, bool):
            return value
        return str(value if value is not None else "--write_bins") != ""

    @classmethod
    def _output_proteins_enabled(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("output_proteins", inputs.get("output_proteins_file", inputs.get("proteins_output"))))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        entries = cls._binning_entries(inputs)
        proteins = str(inputs.get("proteins", ""))
        cmd: list[str] = []
        if proteins:
            cmd.extend(["ln", "-sf", proteins, f"{out}/proteins", "&&"])
        cmd.extend(
            [
                "DAS_Tool",
                "--contigs",
                str(inputs.get("contigs", "")),
                "--outputbasename",
                f"{out}/outputs",
                "--bins",
                ",".join(bin_file for bin_file, _label in entries),
                "--labels",
                ",".join(cls._labels(entries)),
                "--search_engine",
                str(inputs.get("search_engine", "diamond")),
            ]
        )
        if proteins:
            cmd.extend(["--proteins", f"{out}/proteins"])
        cmd.extend(
            [
                "--score_threshold",
                str(inputs.get("score_threshold", 0.5)),
                "--duplicate_penalty",
                str(inputs.get("duplicate_penalty", 0.6)),
                "--megabin_penalty",
                str(inputs.get("megabin_penalty", 0.5)),
                "--max_iter_post_threshold",
                str(inputs.get("max_iter_post_threshold", 10)),
            ]
        )
        if inputs.get("write_bin_evals"):
            cmd.append("--write_bin_evals")
        if cls._write_bins_enabled(inputs):
            cmd.append("--write_bins")
            if inputs.get("write_unbinned"):
                cmd.append("--write_unbinned")
        if inputs.get("debug"):
            cmd.append("--debug")
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "outputs_DASTool_summary.tsv",
            out / "outputs_DASTool_contig2bin.tsv",
            out / "outputs_DASTool.log",
        ]
        if inputs.get("write_bin_evals"):
            outputs.append(out / "outputs_allBins.eval")
        if cls._write_bins_enabled(inputs):
            bins_dir = out / "outputs_DASTool_bins"
            bins_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(bins_dir)
            if inputs.get("write_unbinned"):
                outputs.append(bins_dir / "unbinned.fa")
        if cls._output_proteins_enabled(inputs):
            outputs.append(out / "outputs_proteins.faa")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("FASTA", {"description": "Assembled contig sequences"}),
                "bins": (
                    "TSV",
                    {
                        "list": True,
                        "min_items": 1,
                        "description": "One or more contig-to-bin tables with contig IDs and bin IDs",
                    },
                ),
            },
            "optional": {
                "labels": (
                    "STRING",
                    {
                        "list": True,
                        "description": "Binning prediction labels; blank labels fall back to sanitized table filenames",
                    },
                ),
                "search_engine": (
                    "STRING",
                    {
                        "default": "diamond",
                        "options": ["diamond", "blastp"],
                        "description": "Engine used for single-copy gene identification",
                    },
                ),
                "proteins": (
                    "FASTA",
                    {"default": "", "description": "Optional predicted proteins in Prodigal FASTA format"},
                ),
                "score_threshold": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "description": "Score threshold until selection algorithm keeps selecting bins",
                    },
                ),
                "duplicate_penalty": (
                    "FLOAT",
                    {
                        "default": 0.6,
                        "min": 0,
                        "max": 3,
                        "description": "Penalty for duplicate single-copy genes per bin",
                    },
                ),
                "megabin_penalty": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 3, "description": "Penalty for megabins"},
                ),
                "max_iter_post_threshold": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Maximum iterations after reaching the score threshold",
                    },
                ),
                "output_proteins": ("BOOLEAN", {"default": False, "description": "Output predicted proteins"}),
                "write_bin_evals": (
                    "BOOLEAN",
                    {"default": False, "description": "Write evaluation of input bin sets"},
                ),
                "write_bins": (
                    "STRING",
                    {
                        "default": "--write_bins",
                        "options": ["--write_bins", ""],
                        "description": "Export selected bins as FASTA files",
                    },
                ),
                "write_unbinned": (
                    "BOOLEAN",
                    {"default": False, "description": "Export unbinned contigs when writing bins"},
                ),
                "debug": ("BOOLEAN", {"default": False, "description": "Write debug information to the log file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class FastaToContig2BinNode(CommandNode):
    """Convert genome-bin FASTA files into a DAS Tool contig-to-bin table."""

    NODE_ID = "fasta_to_contig2bin"
    DISPLAY_NAME = "FASTA to Contig2Bin"
    REQUIRED_CONDA_PACKAGES = ["das_tool"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert a list of genome-bin FASTA files into a tabular contig-to-bin assignment table for DAS Tool."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "Fasta_to_Contig2Bin",
        "Fasta_to_Contig2Bin.sh",
        "DAS Tool helper",
        "contig2bin",
        "contigs2bin",
        "genome bins",
        "bin FASTA",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("contigs2bin",)
    REQUIRED_EXECUTABLES = ["Fasta_to_Contig2Bin.sh"]
    DOCUMENTATION_URL = "https://github.com/cmks/DAS_Tool#preparation-of-input-files"
    CITATION_DOIS = ["10.1038/s41564-018-0171-1"]
    CITATION_URLS = ["https://doi.org/10.1038/s41564-018-0171-1"]
    CITATION_TEXT = "Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy."
    VERSION = "1.1.7"
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("inputs", inputs.get("input")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        raw = inputs.get("element_identifiers", inputs.get("identifiers", inputs.get("labels")))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else "" for identifier in raw]
        elif raw is None or raw == "":
            identifiers = []
        else:
            identifiers = [str(raw)]
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(input_file)
            for index, input_file in enumerate(input_files)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/inputs"
        input_files = cls._input_files(inputs)
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ["mkdir", "-p", input_dir]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{input_dir}/{identifier}.fasta"])
        cmd.extend(
            [
                "&&",
                "Fasta_to_Contig2Bin.sh",
                "--extension",
                "fasta",
                "--input_folder",
                input_dir,
                ">",
                f"{out}/contigs2bin.tsv",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "contigs2bin.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    "FASTA_LIST",
                    {"description": "Genome-bin FASTA files to convert into contig-to-bin assignments"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "list": True,
                        "description": "Optional bin labels matching the FASTA collection element identifiers",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


BANDAGE_CITATION_DOI = "10.1093/bioinformatics/btv383"
BANDAGE_CITATION_TEXT = "Bandage: interactive visualization of de novo genome assemblies."


def _bandage_prefix(inputs: dict[str, Any], node_out: str) -> list[str]:
    return [
        "ln",
        "-sf",
        str(inputs.get("input_file", "")),
        f"{node_out}/input.gfa",
        "&&",
        "export",
        "QT_QPA_PLATFORM=offscreen",
        "&&",
    ]


class BandageInfoNode(CommandNode):
    """Summarize de novo assembly graph statistics with Bandage info."""

    NODE_ID = "bandage_info"
    DISPLAY_NAME = "Bandage Info"
    REQUIRED_CONDA_PACKAGES = ["bandage_ng"]
    CATEGORY = "assembly"
    DESCRIPTION = "Determine node, edge, length, connectivity, and N50 statistics for de novo assembly graphs."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "Bandage",
        "bandage info",
        "assembly graph",
        "GFA statistics",
        "FASTG statistics",
        "de novo assembly graph",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["Bandage"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Bandage/wiki/Command-line-options#info"
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BANDAGE_CITATION_DOI}"]
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = "2022.09"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(["Bandage", "info", f"{out}/input.gfa"])
        if inputs.get("tsv"):
            cmd.append("--tsv")
        cmd.extend(["|", "sed", r"s/:\s\+/:\t/g", ">", f"{out}/out.tab"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.tab"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "GFA",
                    {
                        "description": (
                            "Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format"
                        ),
                    },
                ),
            },
            "optional": {
                "tsv": (
                    "BOOLEAN",
                    {"default": False, "description": "Output information as a single tab-delimited line"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BandageImageNode(CommandNode):
    """Render de novo assembly graph images with Bandage image."""

    NODE_ID = "bandage_image"
    DISPLAY_NAME = "Bandage Image"
    REQUIRED_CONDA_PACKAGES = ["bandage_ng"]
    CATEGORY = "visualization"
    DESCRIPTION = "Visualize de novo assembly graphs as JPG, PNG, or SVG images using Bandage."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "Bandage",
        "bandage image",
        "assembly graph image",
        "GFA visualization",
        "FASTG visualization",
        "de novo assembly graph",
    ]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("outfile",)
    REQUIRED_EXECUTABLES = ["Bandage"]
    DOCUMENTATION_URL = "https://github.com/rrwick/Bandage/wiki/Command-line-options#image"
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BANDAGE_CITATION_DOI}"]
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = "2022.09"
    SHELL = True

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("output_format", "jpg") or "jpg").lower()
        return output_format if output_format in {"jpg", "png", "svg"} else "jpg"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = cls._output_format(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(["Bandage", "image", f"{out}/input.gfa", f"{out}/out.{output_format}"])
        _add_if_value(cmd, "--height", inputs.get("height"))
        _add_if_value(cmd, "--width", inputs.get("width"))
        _add_if_value(cmd, "--fontsize", inputs.get("fontsize"))
        _add_if_value(cmd, "--nodewidth", inputs.get("nodewidth"))
        if inputs.get("names"):
            cmd.append("--names")
        if inputs.get("lengths"):
            cmd.append("--lengths")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"out.{cls._output_format(inputs)}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "GFA",
                    {
                        "description": (
                            "Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format"
                        ),
                    },
                ),
            },
            "optional": {
                "height": ("INT", {"default": 1000, "min": 1, "description": "Image height in pixels"}),
                "width": ("INT", {"default": "", "min": 1, "description": "Image width in pixels"}),
                "names": ("BOOLEAN", {"default": False, "description": "Show node name labels"}),
                "lengths": ("BOOLEAN", {"default": False, "description": "Show node length labels"}),
                "fontsize": ("INT", {"default": "", "min": 5, "description": "Node label font size"}),
                "nodewidth": ("FLOAT", {"default": "", "min": 5, "description": "Node width for graph image"}),
                "output_format": (
                    "STRING",
                    {"default": "jpg", "options": ["jpg", "png", "svg"], "description": "Output image format"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class VSearchSearchNode(CommandNode):
    """Search query sequences against a FASTA database with VSEARCH."""

    NODE_ID = "vsearch_search"
    DISPLAY_NAME = "VSEARCH Search"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Search amplicon or nucleotide sequences against a reference database with VSEARCH."
    SEARCH_ALIASES = [GALAXY_ALIAS, "vsearch", "usearch_global", "search", "amplicon", "otu"]
    RETURN_TYPES = ("TSV", "STATS_FILE", "FASTA")
    RETURN_NAMES = ("matches", "alignments", "unmatched")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            f"--{inputs.get('search_mode', 'usearch_global')}",
            str(inputs.get("query", "")),
            "--db",
            str(inputs.get("database", "")),
            "--id",
            str(inputs.get("identity", 0.97)),
            "--strand",
            str(inputs.get("strand", "both")),
            "--maxaccepts",
            str(inputs.get("maxaccepts", 1)),
            "--maxrejects",
            str(inputs.get("maxrejects", 32)),
            "--threads",
            str(inputs.get("threads", 1)),
            "--blast6out",
            f"{_out(inputs)}/matches.tsv",
            "--alnout",
            f"{_out(inputs)}/alignments.txt",
            "--notmatched",
            f"{_out(inputs)}/unmatched.fasta",
        ]
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "matches.tsv", out / "alignments.txt", out / "unmatched.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Query sequences"}),
                "database": ("FASTA", {"description": "Reference database FASTA"}),
            },
            "optional": {
                "search_mode": ("STRING", {"default": "usearch_global", "options": ["usearch_global", "search_exact"]}),
                "identity": ("FLOAT", {"default": 0.97, "min": 0, "max": 1}),
                "strand": ("STRING", {"default": "both", "options": ["plus", "both"]}),
                "maxaccepts": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "maxrejects": ("INT", {"default": 32, "min": 0, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class VSearchClusterNode(CommandNode):
    """Cluster sequences into centroids and UC cluster assignments with VSEARCH."""

    NODE_ID = "vsearch_cluster"
    DISPLAY_NAME = "VSEARCH Cluster"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Cluster amplicon sequences with VSEARCH cluster_fast or cluster_size modes."
    SEARCH_ALIASES = [GALAXY_ALIAS, "vsearch", "cluster_fast", "cluster_size", "otu clustering", "centroids"]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("centroids", "clusters_uc")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            f"--{inputs.get('cluster_mode', 'cluster_fast')}",
            str(inputs.get("sequences", "")),
            "--id",
            str(inputs.get("identity", 0.97)),
            "--strand",
            str(inputs.get("strand", "plus")),
        ]
        if inputs.get("sizein"):
            cmd.append("--sizein")
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        cmd.extend([
            "--threads",
            str(inputs.get("threads", 1)),
            "--centroids",
            f"{_out(inputs)}/centroids.fasta",
            "--uc",
            f"{_out(inputs)}/clusters.uc",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "centroids.fasta", out / "clusters.uc"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"sequences": ("FASTA", {"description": "Sequences to cluster"})},
            "optional": {
                "cluster_mode": ("STRING", {"default": "cluster_fast", "options": ["cluster_fast", "cluster_size", "cluster_smallmem"]}),
                "identity": ("FLOAT", {"default": 0.97, "min": 0, "max": 1}),
                "strand": ("STRING", {"default": "plus", "options": ["plus", "both"]}),
                "sizein": ("BOOLEAN", {"default": False, "advanced": True}),
                "sizeout": ("BOOLEAN", {"default": False, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class DiamondMakeDBNode(CommandNode):
    """Build a DIAMOND protein database from FASTA."""

    NODE_ID = "diamond_makedb"
    DISPLAY_NAME = "DIAMOND MakeDB"
    REQUIRED_CONDA_PACKAGES = ["diamond"]
    CATEGORY = "databases"
    DESCRIPTION = "Build a DIAMOND .dmnd protein database from FASTA, optionally with taxonomy files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "diamond", "makedb", "protein database", "dmnd"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("database",)
    REQUIRED_EXECUTABLES = ["diamond"]
    DOCUMENTATION_URL = "https://github.com/bbuchfink/diamond/wiki"
    CITATION_DOIS = ["10.1038/s41592-021-01101-x"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-021-01101-x"]
    CITATION_TEXT = "Sensitive protein alignments at tree-of-life scale using DIAMOND."
    VERSION = "2.2.2"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "diamond",
            "makedb",
            "--threads",
            str(inputs.get("threads", 12)),
            "--in",
            str(inputs.get("infile", "")),
            "--db",
            f"{_out(inputs)}/database",
        ]
        _add_if_value(cmd, "--taxonmap", inputs.get("taxonmap"))
        _add_if_value(cmd, "--taxonnodes", inputs.get("taxonnodes"))
        _add_if_value(cmd, "--taxonnames", inputs.get("taxonnames"))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "database.dmnd"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "Protein FASTA reference"}),
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "taxonmap": ("TSV", {"description": "Protein accession to taxid mapping", "advanced": True}),
                "taxonnodes": ("TSV", {"description": "NCBI nodes.dmp", "advanced": True}),
                "taxonnames": ("TSV", {"description": "NCBI names.dmp", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class DiamondAlignNode(CommandNode):
    """Align protein or translated nucleotide queries with DIAMOND."""

    NODE_ID = "diamond_align"
    DISPLAY_NAME = "DIAMOND Align"
    REQUIRED_CONDA_PACKAGES = ["diamond"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run DIAMOND blastp or blastx searches against a protein database."
    SEARCH_ALIASES = [GALAXY_ALIAS, "diamond", "blastp", "blastx", "protein alignment", "translated search"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("matches",)
    REQUIRED_EXECUTABLES = ["diamond"]
    DOCUMENTATION_URL = "https://github.com/bbuchfink/diamond/wiki"
    CITATION_DOIS = ["10.1038/s41592-021-01101-x"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-021-01101-x"]
    CITATION_TEXT = "Sensitive protein alignments at tree-of-life scale using DIAMOND."
    VERSION = "2.2.2"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        outfmt = str(inputs.get("outfmt", "6 qseqid sseqid pident length evalue bitscore")).split()
        cmd = [
            "diamond",
            str(inputs.get("method", "blastp")),
            "--threads",
            str(inputs.get("threads", 12)),
            "--db",
            str(inputs.get("database", "")),
            "--query",
            str(inputs.get("query", "")),
            "--out",
            f"{_out(inputs)}/matches.tsv",
            "--outfmt",
            *outfmt,
        ]
        sensitivity = str(inputs.get("sensitivity", ""))
        if sensitivity:
            cmd.append(sensitivity)
        _add_if_value(cmd, "--evalue", inputs.get("evalue"))
        _add_if_value(cmd, "--max-target-seqs", inputs.get("max_target_seqs"))
        _add_if_value(cmd, "--matrix", inputs.get("matrix"))
        if inputs.get("method") == "blastx":
            _add_if_value(cmd, "--query-gencode", inputs.get("query_gencode"))
            _add_if_value(cmd, "--strand", inputs.get("query_strand"))
            _add_if_value(cmd, "--min-orf", inputs.get("min_orf"))
        if inputs.get("no_self_hits"):
            cmd.append("--no-self-hits")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "matches.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Protein or nucleotide query FASTA"}),
                "database": ("FILE", {"description": "DIAMOND .dmnd database"}),
                "method": ("STRING", {"default": "blastp", "options": ["blastp", "blastx"]}),
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "sensitivity": ("STRING", {"default": "", "options": ["", "--fast", "--sensitive", "--more-sensitive", "--very-sensitive", "--ultra-sensitive"]}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "max_target_seqs": ("INT", {"default": 25, "min": 1}),
                "matrix": ("STRING", {"default": "BLOSUM62", "advanced": True}),
                "outfmt": ("STRING", {"default": "6 qseqid sseqid pident length evalue bitscore", "advanced": True}),
                "query_gencode": ("INT", {"default": 1, "advanced": True}),
                "query_strand": ("STRING", {"default": "both", "options": ["both", "plus", "minus"], "advanced": True}),
                "min_orf": ("INT", {"default": 20, "min": 1, "advanced": True}),
                "no_self_hits": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class HMMERHmmsearchNode(CommandNode):
    """Search sequence databases with profile HMMs using hmmsearch."""

    NODE_ID = "hmmer_hmmsearch"
    DISPLAY_NAME = "HMMER hmmsearch"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Search one or more profile HMMs against a sequence FASTA database."
    SEARCH_ALIASES = [GALAXY_ALIAS, "hmmer", "hmmsearch", "profile hmm", "domain search"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout", "pfamtblout")
    REQUIRED_EXECUTABLES = ["hmmsearch"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "Accelerated profile HMM searches."
    VERSION = "3.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["hmmsearch", "--cpu", str(inputs.get("threads", 1))]
        _add_if_value(cmd, "-E", inputs.get("evalue"))
        _add_if_value(cmd, "--incE", inputs.get("incE"))
        _add_if_value(cmd, "--domE", inputs.get("domE"))
        _add_if_value(cmd, "--incdomE", inputs.get("incdomE"))
        if inputs.get("cut_ga"):
            cmd.append("--cut_ga")
        if inputs.get("cut_tc"):
            cmd.append("--cut_tc")
        if inputs.get("cut_nc"):
            cmd.append("--cut_nc")
        if inputs.get("notextw"):
            cmd.append("--notextw")
        out = _out(inputs)
        cmd.extend([
            "--tblout",
            f"{out}/results.tblout",
            "--domtblout",
            f"{out}/domains.domtblout",
            "--pfamtblout",
            f"{out}/pfam.tblout",
            "-o",
            f"{out}/output.txt",
            str(inputs.get("hmmfile", "")),
            str(inputs.get("seqdb", "")),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.txt", out / "results.tblout", out / "domains.domtblout", out / "pfam.tblout"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Profile HMM file"}),
                "seqdb": ("FASTA", {"description": "Sequence database FASTA"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "evalue": ("FLOAT", {"default": 10, "min": 0}),
                "incE": ("FLOAT", {"default": "", "advanced": True}),
                "domE": ("FLOAT", {"default": "", "advanced": True}),
                "incdomE": ("FLOAT", {"default": "", "advanced": True}),
                "cut_ga": ("BOOLEAN", {"default": False, "advanced": True}),
                "cut_tc": ("BOOLEAN", {"default": False, "advanced": True}),
                "cut_nc": ("BOOLEAN", {"default": False, "advanced": True}),
                "notextw": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class HMMERHmmscanNode(HMMERHmmsearchNode):
    """Search sequences against a profile HMM database using hmmscan."""

    NODE_ID = "hmmer_hmmscan"
    DISPLAY_NAME = "HMMER hmmscan"
    DESCRIPTION = "Search protein sequences against a profile HMM database."
    SEARCH_ALIASES = [GALAXY_ALIAS, "hmmer", "hmmscan", "pfam", "domain annotation"]
    REQUIRED_EXECUTABLES = ["hmmscan"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["hmmscan", "--cpu", str(inputs.get("threads", 1))]
        _add_if_value(cmd, "-E", inputs.get("evalue"))
        _add_if_value(cmd, "--incE", inputs.get("incE"))
        _add_if_value(cmd, "--domE", inputs.get("domE"))
        _add_if_value(cmd, "--incdomE", inputs.get("incdomE"))
        if inputs.get("cut_ga"):
            cmd.append("--cut_ga")
        if inputs.get("cut_tc"):
            cmd.append("--cut_tc")
        if inputs.get("cut_nc"):
            cmd.append("--cut_nc")
        if inputs.get("notextw"):
            cmd.append("--notextw")
        out = _out(inputs)
        cmd.extend([
            "--tblout",
            f"{out}/results.tblout",
            "--domtblout",
            f"{out}/domains.domtblout",
            "--pfamtblout",
            f"{out}/pfam.tblout",
            "-o",
            f"{out}/output.txt",
            str(inputs.get("hmmdb", "")),
            str(inputs.get("seqfile", "")),
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seqfile": ("FASTA", {"description": "Sequence FASTA"}),
                "hmmdb": ("FILE", {"description": "Profile HMM database"}),
            },
            "optional": HMMERHmmsearchNode.INPUT_TYPES()["optional"],
            "hidden": {"output": ("STRING", {})},
        }


class MMseqs2EasySearchNode(CommandNode):
    """Run MMseqs2 easy-search for sensitive sequence homology search."""

    NODE_ID = "mmseqs2_easy_search"
    DISPLAY_NAME = "MMseqs2 Easy Search"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run MMseqs2 easy-search for protein, nucleotide, or translated homology searches."
    SEARCH_ALIASES = [GALAXY_ALIAS, "mmseqs2", "mmseqs", "easy-search", "homology", "sequence search"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = "https://github.com/soedinglab/MMseqs2/wiki"
    CITATION_DOIS = [
        "10.1038/nbt.3988",
        "10.1038/s41467-018-04964-5",
        "10.1093/bioinformatics/btab184",
    ]
    CITATION_URLS = [
        "https://doi.org/10.1038/nbt.3988",
        "https://doi.org/10.1038/s41467-018-04964-5",
        "https://doi.org/10.1093/bioinformatics/btab184",
    ]
    CITATION_TEXT = "MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets."
    VERSION = "17-b804f"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "mmseqs",
            "easy-search",
            str(inputs.get("query_fasta", "")),
            str(inputs.get("target_fasta", inputs.get("target_database", ""))),
            f"{out}/search_results",
            f"{out}/tmp",
            "--search-type",
            str(inputs.get("search_type", 0)),
            "-s",
            str(inputs.get("sensitivity", 5.7)),
            "-e",
            str(inputs.get("evalue", 0.001)),
            "--min-seq-id",
            str(inputs.get("min_seq_id", 0.0)),
            "-c",
            str(inputs.get("cov", 0.0)),
            "--cov-mode",
            str(inputs.get("cov_mode", 0)),
        ]
        _add_if_value(cmd, "--format-output", inputs.get("format_output", "query,target,pident,evalue,bits"))
        _add_if_value(cmd, "--num-iterations", inputs.get("num_iterations", 1))
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "search_results"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/Q file"}),
                "target_fasta": ("FASTA", {"description": "Target FASTA database"}),
            },
            "optional": {
                "search_type": ("INT", {"default": 0, "min": 0, "max": 4, "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide"}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 15}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "cov_mode": ("INT", {"default": 0, "min": 0, "max": 5}),
                "format_output": ("STRING", {"default": "query,target,pident,evalue,bits"}),
                "num_iterations": ("INT", {"default": 1, "min": 1, "max": 20, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class MashDistNode(CommandNode):
    """Estimate Mash distances between reference and query sequences."""

    NODE_ID = "mash_dist"
    DISPLAY_NAME = "Mash Dist"
    REQUIRED_CONDA_PACKAGES = ["mash"]
    CATEGORY = "genomics"
    DESCRIPTION = "Estimate genome or metagenome distances from FASTA/FASTQ files or Mash sketches."
    SEARCH_ALIASES = [GALAXY_ALIAS, "mash", "mash dist", "minhash", "genome distance", "metagenome distance"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("distances",)
    REQUIRED_EXECUTABLES = ["mash"]
    DOCUMENTATION_URL = "https://mash.readthedocs.io/en/latest/distances.html"
    CITATION_DOIS = ["10.1186/s13059-016-0997-x"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-016-0997-x"]
    CITATION_TEXT = "Mash: fast genome and metagenome distance estimation using MinHash."
    VERSION = "2.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["mash", "dist"]
        if inputs.get("table_output", True):
            cmd.append("-t")
        cmd.extend(["-p", str(inputs.get("threads", 1))])
        _add_if_value(cmd, "-v", inputs.get("pvalue", 1.0))
        _add_if_value(cmd, "-d", inputs.get("distance", 1.0))
        cmd.extend([str(inputs.get("reference", "")), str(inputs.get("query", ""))])
        _add_shell_redirect(cmd, f"{out}/distances.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "distances.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA/FASTQ or Mash sketch"}),
                "query": ("FASTA", {"description": "Query FASTA/FASTQ or Mash sketch"}),
            },
            "optional": {
                "table_output": ("BOOLEAN", {"default": True, "description": "Use Mash table output (-t)"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "pvalue": ("FLOAT", {"default": 1.0, "min": 0, "max": 1}),
                "distance": ("FLOAT", {"default": 1.0, "min": 0, "max": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class FastANINode(CommandNode):
    """Compute whole-genome average nucleotide identity with FastANI."""

    NODE_ID = "fastani"
    DISPLAY_NAME = "FastANI"
    REQUIRED_CONDA_PACKAGES = ["fastani"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute alignment-free whole-genome Average Nucleotide Identity for one or more query/reference genomes."
    SEARCH_ALIASES = [GALAXY_ALIAS, "fastani", "ANI", "average nucleotide identity", "genome comparison"]
    RETURN_TYPES = ("TSV", "FILE", "FILE")
    RETURN_NAMES = ("ani_table", "ani_matrix", "visual_mappings")
    REQUIRED_EXECUTABLES = ["fastANI"]
    DOCUMENTATION_URL = "https://github.com/ParBLiSS/FastANI"
    CITATION_DOIS = ["10.1038/s41467-018-07641-9"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41467-018-07641-9"]
    CITATION_TEXT = "High throughput ANI analysis of 90K prokaryotic genomes reveals clear species boundaries."
    VERSION = "1.3"

    async def run(self, **kwargs: Any) -> Any:
        output_dir = kwargs.get("output_dir")
        context = kwargs.get("context")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        node_out = Path(output_dir) / self.__class__.NODE_ID if output_dir else Path(".")
        node_out.mkdir(parents=True, exist_ok=True)
        query_files = _as_list(kwargs.get("query"))
        ref_files = _as_list(kwargs.get("reference"))
        if query_files:
            (node_out / "query.lst").write_text("\n".join(query_files) + "\n", encoding="utf-8")
        if ref_files:
            (node_out / "ref.lst").write_text("\n".join(ref_files) + "\n", encoding="utf-8")
        return await super().run(**kwargs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        query_files = _as_list(inputs.get("query"))
        ref_files = _as_list(inputs.get("reference"))
        cmd = ["fastANI"]
        if len(query_files) == 1:
            cmd.extend(["-q", query_files[0]])
        else:
            cmd.extend(["--ql", f"{out}/query.lst"])
        if len(ref_files) == 1:
            cmd.extend(["-r", ref_files[0]])
        else:
            cmd.extend(["--rl", f"{out}/ref.lst"])
        cmd.extend(["-o", f"{out}/fastani.tsv", "-t", str(inputs.get("threads", 1))])
        _add_if_value(cmd, "--fragLen", inputs.get("frag_len"))
        _add_if_value(cmd, "--minFraction", inputs.get("min_fraction"))
        _add_if_value(cmd, "-k", inputs.get("kmer"))
        if inputs.get("matrix"):
            cmd.append("--matrix")
        if inputs.get("visualize"):
            cmd.append("--visualize")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "fastani.tsv"]
        if inputs.get("matrix"):
            outputs.append(out / "fastani.tsv.matrix")
        if inputs.get("visualize"):
            outputs.append(out / "fastani.tsv.visual")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA_LIST", {"description": "One or more query genome assemblies"}),
                "reference": ("FASTA_LIST", {"description": "One or more reference genome assemblies"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "frag_len": ("INT", {"default": 3000, "min": 100, "description": "Fragment length used by FastANI"}),
                "min_fraction": ("FLOAT", {"default": 0.2, "min": 0, "max": 1}),
                "kmer": ("INT", {"default": 16, "min": 4, "max": 32}),
                "matrix": ("BOOLEAN", {"default": False, "description": "Also emit PHYLIP-style ANI matrix"}),
                "visualize": ("BOOLEAN", {"default": False, "description": "Emit reciprocal mapping file for visualization"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class LoFreqCallNode(CommandNode):
    """Call SNVs and indels from BAM alignments with LoFreq."""

    NODE_ID = "lofreq_call"
    DISPLAY_NAME = "LoFreq Call"
    REQUIRED_CONDA_PACKAGES = ["lofreq"]
    CATEGORY = "variant"
    DESCRIPTION = "Call sequence-quality-aware SNVs and indels from mapped reads using LoFreq."
    SEARCH_ALIASES = [GALAXY_ALIAS, "lofreq", "lofreq call", "variant caller", "low frequency variants", "SNV"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("variants")
    REQUIRED_EXECUTABLES = ["lofreq"]
    DOCUMENTATION_URL = "http://csb5.github.io/lofreq/"
    CITATION_DOIS = ["10.1093/nar/gks918"]
    CITATION_URLS = [f"{DOI_URL}10.1093/nar/gks918"]
    CITATION_TEXT = "LoFreq: a sequence-quality aware, ultra-sensitive variant caller for high-throughput sequencing datasets."
    VERSION = "2.1.5"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "lofreq",
            "call-parallel",
            "--pp-threads",
            str(inputs.get("threads", 1)),
            "--verbose",
            "--ref",
            str(inputs.get("reference", "")),
            "--out",
            f"{out}/variants.vcf",
        ]
        variant_types = str(inputs.get("variant_types", ""))
        if variant_types:
            cmd.extend(variant_types.split())
        _add_if_value(cmd, "--bed", inputs.get("bed"))
        _add_if_value(cmd, "--min-cov", inputs.get("min_cov"))
        _add_if_value(cmd, "--max-depth", inputs.get("max_depth"))
        if inputs.get("use_orphan"):
            cmd.append("--use-orphan")
        _add_if_value(cmd, "--min-bq", inputs.get("min_bq"))
        _add_if_value(cmd, "--min-alt-bq", inputs.get("min_alt_bq"))
        _add_if_value(cmd, "--def-alt-bq", inputs.get("def_alt_bq"))
        alnquals_to_use = str(inputs.get("alnquals_to_use", ""))
        if alnquals_to_use:
            cmd.extend(alnquals_to_use.split())
        extended_baq = str(inputs.get("extended_baq", ""))
        if extended_baq:
            cmd.extend(extended_baq.split())
        _add_if_value(cmd, "--min-mq", inputs.get("min_mq"))
        if inputs.get("no_mq"):
            cmd.append("--no-mq")
        else:
            _add_if_value(cmd, "--max-mq", inputs.get("max_mq"))
        if inputs.get("src_qual"):
            cmd.append("--src-qual")
            ign_vcf = _as_list(inputs.get("ign_vcf"))
            if ign_vcf:
                cmd.extend(["--ign-vcf", ",".join(ign_vcf)])
            _add_if_value(cmd, "--def-nm-q", inputs.get("def_nm_q"))
        _add_if_value(cmd, "--min-jq", inputs.get("min_jq"))
        _add_if_value(cmd, "--min-alt-jq", inputs.get("min_alt_jq"))
        _add_if_value(cmd, "--def-alt-jq", inputs.get("def_alt_jq"))
        _add_if_value(cmd, "--sig", inputs.get("sig", 0.01))
        _add_if_value(cmd, "--bonf", inputs.get("bonf", "dynamic"))
        if inputs.get("no_default_filter"):
            cmd.append("--no-default-filter")
        cmd.append(str(inputs.get("reads", "")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "variants.vcf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("BAM", {"description": "Mapped reads in coordinate-sorted BAM format"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
                "variant_types": ("STRING", {"default": "", "options": ["", "--call-indels", "--call-indels --only-indels"]}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "bed": ("BED", {"description": "Restrict calls to BED regions"}),
                "min_cov": ("INT", {"default": 1, "min": 1}),
                "max_depth": ("INT", {"default": 1000000, "min": 1}),
                "use_orphan": ("BOOLEAN", {"default": False, "advanced": True}),
                "min_bq": ("INT", {"default": 6, "min": 0}),
                "min_alt_bq": ("INT", {"default": 6, "min": 0}),
                "def_alt_bq": ("INT", {"default": "", "advanced": True}),
                "alnquals_to_use": ("STRING", {"default": "", "options": ["", "-A", "-B", "-A -B"], "advanced": True}),
                "extended_baq": ("STRING", {"default": "", "options": ["", "-e"], "advanced": True}),
                "min_mq": ("INT", {"default": 0, "min": 0}),
                "max_mq": ("INT", {"default": 255, "min": 0}),
                "no_mq": ("BOOLEAN", {"default": False, "advanced": True}),
                "src_qual": ("BOOLEAN", {"default": False, "advanced": True}),
                "ign_vcf": ("VCF_LIST", {"description": "Known variants to ignore for source quality", "advanced": True}),
                "def_nm_q": ("INT", {"default": -1, "advanced": True}),
                "min_jq": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "min_alt_jq": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "def_alt_jq": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sig": ("FLOAT", {"default": 0.01, "min": 0, "max": 1}),
                "bonf": ("STRING", {"default": "dynamic"}),
                "no_default_filter": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class IVarVariantsNode(CommandNode):
    """Call viral amplicon variants from samtools mpileup using iVar."""

    NODE_ID = "ivar_variants"
    DISPLAY_NAME = "iVar Variants"
    REQUIRED_CONDA_PACKAGES = ["samtools", "ivar"]
    CATEGORY = "variant"
    DESCRIPTION = "Call iSNVs and indels from aligned viral amplicon reads with iVar variants."
    SEARCH_ALIASES = [GALAXY_ALIAS, "ivar", "ivar variants", "viral variants", "amplicon variants", "iSNV"]
    RETURN_TYPES = ("TSV", "VCF")
    RETURN_NAMES = ("variants_tsv", "variants_vcf")
    REQUIRED_EXECUTABLES = ["samtools", "ivar"]
    DOCUMENTATION_URL = "https://andersen-lab.github.io/ivar/html/"
    CITATION_DOIS = ["10.1186/s13059-018-1618-7"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-018-1618-7"]
    CITATION_TEXT = "An amplicon-based sequencing framework for accurately measuring intrahost virus diversity using PrimalSeq and iVar."
    VERSION = "1.4.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = str(inputs.get("output_format", "tabular"))
        cmd = [
            "samtools",
            "mpileup",
            "-A",
            "-d",
            "0",
            "--reference",
            str(inputs.get("ref", "")),
            "-B",
            "-Q",
            "0",
            str(inputs.get("input_bam", "")),
            "|",
            "ivar",
            "variants",
            "-p",
            f"{out}/variants",
            "-q",
            str(inputs.get("min_qual", 20)),
            "-t",
            str(inputs.get("min_freq", 0.03)),
        ]
        gtf = str(inputs.get("gtf", ""))
        if output_format in {"tabular", "tabular_and_vcf"} and gtf:
            cmd.extend(["-r", str(inputs.get("ref", "")), "-g", gtf])
        if output_format in {"vcf", "tabular_and_vcf"}:
            cmd.extend(["&&", "ivar_variants_to_vcf.py"])
            if inputs.get("pass_only"):
                cmd.append("--pass_only")
            cmd.extend([f"{out}/variants.tsv", f"{out}/variants.vcf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        output_format = str(inputs.get("output_format", "tabular"))
        outputs: list[Path] = []
        if output_format in {"tabular", "tabular_and_vcf"}:
            outputs.append(out / "variants.tsv")
        if output_format in {"vcf", "tabular_and_vcf"}:
            outputs.append(out / "variants.vcf")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Aligned BAM file"}),
                "ref": ("FASTA", {"description": "Reference FASTA used for alignment"}),
                "min_qual": ("INT", {"default": 20, "min": 0, "max": 255}),
                "min_freq": ("FLOAT", {"default": 0.03, "min": 0, "max": 1}),
                "output_format": ("STRING", {"default": "tabular", "options": ["tabular", "vcf", "tabular_and_vcf"]}),
            },
            "optional": {
                "gtf": ("GFF", {"description": "Optional ORF annotations for amino-acid effect columns"}),
                "pass_only": ("BOOLEAN", {"default": False, "description": "Only include PASS variants in VCF output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class GTDBTkClassifyWFNode(CommandNode):
    """Assign bacterial and archaeal taxonomy with GTDB-Tk classify_wf."""

    NODE_ID = "gtdbtk_classify_wf"
    DISPLAY_NAME = "GTDB-Tk Classify"
    REQUIRED_CONDA_PACKAGES = ["gtdbtk"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Classify one or more bacterial or archaeal genomes against the GTDB reference taxonomy."
    SEARCH_ALIASES = [GALAXY_ALIAS, "gtdbtk", "GTDB-Tk", "classify_wf", "taxonomy", "genome taxonomy", "MAG classification"]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "STATS_FILE")
    RETURN_NAMES = ("align", "identify", "classify", "summary", "process_log")
    REQUIRED_EXECUTABLES = ["gtdbtk"]
    DOCUMENTATION_URL = "https://ecogenomics.github.io/GTDBTk/commands/classify_wf.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btz848"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btz848"]
    CITATION_TEXT = "GTDB-Tk: a toolkit to classify genomes with the Genome Taxonomy Database."
    VERSION = "2.7.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input_dir"
        output_dir = f"{out}/output_dir"
        cmd = ["mkdir", "-p", input_dir, output_dir]
        genomes = _as_list(inputs.get("input"))
        extension = str(inputs.get("extension", "")).lstrip(".")
        for genome in genomes:
            link_name = _safe_name(genome)
            if extension and not link_name.endswith(f".{extension}"):
                link_name = f"{link_name}.{extension}"
            cmd.extend(["&&", "ln", "-sf", genome, f"{input_dir}/{link_name}"])

        cmd.extend([
            "&&",
            "export",
            f"GTDBTK_DATA_PATH={inputs.get('gtdbtk_data_path', '')}",
            "&&",
            "gtdbtk",
            "classify_wf",
            "--genome_dir",
            input_dir,
            "--extension",
            extension,
            "--out_dir",
            output_dir,
            "--cpus",
            str(inputs.get("threads", 4)),
            "--min_perc_aa",
            str(inputs.get("min_perc_aa", 10)),
        ])
        if inputs.get("force"):
            cmd.append("--force")
        cmd.extend(["--min_af", str(inputs.get("min_af", 0.65))])
        if inputs.get("full_tree"):
            cmd.append("--full_tree")
        if inputs.get("skip_ani_screen", True):
            cmd.append("--skip_ani_screen")
        if inputs.get("output_process_log"):
            cmd.extend([
                "&&",
                "cat",
                f"{output_dir}/gtdbtk.warnings.log",
                f"{output_dir}/gtdbtk.log",
                ">",
                f"{out}/process.log",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        gtdbtk_out = out / "output_dir"
        outputs = [gtdbtk_out / "align", gtdbtk_out / "identify", gtdbtk_out / "classify", gtdbtk_out]
        if inputs.get("output_process_log"):
            outputs.append(out / "process.log")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA_LIST", {"description": "Genome FASTA or FASTA.GZ files to classify"}),
                "gtdbtk_data_path": ("DIRECTORY", {"description": "Local GTDB-Tk reference database path"}),
            },
            "optional": {
                "extension": ("STRING", {"default": "fna.gz", "description": "Input genome extension visible to GTDB-Tk"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 256, "display": "slider"}),
                "min_perc_aa": ("INT", {"default": 10, "min": 0, "max": 100}),
                "force": ("BOOLEAN", {"default": False, "advanced": True}),
                "min_af": ("FLOAT", {"default": 0.65, "min": 0, "max": 1}),
                "full_tree": ("BOOLEAN", {"default": False, "advanced": True}),
                "skip_ani_screen": ("BOOLEAN", {"default": True, "description": "Skip ANI screen when a Mash DB is unavailable", "advanced": True}),
                "output_process_log": ("BOOLEAN", {"default": False, "description": "Emit combined GTDB-Tk warnings and process log"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class RSeQCInferExperimentNode(CommandNode):
    """Infer RNA-seq strandedness from alignments and a BED12 gene model."""

    NODE_ID = "rseqc_infer_experiment"
    DISPLAY_NAME = "RSeQC Infer Experiment"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Estimate RNA-seq strandedness and library configuration from mapped reads."
    SEARCH_ALIASES = [GALAXY_ALIAS, "rseqc", "infer_experiment", "strandedness", "rna-seq qc", "library orientation"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("infer_experiment",)
    REQUIRED_EXECUTABLES = ["infer_experiment.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#infer-experiment-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "infer_experiment.py",
            "-i",
            str(inputs.get("input", "")),
            "-r",
            str(inputs.get("refgene", "")),
            "--sample-size",
            str(inputs.get("sample_size", 200000)),
            "--mapq",
            str(inputs.get("mapq", 30)),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/infer_experiment.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "infer_experiment.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "sample_size": ("INT", {"default": 200000, "min": 1, "description": "Number of usable reads to sample"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsCoverageNode(CommandNode):
    """Compute depth and breadth of B features across A intervals."""

    NODE_ID = "bedtools_coveragebed"
    DISPLAY_NAME = "BEDTools Coverage"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute interval coverage depth and breadth using bedtools coverage."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "coverage", "coveragebed", "depth", "breadth", "interval coverage"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("coverage",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/coverage.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "coverage"]
        if inputs.get("d"):
            cmd.append("-d")
        if inputs.get("hist"):
            cmd.append("-hist")
        if inputs.get("split"):
            cmd.append("-split")
        if inputs.get("strandedness"):
            cmd.append("-s")
        if inputs.get("mean"):
            cmd.append("-mean")
        _add_if_value(cmd, "-f", inputs.get("overlap_a"))
        _add_if_value(cmd, "-F", inputs.get("overlap_b"))
        if inputs.get("reciprocal_overlap"):
            cmd.append("-r")
        if inputs.get("a_or_b"):
            cmd.append("-e")
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", *_as_list(inputs.get("inputB"))])
        if inputs.get("sorted"):
            cmd.append("-sorted")
        if str(inputs.get("inputA", "")).lower().endswith((".gff", ".gff3")):
            cmd.extend(["|", "sort", "-k1,1", "-k4,2n"])
        else:
            cmd.extend(["|", "sort", "-k1,1", "-k2,2n"])
        _add_shell_redirect(cmd, f"{_out(inputs)}/coverage.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "coverage.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "File A intervals on which coverage is calculated"}),
                "inputB": ("BED_LIST", {"description": "One or more file B interval or BAM inputs"}),
            },
            "optional": {
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM alignments as distinct intervals"}),
                "strandedness": ("BOOLEAN", {"default": False, "description": "Require same-strand overlaps"}),
                "d": ("BOOLEAN", {"default": False, "description": "Report depth at each position"}),
                "hist": ("BOOLEAN", {"default": False, "description": "Report coverage histogram"}),
                "mean": ("BOOLEAN", {"default": False, "description": "Report mean depth"}),
                "overlap_a": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal_overlap": ("BOOLEAN", {"default": False, "advanced": True}),
                "a_or_b": ("BOOLEAN", {"default": False, "advanced": True}),
                "sorted": ("BOOLEAN", {"default": False, "description": "Use sorted input mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsGenomeCoverageNode(CommandNode):
    """Compute genome-wide interval coverage with bedtools genomecov."""

    NODE_ID = "bedtools_genomecoveragebed"
    DISPLAY_NAME = "BEDTools Genome Coverage"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute genome-wide coverage from BAM or interval files with bedtools genomecov."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "genomecov", "genome coverage", "bedgraph", "coverage histogram"]
    RETURN_TYPES = ("BEDGRAPH", "TSV")
    RETURN_NAMES = ("genome_coverage_bedgraph", "genome_coverage_histogram")
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/genomecov.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        report = str(inputs.get("report", inputs.get("report_select", "bg")))
        output_name = "genome_coverage.tsv" if report == "hist" else "genome_coverage.bedgraph"
        input_type = str(inputs.get("input_type", inputs.get("input_type_select", "bed")))
        cmd = ["bedtools", "genomecov"]
        if input_type == "bam":
            cmd.extend(["-ibam", str(inputs.get("input", ""))])
        else:
            cmd.extend(["-i", str(inputs.get("input", ""))])
            _add_if_value(cmd, "-g", inputs.get("genome"))
        if inputs.get("split"):
            cmd.append("-split")
        strand = str(inputs.get("strand", ""))
        if strand:
            cmd.extend(["-strand", strand.replace("-strand ", "")])
        if report == "bg":
            cmd.append("-bga" if inputs.get("zero_regions") else "-bg")
            _add_if_value(cmd, "-scale", inputs.get("scale", 1.0))
        else:
            _add_if_value(cmd, "-max", inputs.get("max"))
        if inputs.get("d"):
            cmd.append("-d")
        if inputs.get("dz"):
            cmd.append("-dz")
        if inputs.get("five"):
            cmd.append("-5")
        if inputs.get("three"):
            cmd.append("-3")
        _add_shell_redirect(cmd, f"{_out(inputs)}/{output_name}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        report = str(inputs.get("report", inputs.get("report_select", "bg")))
        if report == "hist":
            return [out / "genome_coverage.tsv"]
        return [out / "genome_coverage.bedgraph"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": ("STRING", {"default": "bed", "options": ["bed", "bam"]}),
                "input": ("FILE", {"description": "Sorted BED/GFF/VCF/BAM input"}),
                "report": ("STRING", {"default": "bg", "options": ["bg", "hist"], "description": "BedGraph or histogram output"}),
            },
            "optional": {
                "genome": ("TSV", {"description": "Genome chromosome sizes file required for BED-like input"}),
                "zero_regions": ("BOOLEAN", {"default": False, "description": "Report zero-coverage regions with -bga"}),
                "scale": ("FLOAT", {"default": 1.0, "min": 0}),
                "max": ("INT", {"default": "", "min": 0, "description": "Histogram max depth bin"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM alignments as distinct intervals"}),
                "strand": ("STRING", {"default": "", "options": ["", "+", "-"], "description": "Restrict coverage to one strand"}),
                "d": ("BOOLEAN", {"default": False, "description": "Report 1-based per-position depth"}),
                "dz": ("BOOLEAN", {"default": False, "description": "Report 0-based non-zero per-position depth"}),
                "five": ("BOOLEAN", {"default": False, "description": "Calculate coverage of 5' positions"}),
                "three": ("BOOLEAN", {"default": False, "description": "Calculate coverage of 3' positions"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsSubtractNode(CommandNode):
    """Remove portions of A intervals that overlap B intervals."""

    NODE_ID = "bedtools_subtractbed"
    DISPLAY_NAME = "BEDTools Subtract"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Remove intervals or overlapping bases from one feature set using bedtools subtract."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "subtract", "subtractbed", "interval subtraction", "blacklist"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("subtracted",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/subtract.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        strand_flags = {"same": "-s", "opposite": "-S", "-s": "-s", "-S": "-S"}
        remove_flags = {
            "remove_feature": "-A",
            "remove_feature_sum": "-N",
            "-A": "-A",
            "-N": "-N",
        }
        cmd = ["bedtools", "subtract"]
        strand = str(inputs.get("strand", ""))
        if strand_flags.get(strand):
            cmd.append(strand_flags[strand])
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", str(inputs.get("inputB", ""))])
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        remove_if_overlap = str(inputs.get("remove_if_overlap", inputs.get("removeIfOverlap", "")))
        if remove_flags.get(remove_if_overlap):
            cmd.append(remove_flags[remove_if_overlap])
        _add_shell_redirect(cmd, f"{_out(inputs)}/subtracted.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "subtracted.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to subtract from"}),
                "inputB": ("BED", {"description": "Intervals used to mask or remove A bases"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap required as a fraction of A"}),
                "remove_if_overlap": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "remove_feature", "remove_feature_sum"],
                        "description": "Remove entire A feature on any overlap, or on cumulative overlap with -f",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsMergeNode(CommandNode):
    """Combine overlapping or nearby intervals with bedtools merge."""

    NODE_ID = "bedtools_mergebed"
    DISPLAY_NAME = "BEDTools Merge"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Combine overlapping or nearby intervals into flattened regions with optional column summaries."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "merge", "mergebed", "combine intervals", "flatten intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("merged",)
    REQUIRED_EXECUTABLES = ["mergeBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/merge.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        strand_flags = {
            "same": ["-s"],
            "forward": ["-S", "+"],
            "reverse": ["-S", "-"],
            "-s": ["-s"],
            "-S +": ["-S", "+"],
            "-S -": ["-S", "-"],
        }
        cmd = ["mergeBed", "-i", str(inputs.get("input", ""))]
        cmd.extend(strand_flags.get(str(inputs.get("strand", "")), []))
        cmd.extend(["-d", str(inputs.get("distance", 0))])
        if inputs.get("header"):
            cmd.append("-header")
        columns = str(inputs.get("columns", inputs.get("cols", ""))).strip()
        operations = str(inputs.get("operations", inputs.get("operation", ""))).strip()
        if columns and operations:
            cmd.extend(["-c", columns, "-o", operations])
        if str(inputs.get("input", "")).lower().endswith(".bam"):
            cmd.append("-bed")
        _add_shell_redirect(cmd, f"{_out(inputs)}/merged.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "merged.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Presorted BED/GFF/VCF/BAM intervals to merge"}),
                "distance": ("INT", {"default": 0, "description": "Maximum distance between intervals to merge"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "forward", "reverse"]}),
                "header": ("BOOLEAN", {"default": False, "description": "Print input header before results"}),
                "columns": ("STRING", {"default": "", "description": "Comma-separated columns to summarize"}),
                "operations": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Comma-separated operations such as sum,mean,count,collapse,distinct",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsSortNode(CommandNode):
    """Sort genomic intervals with bedtools sort."""

    NODE_ID = "bedtools_sortbed"
    DISPLAY_NAME = "BEDTools Sort"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Order BED, GFF, VCF, or bedGraph intervals by coordinate, size, score, or a genome file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "sort", "sortbed", "coordinate sort", "genome order"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("sorted_intervals",)
    REQUIRED_EXECUTABLES = ["sortBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/sort.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["sortBed", "-i", str(inputs.get("input", ""))]
        sort_by = str(inputs.get("sort_by", inputs.get("option", "")))
        if sort_by:
            cmd.append(sort_by)
        _add_if_value(cmd, "-g", inputs.get("genome"))
        output_ext = _bedtools_ext(inputs.get("input"))
        _add_shell_redirect(cmd, f"{_out(inputs)}/sorted.{output_ext}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"sorted.{_bedtools_ext(inputs.get('input'))}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "BED, GFF, VCF, bedGraph, or EncodePeak intervals to sort"}),
            },
            "optional": {
                "sort_by": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "-sizeA", "-sizeD", "-chrThenSizeA", "-chrThenSizeD", "-chrThenScoreA", "-chrThenScoreD"],
                    },
                ),
                "genome": ("TSV", {"description": "Optional genome chromosome sizes file for sort order"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsGetFastaNode(CommandNode):
    """Extract FASTA or tabular sequences for genomic intervals."""

    NODE_ID = "bedtools_getfastabed"
    DISPLAY_NAME = "BEDTools getfasta"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract sequences from a FASTA file using BED, GFF, VCF, or bedGraph intervals."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "getfasta", "getfastabed", "extract sequence", "fasta intervals"]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("extracted_fasta", "extracted_tsv")
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/getfasta.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_name = "extracted.tsv" if inputs.get("tab") else "extracted.fasta"
        cmd = ["ln", "-s", str(inputs.get("fasta", "")), "input.fasta", "&&", "bedtools", "getfasta"]
        if inputs.get("name"):
            cmd.append("-name")
        if inputs.get("name_only", inputs.get("nameOnly")):
            cmd.append("-nameOnly")
        if inputs.get("tab"):
            cmd.append("-tab")
        if inputs.get("strand"):
            cmd.append("-s")
        if inputs.get("split"):
            cmd.append("-split")
        cmd.extend([
            "-fi",
            "input.fasta",
            "-bed",
            str(inputs.get("input", "")),
            "-fo",
            f"{_out(inputs)}/{output_name}",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if inputs.get("tab"):
            return [out / "extracted.tsv"]
        return [out / "extracted.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals used to extract sequence"}),
                "fasta": ("FASTA", {"description": "Reference FASTA file"}),
            },
            "optional": {
                "name": ("BOOLEAN", {"default": False, "description": "Use BED name and coordinates in FASTA headers"}),
                "name_only": ("BOOLEAN", {"default": False, "description": "Use only the BED name in FASTA headers"}),
                "tab": ("BOOLEAN", {"default": False, "description": "Emit tab-delimited name and sequence output"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Reverse complement antisense features"}),
                "split": ("BOOLEAN", {"default": False, "description": "Use BED12 blocks rather than full interval spans"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsComplementNode(CommandNode):
    """Report genome intervals not covered by the input feature file."""

    NODE_ID = "bedtools_complementbed"
    DISPLAY_NAME = "BEDTools Complement"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract genome intervals not represented by an interval file using bedtools complement."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "complement", "complementbed", "genome gaps", "uncovered intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("complement",)
    REQUIRED_EXECUTABLES = ["complementBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/complement.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["complementBed", "-i", str(inputs.get("input", ""))]
        _bedtools_add_genome(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/complement.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "complement.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Sorted interval file whose uncovered genome intervals are reported"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsFlankNode(CommandNode):
    """Create flanking intervals around each input feature."""

    NODE_ID = "bedtools_flankbed"
    DISPLAY_NAME = "BEDTools Flank"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create new intervals from the flanks of existing intervals with bedtools flank."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "flank", "flankbed", "upstream", "downstream"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("flanks",)
    REQUIRED_EXECUTABLES = ["flankBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/flank.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["flankBed"]
        if inputs.get("pct"):
            cmd.append("-pct")
        if inputs.get("strand"):
            cmd.append("-s")
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("input", ""))])
        _bedtools_add_lr_or_b(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/flanks.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "flanks.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals to flank"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "addition_mode": ("STRING", {"default": "b", "options": ["b", "lr"]}),
                "both": ("FLOAT", {"default": 1, "min": 0, "description": "Symmetric flank size"}),
                "left": ("FLOAT", {"default": 0, "min": 0, "description": "Left/upstream flank size"}),
                "right": ("FLOAT", {"default": 0, "min": 0, "description": "Right/downstream flank size"}),
                "pct": ("BOOLEAN", {"default": False, "description": "Interpret sizes as fractions of feature length"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Interpret left/right relative to feature strand"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsSlopNode(CommandNode):
    """Expand input intervals while respecting chromosome bounds."""

    NODE_ID = "bedtools_slopbed"
    DISPLAY_NAME = "BEDTools Slop"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Adjust interval sizes with bedtools slop while clipping to chromosome boundaries."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "slop", "slopbed", "extend intervals", "resize intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("slopped",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/slop.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "slop"]
        if inputs.get("pct"):
            cmd.append("-pct")
        if inputs.get("strand"):
            cmd.append("-s")
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("inputA", ""))])
        _bedtools_add_lr_or_b(cmd, inputs)
        if inputs.get("header"):
            cmd.append("-header")
        _add_shell_redirect(cmd, f"{_out(inputs)}/slopped.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "slopped.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to resize"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "addition_mode": ("STRING", {"default": "b", "options": ["b", "lr"]}),
                "both": ("FLOAT", {"default": 1, "min": 0, "description": "Symmetric extension size"}),
                "left": ("FLOAT", {"default": 0, "min": 0, "description": "Left/upstream extension size"}),
                "right": ("FLOAT", {"default": 0, "min": 0, "description": "Right/downstream extension size"}),
                "pct": ("BOOLEAN", {"default": False, "description": "Interpret sizes as fractions of feature length"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Interpret left/right relative to feature strand"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the input header before results"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsWindowNode(CommandNode):
    """Find B intervals near A intervals within symmetric or asymmetric windows."""

    NODE_ID = "bedtools_windowbed"
    DISPLAY_NAME = "BEDTools Window"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Find intervals in B that overlap a window around each interval in A."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "window", "windowbed", "nearby intervals", "proximal features"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("window_matches",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/window.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "window"]
        input_a = str(inputs.get("inputA", ""))
        if input_a.lower().endswith(".bam"):
            cmd.extend(["-abam", input_a])
            if inputs.get("bed"):
                cmd.append("-bed")
        else:
            cmd.extend(["-a", input_a])
        cmd.extend(["-b", str(inputs.get("inputB", ""))])
        strand_flag = _bedtools_strand_flag(inputs.get("strand"), same="-sm", opposite="-Sm")
        if strand_flag:
            cmd.append(strand_flag)
        if str(inputs.get("addition_mode", "window")) == "lr":
            cmd.extend(["-l", str(inputs.get("left", 1000)), "-r", str(inputs.get("right", 1000))])
        else:
            cmd.extend(["-w", str(inputs.get("window", inputs.get("w", 1000)))])
        if inputs.get("original"):
            cmd.append("-u")
        if inputs.get("number"):
            cmd.append("-c")
        if inputs.get("nooverlaps"):
            cmd.append("-v")
        if inputs.get("header"):
            cmd.append("-header")
        _add_shell_redirect(cmd, f"{_out(inputs)}/window.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "window.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("FILE", {"description": "A intervals or BAM alignments"}),
                "inputB": ("BED", {"description": "B intervals to search near A"}),
            },
            "optional": {
                "addition_mode": ("STRING", {"default": "window", "options": ["window", "lr"]}),
                "window": ("INT", {"default": 1000, "min": 0, "description": "Symmetric window size"}),
                "left": ("INT", {"default": 1000, "min": 0, "description": "Left/upstream window size"}),
                "right": ("INT", {"default": 1000, "min": 0, "description": "Right/downstream window size"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "bed": ("BOOLEAN", {"default": False, "description": "Write BED output for BAM input"}),
                "original": ("BOOLEAN", {"default": False, "description": "Report each A feature once if any B hit is found"}),
                "number": ("BOOLEAN", {"default": False, "description": "Report number of B hits for each A feature"}),
                "nooverlaps": ("BOOLEAN", {"default": False, "description": "Report only A features with no B hits"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the input header before results"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsMapNode(CommandNode):
    """Map statistics from overlapping B intervals onto A intervals."""

    NODE_ID = "bedtools_map"
    DISPLAY_NAME = "BEDTools Map"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Apply summary operations to columns from B intervals that overlap each A interval."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "map", "mapbed", "interval statistics", "overlap summary"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("mapped",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/map.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "map",
            "-a",
            str(inputs.get("inputA", "")),
            "-b",
            str(inputs.get("inputB", "")),
        ]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        columns = str(inputs.get("columns", inputs.get("cols", ""))).strip()
        operations = str(inputs.get("operations", inputs.get("operation", ""))).strip()
        if columns and operations:
            cmd.extend(["-c", columns, "-o", operations])
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        _add_if_value(cmd, "-F", inputs.get("overlap_b", inputs.get("overlapB")))
        if inputs.get("reciprocal"):
            cmd.append("-r")
        if inputs.get("split"):
            cmd.append("-split")
        if inputs.get("header"):
            cmd.append("-header")
        _bedtools_add_genome(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/mapped.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "mapped.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Sorted A intervals"}),
                "inputB": ("BED", {"description": "Sorted B intervals with columns to summarize"}),
                "columns": ("STRING", {"default": "5", "description": "Comma-separated B columns to summarize"}),
                "operations": ("STRING", {"default": "mean", "description": "Comma-separated summary operations"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM entries as distinct intervals"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the input header before results"}),
                "genome": ("TSV", {"description": "Optional genome chromosome sizes file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsMultiIntersectNode(CommandNode):
    """Identify shared intervals across multiple interval files."""

    NODE_ID = "bedtools_multiintersectbed"
    DISPLAY_NAME = "BEDTools Multiple Intersect"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Identify common intervals among multiple sorted interval files with bedtools multiinter."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "multiinter", "multiintersect", "multiple intersect", "shared intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("multiintersect",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/multiinter.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("inputs"))
        names = _as_list(inputs.get("names"))
        cmd = ["bedtools", "multiinter"]
        if inputs.get("header"):
            cmd.append("-header")
        if inputs.get("cluster"):
            cmd.append("-cluster")
        cmd.extend(["-filler", str(inputs.get("filler", "N/A"))])
        if inputs.get("empty"):
            cmd.append("-empty")
            _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", *files])
        if names:
            cmd.extend(["-names", *names])
        _add_shell_redirect(cmd, f"{_out(inputs)}/multiintersect.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "multiintersect.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": ("BED_LIST", {"description": "Two or more sorted interval files"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional custom labels matching the inputs order"}),
                "header": ("BOOLEAN", {"default": False, "description": "Add output header"}),
                "cluster": ("BOOLEAN", {"default": False, "description": "Invoke clustering algorithm"}),
                "filler": ("STRING", {"default": "N/A", "description": "Text for no-coverage values"}),
                "empty": ("BOOLEAN", {"default": False, "description": "Report regions with zero coverage across all files"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file required when empty is enabled"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsClusterNode(CommandNode):
    """Assign cluster IDs to overlapping or nearby intervals."""

    NODE_ID = "bedtools_clusterbed"
    DISPLAY_NAME = "BEDTools Cluster"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Cluster overlapping or nearby sorted intervals without flattening them."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "cluster", "clusterbed", "overlap clusters", "nearby intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("clustered",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/cluster.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "cluster"]
        if inputs.get("strand"):
            cmd.append("-s")
        cmd.extend(["-d", str(inputs.get("distance", 0)), "-i", str(inputs.get("inputA", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/clustered.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "clustered.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Sorted interval file to cluster"}),
            },
            "optional": {
                "strand": ("BOOLEAN", {"default": False, "description": "Only cluster features on the same strand"}),
                "distance": ("INT", {"default": 0, "description": "Maximum distance between features in the same cluster"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsJaccardNode(CommandNode):
    """Calculate Jaccard similarity between two interval sets."""

    NODE_ID = "bedtools_jaccard"
    DISPLAY_NAME = "BEDTools Jaccard"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Calculate intersection, union, Jaccard similarity, and intersection counts for two sorted interval sets."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "jaccard", "jaccardbed", "interval similarity", "set overlap"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("jaccard",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/jaccard.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "jaccard"]
        if inputs.get("strand"):
            cmd.append("-s")
        if inputs.get("split"):
            cmd.append("-split")
        if inputs.get("reciprocal"):
            cmd.append("-r")
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        _add_if_value(cmd, "-F", inputs.get("overlap_b", inputs.get("overlapB")))
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", str(inputs.get("inputB", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/jaccard.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "jaccard.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Sorted interval file A"}),
                "inputB": ("BED", {"description": "Sorted interval file B"}),
            },
            "optional": {
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Require same-strand overlaps"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM entries as distinct intervals"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsFisherNode(CommandNode):
    """Perform Fisher's exact test on overlap between two interval sets."""

    NODE_ID = "bedtools_fisher"
    DISPLAY_NAME = "BEDTools Fisher"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Calculate Fisher's exact test statistics for overlaps between two feature files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "fisher", "fisherbed", "overlap significance", "exact test"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("fisher",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/fisher.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "fisher"]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        if inputs.get("split"):
            cmd.append("-split")
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", str(inputs.get("inputB", ""))])
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        _bedtools_add_genome(cmd, inputs)
        if inputs.get("reciprocal"):
            cmd.append("-r")
        if inputs.get("merge"):
            cmd.append("-m")
        _add_shell_redirect(cmd, f"{_out(inputs)}/fisher.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "fisher.txt", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Interval file A"}),
                "inputB": ("BED", {"description": "Interval file B"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM entries as distinct intervals"}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "merge": ("BOOLEAN", {"default": False, "description": "Merge overlapping intervals before testing"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsRelativeDistanceNode(CommandNode):
    """Calculate relative distance distribution between two interval sets."""

    NODE_ID = "bedtools_reldistbed"
    DISPLAY_NAME = "BEDTools Relative Distance"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Calculate the relative distance distribution between intervals in two feature sets."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "reldist", "reldistbed", "relative distance", "spatial correlation"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("relative_distance",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/reldist.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI, "10.1371/journal.pcbi.1002529"]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}", f"{DOI_URL}10.1371/journal.pcbi.1002529"]
    CITATION_TEXT = (
        f"{BEDTOOLS_CITATION_TEXT}; Exploring Massive, Genome Scale Datasets with the GenometriCorr Package."
    )
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "reldist",
            "-a",
            str(inputs.get("inputA", "")),
            "-b",
            str(inputs.get("inputB", "")),
        ]
        if inputs.get("detail"):
            cmd.append("-detail")
        _add_shell_redirect(cmd, f"{_out(inputs)}/relative_distance.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "relative_distance.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Interval file A"}),
                "inputB": ("BED", {"description": "Interval file B"}),
            },
            "optional": {
                "detail": ("BOOLEAN", {"default": False, "description": "Report relative distance for each A interval"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsSpacingNode(CommandNode):
    """Report distances between adjacent intervals."""

    NODE_ID = "bedtools_spacingbed"
    DISPLAY_NAME = "BEDTools Spacing"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Report the spacing between adjacent intervals in a sorted interval file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "spacing", "spacingbed", "distance between intervals", "adjacent intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("spacing",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/spacing.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "spacing", "-i", str(inputs.get("input", ""))]
        _add_shell_redirect(cmd, f"{_out(inputs)}/spacing.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "spacing.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Sorted interval file"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsGroupByNode(CommandNode):
    """Group rows by columns and summarize values in other columns."""

    NODE_ID = "bedtools_groupbybed"
    DISPLAY_NAME = "BEDTools GroupBy"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Group intervals by one or more columns and summarize selected columns with bedtools groupby."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "groupby", "groupbybed", "summarize intervals", "aggregate columns"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("grouped",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/groupby.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "groupby",
            "-i",
            str(inputs.get("inputA", "")),
            "-g",
            str(inputs.get("group", "1,2,3")),
            "-c",
            str(inputs.get("columns", inputs.get("cols", ""))),
            "-o",
            str(inputs.get("operation", "sum")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/grouped.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "grouped.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Interval or tabular file to group"}),
                "columns": ("STRING", {"default": "4", "description": "Comma-separated columns to summarize"}),
                "group": ("STRING", {"default": "1,2,3", "description": "Columns or ranges to group by"}),
                "operation": (
                    "STRING",
                    {
                        "default": "sum",
                        "options": [
                            "sum",
                            "min",
                            "max",
                            "absmin",
                            "absmax",
                            "mean",
                            "median",
                            "mode",
                            "antimode",
                            "stdev",
                            "sstdev",
                            "collapse",
                            "count",
                            "distinct",
                            "first",
                            "last",
                            "freqasc",
                            "freqdesc",
                        ],
                    },
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsBamToBedNode(CommandNode):
    """Convert BAM alignments to BED, BED12, or BEDPE records."""

    NODE_ID = "bedtools_bamtobed"
    DISPLAY_NAME = "BEDTools BAM to BED"
    REQUIRED_CONDA_PACKAGES = ["bedtools", "samtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BAM alignments to BED, BED12, or paired BEDPE records with bedtools bamtobed."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "bamtobed", "bam to bed", "bed12", "bedpe"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("converted_bed",)
    REQUIRED_EXECUTABLES = ["bedtools", "samtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bamtobed.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        option_aliases = {
            "": "",
            "bed": "",
            "bed6": "",
            "bed12": "-bed12",
            "-bed12": "-bed12",
            "bedpe": "-bedpe",
            "-bedpe": "-bedpe",
        }
        option = option_aliases.get(str(inputs.get("option", "")), str(inputs.get("option", "")))
        out = _out(inputs)
        bedtools_input = str(inputs.get("input", ""))
        cmd: list[str] = []
        if option == "-bedpe":
            bedtools_input = f"{out}/input.bam"
            cmd.extend(
                [
                    "samtools",
                    "sort",
                    "-n",
                    "-@",
                    str(inputs.get("threads", 4)),
                    "-T",
                    f"{out}/tmp",
                    str(inputs.get("input", "")),
                    ">",
                    bedtools_input,
                    "&&",
                ]
            )
        cmd.extend(["bedtools", "bamtobed"])
        if option:
            cmd.append(option)
        if inputs.get("ed_score"):
            cmd.append("-ed")
        if inputs.get("split"):
            cmd.append("-split")
        tag = str(inputs.get("tag", "")).strip()
        if tag:
            cmd.extend(["-tag", tag])
        cmd.extend(["-i", bedtools_input])
        _add_shell_redirect(cmd, f"{out}/converted.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "converted.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file to convert"}),
                "option": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "bed12", "bedpe"],
                        "description": "Output BED flavor: BED6, blocked BED12, or paired BEDPE",
                    },
                ),
            },
            "optional": {
                "split": ("BOOLEAN", {"default": False, "description": "Split spliced alignments into distinct BED records"}),
                "ed_score": ("BOOLEAN", {"default": False, "description": "Use BAM edit distance as the BED score"}),
                "tag": ("STRING", {"default": "", "description": "Numeric BAM tag to use as the BED score"}),
                "threads": ("INT", {"default": 4, "min": 1, "description": "Threads for BEDPE name sorting"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsBed12ToBed6Node(CommandNode):
    """Expand BED12 blocked features into BED6 intervals."""

    NODE_ID = "bedtools_bed12tobed6"
    DISPLAY_NAME = "BEDTools BED12 to BED6"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert blocked BED12 features into discrete BED6 features with bed12ToBed6."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "bed12tobed6", "bed12 to bed6", "blocked bed", "exons"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("bed6",)
    REQUIRED_EXECUTABLES = ["bed12ToBed6"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bed12tobed6.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bed12ToBed6", "-i", str(inputs.get("input", ""))]
        _add_shell_redirect(cmd, f"{_out(inputs)}/bed6.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "bed6.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED12 file to expand into BED6 blocks"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsBedToBamNode(CommandNode):
    """Convert BED features to BAM alignments."""

    NODE_ID = "bedtools_bedtobam"
    DISPLAY_NAME = "BEDTools BED to BAM"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BED annotations to BAM format with optional BED12 spliced alignment handling."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "bedtobam", "bed to bam", "bed12", "annotation bam"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("converted_bam",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bedtobam.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "bedtobam"]
        if inputs.get("bed12"):
            cmd.append("-bed12")
        cmd.extend(["-mapq", str(inputs.get("mapq", 255))])
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("input", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/converted.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "converted.bam", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED feature file to convert"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "bed12": ("BOOLEAN", {"default": False, "description": "Convert blocked BED12 records into spliced BAM alignments"}),
                "mapq": ("INT", {"default": 255, "min": 0, "max": 255, "description": "Mapping quality value for output alignments"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsBedpeToBamNode(CommandNode):
    """Convert BEDPE paired features to BAM alignments."""

    NODE_ID = "bedtools_bedpetobam"
    DISPLAY_NAME = "BEDTools BEDPE to BAM"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BEDPE paired feature records to an unsorted BAM file with bedtools bedpetobam."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "bedpetobam", "bedpe to bam", "paired intervals", "paired-end"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("paired_bam",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bedpetobam.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "bedpetobam",
            "-mapq",
            str(inputs.get("mapq", 255)),
            "-i",
            str(inputs.get("input", "")),
        ]
        _bedtools_add_genome(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/paired.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "paired.bam", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BEDPE or BED-like paired feature file"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "mapq": ("INT", {"default": 255, "min": 0, "max": 255, "description": "Mapping quality value for output alignments"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsMakeWindowsNode(CommandNode):
    """Create fixed-size or fixed-count windows over genomes or intervals."""

    NODE_ID = "bedtools_makewindowsbed"
    DISPLAY_NAME = "BEDTools Make Windows"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create adjacent or sliding windows across a genome file or BED interval file with bedtools makewindows."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "makewindows", "makewindowsbed", "sliding windows", "genome windows"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("windows",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/makewindows.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get("type", inputs.get("type_select", "bed")))
        action = str(inputs.get("action", inputs.get("action_select", "windowsize")))
        cmd = ["bedtools", "makewindows"]
        if source == "genome":
            _bedtools_add_genome(cmd, inputs)
        else:
            cmd.extend(["-b", str(inputs.get("input", ""))])
        if action == "number":
            cmd.extend(["-n", str(inputs.get("number", 1))])
        else:
            cmd.extend(["-w", str(inputs.get("windowsize", 1))])
            _add_if_value(cmd, "-s", inputs.get("step_size"))
        sourcename = str(inputs.get("sourcename", "")).strip()
        if sourcename:
            sourcename = sourcename.replace("-i ", "")
            cmd.extend(["-i", sourcename])
        _add_shell_redirect(cmd, f"{_out(inputs)}/windows.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "windows.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "type": ("STRING", {"default": "bed", "options": ["bed", "genome"], "description": "Create windows over BED intervals or a genome file"}),
                "action": ("STRING", {"default": "windowsize", "options": ["windowsize", "number"], "description": "Window by fixed size or fixed count"}),
            },
            "optional": {
                "input": ("BED", {"description": "BED intervals used when type is bed"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file used when type is genome"}),
                "windowsize": ("INT", {"default": 1, "min": 1, "description": "Window size in bases"}),
                "step_size": ("INT", {"default": "", "min": 1, "description": "Step size for sliding windows"}),
                "number": ("INT", {"default": 1, "min": 1, "description": "Number of windows per input interval"}),
                "sourcename": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "src", "winnum", "srcwinnum"],
                        "description": "ID naming style for generated windows",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsAnnotateNode(CommandNode):
    """Annotate intervals with coverage from multiple feature files."""

    NODE_ID = "bedtools_annotatebed"
    DISPLAY_NAME = "BEDTools Annotate"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Annotate one interval file with coverage fractions or counts from multiple BED-like files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "annotate", "annotatebed", "coverage annotation", "multiple feature types"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("annotated",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/annotate.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("beds", inputs.get("files")))
        names = _as_list(inputs.get("names"))
        cmd = ["bedtools", "annotate", "-i", str(inputs.get("inputA", ""))]
        cmd.extend(["-files", *files])
        if names:
            cmd.extend(["-names", *names])
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        if inputs.get("counts"):
            cmd.append("-counts")
        if inputs.get("both"):
            cmd.append("-both")
        _add_shell_redirect(cmd, f"{_out(inputs)}/annotated.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "annotated.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to annotate"}),
                "beds": ("BED_LIST", {"description": "One or more annotation interval files"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional labels matching the annotation files"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "counts": ("BOOLEAN", {"default": False, "description": "Report counts instead of only coverage fractions"}),
                "both": ("BOOLEAN", {"default": False, "description": "Report counts followed by coverage fractions"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsExpandNode(CommandNode):
    """Replicate rows by expanding comma-separated column values."""

    NODE_ID = "bedtools_expandbed"
    DISPLAY_NAME = "BEDTools Expand"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Replicate BED-like records by expanding comma-separated values in selected columns."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "expand", "expandbed", "split columns", "comma-separated values"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("expanded",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/expand.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "expand",
            "-c",
            str(inputs.get("columns", inputs.get("cols", ""))),
            "-i",
            str(inputs.get("input", "")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/expanded.{_bedtools_ext(inputs.get('input'))}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, f"expanded.{_bedtools_ext(inputs.get('input'))}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED-like file containing comma-separated values"}),
                "columns": ("STRING", {"default": "4", "description": "Comma-separated columns to expand"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsMaskFastaNode(CommandNode):
    """Mask FASTA sequences over selected intervals."""

    NODE_ID = "bedtools_maskfastabed"
    DISPLAY_NAME = "BEDTools Mask FASTA"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Mask FASTA sequence bases that overlap intervals from a BED-like file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "maskfasta", "maskfastabed", "soft mask", "masked genome"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("masked_fasta",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "maskfasta"]
        if inputs.get("soft"):
            cmd.append("-soft")
        cmd.extend([
            "-mc",
            str(inputs.get("mask_character", inputs.get("mc", "N"))),
            "-fi",
            str(inputs.get("fasta", "")),
            "-bed",
            str(inputs.get("input", "")),
            "-fo",
            f"{_out(inputs)}/masked.fasta",
        ])
        if inputs.get("full_header", inputs.get("fullheader")):
            cmd.append("-fullHeader")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "masked.fasta", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals used to mask the FASTA"}),
                "fasta": ("FASTA", {"description": "FASTA sequences to mask"}),
            },
            "optional": {
                "soft": ("BOOLEAN", {"default": False, "description": "Soft-mask by converting bases to lowercase"}),
                "mask_character": ("STRING", {"default": "N", "description": "Hard-mask replacement character"}),
                "full_header": ("BOOLEAN", {"default": False, "description": "Match and emit the full FASTA header"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsMultiCovNode(CommandNode):
    """Count alignments from multiple BAM files over intervals."""

    NODE_ID = "bedtools_multicovtbed"
    DISPLAY_NAME = "BEDTools MultiCov"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Count overlapping alignments from multiple sorted and indexed BAM files for each interval."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "multicov", "multicovbed", "bam counts", "interval read counts"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("multicov",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/multicov.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "multicov", "-bed", str(inputs.get("input", "")), "-bams", *_as_list(inputs.get("bams"))]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        if inputs.get("reciprocal"):
            cmd.append("-r")
        if inputs.get("split"):
            cmd.append("-split")
        cmd.extend(["-q", str(inputs.get("q", 0))])
        if inputs.get("duplicate"):
            cmd.append("-D")
        if inputs.get("failed"):
            cmd.append("-F")
        if inputs.get("proper"):
            cmd.append("-p")
        _add_shell_redirect(cmd, f"{_out(inputs)}/multicov.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "multicov.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Sorted intervals to count over"}),
                "bams": ("BAM_LIST", {"description": "Sorted and indexed BAM files"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split or spliced alignments as separate intervals"}),
                "q": ("INT", {"default": 0, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "duplicate": ("BOOLEAN", {"default": False, "description": "Include duplicate reads"}),
                "failed": ("BOOLEAN", {"default": False, "description": "Include failed-QC reads"}),
                "proper": ("BOOLEAN", {"default": False, "description": "Only count proper pairs"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsNucNode(CommandNode):
    """Profile nucleotide content for intervals in a FASTA file."""

    NODE_ID = "bedtools_nucbed"
    DISPLAY_NAME = "BEDTools Nucleotide Content"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute nucleotide content, optional sequence output, and motif counts for FASTA intervals."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "nuc", "nucbed", "nucleotide content", "gc content"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("nucleotide_content",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/nuc.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "nuc"]
        if inputs.get("strand"):
            cmd.append("-s")
        if inputs.get("seq"):
            cmd.append("-seq")
        pattern = str(inputs.get("pattern", "")).strip()
        if pattern:
            cmd.extend(["-pattern", pattern])
            if inputs.get("ignore_case"):
                cmd.append("-C")
        cmd.extend(["-fi", str(inputs.get("fasta", "")), "-bed", str(inputs.get("input", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/nucleotide_content.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "nucleotide_content.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals whose nucleotide content is profiled"}),
                "fasta": ("FASTA", {"description": "Reference FASTA file"}),
            },
            "optional": {
                "strand": ("BOOLEAN", {"default": False, "description": "Profile sequence according to strand"}),
                "seq": ("BOOLEAN", {"default": False, "description": "Print the extracted sequence"}),
                "pattern": ("STRING", {"default": "", "description": "Sequence pattern to count"}),
                "ignore_case": ("BOOLEAN", {"default": False, "description": "Ignore case when matching pattern"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsRandomNode(CommandNode):
    """Generate random BED intervals across a genome."""

    NODE_ID = "bedtools_randombed"
    DISPLAY_NAME = "BEDTools Random"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Generate a random set of BED6 intervals across chromosomes defined by a genome file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "random", "randombed", "random intervals", "null intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("random_intervals",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/random.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "random"]
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-l", str(inputs.get("length", 100)), "-n", str(inputs.get("intervals", inputs.get("n", 1000000)))])
        _add_if_value(cmd, "-seed", inputs.get("seed"))
        _add_shell_redirect(cmd, f"{_out(inputs)}/random.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "random.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("TSV", {"description": "Genome chromosome sizes file"}),
            },
            "optional": {
                "length": ("INT", {"default": 100, "min": 1, "description": "Length of each random interval"}),
                "intervals": ("INT", {"default": 1000000, "min": 1, "description": "Number of intervals to generate"}),
                "seed": ("INT", {"default": "", "description": "Optional random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsShuffleNode(CommandNode):
    """Randomly redistribute interval locations across a genome."""

    NODE_ID = "bedtools_shufflebed"
    DISPLAY_NAME = "BEDTools Shuffle"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Shuffle feature locations across a genome, optionally constraining or excluding target regions."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "shuffle", "shufflebed", "randomize intervals", "permutation"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("shuffled",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/shuffle.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "shuffle"]
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("inputA", inputs.get("input", "")))])
        if inputs.get("bedpe"):
            cmd.append("-bedpe")
        _add_if_value(cmd, "-seed", inputs.get("seed"))
        if inputs.get("exclude"):
            cmd.extend(["-excl", str(inputs.get("exclude"))])
            _add_if_value(cmd, "-f", inputs.get("overlap"))
        if inputs.get("include"):
            cmd.extend(["-incl", str(inputs.get("include"))])
        if inputs.get("chrom"):
            cmd.append("-chrom")
        if inputs.get("chromfirst"):
            cmd.append("-chromFirst")
        if inputs.get("no_overlap"):
            cmd.append("-noOverlapping")
        if inputs.get("allow_beyond"):
            cmd.append("-allowBeyondChromEnd")
        cmd.extend(["-maxTries", str(inputs.get("maxtries", inputs.get("max_tries", 1000)))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/shuffled.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "shuffled.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to randomly redistribute"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file"}),
            },
            "optional": {
                "bedpe": ("BOOLEAN", {"default": False, "description": "Input is BEDPE format"}),
                "seed": ("INT", {"default": "", "description": "Optional random seed"}),
                "exclude": ("BED", {"description": "Regions where shuffled intervals must not be placed"}),
                "include": ("BED", {"description": "Regions where shuffled intervals must be placed"}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Maximum tolerated overlap with excluded regions"}),
                "chrom": ("BOOLEAN", {"default": False, "description": "Keep intervals on their original chromosome"}),
                "chromfirst": ("BOOLEAN", {"default": False, "description": "Choose chromosome uniformly before choosing position"}),
                "no_overlap": ("BOOLEAN", {"default": False, "description": "Do not allow shuffled intervals to overlap each other"}),
                "allow_beyond": ("BOOLEAN", {"default": False, "description": "Allow intervals to extend beyond chromosome end"}),
                "maxtries": ("INT", {"default": 1000, "min": 1, "description": "Maximum placement attempts per interval"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsUnionBedGraphNode(CommandNode):
    """Combine intervals from multiple BedGraph files."""

    NODE_ID = "bedtools_unionbedgraph"
    DISPLAY_NAME = "BEDTools Union BedGraph"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Merge multiple sorted BedGraph files into a common set of intervals with one value column per input."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "unionbedg", "unionbedgraph", "bedgraph union", "coverage tracks"]
    RETURN_TYPES = ("BEDGRAPH",)
    RETURN_NAMES = ("union_bedgraph",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/unionbedg.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("inputs", inputs.get("bedgraphs")))
        names = _as_list(inputs.get("names"))
        cmd = ["bedtools", "unionbedg"]
        if inputs.get("header"):
            cmd.append("-header")
        cmd.extend(["-filler", str(inputs.get("filler", "N/A"))])
        if inputs.get("empty"):
            cmd.append("-empty")
            _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", *files])
        if names:
            cmd.extend(["-names", *names])
        _add_shell_redirect(cmd, f"{_out(inputs)}/union.bedgraph")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "union.bedgraph", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": ("BEDGRAPH_LIST", {"description": "Sorted non-overlapping BedGraph files"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional column labels matching the input files"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print a header row"}),
                "filler": ("STRING", {"default": "N/A", "description": "Value for no coverage in a file"}),
                "empty": ("BOOLEAN", {"default": False, "description": "Report regions with zero coverage across all files"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file required when empty is enabled"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsClosestBedNode(CommandNode):
    """Find closest features, optionally reporting signed distances."""

    NODE_ID = "bedtools_closestbed"
    DISPLAY_NAME = "BEDTools ClosestBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Find closest or overlapping features in one or more B interval files for every interval in A."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "closest", "closestbed", "nearest interval", "nearest feature"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("closest",)
    REQUIRED_EXECUTABLES = ["closestBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["closestBed"]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        if inputs.get("distance"):
            cmd.append("-d")
        distance_mode = str(inputs.get("distance_mode", inputs.get("addition2_select", ""))).strip()
        if distance_mode:
            cmd.extend(["-D", distance_mode])
            if inputs.get("ignore_upstream"):
                cmd.append("-iu")
            if inputs.get("ignore_downstream"):
                cmd.append("-id")
            if inputs.get("first_upstream"):
                cmd.append("-fu")
            if inputs.get("first_downstream"):
                cmd.append("-fd")
        if inputs.get("ignore_overlaps", inputs.get("io")):
            cmd.append("-io")
        cmd.extend(["-mdb", str(inputs.get("mdb", "each")), "-t", str(inputs.get("ties", "all"))])
        _add_if_value(cmd, "-k", inputs.get("k"))
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", *_as_list(inputs.get("inputB"))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/closest.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "closest.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Query intervals"}),
                "inputB": ("BED_LIST", {"description": "One or more databases of intervals to search"}),
            },
            "optional": {
                "ties": ("STRING", {"default": "all", "options": ["all", "first", "last"], "description": "How equally close B records are handled"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "distance": ("BOOLEAN", {"default": False, "description": "Report distance as an extra column"}),
                "distance_mode": ("STRING", {"default": "", "options": ["", "ref", "a", "b"], "description": "Report signed upstream/downstream distances"}),
                "ignore_upstream": ("BOOLEAN", {"default": False, "description": "Ignore upstream features when using -D"}),
                "ignore_downstream": ("BOOLEAN", {"default": False, "description": "Ignore downstream features when using -D"}),
                "first_upstream": ("BOOLEAN", {"default": False, "description": "Choose first upstream feature when using -D"}),
                "first_downstream": ("BOOLEAN", {"default": False, "description": "Choose first downstream feature when using -D"}),
                "ignore_overlaps": ("BOOLEAN", {"default": False, "description": "Ignore B features that overlap A"}),
                "mdb": ("STRING", {"default": "each", "options": ["each", "all"], "description": "Resolve closest hits per B file or across all B files"}),
                "k": ("INT", {"default": "", "min": 1, "description": "Report the k closest hits"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsIntersectBedNode(CommandNode):
    """Find interval intersections with Galaxy wrapper-compatible options."""

    NODE_ID = "bedtools_intersectbed"
    DISPLAY_NAME = "BEDTools Intersect Intervals"
    REQUIRED_CONDA_PACKAGES = ["bedtools", "samtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Find overlaps between A and one or more B BED-like or BAM files with configurable reporting modes."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "intersect", "intersectbed", "overlap intervals", "feature intersection"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("intersect",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "intersect", "-a", str(inputs.get("inputA", "")), "-b", *_as_list(inputs.get("inputB"))]
        names = _as_list(inputs.get("names"))
        if names:
            cmd.extend(["-names", *names])
        if inputs.get("split"):
            cmd.append("-split")
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        if inputs.get("reciprocal"):
            cmd.append("-r")
        else:
            _add_if_value(cmd, "-F", inputs.get("overlap_b", inputs.get("overlapB")))
            if inputs.get("either_fraction", inputs.get("disjoint")):
                cmd.append("-e")
        if inputs.get("invert"):
            cmd.append("-v")
        if inputs.get("once"):
            cmd.append("-u")
        if inputs.get("header"):
            cmd.append("-header")
        for mode in _as_list(inputs.get("overlap_mode")):
            if mode and mode != "None":
                cmd.append(mode)
        if inputs.get("sorted"):
            cmd.append("-sorted")
            _bedtools_add_genome(cmd, inputs)
        if inputs.get("bed"):
            cmd.append("-bed")
        if inputs.get("count"):
            cmd.append("-c")
        _add_shell_redirect(cmd, f"{_out(inputs)}/intersect.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "intersect.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("FILE", {"description": "A file: BED-like, BAM, VCF, or GFF"}),
                "inputB": ("FILE_LIST", {"description": "One or more B files to intersect with A"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional labels for B files"}),
                "overlap_mode": ("STRING_LIST", {"description": "Reporting flags such as -wa, -wb, -wo, -wao, or -loj"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM alignments as distinct intervals"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "either_fraction": ("BOOLEAN", {"default": False, "description": "Allow either A or B overlap fraction to be satisfied"}),
                "invert": ("BOOLEAN", {"default": False, "description": "Report A records with no overlaps"}),
                "once": ("BOOLEAN", {"default": False, "description": "Report each A record once if any overlap exists"}),
                "count": ("BOOLEAN", {"default": False, "description": "Report overlap count for each A record"}),
                "bed": ("BOOLEAN", {"default": False, "description": "When A is BAM, write BED output"}),
                "sorted": ("BOOLEAN", {"default": False, "description": "Use sorted input algorithm"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file for sorted mode"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the A file header before results"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsBedToIgvNode(CommandNode):
    """Create IGV batch scripts for interval snapshots."""

    NODE_ID = "bedtools_bedtoigv"
    DISPLAY_NAME = "BEDTools BED to IGV"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create an IGV batch script that takes snapshots at intervals from a BED-like file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "bedtoigv", "bedToIgv", "IGV snapshots", "batch script"]
    RETURN_TYPES = ("TEXT",)
    RETURN_NAMES = ("igv_batch_script",)
    REQUIRED_EXECUTABLES = ["bedToIgv"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/blob/main/tools/bedtools/bedToIgv.xml"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedToIgv", "-i", str(inputs.get("input", ""))]
        _add_if_value(cmd, "-sort", inputs.get("sort"))
        if inputs.get("clps"):
            cmd.append("-clps")
        if inputs.get("name"):
            cmd.append("-name")
        cmd.extend(["-slop", str(inputs.get("slop", 0)), "-img", str(inputs.get("img", "png"))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/igv_batch_script.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "igv_batch_script.txt", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "BED-like interval file to convert into IGV snapshot commands"}),
            },
            "optional": {
                "sort": ("STRING", {"default": "", "options": ["", "base", "position", "strand", "quality", "sample", "readGroup"], "description": "BAM sorting mode to apply before snapshots"}),
                "clps": ("BOOLEAN", {"default": False, "description": "Collapse aligned reads before each snapshot"}),
                "name": ("BOOLEAN", {"default": False, "description": "Use column 4 interval names as image filenames"}),
                "slop": ("INT", {"default": 0, "min": 0, "description": "Flanking base pairs on each side of each interval"}),
                "img": ("STRING", {"default": "png", "options": ["png", "eps", "svg"], "description": "Snapshot image format"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsLinksNode(CommandNode):
    """Create UCSC Genome Browser links for each interval."""

    NODE_ID = "bedtools_links"
    DISPLAY_NAME = "BEDTools LinksBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create an HTML page with UCSC Genome Browser links for intervals in a BED-like file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "links", "linksbed", "linksbed ucsc", "UCSC links", "genome browser"]
    RETURN_TYPES = ("HTML",)
    RETURN_NAMES = ("links_html",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/links.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "links",
            "-base",
            str(inputs.get("basename", "http://genome.ucsc.edu")),
            "-org",
            str(inputs.get("org", "human")),
            "-db",
            str(inputs.get("db", "hg19")),
            "-i",
            str(inputs.get("input", "")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/links.html")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "links.html", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "BED-like interval file to link into a genome browser"}),
            },
            "optional": {
                "basename": ("STRING", {"default": "http://genome.ucsc.edu", "description": "Base URL for the UCSC Genome Browser instance"}),
                "org": ("STRING", {"default": "human", "description": "UCSC organism name"}),
                "db": ("STRING", {"default": "hg19", "description": "UCSC genome build"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsOverlapBedNode(CommandNode):
    """Compute overlap or distance between coordinate pairs on each row."""

    NODE_ID = "bedtools_overlapbed"
    DISPLAY_NAME = "BEDTools OverlapBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute the amount of overlap or distance between two feature coordinate ranges on each input row."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "overlap", "overlapbed", "overlapbed custom score", "overlap distance", "custom overlap score"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("overlap",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/overlap.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cols = inputs.get("cols", "")
        if isinstance(cols, (list, tuple)):
            cols = ",".join(str(col) for col in cols)
        cmd = ["bedtools", "overlap", "-i", str(inputs.get("input", "")), "-cols", str(cols)]
        _add_shell_redirect(cmd, f"{_out(inputs)}/overlap.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "overlap.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Input rows containing two coordinate ranges"}),
                "cols": ("STRING", {"default": "", "description": "Comma-separated 1-based columns: start1,end1,start2,end2"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BEDToolsTagBedNode(CommandNode):
    """Tag BAM alignments using overlapping interval annotations."""

    NODE_ID = "bedtools_tagbed"
    DISPLAY_NAME = "BEDTools TagBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Annotate BAM alignments with tags populated from one or more overlapping interval files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bedtools", "tag", "tagbed", "tagbed bam tags", "BAM tags", "alignment annotation"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("tagged_bam",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/tag.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "tag", "-i", str(inputs.get("inputA", "")), "-files", *_as_list(inputs.get("inputB"))]
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        cmd.extend(["-tag", str(inputs.get("tag", "YB"))])
        for field_flag in str(inputs.get("field", "-labels")).split():
            if field_flag:
                cmd.append(field_flag)
        _add_shell_redirect(cmd, f"{_out(inputs)}/tagged.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "tagged.bam", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BAM", {"description": "BAM alignments to annotate"}),
                "inputB": ("FILE_LIST", {"description": "BED-like annotation files used to populate tags"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of each alignment"}),
                "tag": ("STRING", {"default": "YB", "description": "BAM tag name to populate"}),
                "field": ("STRING", {"default": "-labels", "options": ["-labels", "-scores", "-names", "-labels -intervals"], "description": "Annotation field used as tag value"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsConcatNode(CommandNode):
    """Concatenate or combine VCF/BCF files with matching sample columns."""

    NODE_ID = "bcftools_concat"
    DISPLAY_NAME = "BCFtools Concat"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Concatenate chromosome shards or combine sorted VCF/BCF files with compatible sample columns."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "concat", "concatenate vcf", "combine vcf", "ligate phased vcfs"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("concat_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#concat"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "concat"]
        if inputs.get("naive"):
            cmd.append("--naive")
        else:
            if inputs.get("allow_overlaps"):
                cmd.append("--allow-overlaps")
                _add_if_value(cmd, "--rm-dups", inputs.get("rm_dups"))
            if inputs.get("ligate"):
                cmd.append("--ligate")
            ligate_mode = str(inputs.get("ligate_mode", "")).strip()
            if ligate_mode:
                cmd.append(ligate_mode)
        if inputs.get("compact_ps"):
            cmd.append("--compact-PS")
        _add_if_value(cmd, "--min-PQ", inputs.get("min_pq"))
        _add_if_value(cmd, "--regions", inputs.get("regions"))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, "--threads", inputs.get("threads"))
        cmd.extend(_as_list(inputs.get("input_files", inputs.get("inputs"))))
        _add_shell_redirect(cmd, f"{_out(inputs)}/concat{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"concat{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": ("VCF_LIST", {"description": "Sorted VCF/BCF files with compatible sample columns"}),
            },
            "optional": {
                "naive": ("BOOLEAN", {"default": False, "description": "Concatenate without recompression or header checks"}),
                "allow_overlaps": ("BOOLEAN", {"default": False, "description": "Allow overlapping positions between adjacent files"}),
                "rm_dups": ("STRING", {"default": "", "options": ["", "snps", "indels", "both", "all", "none"], "description": "Remove duplicate records when overlaps are allowed"}),
                "ligate": ("BOOLEAN", {"default": False, "description": "Ligate phased VCF chunks"}),
                "ligate_mode": ("STRING", {"default": "", "options": ["", "--ligate-warn", "--ligate-force"], "description": "Fine control of ligate behavior"}),
                "compact_ps": ("BOOLEAN", {"default": False, "description": "Emit phase-set tag only at phase block starts"}),
                "min_pq": ("INT", {"default": "", "min": 0, "description": "Break phase set below this phasing quality"}),
                "regions": ("STRING", {"default": "", "description": "Restrict output to regions"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsConsensusNode(CommandNode):
    """Apply VCF variants to a reference FASTA to build a consensus sequence."""

    NODE_ID = "bcftools_consensus"
    DISPLAY_NAME = "BCFtools Consensus"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Create a consensus FASTA by applying VCF/BCF variants, masks, and sample or haplotype choices to a reference."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "consensus", "consensus fasta", "apply variants", "haplotype consensus"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("consensus_fasta",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#consensus"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "consensus", "--fasta-ref", str(inputs.get("reference", inputs.get("fasta_ref", "")))]
        mode = str(inputs.get("mode", "genotype_iupac"))
        if mode == "first_alt":
            cmd.extend(["-s", "-"])
        elif mode == "all_iupac":
            cmd.extend(["-I", "-s", "-"])
        elif mode == "haplotype":
            cmd.extend(["-H", str(inputs.get("haplotype", "1"))])
            _add_if_value(cmd, "--sample", inputs.get("sample"))
        else:
            _add_if_value(cmd, "--samples", inputs.get("samples"))

        masks = _as_list(inputs.get("mask"))
        mask_with_value = inputs.get("mask_with")
        if isinstance(mask_with_value, str) and "," in mask_with_value:
            mask_with = [part.strip() for part in mask_with_value.split(",") if part.strip()]
        else:
            mask_with = _as_list(mask_with_value)
        for index, mask in enumerate(masks):
            cmd.extend(["--mask", mask])
            if index < len(mask_with):
                cmd.extend(["--mask-with", mask_with[index]])
            elif len(mask_with) == 1:
                cmd.extend(["--mask-with", mask_with[0]])
        _add_if_value(cmd, "--absent", inputs.get("absent"))
        _add_if_value(cmd, "--mark-del", inputs.get("mark_del"))
        _add_if_value(cmd, "--mark-ins", inputs.get("mark_ins"))
        _add_if_value(cmd, "--mark-snv", inputs.get("mark_snv"))
        _add_if_value(cmd, "--include", inputs.get("include"))
        _add_if_value(cmd, "--exclude", inputs.get("exclude"))
        if inputs.get("chain"):
            cmd.extend(["--chain", f"{_out(inputs)}/consensus.chain"])
        cmd.extend(["--output", f"{_out(inputs)}/consensus.fa", str(inputs.get("input_file", ""))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        outputs = [_bcftools_common_output(cls.NODE_ID, "consensus.fa", output_dir)]
        if inputs.get("chain"):
            outputs.append(_bcftools_common_output(cls.NODE_ID, "consensus.chain", output_dir))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF variants to apply"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "genotype_iupac", "options": ["first_alt", "all_iupac", "genotype_iupac", "haplotype"], "description": "Galaxy consensus building mode"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples for genotype-IUPAC mode"}),
                "sample": ("STRING", {"default": "", "description": "Single sample for haplotype mode"}),
                "haplotype": ("STRING", {"default": "1", "description": "Haplotype selector such as 1, 2, 1pIu, R, A, LR, LA, SR, or SA"}),
                "mask": ("BED_LIST", {"description": "Regions to mask before applying variants"}),
                "mask_with": ("STRING_LIST", {"description": "Mask replacement values matching mask files"}),
                "absent": ("STRING", {"default": "", "description": "Character for reference bases absent from VCF"}),
                "mark_del": ("STRING", {"default": "", "description": "Character for deleted reference bases"}),
                "mark_ins": ("STRING", {"default": "", "description": "Insertion marking mode or character"}),
                "mark_snv": ("STRING", {"default": "", "description": "SNV marking mode or character"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "chain": ("BOOLEAN", {"default": False, "description": "Write a liftover chain file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsQueryNode(CommandNode):
    """Extract fields from one or more VCF/BCF files in a user-defined format."""

    NODE_ID = "bcftools_query"
    DISPLAY_NAME = "BCFtools Query"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Transform VCF/BCF records into tabular or custom text output using bcftools query format strings."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "query", "extract fields", "format vcf", "vcf to tsv"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("query_table",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#query"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "query", "--format", str(inputs.get("format", "%CHROM\\t%POS\\t%REF\\t%ALT\\n"))]
        if inputs.get("allow_undef_tags"):
            cmd.append("--allow-undef-tags")
        if inputs.get("print_header"):
            cmd.append("--print-header")
        _bcftools_add_restrict(cmd, inputs)
        cmd.extend(_as_list(inputs.get("input_files", inputs.get("input_file"))))
        _add_shell_redirect(cmd, f"{_out(inputs)}/query.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "query.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": ("VCF_LIST", {"description": "One or more VCF/BCF files"}),
                "format": ("STRING", {"default": "%CHROM\\t%POS\\t%REF\\t%ALT\\n", "description": "bcftools query format string"}),
            },
            "optional": {
                "allow_undef_tags": ("BOOLEAN", {"default": False, "description": "Print . for undefined tags"}),
                "print_header": ("BOOLEAN", {"default": False, "description": "Print a header line"}),
                "collapse": ("STRING", {"default": "", "description": "Compatibility collapse mode"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsQueryListSamplesNode(CommandNode):
    """List sample names from a VCF/BCF file."""

    NODE_ID = "bcftools_query_list_samples"
    DISPLAY_NAME = "BCFtools List Samples"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "List sample names from a VCF/BCF file using bcftools query --list-samples."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "query", "list samples", "sample names", "vcf samples"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("samples",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#query"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "query", "--list-samples", str(inputs.get("input_file", ""))]
        _add_shell_redirect(cmd, f"{_out(inputs)}/samples.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "samples.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsReheaderNode(CommandNode):
    """Modify VCF/BCF headers and sample names."""

    NODE_ID = "bcftools_reheader"
    DISPLAY_NAME = "BCFtools Reheader"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Replace a VCF/BCF header and optionally rename samples using a sample mapping file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "reheader", "rename samples", "change header", "sample names"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("reheadered_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#reheader"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "reheader"]
        _add_if_value(cmd, "--header", inputs.get("header"))
        _add_if_value(cmd, "--samples", inputs.get("sample_file", inputs.get("samples_file")))
        if inputs.get("sample_lines"):
            cmd.extend(["--samples", str(inputs.get("sample_lines"))])
        cmd.append(str(inputs.get("input_file", "")))
        cmd.extend(["|", "bcftools", "view"])
        _bcftools_add_output_type(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/reheadered{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"reheadered{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file"}),
            },
            "optional": {
                "header": ("VCF", {"description": "Replacement VCF header"}),
                "sample_file": ("TSV", {"description": "Sample names or old/new sample mapping"}),
                "sample_lines": ("STRING", {"default": "", "description": "Inline sample renaming text"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsViewNode(CommandNode):
    """Convert, subset, and filter VCF/BCF files."""

    NODE_ID = "bcftools_view"
    DISPLAY_NAME = "BCFtools View"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Subset samples, filter variants, and convert VCF/BCF files with bcftools view."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "view", "subset vcf", "filter vcf", "vcf conversion"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("view_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#view"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "view"]
        if inputs.get("trim_alt_alleles"):
            cmd.append("--trim-alt-alleles")
        if inputs.get("no_update"):
            cmd.append("--no-update")
        _add_if_value(cmd, "--samples", inputs.get("samples"))
        if inputs.get("force_samples"):
            cmd.append("--force-samples")
        _add_if_value(cmd, "--min-ac", inputs.get("min_ac"))
        _add_if_value(cmd, "--max-ac", inputs.get("max_ac"))
        _add_if_value(cmd, "--genotype", inputs.get("select_genotype"))
        known_or_novel = str(inputs.get("known_or_novel", "")).strip()
        if known_or_novel:
            cmd.append(known_or_novel)
        _add_if_value(cmd, "--min-alleles", inputs.get("min_alleles"))
        _add_if_value(cmd, "--max-alleles", inputs.get("max_alleles"))
        phased = str(inputs.get("phased", "")).strip()
        if phased:
            cmd.append(phased)
        _add_if_value(cmd, "--min-af", inputs.get("min_af"))
        _add_if_value(cmd, "--max-af", inputs.get("max_af"))
        uncalled = str(inputs.get("uncalled", "")).strip()
        if uncalled:
            cmd.append(uncalled)
        types = _as_list(inputs.get("types"))
        if types:
            cmd.extend(["--types", ",".join(types)])
        exclude_types = _as_list(inputs.get("exclude_types"))
        if exclude_types:
            cmd.extend(["--exclude-types", ",".join(exclude_types)])
        private = str(inputs.get("private", "")).strip()
        if private:
            cmd.append(private)
        if inputs.get("drop_genotypes"):
            cmd.append("--drop-genotypes")
        header = str(inputs.get("header", "")).strip()
        if header:
            cmd.append(header)
        _add_if_value(cmd, "--compression-level", inputs.get("compression_level"))
        restrict_inputs = {**inputs, "_skip_samples_restrict": True}
        _bcftools_add_restrict(cmd, restrict_inputs)
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, "--threads", inputs.get("threads"))
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/view{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"view{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file"}),
            },
            "optional": {
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples"}),
                "force_samples": ("BOOLEAN", {"default": False, "description": "Only warn about unknown subset samples"}),
                "no_update": ("BOOLEAN", {"default": False, "description": "Do not recalculate INFO AC/AN after subsetting"}),
                "trim_alt_alleles": ("BOOLEAN", {"default": False, "description": "Trim alternate alleles not seen in subset"}),
                "min_ac": ("INT", {"default": "", "description": "Minimum allele count"}),
                "max_ac": ("INT", {"default": "", "description": "Maximum allele count"}),
                "select_genotype": ("STRING", {"default": "", "options": ["", "hom", "het", "miss", "^hom", "^het", "^miss"], "description": "Genotype filter"}),
                "types": ("STRING_LIST", {"description": "Variant types to include"}),
                "exclude_types": ("STRING_LIST", {"description": "Variant types to exclude"}),
                "known_or_novel": ("STRING", {"default": "", "options": ["", "--novel", "--known"], "description": "Filter known or novel IDs"}),
                "min_alleles": ("INT", {"default": "", "description": "Minimum number of REF/ALT alleles"}),
                "max_alleles": ("INT", {"default": "", "description": "Maximum number of REF/ALT alleles"}),
                "phased": ("STRING", {"default": "", "options": ["", "--phased", "--exclude-phased"], "description": "Phasing filter"}),
                "min_af": ("FLOAT", {"default": "", "description": "Minimum allele frequency"}),
                "max_af": ("FLOAT", {"default": "", "description": "Maximum allele frequency"}),
                "uncalled": ("STRING", {"default": "", "options": ["", "--uncalled", "--exclude-uncalled"], "description": "Uncalled genotype filter"}),
                "private": ("STRING", {"default": "", "options": ["", "--private", "--exclude-private"], "description": "Private allele filter"}),
                "drop_genotypes": ("BOOLEAN", {"default": False, "description": "Drop genotype columns"}),
                "header": ("STRING", {"default": "", "options": ["", "--no-header", "--header-only"], "description": "Header output mode"}),
                "compression_level": ("INT", {"default": "", "min": 0, "max": 9, "description": "Compression level"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsMergeNode(CommandNode):
    """Merge VCF/BCF files from non-overlapping sample sets."""

    NODE_ID = "bcftools_merge"
    DISPLAY_NAME = "BCFtools Merge"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Merge multiple VCF/BCF files from non-overlapping sample sets into one multi-sample file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "merge", "merge samples", "multi-sample vcf", "combine cohorts"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("merged_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#merge"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "merge"]
        if inputs.get("print_header"):
            cmd.append("--print-header")
        _add_if_value(cmd, "--use-header", inputs.get("use_header"))
        if inputs.get("force_samples"):
            cmd.append("--force-samples")
        _add_if_value(cmd, "--info-rules", inputs.get("info_rules"))
        _add_if_value(cmd, "--merge", inputs.get("merge"))
        if inputs.get("no_index"):
            cmd.append("--no-index")
        _bcftools_add_apply_filters(cmd, inputs)
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, "--include", inputs.get("include"))
        _add_if_value(cmd, "--exclude", inputs.get("exclude"))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, "--threads", inputs.get("threads"))
        cmd.extend(_as_list(inputs.get("input_files", inputs.get("inputs"))))
        _add_shell_redirect(cmd, f"{_out(inputs)}/merged{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"merged{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": ("VCF_LIST", {"description": "VCF/BCF files from non-overlapping sample sets"}),
            },
            "optional": {
                "force_samples": ("BOOLEAN", {"default": False, "description": "Resolve duplicate sample names"}),
                "info_rules": ("STRING", {"default": "", "description": "INFO merge rules such as DP:sum,AD:join"}),
                "merge": ("STRING", {"default": "", "options": ["", "none", "snps", "indels", "both", "all", "id"], "description": "Allow multiallelic records for the selected class"}),
                "no_index": ("BOOLEAN", {"default": False, "description": "Allow merging unindexed files"}),
                "print_header": ("BOOLEAN", {"default": False, "description": "Print only the merged header"}),
                "use_header": ("VCF", {"description": "Header to use for the merged output"}),
                "apply_filters": ("STRING", {"default": "", "description": "Skip sites whose FILTER does not match these terms"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsIsecNode(CommandNode):
    """Create intersections, unions, and complements of VCF/BCF files."""

    NODE_ID = "bcftools_isec"
    DISPLAY_NAME = "BCFtools Isec"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Create intersections, unions, and complements across multiple VCF/BCF files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "isec", "variant intersection", "vcf union", "vcf complement"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("isec_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#isec"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "isec"]
        if inputs.get("complement"):
            cmd.append("--complement")
        _add_if_value(cmd, "--nfiles", inputs.get("nfiles"))
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, "--collapse", inputs.get("collapse"))
        _bcftools_add_apply_filters(cmd, inputs)
        _add_if_value(cmd, "--include", inputs.get("include"))
        _add_if_value(cmd, "--exclude", inputs.get("exclude"))
        _bcftools_add_output_type(cmd, inputs)
        _add_if_value(cmd, "--threads", inputs.get("threads"))
        cmd.extend(_as_list(inputs.get("input_files", inputs.get("inputs"))))
        _add_shell_redirect(cmd, f"{_out(inputs)}/isec{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"isec{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": ("VCF_LIST", {"description": "VCF/BCF files to intersect or compare"}),
            },
            "optional": {
                "nfiles": ("STRING", {"default": "", "description": "Output positions present in =N, +N, -N, or ~bitmask files"}),
                "complement": ("BOOLEAN", {"default": False, "description": "Output positions present only in the first file"}),
                "collapse": ("STRING", {"default": "", "options": ["", "snps", "indels", "both", "all", "some", "none", "id"], "description": "Compatibility mode for records at duplicate positions"}),
                "apply_filters": ("STRING", {"default": "", "description": "Skip sites whose FILTER does not match these terms"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsGTcheckNode(CommandNode):
    """Check sample identity and genotype concordance."""

    NODE_ID = "bcftools_gtcheck"
    DISPLAY_NAME = "BCFtools GTcheck"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Check sample identity by comparing genotypes within or between VCF/BCF files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "gtcheck", "sample identity", "genotype concordance", "discordance"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("gtcheck_table",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#gtcheck"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "gtcheck"]
        _add_if_value(cmd, "--genotypes", inputs.get("genotypes"))
        if inputs.get("all_sites"):
            cmd.append("--all-sites")
        if inputs.get("homs_only"):
            cmd.append("--homs-only")
        _add_if_value(cmd, "--plot", inputs.get("plot"))
        _add_if_value(cmd, "--query-sample", inputs.get("query_sample"))
        _add_if_value(cmd, "--target-sample", inputs.get("target_sample"))
        _bcftools_add_region_targets(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/gtcheck.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "gtcheck.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "Query VCF/BCF file"}),
            },
            "optional": {
                "genotypes": ("VCF", {"description": "Genotypes to compare against"}),
                "target_sample": ("STRING", {"default": "", "description": "Target sample in the genotype file"}),
                "all_sites": ("BOOLEAN", {"default": False, "description": "Output comparison for all sites"}),
                "homs_only": ("BOOLEAN", {"default": False, "description": "Use homozygous genotypes only"}),
                "query_sample": ("STRING", {"default": "", "description": "Query sample"}),
                "plot": ("STRING", {"default": "", "description": "Plot prefix name"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsConvertToVcfNode(CommandNode):
    """Convert gVCF, TSV, GEN/SAMPLE, or HAP/SAMPLE data to VCF/BCF."""

    NODE_ID = "bcftools_convert_to_vcf"
    DISPLAY_NAME = "BCFtools Convert to VCF"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Convert gVCF, tabular genotype data, and IMPUTE2/SHAPEIT files into VCF/BCF."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "convert", "gvcf to vcf", "tsv to vcf", "shapeit to vcf"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("converted_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#convert"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "convert"]
        _bcftools_add_output_type(cmd, inputs)
        mode = str(inputs.get("convert_from", "tsv"))
        if mode == "gen_sample":
            cmd.extend(["--gensample2vcf", f"{inputs.get('input_file', '')},{inputs.get('input_sample', '')}"])
        elif mode == "hap_sample":
            cmd.extend(["--hapsample2vcf", f"{inputs.get('input_file', '')},{inputs.get('input_sample', '')}"])
        elif mode == "hap_legend_sample":
            cmd.extend(
                [
                    "--haplegendsample2vcf",
                    f"{inputs.get('input_file', '')},{inputs.get('input_legend', '')},{inputs.get('input_sample', '')}",
                ]
            )
        elif mode == "gvcf":
            _add_if_value(cmd, "--fasta-ref", inputs.get("reference"))
            cmd.extend(["--gvcf2vcf", str(inputs.get("input_file", ""))])
        else:
            _add_if_value(cmd, "--fasta-ref", inputs.get("reference"))
            _add_if_value(cmd, "--samples", inputs.get("samples"))
            _add_if_value(cmd, "--columns", inputs.get("columns"))
            cmd.extend(["--tsv2vcf", str(inputs.get("input_file", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/converted{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"converted{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FILE", {"description": "Input gVCF, TSV, GEN, HAP, or related file"}),
            },
            "optional": {
                "convert_from": ("STRING", {"default": "tsv", "options": ["tsv", "gvcf", "gen_sample", "hap_sample", "hap_legend_sample"], "description": "Galaxy conversion source mode"}),
                "input_sample": ("TSV", {"description": "Sample file for GEN/HAP input"}),
                "input_legend": ("TSV", {"description": "Legend file for HAP/LEGEND/SAMPLE input"}),
                "reference": ("FASTA", {"description": "Reference FASTA for gVCF or TSV conversion"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated sample names for TSV conversion"}),
                "columns": ("STRING", {"default": "", "description": "Column mapping for TSV conversion"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsConvertFromVcfNode(CommandNode):
    """Convert VCF/BCF to IMPUTE2 or SHAPEIT tabular formats."""

    NODE_ID = "bcftools_convert_from_vcf"
    DISPLAY_NAME = "BCFtools Convert from VCF"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Convert VCF/BCF records to GEN/SAMPLE, HAP/SAMPLE, or HAP/LEGEND/SAMPLE files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "convert", "vcf to shapeit", "vcf to impute2", "hap legend sample"]
    RETURN_TYPES = ("TSV", "TSV", "TSV")
    RETURN_NAMES = ("converted_variants", "converted_legend", "converted_samples")
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#convert"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["bcftools", "convert"]
        mode = str(inputs.get("convert_to", "gen_sample"))
        if mode == "gen_sample":
            _add_if_value(cmd, "--tag", inputs.get("tag", "GT"))
            if inputs.get("convert_3n6"):
                cmd.append("--3N6")
            if inputs.get("vcf_ids"):
                cmd.append("--vcf-ids")
            cmd.extend(["--gensample", f"{out}/converted.gen,{out}/converted.samples"])
        elif mode == "hap_sample":
            if inputs.get("vcf_ids"):
                cmd.append("--vcf-ids")
            if inputs.get("haploid2diploid"):
                cmd.append("--haploid2diploid")
            cmd.extend(["--hapsample", f"{out}/converted.hap,{out}/converted.samples"])
        else:
            if inputs.get("vcf_ids"):
                cmd.append("--vcf-ids")
            if inputs.get("haploid2diploid"):
                cmd.append("--haploid2diploid")
            cmd.extend(["--haplegendsample", f"{out}/converted.hap,{out}/converted.legend,{out}/converted.samples"])
        _add_if_value(cmd, "--sex", inputs.get("sex_file", inputs.get("sex_info_file")))
        if inputs.get("keep_duplicates"):
            cmd.append("--keep-duplicates")
        _add_if_value(cmd, "--include", inputs.get("include"))
        _add_if_value(cmd, "--exclude", inputs.get("exclude"))
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, "--samples", inputs.get("samples"))
        cmd.extend([str(inputs.get("input_file", "")), "."])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return _bcftools_convert_from_outputs(inputs, output_dir)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file to convert"}),
            },
            "optional": {
                "convert_to": ("STRING", {"default": "gen_sample", "options": ["gen_sample", "hap_sample", "hap_legend_sample"], "description": "Galaxy conversion target mode"}),
                "tag": ("STRING", {"default": "GT", "options": ["GT", "PL", "GP"], "description": "Tag to use for GEN/SAMPLE output"}),
                "convert_3n6": ("BOOLEAN", {"default": False, "description": "Use 3N+6 GEN format"}),
                "vcf_ids": ("BOOLEAN", {"default": False, "description": "Output VCF IDs instead of CHROM:POS_REF_ALT"}),
                "haploid2diploid": ("BOOLEAN", {"default": False, "description": "Convert haploid genotypes to diploid homozygotes"}),
                "sex_file": ("TSV", {"description": "Per-sample sex designation file"}),
                "keep_duplicates": ("BOOLEAN", {"default": False, "description": "Keep all multiallelic variants"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsCNVNode(CommandNode):
    """Call copy number variation from VCF BAF and LRR intensity fields."""

    NODE_ID = "bcftools_cnv"
    DISPLAY_NAME = "BCFtools CNV"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib", "matplotlib"]
    CATEGORY = "variant"
    DESCRIPTION = "Call copy number variation from VCF B-allele frequency and Log R Ratio intensity annotations."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "cnv", "copy number variation", "BAF", "LRR"]
    RETURN_TYPES = ("TSV", "TSV", "HTML")
    RETURN_NAMES = ("cnv_calls", "summary", "plots")
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#cnv"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True
    CNV_POSTPROCESS_SCRIPT = """
from pathlib import Path
import base64
import shutil
import sys

tmp = Path(sys.argv[1])
cn_out = Path(sys.argv[2])
summary_out = Path(sys.argv[3])
plots_out = Path(sys.argv[4])
include_plots = sys.argv[5] == "1"

def move_first(patterns, destination):
    for pattern in patterns:
        matches = sorted(tmp.glob(pattern))
        if matches:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(matches[0]), destination)
            return
    raise FileNotFoundError(f"Missing bcftools cnv output matching {patterns!r}")

move_first(["cn.*.tab"], cn_out)
move_first(["summary.tab", "summary.*.tab"], summary_out)
plots_out.parent.mkdir(parents=True, exist_ok=True)
with plots_out.open("w", encoding="utf-8") as handle:
    handle.write("<html><body>")
    if include_plots:
        for plot in sorted(tmp.glob("*.png")):
            encoded = base64.b64encode(plot.read_bytes()).decode("ascii")
            handle.write('<div><img src="data:image/png;base64,')
            handle.write(encoded)
            handle.write('" /></div><hr>')
    handle.write("</body></html>")
""".strip()

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cnv_tmp = f"{out}/cnv_tmp"
        cmd = ["bcftools", "cnv", "--output-dir", cnv_tmp]
        _add_if_value(cmd, "-c", inputs.get("control_sample"))
        _add_if_value(cmd, "-s", inputs.get("query_sample", inputs.get("sample")))
        _bcftools_add_af_file(cmd, inputs)
        plot_threshold = inputs.get("plot_threshold")
        plot_mode = inputs.get("generate_plots")
        include_plots = bool(plot_mode)
        if isinstance(plot_mode, str):
            include_plots = plot_mode.lower() not in ("", "0", "false", "none", "no")
        if plot_threshold is not None and str(plot_threshold) != "":
            include_plots = True
        if include_plots:
            cmd.extend(["--plot-threshold", str(plot_threshold if plot_threshold is not None and str(plot_threshold) != "" else 0)])
        if inputs.get("aberrant_query") is not None or inputs.get("aberrant_control") is not None:
            cmd.extend(["--aberrant", f"{inputs.get('aberrant_query', '')},{inputs.get('aberrant_control', '')}"])
        _add_if_value(cmd, "--optimize", inputs.get("optimize"))
        _add_if_value(cmd, "--BAF-weight", inputs.get("baf_weight"))
        if inputs.get("baf_dev_query") is not None or inputs.get("baf_dev_control") is not None:
            cmd.extend(["--BAF-dev", f"{inputs.get('baf_dev_query', '')},{inputs.get('baf_dev_control', '')}"])
        _add_if_value(cmd, "--LRR-weight", inputs.get("lrr_weight"))
        if inputs.get("lrr_dev_query") is not None or inputs.get("lrr_dev_control") is not None:
            cmd.extend(["--LRR-dev", f"{inputs.get('lrr_dev_query', '')},{inputs.get('lrr_dev_control', '')}"])
        _add_if_value(cmd, "--LRR-smooth-win", inputs.get("lrr_smooth_win"))
        _add_if_value(cmd, "--same-prob", inputs.get("same_prob"))
        _add_if_value(cmd, "--err-prob", inputs.get("err_prob"))
        _add_if_value(cmd, "--xy-prob", inputs.get("xy_prob"))
        _bcftools_add_region_targets(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        cmd.extend(
            [
                "&&",
                "python",
                "-c",
                cls.CNV_POSTPROCESS_SCRIPT,
                cnv_tmp,
                f"{out}/cnv.tab",
                f"{out}/summary.tab",
                f"{out}/plots.html",
                "1" if include_plots else "0",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [
            _bcftools_common_output(cls.NODE_ID, "cnv.tab", output_dir),
            _bcftools_common_output(cls.NODE_ID, "summary.tab", output_dir),
            _bcftools_common_output(cls.NODE_ID, "plots.html", output_dir),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF with BAF and LRR intensity annotations"}),
                "query_sample": ("STRING", {"description": "Sample to call for copy number variation"}),
            },
            "optional": {
                "control_sample": ("STRING", {"default": "", "description": "Optional control sample for pairwise calling"}),
                "AF_file": ("TSV", {"description": "Allele frequency table with CHR, POS, REF, ALT, and AF columns"}),
                "plot_threshold": ("FLOAT", {"default": "", "description": "Plot only chromosomes above this CNV quality threshold"}),
                "generate_plots": ("BOOLEAN", {"default": False, "description": "Plan an HTML plot summary output"}),
                "aberrant_query": ("FLOAT", {"default": "", "description": "Aberrant copy-number prior for the query sample"}),
                "aberrant_control": ("FLOAT", {"default": "", "description": "Aberrant copy-number prior for the control sample"}),
                "optimize": ("FLOAT", {"default": "", "description": "Adjust purity estimates using this step size"}),
                "baf_weight": ("FLOAT", {"default": "", "description": "Relative weight of BAF evidence"}),
                "baf_dev_query": ("FLOAT", {"default": "", "description": "Expected query BAF deviation"}),
                "baf_dev_control": ("FLOAT", {"default": "", "description": "Expected control BAF deviation"}),
                "lrr_weight": ("FLOAT", {"default": "", "description": "Relative weight of LRR evidence"}),
                "lrr_dev_query": ("FLOAT", {"default": "", "description": "Expected query LRR deviation"}),
                "lrr_dev_control": ("FLOAT", {"default": "", "description": "Expected control LRR deviation"}),
                "lrr_smooth_win": ("INT", {"default": "", "min": 0, "description": "LRR smoothing window"}),
                "same_prob": ("FLOAT", {"default": "", "description": "Prior probability that query and control share a copy-number state"}),
                "err_prob": ("FLOAT", {"default": "", "description": "HMM transition probability to another copy-number state"}),
                "xy_prob": ("FLOAT", {"default": "", "description": "Prior probability for X/Y chromosome copy-number states"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsCSQNode(CommandNode):
    """Annotate haplotype-aware variant consequences with bcftools csq."""

    NODE_ID = "bcftools_csq"
    DISPLAY_NAME = "BCFtools CSQ"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Annotate VCF/BCF records with haplotype-aware consequence predictions from a FASTA and GFF3 annotation."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "csq", "consequence prediction", "haplotype aware consequence", "BCSQ"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("csq_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#csq"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools",
            "csq",
            "--fasta-ref",
            str(inputs.get("reference", inputs.get("fasta_ref", ""))),
            "--gff-annot",
            str(inputs.get("gff_annot", inputs.get("annotation", ""))),
        ]
        _add_if_value(cmd, "--ncsq", inputs.get("ncsq"))
        if inputs.get("local_csq"):
            cmd.append("--local-csq")
        _add_if_value(cmd, "--phase", inputs.get("phase"))
        _add_if_value(cmd, "--custom-tag", inputs.get("custom_tag"))
        _add_if_value(cmd, "--trim-protein-seq", inputs.get("trim_protein_seq"))
        _add_if_value(cmd, "--genetic-code", inputs.get("genetic_code"))
        _add_if_value(cmd, "--samples", inputs.get("samples"))
        _add_if_value(cmd, "--include", inputs.get("include"))
        _add_if_value(cmd, "--exclude", inputs.get("exclude"))
        _bcftools_add_region_targets(cmd, inputs)
        _bcftools_add_output_type(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/csq{_bcftools_variant_suffix(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, f"csq{_bcftools_variant_suffix(inputs)}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file to annotate"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "gff_annot": ("GFF3", {"description": "GFF3 annotation formatted for bcftools csq"}),
            },
            "optional": {
                "ncsq": ("INT", {"default": "", "min": 1, "description": "Maximum number of consequences referenced per sample"}),
                "local_csq": ("BOOLEAN", {"default": False, "description": "Run localized consequence prediction one record at a time"}),
                "phase": ("STRING", {"default": "", "options": ["", "a", "m", "r", "R", "s"], "description": "How unphased genotypes are handled"}),
                "custom_tag": ("STRING", {"default": "", "description": "Custom INFO/FORMAT tag name for consequences"}),
                "trim_protein_seq": ("INT", {"default": "", "min": 0, "description": "Trim protein sequence context to this length"}),
                "genetic_code": ("STRING", {"default": "", "description": "NCBI genetic code identifier"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples or '-' to ignore samples"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "output_type": ("STRING", {"default": "z", "options": ["z", "v", "b", "u"], "description": "BCFtools output type"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsROHNode(CommandNode):
    """Detect runs of homozygosity or autozygosity with bcftools roh."""

    NODE_ID = "bcftools_roh"
    DISPLAY_NAME = "BCFtools ROH"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Detect runs of homozygosity or autozygosity in VCF/BCF genotypes using a hidden Markov model."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "roh", "runs of homozygosity", "autozygosity", "HMM"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("roh_table",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#roh"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "roh"]
        _add_if_value(cmd, "--sample", inputs.get("sample"))
        _bcftools_add_af_file(cmd, inputs)
        _add_if_value(cmd, "--AF-tag", inputs.get("AF_tag", inputs.get("af_tag")))
        _add_if_value(cmd, "--AF-dflt", inputs.get("AF_dflt", inputs.get("af_dflt")))
        _add_if_value(cmd, "--estimate-AF", inputs.get("estimate_AF", inputs.get("estimate_af")))
        _add_if_value(cmd, "--GTs-only", inputs.get("GTs_only", inputs.get("gts_only")))
        if inputs.get("skip_indels"):
            cmd.append("--skip-indels")
        _add_if_value(cmd, "--genetic-map", inputs.get("genetic_map"))
        _add_if_value(cmd, "--rec-rate", inputs.get("rec_rate"))
        buffer_size = inputs.get("buffer_size")
        buffer_overlap = inputs.get("buffer_overlap")
        if buffer_size is not None and str(buffer_size) != "":
            if buffer_overlap is not None and str(buffer_overlap) != "":
                cmd.extend(["--buffer-size", f"{buffer_size},{buffer_overlap}"])
            else:
                cmd.extend(["--buffer-size", str(buffer_size)])
        if inputs.get("ignore_homref"):
            cmd.append("--ignore-homref")
        if inputs.get("include_noalt"):
            cmd.append("--include-noalt")
        _add_if_value(cmd, "--hw-to-az", inputs.get("hw_to_az"))
        _add_if_value(cmd, "--az-to-hw", inputs.get("az_to_hw"))
        if inputs.get("viterbi_training"):
            cmd.append("--viterbi-training")
        _bcftools_add_region_targets(cmd, inputs)
        _add_if_value(cmd, "--samples", inputs.get("samples"))
        _bcftools_add_output_type(cmd, {**inputs, "output_type": inputs.get("output_type", "r")})
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/roh.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "roh.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file for ROH detection"}),
            },
            "optional": {
                "sample": ("STRING", {"default": "", "description": "Single sample to analyze"}),
                "AF_file": ("TSV", {"description": "Allele frequency table"}),
                "AF_tag": ("STRING", {"default": "", "description": "INFO tag containing allele frequencies"}),
                "AF_dflt": ("FLOAT", {"default": "", "description": "Default allele frequency when unavailable"}),
                "estimate_AF": ("TSV", {"description": "Samples file used to estimate allele frequencies"}),
                "GTs_only": ("FLOAT", {"default": "", "min": 0, "description": "Use genotypes only and set quality cap"}),
                "skip_indels": ("BOOLEAN", {"default": False, "description": "Skip indel records"}),
                "genetic_map": ("TSV", {"description": "Genetic map file"}),
                "rec_rate": ("FLOAT", {"default": "", "description": "Constant recombination rate"}),
                "buffer_size": ("INT", {"default": "", "description": "Number of sites to keep in memory"}),
                "buffer_overlap": ("INT", {"default": "", "description": "Number of overlapping sites in the sliding buffer"}),
                "ignore_homref": ("BOOLEAN", {"default": False, "description": "Ignore homozygous reference genotypes"}),
                "include_noalt": ("BOOLEAN", {"default": False, "description": "Include sites without alternate alleles"}),
                "hw_to_az": ("FLOAT", {"default": "", "description": "Hardy-Weinberg to autozygous transition probability"}),
                "az_to_hw": ("FLOAT", {"default": "", "description": "Autozygous to Hardy-Weinberg transition probability"}),
                "viterbi_training": ("BOOLEAN", {"default": False, "description": "Estimate transition probabilities with Viterbi training"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples"}),
                "output_type": ("STRING", {"default": "r", "options": ["s", "r"], "description": "ROH output type: per-site or regions"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginCountsNode(CommandNode):
    """Count samples and variant classes with the bcftools +counts plugin."""

    NODE_ID = "bcftools_plugin_counts"
    DISPLAY_NAME = "BCFtools +counts"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Count samples, SNPs, indels, MNPs, and total sites in a VCF/BCF file."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "counts", "variant counts", "sample counts"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("counts_table",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html#counts"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True
    COUNTS_POSTPROCESS_SCRIPT = r"""
from pathlib import Path
import sys

raw = Path(sys.argv[1])
out = Path(sys.argv[2])
values = {
    "samples": "0",
    "SNPs": "0",
    "INDELs": "0",
    "sites": "0",
}
labels = {
    "Number of samples": "samples",
    "Number of SNPs": "SNPs",
    "Number of INDELs": "INDELs",
    "Number of total sites": "sites",
}
for line in raw.read_text(encoding="utf-8").splitlines():
    label, separator, value = line.partition(":")
    if separator and label in labels:
        values[labels[label]] = value.strip()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(
    "#samples\tSNPs\tINDELs\tsites\n"
    f"{values['samples']}\t{values['SNPs']}\t{values['INDELs']}\t{values['sites']}\n",
    encoding="utf-8",
)
""".strip()

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        raw_counts = f"{out}/counts.raw.txt"
        cmd = _bcftools_plugin_base_cmd("counts", inputs)
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, raw_counts)
        cmd.extend(
            [
                "&&",
                "python",
                "-c",
                cls.COUNTS_POSTPROCESS_SCRIPT,
                raw_counts,
                f"{out}/counts.tsv",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "counts.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file to count"}),
            },
            "optional": {
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginDosageNode(CommandNode):
    """Calculate genotype dosage with the bcftools +dosage plugin."""

    NODE_ID = "bcftools_plugin_dosage"
    DISPLAY_NAME = "BCFtools +dosage"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Calculate per-sample genotype dosage from PL, GL, or GT tags in VCF/BCF records."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "dosage", "genotype dosage", "PL GL GT"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("dosage_table",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html#dosage"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("dosage", inputs)
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args: list[str] = []
        _add_if_value(plugin_args, "--tags", inputs.get("tags"))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/dosage.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "dosage.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with dosage source tags"}),
            },
            "optional": {
                "tags": ("STRING", {"default": "", "description": "Comma-separated dosage source tags such as PL,GL,GT"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginMissing2refNode(CommandNode):
    """Set missing genotypes to reference or major allele calls."""

    NODE_ID = "bcftools_plugin_missing2ref"
    DISPLAY_NAME = "BCFtools +missing2ref"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Replace missing genotypes with reference or major-allele calls using the bcftools +missing2ref plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "missing2ref", "set missing genotypes", "missing to reference"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("missing2ref_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html#missing2ref"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("missing2ref", inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args: list[str] = []
        if inputs.get("phased"):
            plugin_args.append("--phased")
        if inputs.get("major"):
            plugin_args.append("--major")
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/missing2ref.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "missing2ref.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with missing genotypes"}),
            },
            "optional": {
                "phased": ("BOOLEAN", {"default": False, "description": "Set missing genotypes to phased reference calls"}),
                "major": ("BOOLEAN", {"default": False, "description": "Set missing genotypes to the major allele"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginTag2tagNode(CommandNode):
    """Convert between related VCF FORMAT and INFO tags."""

    NODE_ID = "bcftools_plugin_tag2tag"
    DISPLAY_NAME = "BCFtools +tag2tag"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Convert between related genotype likelihood and probability tags such as GL, PL, GP, and GT."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "tag2tag", "convert genotype tags", "GL PL GP GT"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("tag2tag_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html#tag2tag"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("tag2tag", inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args = [str(inputs.get("conversion", "--gp-to-gl"))]
        if inputs.get("replace", True):
            plugin_args.append("--replace")
        if plugin_args[0] == "--gp-to-gt":
            _add_if_value(plugin_args, "--threshold", inputs.get("threshold"))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/tag2tag.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "tag2tag.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with tags to convert"}),
            },
            "optional": {
                "conversion": (
                    "STRING",
                    {
                        "default": "--gp-to-gl",
                        "options": ["--gp-to-gl", "--gp-to-gt", "--gl-to-pl", "--pl-to-gl", "--QR-QA-to-QS"],
                        "description": "Tag conversion mode",
                    },
                ),
                "replace": ("BOOLEAN", {"default": True, "description": "Drop the source tag after conversion"}),
                "threshold": ("FLOAT", {"default": 0.1, "min": 0, "max": 1, "description": "GP-to-GT hard-call threshold"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginFillAnAcNode(CommandNode):
    """Fill INFO/AN and INFO/AC with the deprecated bcftools plugin."""

    NODE_ID = "bcftools_plugin_fill_an_ac"
    DISPLAY_NAME = "BCFtools +fill-AN-AC"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Fill INFO/AN and INFO/AC allele count fields in VCF/BCF records with the deprecated bcftools +fill-AN-AC plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "fill-AN-AC", "fill AN AC", "allele count tags"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("fill_an_ac_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("fill-AN-AC", inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/fill_an_ac.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "fill_an_ac.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file to annotate with AN and AC"}),
            },
            "optional": {
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginFillTagsNode(CommandNode):
    """Fill INFO and FORMAT summary tags with the bcftools +fill-tags plugin."""

    NODE_ID = "bcftools_plugin_fill_tags"
    DISPLAY_NAME = "BCFtools +fill-tags"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Set INFO tags such as AF, AC, AN, HWE, MAF, NS, and FORMAT/VAF with the bcftools +fill-tags plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "fill-tags", "fill INFO tags", "allele frequency tags"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("fill_tags_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.fill-tags.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("fill-tags", inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args: list[str] = []
        tags = _as_list(inputs.get("tags"))
        if tags:
            plugin_args.extend(["--tags", ",".join(tags)])
        samples = str(inputs.get("samples", "")).strip()
        if samples:
            if inputs.get("invert_samples"):
                samples = f"^{samples}"
            plugin_args.extend(["--samples", samples])
        samples_file = str(inputs.get("samples_file", "")).strip()
        if samples_file:
            if inputs.get("invert_samples_file"):
                samples_file = f"^{samples_file}"
            plugin_args.extend(["--samples-file", samples_file])
        if inputs.get("drop_missing"):
            plugin_args.append("--drop-missing")
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/fill_tags.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "fill_tags.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file to annotate with derived INFO/FORMAT tags"}),
            },
            "optional": {
                "tags": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": ["AF", "AN", "AC", "AC_Hom", "AC_Het", "AC_Hemi", "HWE", "ExcHet", "MAF", "NS", "TYPE", "FORMAT/VAF"],
                        "description": "Output tags to set; leave empty to use the plugin default",
                    },
                ),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples to include, or - for all samples"}),
                "invert_samples": ("BOOLEAN", {"default": False, "description": "Exclude the listed samples instead of including them"}),
                "samples_file": ("TSV", {"description": "Sample or population assignment file"}),
                "invert_samples_file": ("BOOLEAN", {"default": False, "description": "Exclude samples from the sample file"}),
                "drop_missing": ("BOOLEAN", {"default": False, "description": "Do not count half-missing genotypes as hemizygous"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginSetgtNode(CommandNode):
    """Set genotypes using the bcftools +setGT plugin."""

    NODE_ID = "bcftools_plugin_setgt"
    DISPLAY_NAME = "BCFtools +setGT"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Set genotypes to missing, reference, major, minor, phased, unphased, or custom calls using bcftools +setGT."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "setGT", "set genotype calls", "replace genotypes"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("setgt_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.setGT.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "plugin", "setGT"]
        _bcftools_add_region_targets(cmd, inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args = [
            "--target-gt",
            str(inputs.get("target_gt", ".")),
            "--new-gt",
            str(inputs.get("new_gt", "0")),
        ]
        _add_if_value(plugin_args, "--include", inputs.get("include"))
        _add_if_value(plugin_args, "--exclude", inputs.get("exclude"))
        _add_if_value(plugin_args, "--seed", inputs.get("seed"))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/setgt.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "setgt.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with genotypes to edit"}),
            },
            "optional": {
                "target_gt": (
                    "STRING",
                    {
                        "default": ".",
                        "options": ["./.", "./x", ".", "a", "b", "q"],
                        "description": "Target genotypes to change: missing, partially missing, all, binomial-test, or query-selected",
                    },
                ),
                "new_gt": (
                    "STRING",
                    {
                        "default": "0",
                        "options": [".", "0", "c:GT", "c:./.", "M", "m", "p", "u"],
                        "description": "New genotype value or transformation",
                    },
                ),
                "include": ("STRING", {"default": "", "description": "Plugin genotype include expression; requires target_gt q"}),
                "exclude": ("STRING", {"default": "", "description": "Plugin genotype exclude expression; requires target_gt q"}),
                "seed": ("INT", {"default": "", "description": "Random seed for target_gt r modes"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginFixploidyNode(CommandNode):
    """Fix genotype ploidy with bcftools +fixploidy."""

    NODE_ID = "bcftools_plugin_fixploidy"
    DISPLAY_NAME = "BCFtools +fixploidy"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Adjust genotype ploidy from sample sex and ploidy-region tables using the bcftools +fixploidy plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "fixploidy", "fix ploidy", "sample sex ploidy"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("fixploidy_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("fixploidy", inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args: list[str] = []
        _add_if_value(plugin_args, "--ploidy", inputs.get("ploidy_file"))
        _add_if_value(plugin_args, "--sex", inputs.get("sex"))
        _add_if_value(plugin_args, "--default-ploidy", inputs.get("default_ploidy"))
        _add_if_value(plugin_args, "--force-ploidy", inputs.get("force_ploidy"))
        _add_if_value(plugin_args, "--tags", inputs.get("tags", "GT"))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/fixploidy.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "fixploidy.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with genotypes to resize by ploidy"}),
            },
            "optional": {
                "ploidy_file": ("TSV", {"description": "Tabular CHROM,FROM,TO,SEX,PLOIDY ploidy map"}),
                "sex": ("TSV", {"description": "Sample sex file with NAME SEX columns"}),
                "default_ploidy": ("INT", {"default": "", "description": "Default ploidy for regions not listed in the ploidy map"}),
                "force_ploidy": ("INT", {"default": "", "description": "Ignore the ploidy file and force this ploidy for all genotypes"}),
                "tags": ("STRING", {"default": "GT", "options": ["GT"], "description": "VCF tag to fix; bcftools currently supports GT"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginMendelianNode(CommandNode):
    """Count and filter Mendelian-consistent or inconsistent genotypes."""

    NODE_ID = "bcftools_plugin_mendelian"
    DISPLAY_NAME = "BCFtools +mendelian2"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Count, annotate, filter, or repair Mendelian-consistent and inconsistent trio genotypes with bcftools +mendelian2."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "mendelian2", "mendelian consistency", "trio genotypes"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("mendelian_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.mendelian.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        stderr_path = f"{out}/mendelian.stderr.txt"
        cmd = ["bcftools", "plugin", "mendelian2"]
        _bcftools_add_restrict(cmd, inputs)
        cmd.extend(["--output-type", "z"])
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args: list[str] = []
        if str(inputs.get("trios_src", "trio")) == "trio_file":
            _add_if_value(plugin_args, "--ped", inputs.get("trio_file"))
        else:
            child = str(inputs.get("child", ""))
            father = str(inputs.get("father", ""))
            mother = str(inputs.get("mother", ""))
            sex_prefix = str(inputs.get("num_x", inputs.get("sex_pattern", "2X")) or "2X")
            plugin_args.extend(["--pfm", f"{sex_prefix}:{child},{father},{mother}"])
        _add_if_value(plugin_args, "--rules", inputs.get("rules"))
        _add_if_value(plugin_args, "--rules-file", inputs.get("rules_file"))
        plugin_args.extend(["--mode", _bcftools_join_mode(inputs.get("mode"), "a")])
        _bcftools_add_plugin_separator(cmd, plugin_args)
        cmd.extend(["2>", stderr_path])
        _add_shell_redirect(cmd, f"{out}/mendelian.vcf.gz")
        cmd.extend(["&&", "cat", stderr_path])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "mendelian.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file containing trio samples"}),
            },
            "optional": {
                "trios_src": ("STRING", {"default": "trio", "options": ["trio", "trio_file"], "description": "Provide one inline trio or a PED trio file"}),
                "child": ("STRING", {"default": "", "description": "Child/proband sample name for inline trio mode"}),
                "mother": ("STRING", {"default": "", "description": "Mother sample name for inline trio mode"}),
                "father": ("STRING", {"default": "", "description": "Father sample name for inline trio mode"}),
                "num_x": ("STRING", {"default": "2X", "options": ["1X", "2X"], "description": "ChrX inheritance pattern for the child"}),
                "trio_file": ("TSV", {"description": "PED file with family, proband, father, mother, and sex columns"}),
                "mode": ("STRING_LIST", {"default": ["a"], "options": ["a", "d", "e", "E", "g", "m", "M", "S"], "description": "VCF output modes to combine"}),
                "rules": ("STRING", {"default": "", "options": ["", "GRCh37", "GRCh38"], "description": "Predefined inheritance rules"}),
                "rules_file": ("TSV", {"description": "Custom inheritance rules file"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginImputeInfoNode(CommandNode):
    """Add IMPUTE2 information metrics with bcftools +impute-info."""

    NODE_ID = "bcftools_plugin_impute_info"
    DISPLAY_NAME = "BCFtools +impute-info"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Add IMPUTE2-style imputation information metrics from FORMAT/GP probabilities using the bcftools +impute-info plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "impute-info", "imputation info", "IMPUTE2 INFO"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("impute_info_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("impute-info", inputs)
        _bcftools_add_plugin_vcf_output(cmd, inputs)
        cmd.append(str(inputs.get("input_file", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/impute_info.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "impute_info.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with FORMAT/GP probabilities"}),
            },
            "optional": {
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginColorChrsNode(CommandNode):
    """Color shared chromosomal segments with bcftools +color-chrs."""

    NODE_ID = "bcftools_plugin_color_chrs"
    DISPLAY_NAME = "BCFtools +color-chrs"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Color shared chromosomal segments between trio or unrelated phased genotype samples with the bcftools +color-chrs plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "color-chrs", "color shared chromosomal segments", "phased GTs"]
    RETURN_TYPES = ("TSV", "IMAGE")
    RETURN_NAMES = ("segments_table", "segments_svg")
    REQUIRED_EXECUTABLES = ["bcftools", "color-chrs.pl"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        prefix = f"{out}/color_chrs_tmp"
        cmd = _bcftools_plugin_base_cmd("color-chrs", inputs)
        _add_if_value(cmd, "--threads", inputs.get("threads"))
        cmd.append(str(inputs.get("input_file", "")))
        if str(inputs.get("sample_rel_sel", "trio")) == "unrelated":
            relation_args = ["--unrelated", f"{inputs.get('sample_a', '')},{inputs.get('sample_b', '')}"]
        else:
            relation_args = ["--trio", f"{inputs.get('mother', '')},{inputs.get('father', '')},{inputs.get('child', '')}"]
        plugin_args = [*relation_args, "-p", prefix]
        _bcftools_add_plugin_separator(cmd, plugin_args)
        cmd.extend(
            [
                "&&",
                "color-chrs.pl",
                f"{prefix}.dat",
                "-p",
                prefix,
                "&&",
                "mv",
                f"{prefix}.dat",
                f"{out}/color_chrs.tsv",
                "&&",
                "mv",
                f"{prefix}.svg",
                f"{out}/color_chrs.svg",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [
            _bcftools_common_output(cls.NODE_ID, "color_chrs.tsv", output_dir),
            _bcftools_common_output(cls.NODE_ID, "color_chrs.svg", output_dir),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "Phased VCF/BCF file with GT genotypes"}),
            },
            "optional": {
                "sample_rel_sel": ("STRING", {"default": "trio", "options": ["trio", "unrelated"], "description": "Sample relationship mode"}),
                "mother": ("STRING", {"default": "", "description": "Mother sample name for trio mode"}),
                "father": ("STRING", {"default": "", "description": "Father sample name for trio mode"}),
                "child": ("STRING", {"default": "", "description": "Child sample name for trio mode"}),
                "sample_a": ("STRING", {"default": "", "description": "First sample name for unrelated mode"}),
                "sample_b": ("STRING", {"default": "", "description": "Second sample name for unrelated mode"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginFrameshiftsNode(CommandNode):
    """Annotate frameshift indels with bcftools +frameshifts."""

    NODE_ID = "bcftools_plugin_frameshifts"
    DISPLAY_NAME = "BCFtools +frameshifts"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Annotate indel records with out-of-frame status from exon intervals using the bcftools +frameshifts plugin."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "frameshifts", "frameshift indels", "OOF annotation"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("frameshifts_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools", "bgzip", "tabix"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        exons_gz = f"{out}/exons.bed.gz"
        cmd = ["bgzip", "-c", str(inputs.get("exons", "")), ">", exons_gz, "&&", "tabix", exons_gz, "&&"]
        plugin_cmd = _bcftools_plugin_base_cmd("frameshifts", inputs)
        _bcftools_add_plugin_vcf_output(plugin_cmd, inputs)
        plugin_cmd.append(str(inputs.get("input_file", "")))
        _bcftools_add_plugin_separator(plugin_cmd, ["--exons", exons_gz])
        _add_shell_redirect(plugin_cmd, f"{out}/frameshifts.vcf.gz")
        cmd.extend(plugin_cmd)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "frameshifts.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file containing indels to annotate"}),
                "exons": ("BED", {"description": "BED file describing reference genome exons"}),
            },
            "optional": {
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class BCFtoolsPluginSplitVepNode(CommandNode):
    """Extract structured annotation fields with bcftools +split-vep."""

    NODE_ID = "bcftools_plugin_split_vep"
    DISPLAY_NAME = "BCFtools +split-vep"
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    CATEGORY = "variant"
    DESCRIPTION = "Extract fields from VEP, ANN, EFF, or other structured INFO annotations into new VCF INFO tags."
    SEARCH_ALIASES = [GALAXY_ALIAS, "bcftools", "plugin", "split-vep", "split VEP annotations", "structured annotations"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("split_vep_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.split-vep.html"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = _bcftools_plugin_base_cmd("split-vep", inputs)
        cmd.extend(["--output-type", "z"])
        cmd.append(str(inputs.get("input_file", "")))
        plugin_args = [
            "-a",
            str(inputs.get("a", "CSQ")),
            "-c",
            str(inputs.get("c", "")),
        ]
        if inputs.get("d"):
            plugin_args.append("-d")
        if inputs.get("allow_undef_tags"):
            plugin_args.append("--allow-undef-tags")
        _add_if_value(plugin_args, "-p", inputs.get("p"))
        _add_if_value(plugin_args, "-s", inputs.get("s"))
        _bcftools_add_plugin_separator(cmd, plugin_args)
        _add_shell_redirect(cmd, f"{_out(inputs)}/split_vep.vcf.gz")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, "split_vep.vcf.gz", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file with structured INFO annotations"}),
            },
            "optional": {
                "a": ("STRING", {"default": "CSQ", "description": "INFO annotation tag to parse, such as CSQ, ANN, EFF, or BCSQ"}),
                "c": ("STRING", {"default": "", "description": "Annotation fields to extract by name or index, optionally with :Integer or :Float types"}),
                "d": ("BOOLEAN", {"default": False, "description": "Output each transcript or allele consequence on a new line"}),
                "allow_undef_tags": ("BOOLEAN", {"default": False, "description": "Print missing values for undefined annotation tags"}),
                "p": ("STRING", {"default": "", "description": "Prefix for newly created INFO annotations"}),
                "s": ("STRING", {"default": "", "description": "Transcript and consequence selector such as worst or :missense"}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
