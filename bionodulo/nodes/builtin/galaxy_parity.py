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
