from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bionodulo.nodes.registry import NodeRegistry


def _registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def _node_class(node_id: str) -> type:
    node_class = _registry().get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


class _RecordingCommandContext:
    def __init__(self, node_dir: Path) -> None:
        self.node_dir = node_dir
        self.commands: list[str | list[str]] = []

    async def run_command(self, cmd: str | list[str], **_: Any) -> dict[str, Any]:
        self.commands.append(cmd)
        if isinstance(cmd, list):
            try:
                output_path = Path(cmd[cmd.index("-o") + 1])
            except (ValueError, IndexError):
                output_path = self.node_dir / "fastani.tsv"
        else:
            output_path = self.node_dir / "fastani.tsv"
        output_path.write_text("q1.fna\tr1.fna\t99.9\t1200\t1200\n", encoding="utf-8")
        output_path.with_suffix(output_path.suffix + ".matrix").write_text("2\nq1\t0\n", encoding="utf-8")
        output_path.with_suffix(output_path.suffix + ".visual").write_text("q1\tr1\t1\t1200\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}


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


def test_galaxy_parity_second_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "mash_dist": {
            "display_name": "Mash Dist",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-016-0997-x",
        },
        "fastani": {
            "display_name": "FastANI",
            "category": "genomics",
            "required_executables": ["fastANI"],
            "required_conda_packages": ["fastani"],
            "doi": "10.1038/s41467-018-07641-9",
        },
        "lofreq_call": {
            "display_name": "LoFreq Call",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1093/nar/gks918",
        },
        "ivar_variants": {
            "display_name": "iVar Variants",
            "category": "variant",
            "required_executables": ["samtools", "ivar"],
            "required_conda_packages": ["samtools", "ivar"],
            "doi": "10.1186/s13059-018-1618-7",
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


def test_mash_dist_renders_distance_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mash_dist")

    assert node_class.render_command(
        {
            "reference": "ref.msh",
            "query": "query.msh",
            "table_output": True,
            "threads": 6,
            "pvalue": 0.05,
            "distance": 0.25,
            "output": "/work/mash_dist",
        }
    ) == [
        "mash",
        "dist",
        "-t",
        "-p",
        "6",
        "-v",
        "0.05",
        "-d",
        "0.25",
        "ref.msh",
        "query.msh",
        ">",
        "/work/mash_dist/distances.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_dist" / "distances.tsv"]


def test_fastani_renders_many_to_many_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("fastani")

    assert node_class.render_command(
        {
            "query": ["q1.fna", "q2.fna"],
            "reference": ["r1.fna", "r2.fna"],
            "threads": 12,
            "frag_len": 3000,
            "min_fraction": 0.2,
            "kmer": 16,
            "matrix": True,
            "visualize": True,
            "output": "/work/fastani",
        }
    ) == [
        "fastANI",
        "--ql",
        "/work/fastani/query.lst",
        "--rl",
        "/work/fastani/ref.lst",
        "-o",
        "/work/fastani/fastani.tsv",
        "-t",
        "12",
        "--fragLen",
        "3000",
        "--minFraction",
        "0.2",
        "-k",
        "16",
        "--matrix",
        "--visualize",
    ]

    assert node_class.PLAN_OUTPUTS({"matrix": True, "visualize": True}, tmp_path) == [
        tmp_path / "fastani" / "fastani.tsv",
        tmp_path / "fastani" / "fastani.tsv.matrix",
        tmp_path / "fastani" / "fastani.tsv.visual",
    ]


def test_fastani_run_writes_many_to_many_list_files(tmp_path: Path) -> None:
    node_class = _node_class("fastani")
    context = _RecordingCommandContext(tmp_path / "fastani")

    result = asyncio.run(
        node_class().run(
            query=["q1.fna", "q2.fna"],
            reference=["r1.fna", "r2.fna"],
            threads=2,
            matrix=True,
            visualize=True,
            context=context,
            output_dir=tmp_path,
        )
    )

    assert result == (
        str(tmp_path / "fastani" / "fastani.tsv"),
        str(tmp_path / "fastani" / "fastani.tsv.matrix"),
        str(tmp_path / "fastani" / "fastani.tsv.visual"),
    )
    assert (tmp_path / "fastani" / "query.lst").read_text(encoding="utf-8") == "q1.fna\nq2.fna\n"
    assert (tmp_path / "fastani" / "ref.lst").read_text(encoding="utf-8") == "r1.fna\nr2.fna\n"
    assert context.commands


def test_fastani_run_writes_single_file_lists_for_planned_outputs(tmp_path: Path) -> None:
    node_class = _node_class("fastani")
    context = _RecordingCommandContext(tmp_path / "fastani")

    result = asyncio.run(
        node_class().run(
            query="q1.fna",
            reference="r1.fna",
            threads=2,
            context=context,
            output_dir=tmp_path,
        )
    )

    assert result == (
        str(tmp_path / "fastani" / "fastani.tsv"),
    )
    assert (tmp_path / "fastani" / "query.lst").read_text(encoding="utf-8") == "q1.fna\n"
    assert (tmp_path / "fastani" / "ref.lst").read_text(encoding="utf-8") == "r1.fna\n"


def test_lofreq_call_renders_configured_variant_call_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_call")

    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "bed": "targets.bed",
            "variant_types": "--call-indels",
            "threads": 4,
            "min_cov": 5,
            "max_depth": 100000,
            "use_orphan": True,
            "min_bq": 10,
            "min_alt_bq": 12,
            "def_alt_bq": 20,
            "alnquals_to_use": "-A",
            "extended_baq": "-e",
            "min_mq": 20,
            "max_mq": 60,
            "src_qual": True,
            "ign_vcf": ["known.vcf.gz", "panel.vcf"],
            "def_nm_q": -1,
            "min_jq": 5,
            "min_alt_jq": 7,
            "def_alt_jq": 9,
            "sig": 0.01,
            "bonf": "dynamic",
            "no_default_filter": True,
            "output": "/work/lofreq",
        }
    ) == [
        "lofreq",
        "call-parallel",
        "--pp-threads",
        "4",
        "--verbose",
        "--ref",
        "ref.fa",
        "--out",
        "/work/lofreq/variants.vcf",
        "--call-indels",
        "--bed",
        "targets.bed",
        "--min-cov",
        "5",
        "--max-depth",
        "100000",
        "--use-orphan",
        "--min-bq",
        "10",
        "--min-alt-bq",
        "12",
        "--def-alt-bq",
        "20",
        "-A",
        "-e",
        "--min-mq",
        "20",
        "--max-mq",
        "60",
        "--src-qual",
        "--ign-vcf",
        "known.vcf.gz,panel.vcf",
        "--def-nm-q",
        "-1",
        "--min-jq",
        "5",
        "--min-alt-jq",
        "7",
        "--def-alt-jq",
        "9",
        "--sig",
        "0.01",
        "--bonf",
        "dynamic",
        "--no-default-filter",
        "reads.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_call" / "variants.vcf"]


def test_ivar_variants_renders_mpileup_pipeline_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("ivar_variants")

    assert node_class.render_command(
        {
            "input_bam": "sorted.bam",
            "ref": "ref.fa",
            "min_qual": 25,
            "min_freq": 0.1,
            "output_format": "tabular_and_vcf",
            "gtf": "genes.gff",
            "pass_only": True,
            "output": "/work/ivar",
        }
    ) == [
        "samtools",
        "mpileup",
        "-A",
        "-d",
        "0",
        "--reference",
        "ref.fa",
        "-B",
        "-Q",
        "0",
        "sorted.bam",
        "|",
        "ivar",
        "variants",
        "-p",
        "/work/ivar/variants",
        "-q",
        "25",
        "-t",
        "0.1",
        "-r",
        "ref.fa",
        "-g",
        "genes.gff",
        "&&",
        "ivar_variants_to_vcf.py",
        "--pass_only",
        "/work/ivar/variants.tsv",
        "/work/ivar/variants.vcf",
    ]

    assert node_class.PLAN_OUTPUTS({"output_format": "tabular_and_vcf"}, tmp_path) == [
        tmp_path / "ivar_variants" / "variants.tsv",
        tmp_path / "ivar_variants" / "variants.vcf",
    ]


def test_galaxy_parity_third_batch_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "gtdbtk_classify_wf": {
            "display_name": "GTDB-Tk Classify",
            "category": "taxonomy",
            "required_executables": ["gtdbtk"],
            "required_conda_packages": ["gtdbtk"],
            "doi": "10.1093/bioinformatics/btz848",
        },
        "rseqc_infer_experiment": {
            "display_name": "RSeQC Infer Experiment",
            "category": "rna_seq",
            "required_executables": ["infer_experiment.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "bedtools_coveragebed": {
            "display_name": "BEDTools Coverage",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_genomecoveragebed": {
            "display_name": "BEDTools Genome Coverage",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
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


def test_gtdbtk_classify_wf_renders_classification_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("gtdbtk_classify_wf")

    assert node_class.render_command(
        {
            "input": ["G1.fna.gz", "G2.fna.gz"],
            "extension": "fna.gz",
            "gtdbtk_data_path": "/db/gtdbtk",
            "threads": 8,
            "min_perc_aa": 15,
            "force": True,
            "min_af": 0.7,
            "full_tree": True,
            "skip_ani_screen": True,
            "output_process_log": True,
            "output": "/work/gtdbtk",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/gtdbtk/input_dir",
        "/work/gtdbtk/output_dir",
        "&&",
        "ln",
        "-sf",
        "G1.fna.gz",
        "/work/gtdbtk/input_dir/G1.fna.gz",
        "&&",
        "ln",
        "-sf",
        "G2.fna.gz",
        "/work/gtdbtk/input_dir/G2.fna.gz",
        "&&",
        "export",
        "GTDBTK_DATA_PATH=/db/gtdbtk",
        "&&",
        "gtdbtk",
        "classify_wf",
        "--genome_dir",
        "/work/gtdbtk/input_dir",
        "--extension",
        "fna.gz",
        "--out_dir",
        "/work/gtdbtk/output_dir",
        "--cpus",
        "8",
        "--min_perc_aa",
        "15",
        "--force",
        "--min_af",
        "0.7",
        "--full_tree",
        "--skip_ani_screen",
        "&&",
        "cat",
        "/work/gtdbtk/output_dir/gtdbtk.warnings.log",
        "/work/gtdbtk/output_dir/gtdbtk.log",
        ">",
        "/work/gtdbtk/process.log",
    ]

    assert node_class.PLAN_OUTPUTS({"output_process_log": True}, tmp_path) == [
        tmp_path / "gtdbtk_classify_wf" / "output_dir" / "align",
        tmp_path / "gtdbtk_classify_wf" / "output_dir" / "identify",
        tmp_path / "gtdbtk_classify_wf" / "output_dir" / "classify",
        tmp_path / "gtdbtk_classify_wf" / "output_dir",
        tmp_path / "gtdbtk_classify_wf" / "process.log",
    ]


def test_rseqc_infer_experiment_renders_strandedness_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_infer_experiment")

    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed",
            "sample_size": 200000,
            "mapq": 30,
            "output": "/work/rseqc_infer_experiment",
        }
    ) == [
        "infer_experiment.py",
        "-i",
        "aligned.bam",
        "-r",
        "genes.bed",
        "--sample-size",
        "200000",
        "--mapq",
        "30",
        ">",
        "/work/rseqc_infer_experiment/infer_experiment.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_infer_experiment" / "infer_experiment.txt",
    ]


def test_bedtools_coveragebed_renders_depth_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_coveragebed")

    assert node_class.render_command(
        {
            "inputA": "windows.bed",
            "inputB": ["reads.bam", "capture.bed"],
            "split": True,
            "strandedness": True,
            "d": True,
            "mean": True,
            "overlap_a": 0.5,
            "overlap_b": 0.2,
            "reciprocal_overlap": True,
            "a_or_b": True,
            "sorted": True,
            "output": "/work/bedtools_coveragebed",
        }
    ) == [
        "bedtools",
        "coverage",
        "-d",
        "-split",
        "-s",
        "-mean",
        "-f",
        "0.5",
        "-F",
        "0.2",
        "-r",
        "-e",
        "-a",
        "windows.bed",
        "-b",
        "reads.bam",
        "capture.bed",
        "-sorted",
        "|",
        "sort",
        "-k1,1",
        "-k2,2n",
        ">",
        "/work/bedtools_coveragebed/coverage.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_coveragebed" / "coverage.bed",
    ]


def test_bedtools_genomecoveragebed_renders_bam_bedgraph_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_genomecoveragebed")

    assert node_class.render_command(
        {
            "input_type": "bam",
            "input": "reads.bam",
            "report": "bg",
            "zero_regions": True,
            "scale": 0.5,
            "split": True,
            "strand": "+",
            "d": True,
            "five": True,
            "output": "/work/bedtools_genomecoveragebed",
        }
    ) == [
        "bedtools",
        "genomecov",
        "-ibam",
        "reads.bam",
        "-split",
        "-strand",
        "+",
        "-bga",
        "-scale",
        "0.5",
        "-d",
        "-5",
        ">",
        "/work/bedtools_genomecoveragebed/genome_coverage.bedgraph",
    ]

    assert node_class.PLAN_OUTPUTS({"report": "bg"}, tmp_path) == [
        tmp_path / "bedtools_genomecoveragebed" / "genome_coverage.bedgraph",
    ]
    assert node_class.PLAN_OUTPUTS({"report": "hist"}, tmp_path) == [
        tmp_path / "bedtools_genomecoveragebed" / "genome_coverage.tsv",
    ]


def test_galaxy_parity_bedtools_followup_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_subtractbed": {
            "display_name": "BEDTools Subtract",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_mergebed": {
            "display_name": "BEDTools Merge",
            "category": "genomics",
            "required_executables": ["mergeBed"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_sortbed": {
            "display_name": "BEDTools Sort",
            "category": "genomics",
            "required_executables": ["sortBed"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_getfastabed": {
            "display_name": "BEDTools getfasta",
            "category": "genomics",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
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


def test_bedtools_subtractbed_renders_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_subtractbed")

    assert node_class.render_command(
        {
            "inputA": "targets.bed",
            "inputB": "blacklist.bed",
            "strand": "opposite",
            "overlap": 0.8,
            "remove_if_overlap": "remove_feature",
            "output": "/work/bedtools_subtractbed",
        }
    ) == [
        "bedtools",
        "subtract",
        "-S",
        "-a",
        "targets.bed",
        "-b",
        "blacklist.bed",
        "-f",
        "0.8",
        "-A",
        ">",
        "/work/bedtools_subtractbed/subtracted.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_subtractbed" / "subtracted.bed",
    ]


def test_bedtools_mergebed_renders_column_operations_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_mergebed")

    assert node_class.render_command(
        {
            "input": "sorted_regions.bed",
            "strand": "forward",
            "distance": 1000,
            "header": True,
            "columns": "4,5",
            "operations": "collapse,mean",
            "output": "/work/bedtools_mergebed",
        }
    ) == [
        "mergeBed",
        "-i",
        "sorted_regions.bed",
        "-S",
        "+",
        "-d",
        "1000",
        "-header",
        "-c",
        "4,5",
        "-o",
        "collapse,mean",
        ">",
        "/work/bedtools_mergebed/merged.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_mergebed" / "merged.bed",
    ]


def test_bedtools_sortbed_renders_genome_order_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_sortbed")

    assert node_class.render_command(
        {
            "input": "regions.gff",
            "sort_by": "-chrThenScoreD",
            "genome": "chrom.sizes",
            "output": "/work/bedtools_sortbed",
        }
    ) == [
        "sortBed",
        "-i",
        "regions.gff",
        "-chrThenScoreD",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_sortbed/sorted.gff",
    ]

    assert node_class.PLAN_OUTPUTS({"input": "regions.gff"}, tmp_path) == [
        tmp_path / "bedtools_sortbed" / "sorted.gff",
    ]


def test_bedtools_getfastabed_renders_sequence_extraction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_getfastabed")

    assert node_class.render_command(
        {
            "input": "exons.bed12",
            "fasta": "genome.fa",
            "name_only": True,
            "tab": True,
            "strand": True,
            "split": True,
            "output": "/work/bedtools_getfastabed",
        }
    ) == [
        "ln",
        "-s",
        "genome.fa",
        "input.fasta",
        "&&",
        "bedtools",
        "getfasta",
        "-nameOnly",
        "-tab",
        "-s",
        "-split",
        "-fi",
        "input.fasta",
        "-bed",
        "exons.bed12",
        "-fo",
        "/work/bedtools_getfastabed/extracted.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({"tab": True}, tmp_path) == [
        tmp_path / "bedtools_getfastabed" / "extracted.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({"tab": False}, tmp_path) == [
        tmp_path / "bedtools_getfastabed" / "extracted.fasta",
    ]


def test_galaxy_parity_bedtools_interval_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_complementbed": {
            "display_name": "BEDTools Complement",
            "required_executables": ["complementBed"],
        },
        "bedtools_flankbed": {
            "display_name": "BEDTools Flank",
            "required_executables": ["flankBed"],
        },
        "bedtools_slopbed": {
            "display_name": "BEDTools Slop",
            "required_executables": ["bedtools"],
        },
        "bedtools_windowbed": {
            "display_name": "BEDTools Window",
            "required_executables": ["bedtools"],
        },
        "bedtools_map": {
            "display_name": "BEDTools Map",
            "required_executables": ["bedtools"],
        },
        "bedtools_multiintersectbed": {
            "display_name": "BEDTools Multiple Intersect",
            "required_executables": ["bedtools"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith("https://bedtools.readthedocs.io/")
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_complementbed_renders_genome_gap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_complementbed")

    assert node_class.render_command(
        {
            "input": "covered.bed",
            "genome": "chrom.sizes",
            "output": "/work/bedtools_complementbed",
        }
    ) == [
        "complementBed",
        "-i",
        "covered.bed",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_complementbed/complement.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_complementbed" / "complement.bed",
    ]


def test_bedtools_flankbed_renders_fractional_stranded_flank_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_flankbed")

    assert node_class.render_command(
        {
            "input": "genes.bed",
            "genome": "chrom.sizes",
            "pct": True,
            "strand": True,
            "addition_mode": "lr",
            "left": 0.2,
            "right": 0.5,
            "output": "/work/bedtools_flankbed",
        }
    ) == [
        "flankBed",
        "-pct",
        "-s",
        "-g",
        "chrom.sizes",
        "-i",
        "genes.bed",
        "-l",
        "0.2",
        "-r",
        "0.5",
        ">",
        "/work/bedtools_flankbed/flanks.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_flankbed" / "flanks.bed",
    ]


def test_bedtools_slopbed_renders_symmetric_extension_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_slopbed")

    assert node_class.render_command(
        {
            "inputA": "peaks.bed",
            "genome": "chrom.sizes",
            "addition_mode": "b",
            "both": 250,
            "header": True,
            "output": "/work/bedtools_slopbed",
        }
    ) == [
        "bedtools",
        "slop",
        "-g",
        "chrom.sizes",
        "-i",
        "peaks.bed",
        "-b",
        "250",
        "-header",
        ">",
        "/work/bedtools_slopbed/slopped.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_slopbed" / "slopped.bed",
    ]


def test_bedtools_windowbed_renders_asymmetric_count_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_windowbed")

    assert node_class.render_command(
        {
            "inputA": "promoters.bed",
            "inputB": "enhancers.bed",
            "addition_mode": "lr",
            "left": 200,
            "right": 20000,
            "strand": "same",
            "number": True,
            "header": True,
            "output": "/work/bedtools_windowbed",
        }
    ) == [
        "bedtools",
        "window",
        "-a",
        "promoters.bed",
        "-b",
        "enhancers.bed",
        "-sm",
        "-l",
        "200",
        "-r",
        "20000",
        "-c",
        "-header",
        ">",
        "/work/bedtools_windowbed/window.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_windowbed" / "window.bed",
    ]


def test_bedtools_map_renders_column_operation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_map")

    assert node_class.render_command(
        {
            "inputA": "exons.bed",
            "inputB": "coverage.bedgraph",
            "columns": "4",
            "operations": "mean",
            "strand": "opposite",
            "overlap": 0.5,
            "overlap_b": 0.25,
            "reciprocal": True,
            "split": True,
            "header": True,
            "genome": "chrom.sizes",
            "output": "/work/bedtools_map",
        }
    ) == [
        "bedtools",
        "map",
        "-a",
        "exons.bed",
        "-b",
        "coverage.bedgraph",
        "-S",
        "-c",
        "4",
        "-o",
        "mean",
        "-f",
        "0.5",
        "-F",
        "0.25",
        "-r",
        "-split",
        "-header",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_map/mapped.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_map" / "mapped.bed",
    ]


def test_bedtools_multiintersectbed_renders_custom_names_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_multiintersectbed")

    assert node_class.render_command(
        {
            "inputs": ["a.bed", "b.bed", "c.bed"],
            "names": ["sampleA", "sampleB", "sampleC"],
            "header": True,
            "cluster": True,
            "filler": "0",
            "empty": True,
            "genome": "chrom.sizes",
            "output": "/work/bedtools_multiintersectbed",
        }
    ) == [
        "bedtools",
        "multiinter",
        "-header",
        "-cluster",
        "-filler",
        "0",
        "-empty",
        "-g",
        "chrom.sizes",
        "-i",
        "a.bed",
        "b.bed",
        "c.bed",
        "-names",
        "sampleA",
        "sampleB",
        "sampleC",
        ">",
        "/work/bedtools_multiintersectbed/multiintersect.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_multiintersectbed" / "multiintersect.bed",
    ]


def test_galaxy_parity_bedtools_statistics_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_clusterbed": {
            "display_name": "BEDTools Cluster",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_jaccard": {
            "display_name": "BEDTools Jaccard",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_fisher": {
            "display_name": "BEDTools Fisher",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_reldistbed": {
            "display_name": "BEDTools Relative Distance",
            "required_executables": ["bedtools"],
            "doi": "10.1371/journal.pcbi.1002529",
        },
        "bedtools_spacingbed": {
            "display_name": "BEDTools Spacing",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
        "bedtools_groupbybed": {
            "display_name": "BEDTools GroupBy",
            "required_executables": ["bedtools"],
            "doi": "10.1093/bioinformatics/btq033",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert metadata["doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['doi']}" in node_info["citation_urls"]
        assert node_info["documentation_url"].startswith("https://bedtools.readthedocs.io/")
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_clusterbed_renders_stranded_cluster_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_clusterbed")

    assert node_class.render_command(
        {
            "inputA": "sorted.bed",
            "strand": True,
            "distance": 500,
            "output": "/work/bedtools_clusterbed",
        }
    ) == [
        "bedtools",
        "cluster",
        "-s",
        "-d",
        "500",
        "-i",
        "sorted.bed",
        ">",
        "/work/bedtools_clusterbed/clustered.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_clusterbed" / "clustered.bed",
    ]


def test_bedtools_jaccard_renders_overlap_statistic_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_jaccard")

    assert node_class.render_command(
        {
            "inputA": "a.bed",
            "inputB": "b.bed",
            "strand": True,
            "split": True,
            "reciprocal": True,
            "overlap": 0.2,
            "overlap_b": 0.3,
            "output": "/work/bedtools_jaccard",
        }
    ) == [
        "bedtools",
        "jaccard",
        "-s",
        "-split",
        "-r",
        "-f",
        "0.2",
        "-F",
        "0.3",
        "-a",
        "a.bed",
        "-b",
        "b.bed",
        ">",
        "/work/bedtools_jaccard/jaccard.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_jaccard" / "jaccard.tsv",
    ]


def test_bedtools_fisher_renders_exact_test_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_fisher")

    assert node_class.render_command(
        {
            "inputA": "case.bed",
            "inputB": "background.bed",
            "genome": "chrom.sizes",
            "strand": "same",
            "split": True,
            "overlap": 0.5,
            "reciprocal": True,
            "merge": True,
            "output": "/work/bedtools_fisher",
        }
    ) == [
        "bedtools",
        "fisher",
        "-s",
        "-split",
        "-a",
        "case.bed",
        "-b",
        "background.bed",
        "-f",
        "0.5",
        "-g",
        "chrom.sizes",
        "-r",
        "-m",
        ">",
        "/work/bedtools_fisher/fisher.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_fisher" / "fisher.txt",
    ]


def test_bedtools_reldistbed_renders_relative_distance_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_reldistbed")

    assert node_class.render_command(
        {
            "inputA": "enhancers.bed",
            "inputB": "tss.bed",
            "detail": True,
            "output": "/work/bedtools_reldistbed",
        }
    ) == [
        "bedtools",
        "reldist",
        "-a",
        "enhancers.bed",
        "-b",
        "tss.bed",
        "-detail",
        ">",
        "/work/bedtools_reldistbed/relative_distance.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_reldistbed" / "relative_distance.tsv",
    ]


def test_bedtools_spacingbed_renders_spacing_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_spacingbed")

    assert node_class.render_command(
        {
            "input": "sorted.bed",
            "output": "/work/bedtools_spacingbed",
        }
    ) == [
        "bedtools",
        "spacing",
        "-i",
        "sorted.bed",
        ">",
        "/work/bedtools_spacingbed/spacing.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_spacingbed" / "spacing.bed",
    ]


def test_bedtools_groupbybed_renders_summary_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_groupbybed")

    assert node_class.render_command(
        {
            "inputA": "annotated.bed",
            "group": "1,2,3",
            "columns": "9",
            "operation": "median",
            "output": "/work/bedtools_groupbybed",
        }
    ) == [
        "bedtools",
        "groupby",
        "-i",
        "annotated.bed",
        "-g",
        "1,2,3",
        "-c",
        "9",
        "-o",
        "median",
        ">",
        "/work/bedtools_groupbybed/grouped.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_groupbybed" / "grouped.bed",
    ]


def test_galaxy_parity_bedtools_conversion_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_bamtobed": {
            "display_name": "BEDTools BAM to BED",
            "required_executables": ["bedtools", "samtools"],
            "required_conda_packages": ["bedtools", "samtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bamtobed.html",
        },
        "bedtools_bed12tobed6": {
            "display_name": "BEDTools BED12 to BED6",
            "required_executables": ["bed12ToBed6"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bed12tobed6.html",
        },
        "bedtools_bedtobam": {
            "display_name": "BEDTools BED to BAM",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bedtobam.html",
        },
        "bedtools_bedpetobam": {
            "display_name": "BEDTools BEDPE to BAM",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/bedpetobam.html",
        },
        "bedtools_makewindowsbed": {
            "display_name": "BEDTools Make Windows",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/makewindows.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_bamtobed_renders_bedpe_sort_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bamtobed")

    assert node_class.render_command(
        {
            "input": "alignments.bam",
            "option": "bedpe",
            "split": True,
            "ed_score": True,
            "tag": "NM",
            "threads": 6,
            "output": "/work/bedtools_bamtobed",
        }
    ) == [
        "samtools",
        "sort",
        "-n",
        "-@",
        "6",
        "-T",
        "/work/bedtools_bamtobed/tmp",
        "alignments.bam",
        ">",
        "/work/bedtools_bamtobed/input.bam",
        "&&",
        "bedtools",
        "bamtobed",
        "-bedpe",
        "-ed",
        "-split",
        "-tag",
        "NM",
        "-i",
        "/work/bedtools_bamtobed/input.bam",
        ">",
        "/work/bedtools_bamtobed/converted.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bamtobed" / "converted.bed",
    ]


def test_bedtools_bed12tobed6_renders_block_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bed12tobed6")

    assert node_class.render_command(
        {
            "input": "transcripts.bed12",
            "output": "/work/bedtools_bed12tobed6",
        }
    ) == [
        "bed12ToBed6",
        "-i",
        "transcripts.bed12",
        ">",
        "/work/bedtools_bed12tobed6/bed6.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bed12tobed6" / "bed6.bed",
    ]


def test_bedtools_bedtobam_renders_bed12_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bedtobam")

    assert node_class.render_command(
        {
            "input": "features.bed",
            "bed12": True,
            "genome": "chrom.sizes",
            "mapq": 42,
            "output": "/work/bedtools_bedtobam",
        }
    ) == [
        "bedtools",
        "bedtobam",
        "-bed12",
        "-mapq",
        "42",
        "-g",
        "chrom.sizes",
        "-i",
        "features.bed",
        ">",
        "/work/bedtools_bedtobam/converted.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bedtobam" / "converted.bam",
    ]


def test_bedtools_bedpetobam_renders_paired_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bedpetobam")

    assert node_class.render_command(
        {
            "input": "pairs.bedpe",
            "genome": "chrom.sizes",
            "mapq": 60,
            "output": "/work/bedtools_bedpetobam",
        }
    ) == [
        "bedtools",
        "bedpetobam",
        "-mapq",
        "60",
        "-i",
        "pairs.bedpe",
        "-g",
        "chrom.sizes",
        ">",
        "/work/bedtools_bedpetobam/paired.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bedpetobam" / "paired.bam",
    ]


def test_bedtools_makewindowsbed_renders_sliding_windows_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_makewindowsbed")

    assert node_class.render_command(
        {
            "type": "bed",
            "input": "regions.bed",
            "action": "windowsize",
            "windowsize": 1000,
            "step_size": 250,
            "sourcename": "srcwinnum",
            "output": "/work/bedtools_makewindowsbed",
        }
    ) == [
        "bedtools",
        "makewindows",
        "-b",
        "regions.bed",
        "-w",
        "1000",
        "-s",
        "250",
        "-i",
        "srcwinnum",
        ">",
        "/work/bedtools_makewindowsbed/windows.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_makewindowsbed" / "windows.bed",
    ]


def test_galaxy_parity_bedtools_annotation_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_annotatebed": {
            "display_name": "BEDTools Annotate",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/annotate.html",
        },
        "bedtools_expandbed": {
            "display_name": "BEDTools Expand",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/expand.html",
        },
        "bedtools_maskfastabed": {
            "display_name": "BEDTools Mask FASTA",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html",
        },
        "bedtools_multicovtbed": {
            "display_name": "BEDTools MultiCov",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/multicov.html",
        },
        "bedtools_nucbed": {
            "display_name": "BEDTools Nucleotide Content",
            "required_executables": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/nuc.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_annotatebed_renders_named_coverage_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_annotatebed")

    assert node_class.render_command(
        {
            "inputA": "regions.bed",
            "beds": ["enhancers.bed", "promoters.bed"],
            "names": ["enhancer", "promoter"],
            "strand": "same",
            "counts": True,
            "both": True,
            "output": "/work/bedtools_annotatebed",
        }
    ) == [
        "bedtools",
        "annotate",
        "-i",
        "regions.bed",
        "-files",
        "enhancers.bed",
        "promoters.bed",
        "-names",
        "enhancer",
        "promoter",
        "-s",
        "-counts",
        "-both",
        ">",
        "/work/bedtools_annotatebed/annotated.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_annotatebed" / "annotated.bed",
    ]


def test_bedtools_expandbed_renders_column_expansion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_expandbed")

    assert node_class.render_command(
        {
            "input": "tagged.bed",
            "columns": "4,5",
            "output": "/work/bedtools_expandbed",
        }
    ) == [
        "bedtools",
        "expand",
        "-c",
        "4,5",
        "-i",
        "tagged.bed",
        ">",
        "/work/bedtools_expandbed/expanded.bed",
    ]

    assert node_class.PLAN_OUTPUTS({"input": "tagged.gff3"}, tmp_path) == [
        tmp_path / "bedtools_expandbed" / "expanded.gff",
    ]


def test_bedtools_maskfastabed_renders_soft_mask_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_maskfastabed")

    assert node_class.render_command(
        {
            "input": "mask_regions.bed",
            "fasta": "genome.fa",
            "soft": True,
            "mask_character": "X",
            "full_header": True,
            "output": "/work/bedtools_maskfastabed",
        }
    ) == [
        "bedtools",
        "maskfasta",
        "-soft",
        "-mc",
        "X",
        "-fi",
        "genome.fa",
        "-bed",
        "mask_regions.bed",
        "-fo",
        "/work/bedtools_maskfastabed/masked.fasta",
        "-fullHeader",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_maskfastabed" / "masked.fasta",
    ]


def test_bedtools_multicovtbed_renders_bam_count_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_multicovtbed")

    assert node_class.render_command(
        {
            "input": "targets.bed",
            "bams": ["case.bam", "control.bam"],
            "strand": "opposite",
            "overlap": 0.5,
            "reciprocal": True,
            "split": True,
            "q": 20,
            "duplicate": True,
            "failed": True,
            "proper": True,
            "output": "/work/bedtools_multicovtbed",
        }
    ) == [
        "bedtools",
        "multicov",
        "-bed",
        "targets.bed",
        "-bams",
        "case.bam",
        "control.bam",
        "-S",
        "-f",
        "0.5",
        "-r",
        "-split",
        "-q",
        "20",
        "-D",
        "-F",
        "-p",
        ">",
        "/work/bedtools_multicovtbed/multicov.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_multicovtbed" / "multicov.bed",
    ]


def test_bedtools_nucbed_renders_sequence_pattern_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_nucbed")

    assert node_class.render_command(
        {
            "input": "regions.bed",
            "fasta": "genome.fa",
            "strand": True,
            "seq": True,
            "pattern": "TAC",
            "ignore_case": True,
            "output": "/work/bedtools_nucbed",
        }
    ) == [
        "bedtools",
        "nuc",
        "-s",
        "-seq",
        "-pattern",
        "TAC",
        "-C",
        "-fi",
        "genome.fa",
        "-bed",
        "regions.bed",
        ">",
        "/work/bedtools_nucbed/nucleotide_content.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_nucbed" / "nucleotide_content.tsv",
    ]


def test_galaxy_parity_bedtools_randomization_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_randombed": {
            "display_name": "BEDTools Random",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/random.html",
        },
        "bedtools_shufflebed": {
            "display_name": "BEDTools Shuffle",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/shuffle.html",
        },
        "bedtools_unionbedgraph": {
            "display_name": "BEDTools Union BedGraph",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/unionbedg.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == ["bedtools"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_randombed_renders_seeded_interval_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_randombed")

    assert node_class.render_command(
        {
            "genome": "chrom.sizes",
            "length": 250,
            "intervals": 1000,
            "seed": 17,
            "output": "/work/bedtools_randombed",
        }
    ) == [
        "bedtools",
        "random",
        "-g",
        "chrom.sizes",
        "-l",
        "250",
        "-n",
        "1000",
        "-seed",
        "17",
        ">",
        "/work/bedtools_randombed/random.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_randombed" / "random.bed",
    ]


def test_bedtools_shufflebed_renders_excluded_same_chromosome_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_shufflebed")

    assert node_class.render_command(
        {
            "inputA": "peaks.bed",
            "genome": "chrom.sizes",
            "bedpe": True,
            "seed": 23,
            "exclude": "gaps.bed",
            "overlap": 0.2,
            "chrom": True,
            "chromfirst": True,
            "no_overlap": True,
            "allow_beyond": True,
            "maxtries": 5000,
            "output": "/work/bedtools_shufflebed",
        }
    ) == [
        "bedtools",
        "shuffle",
        "-g",
        "chrom.sizes",
        "-i",
        "peaks.bed",
        "-bedpe",
        "-seed",
        "23",
        "-excl",
        "gaps.bed",
        "-f",
        "0.2",
        "-chrom",
        "-chromFirst",
        "-noOverlapping",
        "-allowBeyondChromEnd",
        "-maxTries",
        "5000",
        ">",
        "/work/bedtools_shufflebed/shuffled.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_shufflebed" / "shuffled.bed",
    ]


def test_bedtools_unionbedgraph_renders_named_empty_union_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_unionbedgraph")

    assert node_class.render_command(
        {
            "inputs": ["sample1.bg", "sample2.bg"],
            "names": ["case", "control"],
            "header": True,
            "filler": "0",
            "empty": True,
            "genome": "chrom.sizes",
            "output": "/work/bedtools_unionbedgraph",
        }
    ) == [
        "bedtools",
        "unionbedg",
        "-header",
        "-filler",
        "0",
        "-empty",
        "-g",
        "chrom.sizes",
        "-i",
        "sample1.bg",
        "sample2.bg",
        "-names",
        "case",
        "control",
        ">",
        "/work/bedtools_unionbedgraph/union.bedgraph",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_unionbedgraph" / "union.bedgraph",
    ]


def test_galaxy_parity_bedtools_overlap_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_closestbed": {
            "display_name": "BEDTools ClosestBed",
            "required_executables": ["closestBed"],
            "required_conda_packages": ["bedtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html",
        },
        "bedtools_intersectbed": {
            "display_name": "BEDTools Intersect Intervals",
            "required_executables": ["bedtools"],
            "required_conda_packages": ["bedtools", "samtools"],
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]


def test_bedtools_closestbed_renders_distance_mode_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_closestbed")

    assert node_class.render_command(
        {
            "inputA": "query.bed",
            "inputB": ["genes.bed", "enhancers.bed"],
            "strand": "opposite",
            "distance": True,
            "distance_mode": "a",
            "ignore_upstream": True,
            "first_upstream": True,
            "ignore_overlaps": True,
            "mdb": "all",
            "ties": "first",
            "k": 3,
            "output": "/work/bedtools_closestbed",
        }
    ) == [
        "closestBed",
        "-S",
        "-d",
        "-D",
        "a",
        "-iu",
        "-fu",
        "-io",
        "-mdb",
        "all",
        "-t",
        "first",
        "-k",
        "3",
        "-a",
        "query.bed",
        "-b",
        "genes.bed",
        "enhancers.bed",
        ">",
        "/work/bedtools_closestbed/closest.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_closestbed" / "closest.bed",
    ]


def test_bedtools_intersectbed_renders_reduced_named_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_intersectbed")

    assert node_class.render_command(
        {
            "inputA": "reads.bam",
            "inputB": ["promoters.bed", "enhancers.bed"],
            "names": ["promoters", "enhancers"],
            "overlap_mode": ["-wa", "-wb"],
            "split": True,
            "strand": "same",
            "overlap": 0.5,
            "overlap_b": 0.25,
            "either_fraction": True,
            "invert": True,
            "once": True,
            "header": True,
            "sorted": True,
            "genome": "chrom.sizes",
            "bed": True,
            "count": True,
            "output": "/work/bedtools_intersectbed",
        }
    ) == [
        "bedtools",
        "intersect",
        "-a",
        "reads.bam",
        "-b",
        "promoters.bed",
        "enhancers.bed",
        "-names",
        "promoters",
        "enhancers",
        "-split",
        "-s",
        "-f",
        "0.5",
        "-F",
        "0.25",
        "-e",
        "-v",
        "-u",
        "-header",
        "-wa",
        "-wb",
        "-sorted",
        "-g",
        "chrom.sizes",
        "-bed",
        "-c",
        ">",
        "/work/bedtools_intersectbed/intersect.bed",
    ]

    assert node_class.PLAN_OUTPUTS({"bed": True}, tmp_path) == [
        tmp_path / "bedtools_intersectbed" / "intersect.bed",
    ]
