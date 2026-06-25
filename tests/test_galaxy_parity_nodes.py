from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def _node_class(node_id: str) -> type:
    node_class = _registry().get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_galaxy_parity_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "busco": {
            "display_name": "BUSCO",
            "category": "assembly",
            "required_executables": ["busco"],
            "required_conda_packages": ["busco"],
            "doi": "10.1093/bioinformatics/btv351",
        },
        "htseq_count": {
            "display_name": "HTSeq-count",
            "category": "rna_seq",
            "required_executables": ["htseq-count", "samtools"],
            "required_conda_packages": ["htseq", "samtools"],
            "doi": "10.1093/bioinformatics/btu638",
        },
        "seqkit_stats": {
            "display_name": "SeqKit Stats",
            "category": "qc",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "vsearch_search": {
            "display_name": "VSEARCH Search",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_cluster": {
            "display_name": "VSEARCH Cluster",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "diamond_makedb": {
            "display_name": "DIAMOND MakeDB",
            "category": "databases",
            "required_executables": ["diamond"],
            "required_conda_packages": ["diamond"],
            "doi": "10.1038/s41592-021-01101-x",
        },
        "diamond_align": {
            "display_name": "DIAMOND Align",
            "category": "alignment",
            "required_executables": ["diamond"],
            "required_conda_packages": ["diamond"],
            "doi": "10.1038/s41592-021-01101-x",
        },
        "hmmer_hmmsearch": {
            "display_name": "HMMER hmmsearch",
            "category": "annotation",
            "required_executables": ["hmmsearch"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmscan": {
            "display_name": "HMMER hmmscan",
            "category": "annotation",
            "required_executables": ["hmmscan"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "mmseqs2_easy_search": {
            "display_name": "MMseqs2 Easy Search",
            "category": "alignment",
            "required_executables": ["mmseqs"],
            "required_conda_packages": ["mmseqs2"],
            "doi": "10.1038/nbt.3988",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == metadata["category"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith(("https://", "http://"))
        assert "Galaxy" in node_info["search_aliases"]


def test_busco_renders_galaxy_aligned_completeness_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("busco")

    cmd = node_class.render_command(
        {
            "input": "assembly.fasta",
            "mode": "genome",
            "lineage_dataset": "bacteria_odb10",
            "lineage_mode": "select_lineage",
            "gene_predictor": "miniprot",
            "threads": 8,
            "offline": True,
            "download_path": "/db/busco",
            "evalue": 0.001,
            "limit": 3,
            "contig_break": 10,
            "output": "/work/busco",
        }
    )

    assert cmd == [
        "busco",
        "--in",
        "assembly.fasta",
        "--mode",
        "genome",
        "--out",
        "busco_galaxy",
        "--out_path",
        "/work/busco",
        "--cpu",
        "8",
        "--evalue",
        "0.001",
        "--limit",
        "3",
        "--contig_break",
        "10",
        "--offline",
        "--download_path",
        "/db/busco",
        "--lineage_dataset",
        "bacteria_odb10",
        "--miniprot",
    ]

    outputs = node_class.PLAN_OUTPUTS({}, tmp_path)
    assert outputs == [
        tmp_path / "busco" / "short_summary.txt",
        tmp_path / "busco" / "full_table.tsv",
        tmp_path / "busco" / "missing_buscos.tsv",
        tmp_path / "busco" / "summary.png",
    ]


def test_htseq_count_renders_counting_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("htseq_count")

    cmd = node_class.render_command(
        {
            "samfile": "aligned.bam",
            "gfffile": "genes.gtf",
            "mode": "intersection-nonempty",
            "stranded": "reverse",
            "minaqual": 10,
            "featuretype": "exon",
            "idattr": "gene_id",
            "nonunique": "fraction",
            "secondary_alignments": "ignore",
            "supplementary_alignments": "score",
            "order": "name",
            "sort_bam": True,
            "output": "/work/htseq_count",
        }
    )

    assert cmd == [
        "samtools",
        "sort",
        "-n",
        "-o",
        "/work/htseq_count/name_sorted.bam",
        "aligned.bam",
        "&&",
        "htseq-count",
        "--format=bam",
        "--mode=intersection-nonempty",
        "--stranded=reverse",
        "--minaqual=10",
        "--type=exon",
        "--idattr=gene_id",
        "--nonunique=fraction",
        "--secondary-alignments=ignore",
        "--supplementary-alignments=score",
        "--order=name",
        "/work/htseq_count/name_sorted.bam",
        "genes.gtf",
        ">",
        "/work/htseq_count/counts.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "htseq_count" / "counts.tsv"]


def test_seqkit_stats_renders_statistics_command() -> None:
    node_class = _node_class("seqkit_stats")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "all": True,
            "basename": True,
            "skip_err": True,
            "tabular": True,
            "output": "/work/seqkit_stats",
        }
    ) == [
        "seqkit",
        "stats",
        "reads.fastq.gz",
        "--all",
        "--basename",
        "--skip-err",
        "--tabular",
        ">",
        "/work/seqkit_stats/stats.tsv",
    ]


def test_vsearch_search_and_cluster_render_commands_and_outputs(tmp_path: Path) -> None:
    search_class = _node_class("vsearch_search")
    cluster_class = _node_class("vsearch_cluster")

    assert search_class.render_command(
        {
            "query": "queries.fasta",
            "database": "db.fasta",
            "search_mode": "usearch_global",
            "identity": 0.97,
            "strand": "both",
            "maxaccepts": 10,
            "maxrejects": 32,
            "threads": 6,
            "output": "/work/vsearch_search",
        }
    ) == [
        "vsearch",
        "--usearch_global",
        "queries.fasta",
        "--db",
        "db.fasta",
        "--id",
        "0.97",
        "--strand",
        "both",
        "--maxaccepts",
        "10",
        "--maxrejects",
        "32",
        "--threads",
        "6",
        "--blast6out",
        "/work/vsearch_search/matches.tsv",
        "--alnout",
        "/work/vsearch_search/alignments.txt",
        "--notmatched",
        "/work/vsearch_search/unmatched.fasta",
    ]
    assert search_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_search" / "matches.tsv",
        tmp_path / "vsearch_search" / "alignments.txt",
        tmp_path / "vsearch_search" / "unmatched.fasta",
    ]

    assert cluster_class.render_command(
        {
            "sequences": "amplicons.fasta",
            "cluster_mode": "cluster_fast",
            "identity": 0.99,
            "strand": "plus",
            "sizein": True,
            "sizeout": True,
            "threads": 4,
            "output": "/work/vsearch_cluster",
        }
    ) == [
        "vsearch",
        "--cluster_fast",
        "amplicons.fasta",
        "--id",
        "0.99",
        "--strand",
        "plus",
        "--sizein",
        "--sizeout",
        "--threads",
        "4",
        "--centroids",
        "/work/vsearch_cluster/centroids.fasta",
        "--uc",
        "/work/vsearch_cluster/clusters.uc",
    ]


def test_diamond_nodes_render_database_and_alignment_commands(tmp_path: Path) -> None:
    makedb_class = _node_class("diamond_makedb")
    align_class = _node_class("diamond_align")

    assert makedb_class.render_command(
        {
            "infile": "proteins.faa",
            "threads": 12,
            "taxonmap": "prot.accession2taxid.gz",
            "taxonnodes": "nodes.dmp",
            "taxonnames": "names.dmp",
            "output": "/work/diamond_makedb",
        }
    ) == [
        "diamond",
        "makedb",
        "--threads",
        "12",
        "--in",
        "proteins.faa",
        "--db",
        "/work/diamond_makedb/database",
        "--taxonmap",
        "prot.accession2taxid.gz",
        "--taxonnodes",
        "nodes.dmp",
        "--taxonnames",
        "names.dmp",
    ]
    assert makedb_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "diamond_makedb" / "database.dmnd"]

    assert align_class.render_command(
        {
            "query": "reads.fasta",
            "database": "nr.dmnd",
            "method": "blastx",
            "threads": 10,
            "sensitivity": "--very-sensitive",
            "evalue": 1e-5,
            "max_target_seqs": 25,
            "matrix": "BLOSUM62",
            "query_gencode": 1,
            "query_strand": "both",
            "min_orf": 20,
            "outfmt": "6 qseqid sseqid pident length evalue bitscore",
            "output": "/work/diamond_align",
        }
    ) == [
        "diamond",
        "blastx",
        "--threads",
        "10",
        "--db",
        "nr.dmnd",
        "--query",
        "reads.fasta",
        "--out",
        "/work/diamond_align/matches.tsv",
        "--outfmt",
        "6",
        "qseqid",
        "sseqid",
        "pident",
        "length",
        "evalue",
        "bitscore",
        "--very-sensitive",
        "--evalue",
        "1e-05",
        "--max-target-seqs",
        "25",
        "--matrix",
        "BLOSUM62",
        "--query-gencode",
        "1",
        "--strand",
        "both",
        "--min-orf",
        "20",
    ]


def test_hmmer_nodes_render_table_outputs() -> None:
    hmmsearch_class = _node_class("hmmer_hmmsearch")
    hmmscan_class = _node_class("hmmer_hmmscan")

    assert hmmsearch_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "seqdb": "proteins.fasta",
            "evalue": 1e-3,
            "incE": 1e-5,
            "cut_ga": True,
            "notextw": True,
            "threads": 4,
            "output": "/work/hmmsearch",
        }
    ) == [
        "hmmsearch",
        "--cpu",
        "4",
        "-E",
        "0.001",
        "--incE",
        "1e-05",
        "--cut_ga",
        "--notextw",
        "--tblout",
        "/work/hmmsearch/results.tblout",
        "--domtblout",
        "/work/hmmsearch/domains.domtblout",
        "--pfamtblout",
        "/work/hmmsearch/pfam.tblout",
        "-o",
        "/work/hmmsearch/output.txt",
        "profile.hmm",
        "proteins.fasta",
    ]

    assert hmmscan_class.render_command(
        {
            "seqfile": "proteins.fasta",
            "hmmdb": "pfam.hmm",
            "domE": 0.01,
            "incdomE": 0.001,
            "cut_tc": True,
            "threads": 2,
            "output": "/work/hmmscan",
        }
    ) == [
        "hmmscan",
        "--cpu",
        "2",
        "--domE",
        "0.01",
        "--incdomE",
        "0.001",
        "--cut_tc",
        "--tblout",
        "/work/hmmscan/results.tblout",
        "--domtblout",
        "/work/hmmscan/domains.domtblout",
        "--pfamtblout",
        "/work/hmmscan/pfam.tblout",
        "-o",
        "/work/hmmscan/output.txt",
        "pfam.hmm",
        "proteins.fasta",
    ]


def test_hmmer_nodes_skip_blank_advanced_thresholds_from_default_params() -> None:
    node_class = _node_class("hmmer_hmmsearch")

    cmd = node_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "seqdb": "proteins.fasta",
            "evalue": 10,
            "incE": "",
            "domE": "",
            "incdomE": "",
            "threads": 1,
            "output": "/work/hmmsearch",
        }
    )

    assert "--incE" not in cmd
    assert "--domE" not in cmd
    assert "--incdomE" not in cmd


def test_mmseqs2_easy_search_renders_sensitive_search_command() -> None:
    node_class = _node_class("mmseqs2_easy_search")

    assert node_class.render_command(
        {
            "query_fasta": "query.fasta",
            "target_fasta": "target.fasta",
            "search_type": 0,
            "sensitivity": 7.5,
            "evalue": 1e-5,
            "min_seq_id": 0.4,
            "cov": 0.6,
            "cov_mode": 2,
            "format_output": "query,target,pident,evalue,qaln,taln",
            "num_iterations": 2,
            "threads": 8,
            "output": "/work/mmseqs",
        }
    ) == [
        "mmseqs",
        "easy-search",
        "query.fasta",
        "target.fasta",
        "/work/mmseqs/search_results",
        "/work/mmseqs/tmp",
        "--search-type",
        "0",
        "-s",
        "7.5",
        "-e",
        "1e-05",
        "--min-seq-id",
        "0.4",
        "-c",
        "0.6",
        "--cov-mode",
        "2",
        "--format-output",
        "query,target,pident,evalue,qaln,taln",
        "--num-iterations",
        "2",
        "--threads",
        "8",
    ]
