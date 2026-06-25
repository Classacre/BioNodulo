"""Galaxy IUC parity nodes with DOI-backed citation metadata."""
from __future__ import annotations

from pathlib import Path
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
