from __future__ import annotations

import asyncio
import sys
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
        "seqkit_grep": {
            "display_name": "SeqKit Grep",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_head": {
            "display_name": "SeqKit Head",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_fx2tab": {
            "display_name": "SeqKit fx2tab",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_sort": {
            "display_name": "SeqKit Sort",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_locate": {
            "display_name": "SeqKit Locate",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_translate": {
            "display_name": "SeqKit Translate",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "seqkit_split2": {
            "display_name": "SeqKit Split2",
            "category": "sequence",
            "required_executables": ["seqkit"],
            "required_conda_packages": ["seqkit"],
            "doi": "10.1371/journal.pone.0163962",
        },
        "amrfinderplus": {
            "display_name": "AMRFinderPlus",
            "category": "annotation",
            "required_executables": ["amrfinder"],
            "required_conda_packages": ["ncbi-amrfinderplus"],
            "doi": "10.1038/s41598-021-91456-0",
        },
        "checkm2": {
            "display_name": "CheckM2",
            "category": "qc",
            "required_executables": ["checkm2"],
            "required_conda_packages": ["checkm2"],
            "doi": "10.1038/s41592-023-01940-w",
        },
        "das_tool": {
            "display_name": "DAS Tool",
            "category": "metagenomics",
            "required_executables": ["DAS_Tool"],
            "required_conda_packages": ["das_tool"],
            "doi": "10.1038/s41564-018-0171-1",
        },
        "fasta_to_contig2bin": {
            "display_name": "FASTA to Contig2Bin",
            "category": "metagenomics",
            "required_executables": ["Fasta_to_Contig2Bin.sh"],
            "required_conda_packages": ["das_tool"],
            "doi": "10.1038/s41564-018-0171-1",
        },
        "bandage_info": {
            "display_name": "Bandage Info",
            "category": "assembly",
            "required_executables": ["Bandage"],
            "required_conda_packages": ["bandage_ng"],
            "doi": "10.1093/bioinformatics/btv383",
        },
        "bandage_image": {
            "display_name": "Bandage Image",
            "category": "visualization",
            "required_executables": ["Bandage"],
            "required_conda_packages": ["bandage_ng"],
            "doi": "10.1093/bioinformatics/btv383",
        },
        "adapter_removal": {
            "display_name": "AdapterRemoval",
            "category": "trimming",
            "required_executables": ["AdapterRemoval"],
            "required_conda_packages": ["adapterremoval"],
            "doi": "10.1186/s13104-016-1900-2",
        },
        "assembly_stats": {
            "display_name": "Assembly Stats",
            "category": "assembly",
            "required_executables": ["asm2stats.minmaxgc.pl"],
            "required_conda_packages": ["rjchallis-assembly-stats"],
            "doi": "10.5281/zenodo.322347",
        },
        "amas_summary": {
            "display_name": "AMAS Summary",
            "category": "phylogeny",
            "required_executables": ["python"],
            "required_conda_packages": ["amas"],
            "doi": "10.7717/peerj.1660",
        },
        "amas_concat": {
            "display_name": "AMAS Concat",
            "category": "phylogeny",
            "required_executables": ["python"],
            "required_conda_packages": ["amas"],
            "doi": "10.7717/peerj.1660",
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
        "vsearch_dereplication": {
            "display_name": "VSEARCH Dereplication",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_masking": {
            "display_name": "VSEARCH Masking",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_shuffling": {
            "display_name": "VSEARCH Shuffling",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_sorting": {
            "display_name": "VSEARCH Sorting",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_alignment": {
            "display_name": "VSEARCH Alignment",
            "category": "metagenomics",
            "required_executables": ["vsearch"],
            "required_conda_packages": ["vsearch"],
            "doi": "10.7717/peerj.2584",
        },
        "vsearch_chimera_detection": {
            "display_name": "VSEARCH Chimera Detection",
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
        "hmmer_hmmalign": {
            "display_name": "HMMER hmmalign",
            "category": "alignment",
            "required_executables": ["hmmalign"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmbuild": {
            "display_name": "HMMER hmmbuild",
            "category": "annotation",
            "required_executables": ["hmmbuild"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmconvert": {
            "display_name": "HMMER hmmconvert",
            "category": "annotation",
            "required_executables": ["hmmconvert"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmemit": {
            "display_name": "HMMER hmmemit",
            "category": "annotation",
            "required_executables": ["hmmemit"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_hmmfetch": {
            "display_name": "HMMER hmmfetch",
            "category": "annotation",
            "required_executables": ["hmmfetch"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_jackhmmer": {
            "display_name": "HMMER jackhmmer",
            "category": "annotation",
            "required_executables": ["jackhmmer"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_phmmer": {
            "display_name": "HMMER phmmer",
            "category": "annotation",
            "required_executables": ["phmmer"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
        },
        "hmmer_nhmmer": {
            "display_name": "HMMER nhmmer",
            "category": "annotation",
            "required_executables": ["nhmmer"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/bioinformatics/btt403",
        },
        "hmmer_alimask": {
            "display_name": "HMMER alimask",
            "category": "annotation",
            "required_executables": ["alimask"],
            "required_conda_packages": ["hmmer"],
            "doi": "10.1093/nar/gkr367",
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


def test_seqkit_grep_exposes_sequence_and_count_outputs() -> None:
    info = _registry().object_info()["seqkit_grep"]

    assert info["output"] == ["FASTQ", "FASTA", "STATS_FILE"]
    assert info["output_name"] == ["fastq_output", "fasta_output", "count"]


def test_seqkit_grep_renders_sequence_expression_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_grep")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "pattern_mode": "expression",
            "pattern": "ATGC",
            "by_seq": True,
            "max_mismatch": 2,
            "ignore_case": True,
            "only_positive_strand": True,
            "region": "1:120",
            "threads": 6,
            "output_ext": "fastq.gz",
            "output": "/work/seqkit_grep",
        }
    ) == [
        "seqkit",
        "grep",
        "--threads",
        "6",
        "--pattern",
        "ATGC",
        "--by-seq",
        "--ignore-case",
        "--max-mismatch",
        "2",
        "--only-positive-strand",
        "--region",
        "1:120",
        "reads.fastq.gz",
        ">",
        "/work/seqkit_grep/grep.fastq.gz",
    ]
    assert node_class.PLAN_OUTPUTS({"output_ext": "fastq.gz"}, tmp_path) == [
        tmp_path / "seqkit_grep" / "grep.fastq.gz",
    ]


def test_seqkit_grep_renders_pattern_file_count_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_grep")

    assert node_class.render_command(
        {
            "input": "records.fasta.gz",
            "pattern_mode": "file",
            "pattern_file": "patterns.txt",
            "allow_duplicated_patterns": True,
            "by_name": True,
            "circular": True,
            "count": True,
            "degenerate": True,
            "delete_matched": True,
            "invert_match": True,
            "threads": 4,
            "output": "/work/seqkit_grep",
        }
    ) == [
        "seqkit",
        "grep",
        "--threads",
        "4",
        "--pattern-file",
        "patterns.txt",
        "--allow-duplicated-patterns",
        "--by-name",
        "--circular",
        "--count",
        "--degenerate",
        "--delete-matched",
        "--invert-match",
        "records.fasta.gz",
        ">",
        "/work/seqkit_grep/count.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"count": True}, tmp_path) == [
        tmp_path / "seqkit_grep" / "count.txt",
    ]


def test_seqkit_head_exposes_galaxy_aligned_output_and_citation() -> None:
    info = _registry().object_info()["seqkit_head"]

    assert info["output"] == ["FASTQ"]
    assert info["output_name"] == ["head_output"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_head_renders_head_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_head")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "number": 25,
            "threads": 8,
            "output_ext": "fastq.gz",
            "output": "/work/seqkit_head",
        }
    ) == (
        "ln -sf reads.fastq.gz input.fastq.gz && "
        "seqkit head input.fastq.gz --number 25 -o /work/seqkit_head/head.fastq.gz --threads 8"
    )
    assert node_class.PLAN_OUTPUTS({"output_ext": "fastq.gz"}, tmp_path) == [
        tmp_path / "seqkit_head" / "head.fastq.gz",
    ]


def test_seqkit_fx2tab_exposes_galaxy_aligned_output_and_citation() -> None:
    info = _registry().object_info()["seqkit_fx2tab"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["tabular"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_fx2tab_renders_rich_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_fx2tab")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "input_ext": "fastqsanger.gz",
            "alphabet": True,
            "avg_qual": True,
            "base_percentages": ["A", "T"],
            "base_counts": ["A", "N"],
            "gc": True,
            "gc_skew": True,
            "header_line": True,
            "length": True,
            "name": True,
            "no_qual": True,
            "only_id": True,
            "seq_hash": True,
            "qual_ascii_base": 33,
            "output": "/work/seqkit_fx2tab",
        }
    ) == (
        "ln -sf reads.fastq.gz input.fastqsanger.gz && "
        "seqkit fx2tab input.fastqsanger.gz --alphabet --avg-qual -B AT -C AN --gc --gc-skew "
        "--header-line --length --name --no-qual --only-id --qual-ascii-base 33 --seq-hash "
        "> /work/seqkit_fx2tab/fx2tab.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "seqkit_fx2tab" / "fx2tab.tsv",
    ]


def test_seqkit_sort_exposes_galaxy_aligned_output_and_citation() -> None:
    info = _registry().object_info()["seqkit_sort"]

    assert info["output"] == ["FASTQ"]
    assert info["output_name"] == ["sorted_sequences"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_sort_renders_sort_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_sort")

    assert node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "input_ext": "fastq.gz",
            "output_ext": "fastq.gz",
            "sort_by": "--by-seq",
            "reverse": True,
            "threads": 12,
            "output": "/work/seqkit_sort",
        }
    ) == (
        "ln -sf reads.fastq.gz input.fastq.gz && "
        "seqkit sort input.fastq.gz --reverse --by-seq -o /work/seqkit_sort/sorted.fastq.gz --threads 12"
    )
    assert node_class.PLAN_OUTPUTS({"output_ext": "fasta.gz"}, tmp_path) == [
        tmp_path / "seqkit_sort" / "sorted.fasta.gz",
    ]


def test_seqkit_locate_exposes_galaxy_aligned_outputs_and_citation() -> None:
    info = _registry().object_info()["seqkit_locate"]

    assert info["output"] == ["TSV", "BED", "GFF_GTF"]
    assert info["output_name"] == ["tabular", "bed", "gtf"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_locate_renders_expression_bed_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_locate")

    assert node_class.render_command(
        {
            "input": "genome.fasta.gz",
            "input_ext": "fasta.gz",
            "pattern_mode": "expression",
            "pattern": "A[TU]G",
            "use_regexp": True,
            "output_mode": "--bed",
            "circular": True,
            "hide_matched": True,
            "ignore_case": True,
            "max_mismatch": 1,
            "only_positive_strand": True,
            "id_ncbi": True,
            "seq_type": "dna",
            "threads": 8,
            "output": "/work/seqkit_locate",
        }
    ) == (
        "ln -sf genome.fasta.gz input.fasta.gz && "
        "seqkit locate --threads 8 --pattern 'A[TU]G' --use-regexp --bed --circular "
        "--hide-matched --ignore-case --max-mismatch 1 --only-positive-strand --id-ncbi "
        "--seq-type dna input.fasta.gz > /work/seqkit_locate/locate.bed"
    )
    assert node_class.PLAN_OUTPUTS({"output_mode": "--bed"}, tmp_path) == [
        tmp_path / "seqkit_locate" / "locate.bed",
    ]


def test_seqkit_locate_renders_pattern_file_gtf_command_without_incompatible_fmi(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_locate")

    command = node_class.render_command(
        {
            "input": "records.fasta",
            "input_ext": "fasta",
            "pattern_mode": "file",
            "pattern_file": "motifs.fasta",
            "output_mode": "--gtf",
            "degenerate": True,
            "max_mismatch": 2,
            "use_fmi": True,
            "non_greedy": True,
            "seq_type": "protein",
            "threads": 4,
            "output": "/work/seqkit_locate",
        }
    )

    assert command == (
        "ln -sf records.fasta input.fasta && "
        "seqkit locate --threads 4 --pattern-file motifs.fasta --gtf --degenerate "
        "--non-greedy --seq-type protein input.fasta > /work/seqkit_locate/locate.gtf"
    )
    assert "--max-mismatch" not in command
    assert "--use-fmi" not in command
    assert node_class.PLAN_OUTPUTS({"output_mode": "--gtf"}, tmp_path) == [
        tmp_path / "seqkit_locate" / "locate.gtf",
    ]


def test_seqkit_translate_exposes_galaxy_aligned_outputs_and_citation() -> None:
    info = _registry().object_info()["seqkit_translate"]

    assert info["output"] == ["FASTA", "FASTQ"]
    assert info["output_name"] == ["translated_fasta", "translated_fastq"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_translate_renders_multiframe_unknown_codon_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_translate")

    assert node_class.render_command(
        {
            "input": "cds.fasta.gz",
            "frame": ["2", "3"],
            "unknown_action": "translate",
            "allow_unknown_codon": True,
            "append_frame": True,
            "clean": True,
            "init_codon_as_M": True,
            "transl_table": "3",
            "output_ext": "fasta.gz",
            "output": "/work/seqkit_translate",
        }
    ) == [
        "seqkit",
        "translate",
        "cds.fasta.gz",
        "-o",
        "/work/seqkit_translate/translated.fasta.gz",
        "--allow-unknown-codon",
        "--append-frame",
        "--clean",
        "-f",
        "2,3",
        "--init-codon-as-M",
        "-T",
        "3",
    ]
    assert node_class.PLAN_OUTPUTS({"output_ext": "fasta.gz"}, tmp_path) == [
        tmp_path / "seqkit_translate" / "translated.fasta.gz",
    ]


def test_seqkit_translate_renders_trim_fastq_command_without_unknown_translation(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_translate")

    command = node_class.render_command(
        {
            "input": "reads.fastq.gz",
            "unknown_action": "trimming",
            "trim": True,
            "allow_unknown_codon": True,
            "output_ext": "fastq.gz",
            "output": "/work/seqkit_translate",
        }
    )

    assert command == [
        "seqkit",
        "translate",
        "reads.fastq.gz",
        "-o",
        "/work/seqkit_translate/translated.fastq.gz",
        "--trim",
        "-f",
        "1",
        "-T",
        "1",
    ]
    assert "--allow-unknown-codon" not in command
    assert node_class.PLAN_OUTPUTS({"output_ext": "fastq.gz"}, tmp_path) == [
        tmp_path / "seqkit_translate" / "translated.fastq.gz",
    ]


def test_seqkit_split2_exposes_galaxy_aligned_directory_outputs_and_citation() -> None:
    info = _registry().object_info()["seqkit_split2"]

    assert info["output"] == ["DIRECTORY", "DIRECTORY"]
    assert info["output_name"] == ["split_files", "paired_split_files"]
    assert info["citation_dois"] == ["10.1371/journal.pone.0163962"]
    assert info["required_executables"] == ["seqkit"]
    assert info["required_conda_packages"] == ["seqkit"]


def test_seqkit_split2_renders_single_length_split_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_split2")

    assert node_class.render_command(
        {
            "input_type": "single",
            "input_1": "hairpin.fa.gz",
            "input_1_ext": "fasta.gz",
            "split_selector": "by_length",
            "by_length": "50K",
            "threads": 6,
            "output": "/work/seqkit_split2",
        }
    ) == (
        "mkdir -p /work/seqkit_split2/split_files && "
        "ln -sf hairpin.fa.gz input.fasta.gz && "
        "seqkit split2 input.fasta.gz -l 50K -o seqkit_split2 "
        "-O /work/seqkit_split2/split_files -j 6"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "single"}, tmp_path) == [
        tmp_path / "seqkit_split2" / "split_files",
    ]


def test_seqkit_split2_renders_paired_part_split_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("seqkit_split2")

    assert node_class.render_command(
        {
            "input_type": "paired_collection",
            "input_1": "reads_1.fq.gz",
            "input_2": "reads_2.fq.gz",
            "input_1_ext": "fastqsanger.gz",
            "input_2_ext": "fastqsanger.gz",
            "split_selector": "by_part",
            "by_part": 2,
            "threads": 8,
            "output": "/work/seqkit_split2",
        }
    ) == (
        "mkdir -p /work/seqkit_split2/paired_split_files && "
        "ln -sf reads_1.fq.gz input_1.fastqsanger.gz && "
        "ln -sf reads_2.fq.gz input_2.fastqsanger.gz && "
        "seqkit split2 -1 input_1.fastqsanger.gz -2 input_2.fastqsanger.gz "
        "-p 2 --by-part-prefix 'seqkit_split2_R{read}_' -o seqkit_split2 "
        "-O /work/seqkit_split2/paired_split_files -j 8 && "
        "(find /work/seqkit_split2/paired_split_files/ -type f -name 'seqkit_split2_*.*' | "
        "while read -r file; do mv \"$file\" \"$(echo \"$file\" | "
        "sed -E 's/(seqkit_split2)_(R1|R2)_([0-9]+)(\\..+)/\\1_\\3_\\2\\4/' | "
        "sed -E 's/_R1/_forward/; s/_R2/_reverse/')\"; done)"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "paired_collection"}, tmp_path) == [
        tmp_path / "seqkit_split2" / "paired_split_files",
    ]


def test_amrfinderplus_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amrfinderplus"]

    assert info["output"] == ["TSV", "TSV", "FASTA", "FASTA", "FASTA"]
    assert info["output_name"] == [
        "amrfinderplus_report",
        "mutation_all_report",
        "protein_output",
        "nucleotide_output",
        "nucleotide_flank5_output",
    ]


def test_amrfinderplus_renders_nucleotide_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amrfinderplus")

    assert node_class.render_command(
        {
            "database": "/db/amrfinderplus/latest",
            "input_select": "nucleotide",
            "nucleotide_input": "enterococcus_faecalis.fna",
            "nucleotide_flank5_size": 150,
            "organism_select": "add_organism",
            "organism": "Enterococcus_faecalis",
            "plus": True,
            "report_common": True,
            "ident_min": 0.1,
            "coverage_min": 0.1,
            "translation_table": "11",
            "report_all_equal": True,
            "print_node": True,
            "name": "sample_1",
            "threads": 8,
            "output": "/work/amrfinderplus",
        }
    ) == [
        "amrfinder",
        "--threads",
        "8",
        "--database",
        "/db/amrfinderplus/latest",
        "--nucleotide",
        "enterococcus_faecalis.fna",
        "--nucleotide_flank5_size",
        "150",
        "--nucleotide_flank5_output",
        "/work/amrfinderplus/amrfinderplus_flanking_sequence_output.fasta",
        "--nucleotide_output",
        "/work/amrfinderplus/amrfinderplus_nucleotide_output.fasta",
        "--organism",
        "Enterococcus_faecalis",
        "--report_common",
        "--ident_min",
        "0.1",
        "--coverage_min",
        "0.1",
        "--translation_table",
        "11",
        "--name",
        "sample_1",
        "--plus",
        "--report_all_equal",
        "--print_node",
        "--output",
        "/work/amrfinderplus/amrfinderplus_report.tsv",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"input_select": "nucleotide", "nucleotide_flank5_size": 150},
        tmp_path,
    ) == [
        tmp_path / "amrfinderplus" / "amrfinderplus_report.tsv",
        tmp_path / "amrfinderplus" / "amrfinderplus_nucleotide_output.fasta",
        tmp_path / "amrfinderplus" / "amrfinderplus_flanking_sequence_output.fasta",
    ]


def test_amrfinderplus_renders_combined_mode_with_mutation_and_version_columns(tmp_path: Path) -> None:
    node_class = _node_class("amrfinderplus")

    assert node_class.render_command(
        {
            "database": "/db/amrfinderplus/V4.2-2026-05-15.1",
            "database_name": "V4.2-2026-05-15.1",
            "input_select": "nucl_prot",
            "nucleotide_input": "e_faecalis_rast.fna",
            "protein_input": "e_faecalis_rast.faa",
            "gff_annotation": "e_faecalis_rast.gff",
            "annotation_format": "rast",
            "organism_select": "add_organism",
            "organism": "Enterococcus_faecalis",
            "mutation_all": True,
            "ident_min": 0.1,
            "coverage_min": 0.1,
            "plus": True,
            "print_node": True,
            "name": "test_5",
            "add_version_columns": True,
            "threads": 4,
            "output": "/work/amrfinderplus",
        }
    ) == [
        "amrfinder",
        "--threads",
        "4",
        "--database",
        "/db/amrfinderplus/V4.2-2026-05-15.1",
        "--nucleotide",
        "e_faecalis_rast.fna",
        "--protein",
        "e_faecalis_rast.faa",
        "--gff",
        "e_faecalis_rast.gff",
        "--annotation_format",
        "rast",
        "--nucleotide_output",
        "/work/amrfinderplus/amrfinderplus_nucleotide_output.fasta",
        "--protein_output",
        "/work/amrfinderplus/amrfinderplus_protein_output.fasta",
        "--organism",
        "Enterococcus_faecalis",
        "--mutation_all",
        "/work/amrfinderplus/mutation_all_report.tsv",
        "--ident_min",
        "0.1",
        "--coverage_min",
        "0.1",
        "--name",
        "test_5",
        "--plus",
        "--print_node",
        "--output",
        "/work/amrfinderplus/amrfinderplus_report.tsv",
        "&&",
        "python",
        "-c",
        (
            "from pathlib import Path\n"
            "tool_version = '4.2.7'\n"
            "database = Path('/db/amrfinderplus/V4.2-2026-05-15.1')\n"
            "database_version = (database / 'version.txt').read_text().strip() if (database / 'version.txt').is_file() else 'V4.2-2026-05-15.1'\n"
            "for report in [Path('/work/amrfinderplus/amrfinderplus_report.tsv'), Path('/work/amrfinderplus/mutation_all_report.tsv')]:\n"
            "    if not report.is_file() or report.stat().st_size == 0:\n"
            "        continue\n"
            "    lines = report.read_text().splitlines()\n"
            "    if not lines:\n"
            "        continue\n"
            "    updated = [lines[0] + '\\tDatabase version\\tTool version']\n"
            "    updated.extend(line + '\\t' + database_version + '\\t' + tool_version for line in lines[1:])\n"
            "    report.write_text('\\n'.join(updated) + '\\n')\n"
        ),
    ]
    assert node_class.PLAN_OUTPUTS(
        {"input_select": "nucl_prot", "organism_select": "add_organism", "mutation_all": True},
        tmp_path,
    ) == [
        tmp_path / "amrfinderplus" / "amrfinderplus_report.tsv",
        tmp_path / "amrfinderplus" / "mutation_all_report.tsv",
        tmp_path / "amrfinderplus" / "amrfinderplus_protein_output.fasta",
        tmp_path / "amrfinderplus" / "amrfinderplus_nucleotide_output.fasta",
    ]


def test_checkm2_exposes_quality_and_discovered_output_collections() -> None:
    info = _registry().object_info()["checkm2"]

    assert info["output"] == ["TSV", "FASTA_LIST", "TSV_LIST"]
    assert info["output_name"] == ["quality", "protein_files", "diamond_files"]


def test_checkm2_renders_protein_all_models_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("checkm2")

    assert node_class.render_command(
        {
            "input": ["test1.faa", "test2.faa"],
            "database_path": "/db/checkm2/uniref100.KO.1.dmnd",
            "model": "--allmodels",
            "genes": True,
            "ttable": "13",
            "threads": 12,
            "output": "/work/checkm2",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/checkm2/input_dir",
        "/work/checkm2/output",
        "&&",
        "ln",
        "-sf",
        "test1.faa",
        "/work/checkm2/input_dir/test1.faa.dat",
        "&&",
        "ln",
        "-sf",
        "test2.faa",
        "/work/checkm2/input_dir/test2.faa.dat",
        "&&",
        "checkm2",
        "predict",
        "--input",
        "/work/checkm2/input_dir",
        "--allmodels",
        "--genes",
        "--ttable",
        "13",
        "-x",
        ".dat",
        "--threads",
        "12",
        "--database_path",
        "/db/checkm2/uniref100.KO.1.dmnd",
        "--output-directory",
        "/work/checkm2/output",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "checkm2" / "output" / "quality_report.tsv",
        tmp_path / "checkm2" / "output" / "protein_files",
        tmp_path / "checkm2" / "output" / "diamond_output",
    ]


def test_checkm2_renders_specific_model_command_with_safe_input_names() -> None:
    node_class = _node_class("checkm2")

    assert node_class.render_command(
        {
            "input": ["MAG 01.fna", "bin#2.fa.gz"],
            "database_path": "/db/checkm2/current.dmnd",
            "model": "--specific",
            "genes": False,
            "threads": 4,
            "output": "/work/checkm2",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/checkm2/input_dir",
        "/work/checkm2/output",
        "&&",
        "ln",
        "-sf",
        "MAG 01.fna",
        "/work/checkm2/input_dir/MAG_01.fna.dat",
        "&&",
        "ln",
        "-sf",
        "bin#2.fa.gz",
        "/work/checkm2/input_dir/bin_2.fa.gz.dat",
        "&&",
        "checkm2",
        "predict",
        "--input",
        "/work/checkm2/input_dir",
        "--specific",
        "-x",
        ".dat",
        "--threads",
        "4",
        "--database_path",
        "/db/checkm2/current.dmnd",
        "--output-directory",
        "/work/checkm2/output",
    ]


def test_das_tool_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["das_tool"]

    assert info["output"] == ["TSV", "TSV", "TEXT", "TSV", "FASTA_LIST", "FASTA", "FASTA"]
    assert info["output_name"] == [
        "summary",
        "contigs2bin",
        "log",
        "eval",
        "bins",
        "unbinned_contigs",
        "proteins",
    ]


def test_das_tool_renders_command_with_proteins_and_binning_labels(tmp_path: Path) -> None:
    node_class = _node_class("das_tool")

    assert node_class.render_command(
        {
            "contigs": "assembly.fasta",
            "bins": ["metabat.tabular", "MaxBin bins.tsv"],
            "labels": ["", "max bin!"],
            "proteins": "predicted proteins.faa",
            "search_engine": "blastp",
            "score_threshold": 0.6,
            "duplicate_penalty": 0.7,
            "megabin_penalty": 0.2,
            "max_iter_post_threshold": 12,
            "write_bin_evals": True,
            "write_bins": "",
            "write_unbinned": True,
            "debug": True,
            "threads": 8,
            "output": "/work/das_tool",
        }
    ) == [
        "ln",
        "-sf",
        "predicted proteins.faa",
        "/work/das_tool/proteins",
        "&&",
        "DAS_Tool",
        "--contigs",
        "assembly.fasta",
        "--outputbasename",
        "/work/das_tool/outputs",
        "--bins",
        "metabat.tabular,MaxBin bins.tsv",
        "--labels",
        "metabat.tabular,max_bin_",
        "--search_engine",
        "blastp",
        "--proteins",
        "/work/das_tool/proteins",
        "--score_threshold",
        "0.6",
        "--duplicate_penalty",
        "0.7",
        "--megabin_penalty",
        "0.2",
        "--max_iter_post_threshold",
        "12",
        "--write_bin_evals",
        "--debug",
        "--threads",
        "8",
    ]
    assert node_class.PLAN_OUTPUTS({"write_bin_evals": True, "write_bins": ""}, tmp_path) == [
        tmp_path / "das_tool" / "outputs_DASTool_summary.tsv",
        tmp_path / "das_tool" / "outputs_DASTool_contig2bin.tsv",
        tmp_path / "das_tool" / "outputs_DASTool.log",
        tmp_path / "das_tool" / "outputs_allBins.eval",
    ]


def test_das_tool_plans_optional_bins_unbinned_and_proteins_outputs(tmp_path: Path) -> None:
    node_class = _node_class("das_tool")

    assert node_class.render_command(
        {
            "contigs": "assembly.fasta",
            "binning": [
                {"bins": "metabat.tabular", "labels": "metabat"},
                {"bins": "concoct table.tsv", "labels": "concoct"},
            ],
            "search_engine": "diamond",
            "score_threshold": 0.5,
            "duplicate_penalty": 0.6,
            "megabin_penalty": 0.5,
            "max_iter_post_threshold": 10,
            "output_proteins": True,
            "write_bins": "--write_bins",
            "write_unbinned": True,
            "threads": 4,
            "output": "/work/das_tool",
        }
    ) == [
        "DAS_Tool",
        "--contigs",
        "assembly.fasta",
        "--outputbasename",
        "/work/das_tool/outputs",
        "--bins",
        "metabat.tabular,concoct table.tsv",
        "--labels",
        "metabat,concoct",
        "--search_engine",
        "diamond",
        "--score_threshold",
        "0.5",
        "--duplicate_penalty",
        "0.6",
        "--megabin_penalty",
        "0.5",
        "--max_iter_post_threshold",
        "10",
        "--write_bins",
        "--write_unbinned",
        "--threads",
        "4",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"output_proteins": True, "write_bins": "--write_bins", "write_unbinned": True},
        tmp_path,
    ) == [
        tmp_path / "das_tool" / "outputs_DASTool_summary.tsv",
        tmp_path / "das_tool" / "outputs_DASTool_contig2bin.tsv",
        tmp_path / "das_tool" / "outputs_DASTool.log",
        tmp_path / "das_tool" / "outputs_DASTool_bins",
        tmp_path / "das_tool" / "outputs_DASTool_bins" / "unbinned.fa",
        tmp_path / "das_tool" / "outputs_proteins.faa",
    ]


def test_fasta_to_contig2bin_exposes_single_tabular_output() -> None:
    info = _registry().object_info()["fasta_to_contig2bin"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["contigs2bin"]


def test_fasta_to_contig2bin_renders_galaxy_helper_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("fasta_to_contig2bin")

    assert node_class.render_command(
        {
            "inputs": ["maxbin2.001.fa", "bin set/002.fa"],
            "element_identifiers": ["001", "bin/set 002"],
            "output": "/work/fasta_to_contig2bin",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/fasta_to_contig2bin/inputs",
        "&&",
        "ln",
        "-sf",
        "maxbin2.001.fa",
        "/work/fasta_to_contig2bin/inputs/001.fasta",
        "&&",
        "ln",
        "-sf",
        "bin set/002.fa",
        "/work/fasta_to_contig2bin/inputs/bin_set_002.fasta",
        "&&",
        "Fasta_to_Contig2Bin.sh",
        "--extension",
        "fasta",
        "--input_folder",
        "/work/fasta_to_contig2bin/inputs",
        ">",
        "/work/fasta_to_contig2bin/contigs2bin.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "fasta_to_contig2bin" / "contigs2bin.tsv",
    ]


def test_bandage_nodes_expose_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()

    assert info["bandage_info"]["output"] == ["TSV"]
    assert info["bandage_info"]["output_name"] == ["outfile"]
    assert info["bandage_image"]["output"] == ["IMAGE"]
    assert info["bandage_image"]["output_name"] == ["outfile"]


def test_bandage_info_renders_headless_statistics_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bandage_info")

    assert node_class.render_command(
        {
            "input_file": "assembly graph.gfa",
            "tsv": True,
            "output": "/work/bandage_info",
        }
    ) == [
        "ln",
        "-sf",
        "assembly graph.gfa",
        "/work/bandage_info/input.gfa",
        "&&",
        "export",
        "QT_QPA_PLATFORM=offscreen",
        "&&",
        "Bandage",
        "info",
        "/work/bandage_info/input.gfa",
        "--tsv",
        "|",
        "sed",
        r"s/:\s\+/:\t/g",
        ">",
        "/work/bandage_info/out.tab",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bandage_info" / "out.tab",
    ]


def test_bandage_image_renders_graph_image_command_and_dynamic_output(tmp_path: Path) -> None:
    node_class = _node_class("bandage_image")

    assert node_class.render_command(
        {
            "input_file": "assembly.fastg",
            "output_format": "svg",
            "height": 800,
            "width": 1200,
            "fontsize": 12,
            "nodewidth": 8.5,
            "names": True,
            "lengths": True,
            "output": "/work/bandage_image",
        }
    ) == [
        "ln",
        "-sf",
        "assembly.fastg",
        "/work/bandage_image/input.gfa",
        "&&",
        "export",
        "QT_QPA_PLATFORM=offscreen",
        "&&",
        "Bandage",
        "image",
        "/work/bandage_image/input.gfa",
        "/work/bandage_image/out.svg",
        "--height",
        "800",
        "--width",
        "1200",
        "--fontsize",
        "12",
        "--nodewidth",
        "8.5",
        "--names",
        "--lengths",
    ]
    assert node_class.PLAN_OUTPUTS({"output_format": "svg"}, tmp_path) == [
        tmp_path / "bandage_image" / "out.svg",
    ]


def test_adapter_removal_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["adapter_removal"]

    assert info["output"] == [
        "TEXT",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
    ]
    assert info["output_name"] == [
        "output_settings",
        "output_truncated",
        "output_forward_truncated",
        "output_reverse_truncated",
        "output_interleaved_truncated",
        "output_singleton_truncated",
        "output_collapsed",
        "output_collapsed_truncated",
        "output_discarded",
    ]
    assert (
        info["citation_text"]
        == "AdapterRemoval v2: rapid adapter trimming, identification, and read merging."
    )


def test_adapter_removal_renders_single_read_defaults_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("adapter_removal")

    assert node_class.render_command(
        {
            "input_type": "single",
            "read1": "reads1.fastq.gz",
            "output": "/work/adapter_removal",
        }
    ) == (
        "ln -sf reads1.fastq.gz read1fastqsanger.gz && "
        "AdapterRemoval --file1 read1fastqsanger.gz --threads ${GALAXY_SLOTS:-8} "
        "--qualitybase 33 --qualitybase-output 33 --qualitymax 41 "
        "--adapter1 AGATCGGAAGAGCACACGTCTGAACTCCAGTCACNNNNNNATCTCGTATGCCGTCTTCTGCTTG "
        "--adapter2 AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT "
        "--minadapteroverlap 0 --mm 3.0 --shift 2 --maxns 1000 --minquality 2 "
        "--minlength 15 --maxlength 4294967295 --minalignmentlength 11 "
        "--settings /work/adapter_removal/output_settings.txt "
        "--output1 /work/adapter_removal/output_truncated.fastq"
    )
    assert node_class.PLAN_OUTPUTS({"input_type": "single"}, tmp_path) == [
        tmp_path / "adapter_removal" / "output_settings.txt",
        tmp_path / "adapter_removal" / "output_truncated.fastq",
    ]


def test_adapter_removal_renders_paired_interleaved_command_and_optional_outputs(tmp_path: Path) -> None:
    node_class = _node_class("adapter_removal")

    assert node_class.render_command(
        {
            "input_type": "pair",
            "read1": "sample R1.fq.gz",
            "read2": "sample R2.fq.gz",
            "interleaved_output": "yes",
            "identify_adapters": True,
            "combined_output": True,
            "convert_uracils": True,
            "mask_degenerate_bases": True,
            "adapter_list": "adapters.tsv",
            "trim5p": True,
            "trim5p_mate1": 2,
            "trim5p_mate2": 3,
            "trim3p": True,
            "trim3p_mate1": 4,
            "trim3p_mate2": 5,
            "trimns": True,
            "trimqualities": True,
            "sliding_window": True,
            "window_size": 8,
            "preserve5p": True,
            "collapse": True,
            "collapse_deterministic": True,
            "collapse_conservatively": True,
            "output_select": "output_singleton,output_collapsed,output_collapsed_truncated,output_discarded",
            "output": "/work/adapter_removal",
        }
    ) == (
        "ln -sf 'sample R1.fq.gz' read1fastqsanger.gz && "
        "ln -sf 'sample R2.fq.gz' read2fastqsanger.gz && "
        "AdapterRemoval --file1 read1fastqsanger.gz --file2 read2fastqsanger.gz "
        "--identify-adapters --interleaved-output --combined-output "
        "--threads ${GALAXY_SLOTS:-8} --qualitybase 33 --qualitybase-output 33 --qualitymax 41 "
        "--convert-uracils --mask-degenerate-bases "
        "--adapter1 AGATCGGAAGAGCACACGTCTGAACTCCAGTCACNNNNNNATCTCGTATGCCGTCTTCTGCTTG "
        "--adapter2 AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGTAGATCTCGGTGGTCGCCGTATCATT "
        "--adapter-list adapters.tsv --minadapteroverlap 0 --mm 3.0 --shift 2 "
        "--trim5p 2 3 --trim3p 4 5 --trimns --maxns 1000 --trimqualities "
        "--trimwindows 8 --minquality 2 --preserve5p --minlength 15 --maxlength 4294967295 "
        "--collapse --minalignmentlength 11 --collapse-deterministic --collapse-conservatively "
        "--settings /work/adapter_removal/output_settings.txt "
        "--output1 /work/adapter_removal/output_interleaved_truncated.fastq "
        "--singleton /work/adapter_removal/output_singleton_truncated.fastq "
        "--outputcollapsed /work/adapter_removal/output_collapsed.fastq "
        "--outputcollapsedtruncated /work/adapter_removal/output_collapsed_truncated.fastq "
        "--discarded /work/adapter_removal/output_discarded.fastq"
    )
    assert node_class.PLAN_OUTPUTS(
        {
            "input_type": "pair",
            "interleaved_output": "yes",
            "output_select": [
                "output_singleton",
                "output_collapsed",
                "output_collapsed_truncated",
                "output_discarded",
            ],
        },
        tmp_path,
    ) == [
        tmp_path / "adapter_removal" / "output_settings.txt",
        tmp_path / "adapter_removal" / "output_interleaved_truncated.fastq",
        tmp_path / "adapter_removal" / "output_singleton_truncated.fastq",
        tmp_path / "adapter_removal" / "output_collapsed.fastq",
        tmp_path / "adapter_removal" / "output_collapsed_truncated.fastq",
        tmp_path / "adapter_removal" / "output_discarded.fastq",
    ]


def test_assembly_stats_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["assembly_stats"]

    assert info["output"] == ["HTML_REPORT", "JSON"]
    assert info["output_name"] == ["output_html", "output_json"]


def test_assembly_stats_renders_html_visualisation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("assembly_stats")

    assert node_class.render_command(
        {
            "input_fasta": "assembly.fasta",
            "output_format": "html",
            "output": "/work/assembly_stats",
            "tool_directory": "/iuc/tools/assembly-stats",
        }
    ) == (
        'SRC="$(dirname $(which asm2stats.pl))/../opt/assembly-stats" && '
        "mkdir -p /work/assembly_stats/output_files/json && "
        'cp -r "$SRC/css/" /work/assembly_stats/output_files && '
        'cp -r "$SRC/js/" /work/assembly_stats/output_files && '
        "cp /iuc/tools/assembly-stats/d3-tip.js /work/assembly_stats/output_files/js/d3-tip.js && "
        "cp /iuc/tools/assembly-stats/assembly-stats.html /work/assembly_stats/output.html && "
        "cp /iuc/tools/assembly-stats/assembly-stats.html /work/assembly_stats/output_files && "
        "asm2stats.minmaxgc.pl assembly.fasta > "
        "/work/assembly_stats/output_files/json/output.assembly-stats.json"
    )

    assert node_class.PLAN_OUTPUTS({"output_format": "html"}, tmp_path) == [
        tmp_path / "assembly_stats" / "output.html",
    ]


def test_assembly_stats_renders_json_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("assembly_stats")

    assert node_class.render_command(
        {
            "input_fasta": "assembly.fasta",
            "output_format": "json",
            "output": "/work/assembly_stats",
        }
    ) == "asm2stats.minmaxgc.pl assembly.fasta > /work/assembly_stats/output.json"

    assert node_class.PLAN_OUTPUTS({"output_format": "json"}, tmp_path) == [
        tmp_path / "assembly_stats" / "output.json",
    ]


def test_amas_summary_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_summary"]

    assert info["output"] == ["TEXT", "DIRECTORY"]
    assert info["output_name"] == ["summary_out", "taxon_summaries"]


def test_amas_summary_renders_checked_multi_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_summary")

    assert node_class.render_command(
        {
            "input_files": ["alignments/gene one.fas", "gene2.nex"],
            "input_labels": ["gene one.fas", "gene2.nex"],
            "input_format": "nex",
            "data_type": "dna",
            "by_taxon": True,
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_summary",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'alignments/gene one.fas' gene2.nex --format nexus) && "
        "ln -sf 'alignments/gene one.fas' gene_one.fas && "
        "ln -sf gene2.nex gene2.nex && "
        "python -m amas.AMAS summary --by-taxon --in-files gene_one.fas gene2.nex "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_summary/taxon_summaries && "
        "find . -maxdepth 1 -name '*-seq-summary.txt' -exec mv {} /work/amas_summary/taxon_summaries/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"by_taxon": True}, tmp_path) == [
        tmp_path / "amas_summary" / "summary.txt",
        tmp_path / "amas_summary" / "taxon_summaries",
    ]


def test_amas_summary_renders_minimal_command_and_summary_output(tmp_path: Path) -> None:
    node_class = _node_class("amas_summary")

    assert node_class.render_command(
        {
            "input_files": ["gene1.fasta"],
            "data_type": "aa",
            "input_format": "fasta",
            "output": "/work/amas_summary",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "gene1.fasta --format fasta) && "
        "ln -sf gene1.fasta gene1.fasta && "
        "python -m amas.AMAS summary --in-files gene1.fasta "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}"'
    )

    assert node_class.PLAN_OUTPUTS({"by_taxon": False}, tmp_path) == [
        tmp_path / "amas_summary" / "summary.txt",
    ]


def test_amas_concat_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_concat"]

    assert info["output"] == ["ALIGNMENT", "TEXT"]
    assert info["output_name"] == ["output", "partitions_out"]


def test_amas_concat_renders_partitioned_concat_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_concat")

    assert node_class.render_command(
        {
            "input_files": ["gene A.fasta", "geneB.fasta"],
            "input_labels": ["gene A.fasta", "geneB.fasta"],
            "input_format": "fasta",
            "out_format": "phylip",
            "part_format": "nexus",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_concat",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'gene A.fasta' geneB.fasta --format fasta) && "
        "ln -sf 'gene A.fasta' gene_A.fasta && "
        "ln -sf geneB.fasta geneB.fasta && "
        "python -m amas.AMAS concat --concat-part partitions.txt --concat-out concatenated.out "
        "--part-format nexus --out-format phylip --in-files gene_A.fasta geneB.fasta "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align'
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "phylip", "part_format": "nexus"}, tmp_path) == [
        tmp_path / "amas_concat" / "concatenated.phy",
        tmp_path / "amas_concat" / "partitions.nex",
    ]


def test_amas_concat_plans_interleaved_nexus_and_raxml_partitions(tmp_path: Path) -> None:
    node_class = _node_class("amas_concat")

    assert node_class.PLAN_OUTPUTS({"out_format": "nexus-int", "part_format": "raxml"}, tmp_path) == [
        tmp_path / "amas_concat" / "concatenated.nex",
        tmp_path / "amas_concat" / "partitions.txt",
    ]


def test_amas_split_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_split"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["split_alignments"]


def test_amas_split_renders_checked_split_command_and_directory_output(tmp_path: Path) -> None:
    node_class = _node_class("amas_split")

    assert node_class.render_command(
        {
            "input_file": "concat result.phy",
            "input_label": "concat result.phy",
            "input_format": "phylip",
            "split_by": "partitions.txt",
            "remove_empty": True,
            "out_format": "fasta",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_split",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'concat result.phy' --format phylip) && "
        "ln -sf 'concat result.phy' concat_result.phy && "
        "python -m amas.AMAS split --split-by partitions.txt --remove-empty "
        "--out-format fasta --in-files concat_result.phy "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_split/split_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_split/split_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "fasta"}, tmp_path) == [
        tmp_path / "amas_split" / "split_alignments",
    ]


def test_amas_split_renders_minimal_nexus_command(tmp_path: Path) -> None:
    node_class = _node_class("amas_split")

    assert node_class.render_command(
        {
            "input_file": "combined.nex",
            "split_by": "parts.txt",
            "out_format": "nexus-int",
            "data_type": "aa",
            "output": "/work/amas_split",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "combined.nex --format nexus) && "
        "ln -sf combined.nex combined.nex && "
        "python -m amas.AMAS split --split-by parts.txt --out-format nexus-int "
        "--in-files combined.nex "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}" && '
        "mkdir -p /work/amas_split/split_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_split/split_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "amas_split" / "split_alignments",
    ]


def test_amas_remove_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_remove"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["reduced_alignments"]


def test_amas_remove_renders_checked_multi_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_remove")

    assert node_class.render_command(
        {
            "input_files": ["alignments/gene one.fas", "gene2.nex"],
            "input_labels": ["gene one.fas", "gene2.nex"],
            "input_format": "nex",
            "taxa_to_remove": "OTU9 OTU10 Sample_A",
            "out_format": "nexus-int",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_remove",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'alignments/gene one.fas' gene2.nex --format nexus) && "
        "ln -sf 'alignments/gene one.fas' gene_one.fas && "
        "ln -sf gene2.nex gene2.nex && "
        "python -m amas.AMAS remove --taxa-to-remove OTU9 OTU10 Sample_A "
        "--out-format nexus-int --in-files gene_one.fas gene2.nex "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_remove/reduced_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_remove/reduced_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "nexus-int"}, tmp_path) == [
        tmp_path / "amas_remove" / "reduced_alignments",
    ]


def test_amas_remove_renders_minimal_command(tmp_path: Path) -> None:
    node_class = _node_class("amas_remove")

    assert node_class.render_command(
        {
            "input_files": ["gene1.fasta"],
            "taxa_to_remove": "BadTaxon",
            "out_format": "fasta",
            "data_type": "aa",
            "output": "/work/amas_remove",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "gene1.fasta --format fasta) && "
        "ln -sf gene1.fasta gene1.fasta && "
        "python -m amas.AMAS remove --taxa-to-remove BadTaxon --out-format fasta "
        "--in-files gene1.fasta "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}" && '
        "mkdir -p /work/amas_remove/reduced_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_remove/reduced_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "amas_remove" / "reduced_alignments",
    ]


def test_amas_replicate_exposes_galaxy_aligned_outputs() -> None:
    info = _registry().object_info()["amas_replicate"]

    assert info["output"] == ["DIRECTORY"]
    assert info["output_name"] == ["replicate_alignments"]


def test_amas_replicate_renders_checked_multi_alignment_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("amas_replicate")

    assert node_class.render_command(
        {
            "input_files": ["alignments/locus one.fas", "locus2.nex"],
            "input_labels": ["locus one.fas", "locus2.nex"],
            "input_format": "nex",
            "replicate_replicates": 10,
            "replicate_loci": 2,
            "out_format": "nexus",
            "data_type": "dna",
            "check_align": True,
            "tool_directory": "/iuc/tools/amas",
            "output": "/work/amas_replicate",
        }
    ) == (
        "set -eu && "
        "IN_FORMAT=$(python /iuc/tools/amas/check_interleaved.py "
        "'alignments/locus one.fas' locus2.nex --format nexus) && "
        "ln -sf 'alignments/locus one.fas' locus_one.fas && "
        "ln -sf locus2.nex locus2.nex && "
        "python -m amas.AMAS replicate --rep-aln 10 2 --out-format nexus "
        "--in-files locus_one.fas locus2.nex "
        '--in-format "${IN_FORMAT}" --data-type dna --cores "${GALAXY_SLOTS:-1}" --check-align && '
        "mkdir -p /work/amas_replicate/replicate_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_replicate/replicate_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({"out_format": "nexus"}, tmp_path) == [
        tmp_path / "amas_replicate" / "replicate_alignments",
    ]


def test_amas_replicate_renders_minimal_command(tmp_path: Path) -> None:
    node_class = _node_class("amas_replicate")

    assert node_class.render_command(
        {
            "input_files": ["locus1.fasta"],
            "replicate_replicates": 2,
            "replicate_loci": 1,
            "out_format": "fasta",
            "data_type": "aa",
            "output": "/work/amas_replicate",
        }
    ) == (
        "set -eu && "
        'IN_FORMAT=$(python "${BIONODULO_AMAS_TOOL_DIR:-.}"/check_interleaved.py '
        "locus1.fasta --format fasta) && "
        "ln -sf locus1.fasta locus1.fasta && "
        "python -m amas.AMAS replicate --rep-aln 2 1 --out-format fasta "
        "--in-files locus1.fasta "
        '--in-format "${IN_FORMAT}" --data-type aa --cores "${GALAXY_SLOTS:-1}" && '
        "mkdir -p /work/amas_replicate/replicate_alignments && "
        "find . -maxdepth 1 -name '*-out.*' -exec mv {} /work/amas_replicate/replicate_alignments/ \\;"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "amas_replicate" / "replicate_alignments",
    ]


def test_prinseq_exposes_galaxy_aligned_outputs_and_citation() -> None:
    info = _registry().object_info()["prinseq"]

    assert info["output"] == ["FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ"]
    assert info["output_name"] == [
        "good_sequences",
        "rejected_sequences",
        "good_sequences_1",
        "good_sequences_1_singletons",
        "good_sequences_2",
        "rejected_sequences_2",
    ]
    assert info["citation_dois"] == ["10.1093/bioinformatics/btr026"]
    assert info["required_executables"] == ["prinseq-lite.pl"]
    assert info["required_conda_packages"] == ["prinseq"]


def test_prinseq_renders_single_end_filter_and_trim_command(tmp_path: Path) -> None:
    node_class = _node_class("prinseq")

    assert node_class.render_command(
        {
            "input_singles": "reads.fastq.gz",
            "paired": False,
            "phred64": True,
            "min_len": 60,
            "min_qual_mean": 15,
            "ns_max_p": 2,
            "trim_qual_right": 20,
            "trim_qual_type": "min",
            "trim_qual_rule": "lt",
            "trim_qual_window": 1,
            "trim_qual_step": 1,
            "output": "/work/prinseq",
        }
    ) == (
        "set -eu && mkdir -p /work/prinseq/tmp && "
        "gunzip -c reads.fastq.gz > fwd.fastq && "
        "touch /work/prinseq/tmp/good_sequences.fastq /work/prinseq/tmp/rejected_sequences.fastq && "
        "prinseq-lite.pl -fastq fwd.fastq -phred64 -out_good /work/prinseq/tmp/good_sequences "
        "-out_bad /work/prinseq/tmp/rejected_sequences -min_len 60 -min_qual_mean 15 -ns_max_p 2 "
        "-trim_qual_right 20 -trim_qual_type min -trim_qual_rule lt -trim_qual_window 1 -trim_qual_step 1 && "
        "gzip -c /work/prinseq/tmp/good_sequences.fastq > /work/prinseq/good_sequences.fastq.gz && "
        "gzip -c /work/prinseq/tmp/rejected_sequences.fastq > /work/prinseq/rejected_sequences.fastq.gz"
    )

    assert node_class.PLAN_OUTPUTS({"paired": False}, tmp_path) == [
        tmp_path / "prinseq" / "good_sequences.fastq.gz",
        tmp_path / "prinseq" / "rejected_sequences.fastq.gz",
    ]


def test_prinseq_renders_paired_end_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("prinseq")

    assert node_class.render_command(
        {
            "input_mate1": "r1.fastq",
            "input_mate2": "r2.fastq",
            "paired": True,
            "min_len": 50,
            "min_qual_mean": 15,
            "ns_max_p": 2,
            "trim_qual_right": 20,
            "output": "/work/prinseq",
        }
    ) == (
        "set -eu && mkdir -p /work/prinseq/tmp && "
        "ln -sf r1.fastq fwd.fastq && ln -sf r2.fastq rev.fastq && "
        "touch /work/prinseq/tmp/good_sequences_1.fastq /work/prinseq/tmp/good_sequences_1_singletons.fastq "
        "/work/prinseq/tmp/rejected_sequences_1.fastq /work/prinseq/tmp/good_sequences_2.fastq "
        "/work/prinseq/tmp/good_sequences_2_singletons.fastq /work/prinseq/tmp/rejected_sequences_2.fastq && "
        "prinseq-lite.pl -fastq fwd.fastq -fastq2 rev.fastq -out_good /work/prinseq/tmp/good_sequences "
        "-out_bad /work/prinseq/tmp/rejected_sequences -min_len 50 -min_qual_mean 15 -ns_max_p 2 "
        "-trim_qual_right 20 && "
        "cp /work/prinseq/tmp/good_sequences_1.fastq /work/prinseq/good_sequences_1.fastq && "
        "cp /work/prinseq/tmp/good_sequences_1_singletons.fastq /work/prinseq/good_sequences_1_singletons.fastq && "
        "cp /work/prinseq/tmp/rejected_sequences_1.fastq /work/prinseq/rejected_sequences_1.fastq && "
        "cp /work/prinseq/tmp/good_sequences_2.fastq /work/prinseq/good_sequences_2.fastq && "
        "cp /work/prinseq/tmp/good_sequences_2_singletons.fastq /work/prinseq/good_sequences_2_singletons.fastq && "
        "cp /work/prinseq/tmp/rejected_sequences_2.fastq /work/prinseq/rejected_sequences_2.fastq"
    )

    assert node_class.PLAN_OUTPUTS({"paired": True, "compress_output": False}, tmp_path) == [
        tmp_path / "prinseq" / "good_sequences_1.fastq",
        tmp_path / "prinseq" / "good_sequences_1_singletons.fastq",
        tmp_path / "prinseq" / "rejected_sequences_1.fastq",
        tmp_path / "prinseq" / "good_sequences_2.fastq",
        tmp_path / "prinseq" / "good_sequences_2_singletons.fastq",
        tmp_path / "prinseq" / "rejected_sequences_2.fastq",
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


def test_vsearch_dereplication_renders_abundance_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_dereplication")
    info = _registry().object_info()["vsearch_dereplication"]

    assert info["output"] == ["FASTA", "TSV"]
    assert info["output_name"] == ["dereplicated_sequences", "uclust_output"]
    assert node_class.render_command(
        {
            "infile": "amplicons.fasta",
            "threads": 6,
            "minuniquesize": 2,
            "maxuniquesize": 100000,
            "sizein": True,
            "sizeout": True,
            "strand": "both",
            "topn": 10000,
            "uc": True,
            "output": "/work/vsearch_dereplication",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--derep_fulllength",
        "amplicons.fasta",
        "--maxuniquesize",
        "100000",
        "--minuniquesize",
        "2",
        "--output",
        "/work/vsearch_dereplication/dereplicated.fasta",
        "--sizein",
        "--sizeout",
        "--strand",
        "both",
        "--topn",
        "10000",
        "--uc",
        "/work/vsearch_dereplication/dereplication.uc",
    ]

    assert node_class.PLAN_OUTPUTS({"uc": True}, tmp_path) == [
        tmp_path / "vsearch_dereplication" / "dereplicated.fasta",
        tmp_path / "vsearch_dereplication" / "dereplication.uc",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_dereplication" / "dereplicated.fasta",
    ]


def test_vsearch_masking_renders_maskfasta_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_masking")
    info = _registry().object_info()["vsearch_masking"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["masked_sequences"]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 6,
            "qmask": "dust",
            "hardmask": True,
            "output": "/work/vsearch_masking",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--qmask",
        "dust",
        "--hardmask",
        "--maskfasta",
        "db.fasta",
        "--output",
        "/work/vsearch_masking/masked.fasta",
    ]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 2,
            "qmask": "none",
            "hardmask": False,
            "output": "/work/vsearch_masking",
        }
    ) == [
        "vsearch",
        "--threads",
        "2",
        "--notrunclabels",
        "--maskfasta",
        "db.fasta",
        "--output",
        "/work/vsearch_masking/masked.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_masking" / "masked.fasta",
    ]


def test_vsearch_shuffling_renders_shuffle_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_shuffling")
    info = _registry().object_info()["vsearch_shuffling"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["shuffled_sequences"]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 6,
            "randseed": 1,
            "topn": 5,
            "output": "/work/vsearch_shuffling",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--output",
        "/work/vsearch_shuffling/shuffled.fasta",
        "--randseed",
        "1",
        "--shuffle",
        "db.fasta",
        "--topn",
        "5",
    ]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 2,
            "randseed": 0,
            "topn": "",
            "output": "/work/vsearch_shuffling",
        }
    ) == [
        "vsearch",
        "--threads",
        "2",
        "--notrunclabels",
        "--output",
        "/work/vsearch_shuffling/shuffled.fasta",
        "--randseed",
        "0",
        "--shuffle",
        "db.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_shuffling" / "shuffled.fasta",
    ]


def test_vsearch_sorting_renders_length_and_abundance_commands(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_sorting")
    info = _registry().object_info()["vsearch_sorting"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["sorted_sequences"]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 6,
            "sorting_mode": "sortbylength",
            "relabel": "With spaces",
            "sizeout": True,
            "topn": 5,
            "output": "/work/vsearch_sorting",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--sortbylength",
        "db.fasta",
        "--output",
        "/work/vsearch_sorting/sorted.fasta",
        "--relabel",
        "With spaces",
        "--sizeout",
        "--topn",
        "5",
    ]
    assert node_class.render_command(
        {
            "infile": "db.fasta",
            "threads": 2,
            "sorting_mode": "sortbyabundance",
            "minsize": 2,
            "maxsize": 500,
            "sizeout": False,
            "topn": "",
            "output": "/work/vsearch_sorting",
        }
    ) == [
        "vsearch",
        "--threads",
        "2",
        "--notrunclabels",
        "--sortbysize",
        "db.fasta",
        "--minsize",
        "2",
        "--maxsize",
        "500",
        "--output",
        "/work/vsearch_sorting/sorted.fasta",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_sorting" / "sorted.fasta",
    ]


def test_vsearch_alignment_renders_allpairs_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_alignment")
    info = _registry().object_info()["vsearch_alignment"]

    assert info["output"] == ["STATS_FILE", "TSV"]
    assert info["output_name"] == ["alignments", "userfields"]
    assert node_class.render_command(
        {
            "infile": "reads.fasta",
            "threads": 6,
            "acceptall": True,
            "id": 0.97,
            "iddef": 2,
            "query_cov": 0.95,
            "userfields_output_select": "yes",
            "userfields": ["query", "target"],
            "output": "/work/vsearch_alignment",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--acceptall",
        "--id",
        "0.97",
        "--iddef",
        "2",
        "--allpairs_global",
        "reads.fasta",
        "--alnout",
        "/work/vsearch_alignment/alignments.txt",
        "--query_cov",
        "0.95",
        "--userfields",
        "query+target",
        "--userout",
        "/work/vsearch_alignment/userfields.tsv",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"userfields_output_select": "yes", "userfields": ["query", "target"]},
        tmp_path,
    ) == [
        tmp_path / "vsearch_alignment" / "alignments.txt",
        tmp_path / "vsearch_alignment" / "userfields.tsv",
    ]
    assert node_class.render_command(
        {
            "infile": "reads.fasta",
            "userfields_output_select": "no",
            "userfields": ["query", "target"],
            "output": "/work/vsearch_alignment",
        }
    ) == [
        "vsearch",
        "--threads",
        "4",
        "--notrunclabels",
        "--id",
        "0.97",
        "--iddef",
        "2",
        "--allpairs_global",
        "reads.fasta",
        "--alnout",
        "/work/vsearch_alignment/alignments.txt",
    ]
    assert node_class.PLAN_OUTPUTS(
        {"userfields_output_select": "no", "userfields": ["query", "target"]},
        tmp_path,
    ) == [
        tmp_path / "vsearch_alignment" / "alignments.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_alignment" / "alignments.txt",
    ]


def test_vsearch_chimera_detection_renders_uchime_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("vsearch_chimera_detection")
    info = _registry().object_info()["vsearch_chimera_detection"]

    assert info["output"] == ["FASTA", "FASTA", "STATS_FILE", "TSV"]
    assert info["output_name"] == ["chimeras", "nonchimeras", "uchime_alignments", "uchimeout"]
    assert node_class.render_command(
        {
            "detection_mode": "denovo",
            "infile_denovo": "amplicons.fasta",
            "threads": 6,
            "abskew": 2.0,
            "dn": 1.4,
            "mindiffs": 3,
            "mindiv": 0.8,
            "minh": 0.28,
            "xn": 8.0,
            "outputs": ["nonchimeras", "uchimealns", "uchimeout"],
            "output": "/work/vsearch_chimera_detection",
        }
    ) == [
        "vsearch",
        "--threads",
        "6",
        "--notrunclabels",
        "--abskew",
        "2.0",
        "--chimeras",
        "/work/vsearch_chimera_detection/chimeras.fasta",
        "--dn",
        "1.4",
        "--mindiffs",
        "3",
        "--mindiv",
        "0.8",
        "--minh",
        "0.28",
        "--xn",
        "8.0",
        "--uchime_denovo",
        "amplicons.fasta",
        "--nonchimeras",
        "/work/vsearch_chimera_detection/nonchimeras.fasta",
        "--uchimealns",
        "/work/vsearch_chimera_detection/uchime_alignments.txt",
        "--uchimeout",
        "/work/vsearch_chimera_detection/uchimeout.tsv",
    ]
    assert node_class.render_command(
        {
            "detection_mode": "reference",
            "infile_reference": "queries.fasta",
            "db": "gold.fasta",
            "self_param": True,
            "selfid_param": True,
            "outputs": ["uchimeout"],
            "output": "/work/vsearch_chimera_detection",
        }
    ) == [
        "vsearch",
        "--threads",
        "4",
        "--notrunclabels",
        "--abskew",
        "2.0",
        "--chimeras",
        "/work/vsearch_chimera_detection/chimeras.fasta",
        "--dn",
        "1.4",
        "--mindiffs",
        "3",
        "--mindiv",
        "0.8",
        "--minh",
        "0.28",
        "--xn",
        "8.0",
        "--self",
        "--selfid",
        "--uchime_ref",
        "queries.fasta",
        "--db",
        "gold.fasta",
        "--uchimeout",
        "/work/vsearch_chimera_detection/uchimeout.tsv",
    ]

    assert node_class.PLAN_OUTPUTS(
        {"outputs": ["nonchimeras", "uchimealns", "uchimeout"]},
        tmp_path,
    ) == [
        tmp_path / "vsearch_chimera_detection" / "chimeras.fasta",
        tmp_path / "vsearch_chimera_detection" / "nonchimeras.fasta",
        tmp_path / "vsearch_chimera_detection" / "uchime_alignments.txt",
        tmp_path / "vsearch_chimera_detection" / "uchimeout.tsv",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "vsearch_chimera_detection" / "chimeras.fasta",
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


def test_hmmer_alimask_renders_mask_ranges_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_alimask")
    info = _registry().object_info()["hmmer_alimask"]

    assert info["output"] == ["ALIGNMENT"]
    assert info["output_name"] == ["masked_alignment"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["optional"]["symfrac"][1]["displayOptions"] == {
        "show": {"model_construction": ["fast"]},
    }
    assert info["input"]["optional"]["wid"][1]["displayOptions"] == {
        "show": {"relative_weighting": ["--wblosum"]},
    }
    assert node_class.render_command(
        {
            "msafile": "globins.sto",
            "range_type": "model",
            "ranges": ["10-20", "45-60"],
            "input_format": "--amino",
            "model_construction": "fast",
            "symfrac": 0.45,
            "fragthresh": 0.7,
            "relative_weighting": "--wblosum",
            "wid": 0.8,
            "seed": 4,
            "output": "/work/alimask",
        }
    ) == [
        "alimask",
        "--modelrange",
        "10-20,45-60",
        "--amino",
        "--fast",
        "--symfrac",
        "0.45",
        "--fragthresh",
        "0.7",
        "--wblosum",
        "--wid",
        "0.8",
        "--seed",
        "4",
        "globins.sto",
        "/work/alimask/masked.sto",
    ]

    assert node_class.render_command(
        {
            "msafile": "globins.sto",
            "range_type": "ali",
            "ranges": ["5-15"],
            "input_format": "--dna",
            "model_construction": "hand",
            "relative_weighting": "--wpb",
            "seed": 42,
            "output": "/work/alimask",
        }
    ) == [
        "alimask",
        "--alirange",
        "5-15",
        "--dna",
        "--hand",
        "--fragthresh",
        "0.5",
        "--wpb",
        "--seed",
        "42",
        "globins.sto",
        "/work/alimask/masked.sto",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_alimask" / "masked.sto"]


def test_hmmer_hmmalign_renders_stockholm_alignment_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmalign")
    info = _registry().object_info()["hmmer_hmmalign"]

    assert info["output"] == ["ALIGNMENT"]
    assert info["output_name"] == ["alignment"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["input_format_select"][1]["options"] == ["--amino", "--dna", "--rna"]
    assert node_class.render_command(
        {
            "seq": "globins45.fa",
            "hmmfile": "globins4.hmm",
            "trim": True,
            "input_format_select": "--amino",
            "output": "/work/hmmalign",
        }
    ) == [
        "hmmalign",
        "--trim",
        "--amino",
        "--outformat",
        "stockholm",
        "globins4.hmm",
        "globins45.fa",
        ">",
        "/work/hmmalign/alignment.sto",
    ]

    assert node_class.render_command(
        {
            "seq": "reads.fasta",
            "hmmfile": "model.hmm",
            "trim": False,
            "input_format_select": "--rna",
            "output": "/work/hmmalign",
        }
    ) == [
        "hmmalign",
        "--rna",
        "--outformat",
        "stockholm",
        "model.hmm",
        "reads.fasta",
        ">",
        "/work/hmmalign/alignment.sto",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_hmmalign" / "alignment.sto"]


def test_hmmer_hmmbuild_renders_profile_build_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmbuild")
    info = _registry().object_info()["hmmer_hmmbuild"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["hmm_profile"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["optional"]["symfrac"][1]["displayOptions"] == {
        "show": {"model_construction": ["fast"]},
    }
    assert info["input"]["optional"]["wid"][1]["displayOptions"] == {
        "show": {"relative_weighting": ["--wblosum"]},
    }
    assert info["input"]["optional"]["esigma"][1]["displayOptions"] == {
        "show": {"effective_weighting": ["eent"]},
    }
    assert node_class.render_command(
        {
            "msafile": "globins4.sto",
            "hmmname": "globins",
            "input_format_select": "--amino",
            "model_construction": "fast",
            "symfrac": 0.6,
            "fragthresh": 0.4,
            "relative_weighting": "--wblosum",
            "wid": 0.7,
            "effective_weighting": "eent",
            "eset": 2.5,
            "ere": 0.59,
            "esigma": 45,
            "prior": "--pnone",
            "single_sequence_scoring": "singlemx",
            "popen": 0.03,
            "pextend": 0.5,
            "eml": 220,
            "emn": 210,
            "evl": 230,
            "evn": 220,
            "efl": 120,
            "efn": 210,
            "eft": 0.05,
            "threads": 6,
            "seed": 4,
            "w_beta": 1e-7,
            "w_length": 450,
            "maxinsertlen": 25,
            "output": "/work/hmmbuild",
        }
    ) == [
        "hmmbuild",
        "-n",
        "globins",
        "--amino",
        "--fast",
        "--symfrac",
        "0.6",
        "--fragthresh",
        "0.4",
        "--wblosum",
        "--wid",
        "0.7",
        "--eent",
        "--eset",
        "2.5",
        "--ere",
        "0.59",
        "--esigma",
        "45",
        "--pnone",
        "--popen",
        "0.03",
        "--pextend",
        "0.5",
        "--EmL",
        "220",
        "--EmN",
        "210",
        "--EvL",
        "230",
        "--EvN",
        "220",
        "--EfL",
        "120",
        "--EfN",
        "210",
        "--Eft",
        "0.05",
        "--cpu",
        "5",
        "--seed",
        "4",
        "--w_beta",
        "1e-07",
        "--w_length",
        "450",
        "--maxinsertlen",
        "25",
        "/work/hmmbuild/profile.hmm",
        "globins4.sto",
    ]

    assert node_class.render_command(
        {
            "msafile": "MADE1.sto",
            "input_format_select": "--dna",
            "model_construction": "hand",
            "relative_weighting": "--wpb",
            "effective_weighting": "enone",
            "prior": "",
            "single_sequence_scoring": "false",
            "threads": 1,
            "seed": 42,
            "output": "/work/hmmbuild",
        }
    ) == [
        "hmmbuild",
        "--dna",
        "--hand",
        "--fragthresh",
        "0.5",
        "--wpb",
        "--enone",
        "--EmL",
        "200",
        "--EmN",
        "200",
        "--EvL",
        "200",
        "--EvN",
        "200",
        "--EfL",
        "100",
        "--EfN",
        "200",
        "--Eft",
        "0.04",
        "--cpu",
        "1",
        "--seed",
        "42",
        "/work/hmmbuild/profile.hmm",
        "MADE1.sto",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_hmmbuild" / "profile.hmm"]


def test_hmmer_hmmconvert_renders_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmconvert")
    info = _registry().object_info()["hmmer_hmmconvert"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["converted_profile"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["format"][1]["options"] == ["-a", "-2"]
    assert node_class.render_command(
        {
            "hmmfile": "globins4.hmm",
            "format": "-2",
            "output": "/work/hmmconvert",
        }
    ) == [
        "hmmconvert",
        "-2",
        "globins4.hmm",
        ">",
        "/work/hmmconvert/converted.hmm2",
    ]
    assert node_class.render_command(
        {
            "hmmfile": "legacy.hmm2",
            "format": "-a",
            "output": "/work/hmmconvert",
        }
    ) == [
        "hmmconvert",
        "-a",
        "legacy.hmm2",
        ">",
        "/work/hmmconvert/converted.hmm3",
    ]
    assert node_class.PLAN_OUTPUTS({"format": "-2"}, tmp_path) == [tmp_path / "hmmer_hmmconvert" / "converted.hmm2"]
    assert node_class.PLAN_OUTPUTS({"format": "-a"}, tmp_path) == [tmp_path / "hmmer_hmmconvert" / "converted.hmm3"]


def test_hmmer_hmmemit_renders_sampling_command_and_dynamic_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmemit")
    info = _registry().object_info()["hmmer_hmmemit"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["emitted_sequences"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["output_mode"][1]["options"] == ["fasta", "aln", "mrcs", "mrcsf", "sample"]
    assert info["input"]["optional"]["length"][1]["displayOptions"] == {
        "show": {"output_mode": ["sample"]},
    }
    assert node_class.render_command(
        {
            "hmmfile": "globins4.hmm",
            "output_mode": "fasta",
            "n_fasta": 3,
            "seed": 4,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "-N",
        "3",
        "--seed",
        "4",
        "globins4.hmm",
        ">",
        "/work/hmmemit/emitted.fasta",
    ]

    assert node_class.render_command(
        {
            "hmmfile": "globins4.hmm",
            "output_mode": "aln",
            "n_alignment": 10,
            "seed": 4,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "-N",
        "10",
        "-a",
        "--seed",
        "4",
        "globins4.hmm",
        ">",
        "/work/hmmemit/emitted.sto",
    ]

    assert node_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "output_mode": "mrcsf",
            "minl": 0.75,
            "minu": 0.35,
            "seed": 42,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "--minl",
        "0.75",
        "--minu",
        "0.35",
        "-C",
        "--seed",
        "42",
        "profile.hmm",
        ">",
        "/work/hmmemit/emitted.fasta",
    ]

    assert node_class.render_command(
        {
            "hmmfile": "profile.hmm",
            "output_mode": "sample",
            "n_sample": 2,
            "length": 600,
            "emission_profile": "--uniglocal",
            "seed": 7,
            "output": "/work/hmmemit",
        }
    ) == [
        "hmmemit",
        "-N",
        "2",
        "-p",
        "-L",
        "600",
        "--uniglocal",
        "--seed",
        "7",
        "profile.hmm",
        ">",
        "/work/hmmemit/emitted.fasta",
    ]
    assert node_class.PLAN_OUTPUTS({"output_mode": "aln"}, tmp_path) == [tmp_path / "hmmer_hmmemit" / "emitted.sto"]
    assert node_class.PLAN_OUTPUTS({"output_mode": "mrcs"}, tmp_path) == [tmp_path / "hmmer_hmmemit" / "emitted.fasta"]


def test_hmmer_hmmfetch_renders_model_selection_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_hmmfetch")
    info = _registry().object_info()["hmmer_hmmfetch"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["selected_hmm_models"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["hmmfile"][0] == "FILE"
    assert info["input"]["required"]["keyfile"][0] == "FILE"
    assert node_class.render_command(
        {
            "hmmfile": "pfam-a.hmm",
            "keyfile": "models.txt",
            "output": "/work/hmmfetch",
        }
    ) == [
        "hmmfetch",
        "-f",
        "pfam-a.hmm",
        "models.txt",
        ">",
        "/work/hmmfetch/selected.hmm",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hmmer_hmmfetch" / "selected.hmm"]


def test_hmmer_jackhmmer_renders_iterative_search_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_jackhmmer")
    info = _registry().object_info()["hmmer_jackhmmer"]

    assert info["output"] == ["STATS_FILE", "TSV", "TSV"]
    assert info["output_name"] == ["output", "tblout", "domtblout"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["required"]["seqdb"][0] == "FASTA"
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "domtblout"]
    assert info["input"]["optional"]["output_formats"][1]["list"] is True
    assert info["input"]["optional"]["popen"][1]["displayOptions"] == {
        "show": {"single_sequence_scoring": ["singlemx"]},
    }
    assert info["input"]["optional"]["incT"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["score"]},
    }
    assert node_class.render_command(
        {
            "seqfile": "query.fa",
            "seqdb": "uniprot.fa",
            "iterations": 3,
            "output_formats": ["tblout", "domtblout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "single_sequence_scoring": "singlemx",
            "popen": 0.03,
            "pextend": 0.5,
            "threshold_mode": "score",
            "score_threshold": 25,
            "incT": 30,
            "max": True,
            "F1": 0.01,
            "F2": 0.002,
            "F3": 1e-6,
            "nobias": True,
            "relative_weighting": "--wblosum",
            "wid": 0.65,
            "effective_weighting": "eent",
            "eset": 2.0,
            "ere": 0.59,
            "esigma": 45,
            "prior": "--pnone",
            "eml": 220,
            "emn": 210,
            "evl": 230,
            "evn": 220,
            "efl": 120,
            "efn": 210,
            "eft": 0.05,
            "nonull2": True,
            "z": 1000,
            "domz": 50,
            "threads": 6,
            "seed": 4,
            "output": "/work/jackhmmer",
        }
    ) == [
        "jackhmmer",
        "-N",
        "3",
        "--tblout",
        "/work/jackhmmer/results.tblout",
        "--domtblout",
        "/work/jackhmmer/domains.domtblout",
        "--acc",
        "--noali",
        "--notextw",
        "--popen",
        "0.03",
        "--pextend",
        "0.5",
        "-T",
        "25",
        "--incT",
        "30",
        "--max",
        "--F1",
        "0.01",
        "--F2",
        "0.002",
        "--F3",
        "1e-06",
        "--nobias",
        "--wblosum",
        "--wid",
        "0.65",
        "--eent",
        "--eset",
        "2.0",
        "--ere",
        "0.59",
        "--esigma",
        "45",
        "--pnone",
        "--EmL",
        "220",
        "--EmN",
        "210",
        "--EvL",
        "230",
        "--EvN",
        "220",
        "--EfL",
        "120",
        "--EfN",
        "210",
        "--Eft",
        "0.05",
        "--nonull2",
        "-Z",
        "1000",
        "--domZ",
        "50",
        "--cpu",
        "5",
        "--seed",
        "4",
        "query.fa",
        "uniprot.fa",
        ">",
        "/work/jackhmmer/output.txt",
    ]
    assert node_class.render_command(
        {
            "seqfile": "query.fa",
            "seqdb": "uniprot.fa",
            "output_formats": [],
            "threshold_mode": "evalue",
            "evalue": 10,
            "threads": 1,
            "seed": 42,
            "output": "/work/jackhmmer",
        }
    ) == [
        "jackhmmer",
        "-N",
        "5",
        "-E",
        "10",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--wpb",
        "--EmL",
        "200",
        "--EmN",
        "200",
        "--EvL",
        "200",
        "--EvN",
        "200",
        "--EfL",
        "100",
        "--EfN",
        "200",
        "--Eft",
        "0.04",
        "--cpu",
        "1",
        "--seed",
        "42",
        "query.fa",
        "uniprot.fa",
        ">",
        "/work/jackhmmer/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_jackhmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_jackhmmer" / "results.tblout",
        "domtblout": tmp_path / "hmmer_jackhmmer" / "domains.domtblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": []}, tmp_path) == {
        "output": tmp_path / "hmmer_jackhmmer" / "output.txt",
    }


def test_hmmer_phmmer_renders_protein_search_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_phmmer")
    info = _registry().object_info()["hmmer_phmmer"]

    assert info["output"] == ["STATS_FILE", "TSV", "TSV", "TSV"]
    assert info["output_name"] == ["output", "tblout", "domtblout", "pfamtblout"]
    assert "10.1093/nar/gkr367" in info["citation_dois"]
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["required"]["seqdb"][0] == "FASTA"
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "domtblout", "pfamtblout"]
    assert info["input"]["optional"]["domT"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["score"]},
    }
    assert "relative_weighting" not in info["input"]["optional"]
    assert "effective_weighting" not in info["input"]["optional"]
    assert "prior" not in info["input"]["optional"]
    assert node_class.render_command(
        {
            "seqfile": "globins.fa",
            "seqdb": "uniprot.fa",
            "output_formats": ["tblout", "domtblout", "pfamtblout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "single_sequence_scoring": "singlemx",
            "popen": 0.04,
            "pextend": 0.45,
            "threshold_mode": "score",
            "score_threshold": 35,
            "incT": 40,
            "domT": 20,
            "incdomT": 25,
            "max": True,
            "F1": 0.03,
            "F2": 0.004,
            "F3": 2e-6,
            "nobias": True,
            "eml": 240,
            "emn": 230,
            "evl": 250,
            "evn": 240,
            "efl": 130,
            "efn": 220,
            "eft": 0.06,
            "nonull2": True,
            "z": 2000,
            "domz": 75,
            "threads": 8,
            "seed": 4,
            "output": "/work/phmmer",
        }
    ) == [
        "phmmer",
        "--tblout",
        "/work/phmmer/results.tblout",
        "--domtblout",
        "/work/phmmer/domains.domtblout",
        "--pfamtblout",
        "/work/phmmer/pfam.tblout",
        "--acc",
        "--noali",
        "--notextw",
        "--popen",
        "0.04",
        "--pextend",
        "0.45",
        "-T",
        "35",
        "--incT",
        "40",
        "--domT",
        "20",
        "--incdomT",
        "25",
        "--max",
        "--F1",
        "0.03",
        "--F2",
        "0.004",
        "--F3",
        "2e-06",
        "--nobias",
        "--EmL",
        "240",
        "--EmN",
        "230",
        "--EvL",
        "250",
        "--EvN",
        "240",
        "--EfL",
        "130",
        "--EfN",
        "220",
        "--Eft",
        "0.06",
        "--nonull2",
        "-Z",
        "2000",
        "--domZ",
        "75",
        "--cpu",
        "7",
        "--seed",
        "4",
        "globins.fa",
        "uniprot.fa",
        ">",
        "/work/phmmer/output.txt",
    ]
    assert node_class.render_command(
        {
            "seqfile": "globins.fa",
            "seqdb": "uniprot.fa",
            "output_formats": [],
            "threshold_mode": "evalue",
            "evalue": 10,
            "domE": 10,
            "threads": 1,
            "seed": 42,
            "output": "/work/phmmer",
        }
    ) == [
        "phmmer",
        "-E",
        "10",
        "--domE",
        "10",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--EmL",
        "200",
        "--EmN",
        "200",
        "--EvL",
        "200",
        "--EvN",
        "200",
        "--EfL",
        "100",
        "--EfN",
        "200",
        "--Eft",
        "0.04",
        "--cpu",
        "1",
        "--seed",
        "42",
        "globins.fa",
        "uniprot.fa",
        ">",
        "/work/phmmer/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_phmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_phmmer" / "results.tblout",
        "domtblout": tmp_path / "hmmer_phmmer" / "domains.domtblout",
        "pfamtblout": tmp_path / "hmmer_phmmer" / "pfam.tblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": ["tblout"]}, tmp_path) == {
        "output": tmp_path / "hmmer_phmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_phmmer" / "results.tblout",
    }


def test_hmmer_nhmmer_renders_nucleotide_search_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("hmmer_nhmmer")
    info = _registry().object_info()["hmmer_nhmmer"]

    assert info["output"] == ["STATS_FILE", "TSV", "TEXT", "TEXT"]
    assert info["output_name"] == ["output", "tblout", "dfamtblout", "aliscoresout"]
    assert "10.1093/bioinformatics/btt403" in info["citation_dois"]
    assert info["input"]["required"]["hmmfile"][0] == "FILE"
    assert info["input"]["required"]["seqfile"][0] == "FASTA"
    assert info["input"]["optional"]["output_formats"][1]["default"] == ["tblout", "dfamtblout"]
    assert info["input"]["optional"]["output_formats"][1]["options"] == ["tblout", "dfamtblout", "aliscoresout"]
    assert info["input"]["optional"]["input_format_select"][1]["options"] == ["--dna", "--rna"]
    assert info["input"]["optional"]["cut_mode"][1]["options"] == ["none", "--cut_ga", "--cut_nc", "--cut_tc"]
    assert info["input"]["optional"]["score_threshold"][1]["displayOptions"] == {
        "show": {"threshold_mode": ["score"]},
    }
    assert node_class.render_command(
        {
            "hmmfile": "MADE1.hmm",
            "seqfile": "dna_target.fa",
            "output_formats": ["tblout", "dfamtblout", "aliscoresout"],
            "acc": True,
            "noali": True,
            "notextw": True,
            "single_sequence_scoring": "singlemx",
            "popen": 0.03,
            "pextend": 0.5,
            "threshold_mode": "score",
            "score_threshold": 27,
            "incT": 31,
            "max": True,
            "F1": 0.04,
            "F2": 0.005,
            "F3": 3e-6,
            "nobias": True,
            "input_format_select": "--rna",
            "nonull2": True,
            "z": 1500,
            "domz": 60,
            "w_beta": 1e-7,
            "w_length": 120,
            "threads": 8,
            "seed": 4,
            "output": "/work/nhmmer",
        }
    ) == [
        "nhmmer",
        "--tblout",
        "/work/nhmmer/results.tblout",
        "--dfamtblout",
        "/work/nhmmer/dfam.tblout",
        "--aliscoresout",
        "/work/nhmmer/alignment_scores.txt",
        "--acc",
        "--noali",
        "--notextw",
        "--popen",
        "0.03",
        "--pextend",
        "0.5",
        "-T",
        "27",
        "--incT",
        "31",
        "--max",
        "--F1",
        "0.04",
        "--F2",
        "0.005",
        "--F3",
        "3e-06",
        "--nobias",
        "--rna",
        "--nonull2",
        "-Z",
        "1500",
        "--domZ",
        "60",
        "--w_beta",
        "1e-07",
        "--w_length",
        "120",
        "--cpu",
        "7",
        "--seed",
        "4",
        "MADE1.hmm",
        "dna_target.fa",
        ">",
        "/work/nhmmer/output.txt",
    ]
    assert node_class.render_command(
        {
            "hmmfile": "MADE1.hmm",
            "seqfile": "dna_target.fa",
            "output_formats": [],
            "threshold_mode": "cut",
            "cut_mode": "--cut_ga",
            "input_format_select": "--dna",
            "threads": 1,
            "seed": 42,
            "output": "/work/nhmmer",
        }
    ) == [
        "nhmmer",
        "--cut_ga",
        "--F1",
        "0.02",
        "--F2",
        "0.001",
        "--F3",
        "1e-05",
        "--dna",
        "--cpu",
        "1",
        "--seed",
        "42",
        "MADE1.hmm",
        "dna_target.fa",
        ">",
        "/work/nhmmer/output.txt",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == {
        "output": tmp_path / "hmmer_nhmmer" / "output.txt",
        "tblout": tmp_path / "hmmer_nhmmer" / "results.tblout",
        "dfamtblout": tmp_path / "hmmer_nhmmer" / "dfam.tblout",
    }
    assert node_class.PLAN_OUTPUTS({"output_formats": ["aliscoresout"]}, tmp_path) == {
        "output": tmp_path / "hmmer_nhmmer" / "output.txt",
        "aliscoresout": tmp_path / "hmmer_nhmmer" / "alignment_scores.txt",
    }


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
        "mash_sketch": {
            "display_name": "Mash Sketch",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-016-0997-x",
        },
        "mash_paste": {
            "display_name": "Mash Paste",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-016-0997-x",
        },
        "mash_screen": {
            "display_name": "Mash Screen",
            "category": "genomics",
            "required_executables": ["mash"],
            "required_conda_packages": ["mash"],
            "doi": "10.1186/s13059-019-1841-x",
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
        "lofreq_alnqual": {
            "display_name": "LoFreq Alignment Quality",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1093/nar/gks918",
        },
        "lofreq_indelqual": {
            "display_name": "LoFreq Indel Quality",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1101/gr.112326.110",
        },
        "lofreq_filter": {
            "display_name": "LoFreq Filter",
            "category": "variant",
            "required_executables": ["lofreq"],
            "required_conda_packages": ["lofreq"],
            "doi": "10.1093/nar/gks918",
        },
        "lofreq_viterbi": {
            "display_name": "LoFreq Viterbi Realignment",
            "category": "variant",
            "required_executables": ["lofreq", "samtools"],
            "required_conda_packages": ["lofreq", "samtools"],
            "doi": "10.1093/nar/gks918",
        },
        "ivar_trim": {
            "display_name": "iVar Trim",
            "category": "variant",
            "required_executables": ["scheme-convert", "ivar", "samtools"],
            "required_conda_packages": ["ivar", "viramp-hub", "samtools"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_variants": {
            "display_name": "iVar Variants",
            "category": "variant",
            "required_executables": ["samtools", "ivar"],
            "required_conda_packages": ["samtools", "ivar"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_consensus": {
            "display_name": "iVar Consensus",
            "category": "variant",
            "required_executables": ["samtools", "ivar"],
            "required_conda_packages": ["samtools", "ivar"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_filtervariants": {
            "display_name": "iVar Filter Variants",
            "category": "variant",
            "required_executables": ["ivar"],
            "required_conda_packages": ["ivar"],
            "doi": "10.1186/s13059-018-1618-7",
        },
        "ivar_removereads": {
            "display_name": "iVar Remove Reads",
            "category": "variant",
            "required_executables": ["scheme-convert", "ivar", "python"],
            "required_conda_packages": ["ivar", "viramp-hub", "python"],
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


def test_mash_sketch_renders_reads_and_assembly_commands(tmp_path: Path) -> None:
    node_class = _node_class("mash_sketch")
    info = _registry().object_info()["mash_sketch"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["sketch"]
    assert node_class.render_command(
        {
            "reads_assembly_selector": "reads",
            "reads_input_selector": "single",
            "reads": "reads.fastq.gz",
            "minimum_kmer_copies": 10,
            "target_coverage": 30,
            "genome_size": 5000000,
            "sketch_size": 5000,
            "kmer_size": 21,
            "prob_threshold": 0.01,
            "output": "/work/mash_sketch",
        }
    ) == (
        "ln -sf reads.fastq.gz reads.fastq.gz && "
        "mash sketch -s 5000 -k 21 -w 0.01 -m 10 -r -c 30 -g 5000000 "
        "reads.fastq.gz -o /work/mash_sketch/sketch"
    )
    assert node_class.render_command(
        {
            "reads_assembly_selector": "assembly",
            "assembly": "contigs.fasta",
            "individual_sequences": True,
            "threads": 8,
            "sketch_size": 1000,
            "kmer_size": 17,
            "prob_threshold": 0.1,
            "output": "/work/mash_sketch",
        }
    ) == (
        "ln -sf contigs.fasta contigs.fasta && "
        "mash sketch -s 1000 -k 17 -w 0.1 -p 8 -i contigs.fasta -o /work/mash_sketch/sketch"
    )
    assert node_class.render_command(
        {
            "reads_assembly_selector": "reads",
            "reads_input_selector": "paired",
            "reads_1": "L1 R1.fastq.gz",
            "reads_2": "L1 R2.fastq.gz",
            "minimum_kmer_copies": 2,
            "output": "/work/mash_sketch",
        }
    ) == (
        "cat 'L1 R1.fastq.gz' 'L1 R2.fastq.gz' > L1_R1.fastq.gz && "
        "mash sketch -s 1000 -k 21 -w 0.01 -m 2 -r L1_R1.fastq.gz -o /work/mash_sketch/sketch"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_sketch" / "sketch.msh"]


def test_mash_paste_renders_merge_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mash_paste")
    info = _registry().object_info()["mash_paste"]

    assert info["output"] == ["FILE"]
    assert info["output_name"] == ["sketch"]
    assert node_class.render_command(
        {
            "msh_files": ["alpha sketch.msh", "beta.msh"],
            "output": "/work/mash_paste",
        }
    ) == (
        "ln -sf 'alpha sketch.msh' alpha_sketch.msh && "
        "ln -sf beta.msh beta.msh && "
        "mash paste /work/mash_paste/sketch alpha_sketch.msh beta.msh"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_paste" / "sketch.msh"]


def test_mash_screen_renders_single_and_paired_commands_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mash_screen")
    info = _registry().object_info()["mash_screen"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["screen"]
    assert "10.1186/s13059-019-1841-x" in info["citation_dois"]
    assert "10.1186/s13059-016-0997-x" in info["citation_dois"]
    assert node_class.render_command(
        {
            "queries": "Ref Seq.msh",
            "pool_input_selector": "single",
            "pool": "reads.fastq.gz",
            "winner_takes_all": True,
            "minimum_identity_to_report": 0.8,
            "maximum_p_value_to_report": 0.05,
            "output": "/work/mash_screen",
        }
    ) == (
        "ln -sf 'Ref Seq.msh' queries.msh && "
        "mash screen -w -i 0.8 -v 0.05 queries.msh reads.fastq.gz > /work/mash_screen/screen.tsv"
    )
    assert node_class.render_command(
        {
            "queries": "refs.msh",
            "pool_input_selector": "paired",
            "pool_1": "R1.fastq.gz",
            "pool_2": "R2.fastq.gz",
            "winner_takes_all": False,
            "output": "/work/mash_screen",
        }
    ) == (
        "ln -sf refs.msh queries.msh && "
        "mash screen -i 0.0 -v 1.0 queries.msh R1.fastq.gz R2.fastq.gz > /work/mash_screen/screen.tsv"
    )
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mash_screen" / "screen.tsv"]


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


def test_lofreq_alnqual_renders_alignment_quality_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_alnqual")
    info = _registry().object_info()["lofreq_alnqual"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["reads_with_alignment_qualities"]
    assert info["input"]["optional"]["extended_baq"][1]["displayOptions"] == {
        "show": {"alnquals_to_use": ["", "-A"]},
    }
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "alnquals_to_use": "",
            "extended_baq": True,
            "recompute_all": False,
            "output": "/work/lofreq_alnqual",
        }
    ) == [
        "lofreq",
        "alnqual",
        "-b",
        "",
        "reads.bam",
        "ref.fa",
        ">",
        "/work/lofreq_alnqual/alnqual.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "alnquals_to_use": "-B",
            "recompute_all": True,
            "output": "/work/lofreq_alnqual",
        }
    ) == [
        "lofreq",
        "alnqual",
        "-b",
        "",
        "-B",
        "-r",
        "reads.bam",
        "ref.fa",
        ">",
        "/work/lofreq_alnqual/alnqual.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "alnquals_to_use": "-B",
            "extended_baq": False,
            "output": "/work/lofreq_alnqual",
        }
    ) == [
        "lofreq",
        "alnqual",
        "-b",
        "",
        "-B",
        "reads.bam",
        "ref.fa",
        ">",
        "/work/lofreq_alnqual/alnqual.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_alnqual" / "alnqual.bam"]


def test_lofreq_indelqual_renders_uniform_and_dindel_commands_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_indelqual")
    info = _registry().object_info()["lofreq_indelqual"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["reads_with_indel_qualities"]
    assert "10.1093/nar/gks918" in info["citation_dois"]
    assert "10.1101/gr.112326.110" in info["citation_dois"]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "strategy": "uniform",
            "insertions": 20,
            "deletions": 30,
            "output": "/work/lofreq_indelqual",
        }
    ) == [
        "lofreq",
        "indelqual",
        "--uniform",
        "20,30",
        "-o",
        "/work/lofreq_indelqual/indelqual.bam",
        "reads.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "strategy": "uniform",
            "insertions": 20,
            "deletions": "",
            "output": "/work/lofreq_indelqual",
        }
    ) == [
        "lofreq",
        "indelqual",
        "--uniform",
        "20",
        "-o",
        "/work/lofreq_indelqual/indelqual.bam",
        "reads.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "strategy": "dindel",
            "reference": "ref.fa",
            "output": "/work/lofreq_indelqual",
        }
    ) == [
        "lofreq",
        "indelqual",
        "--dindel",
        "--ref",
        "ref.fa",
        "-o",
        "/work/lofreq_indelqual/indelqual.bam",
        "reads.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_indelqual" / "indelqual.bam"]


def test_lofreq_filter_renders_quality_coverage_af_and_strand_bias_filters(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_filter")
    info = _registry().object_info()["lofreq_filter"]

    assert info["output"] == ["VCF"]
    assert info["output_name"] == ["filtered_variants"]
    assert "10.1093/nar/gks918" in info["citation_dois"]
    assert info["input"]["optional"]["snvqual_thresh"][1]["displayOptions"] == {
        "show": {"snvqual_filter": ["min-phred"]},
    }
    assert info["input"]["optional"]["indelqual_alpha"][1]["displayOptions"] == {
        "show": {"indelqual_filter": ["mtc"]},
    }
    assert node_class.render_command(
        {
            "invcf": "calls.vcf",
            "keep_only": "",
            "snvqual_filter": "min-phred",
            "snvqual_thresh": 38,
            "indelqual_filter": "min-phred",
            "indelqual_thresh": 20,
            "cov_min": 12,
            "cov_max": 300,
            "af_min": 0.02,
            "af_max": 0.7,
            "strand_bias": "mtc",
            "sb_mtc": "fdr",
            "sb_alpha": 0.001,
            "sb_compound": False,
            "sb_indels": True,
            "flag_or_drop": "--print-all",
            "output": "/work/lofreq_filter",
        }
    ) == [
        "lofreq",
        "filter",
        "-i",
        "calls.vcf",
        "--no-defaults",
        "--verbose",
        "--print-all",
        "-Q",
        "38",
        "-K",
        "20",
        "-v",
        "12",
        "-V",
        "300",
        "-a",
        "0.02",
        "-A",
        "0.7",
        "-b",
        "fdr",
        "-c",
        "0.001",
        "--sb-no-compound",
        "--sb-incl-indels",
        "-o",
        "/work/lofreq_filter/filtered.vcf",
    ]
    assert node_class.render_command(
        {
            "invcf": "calls.vcf",
            "keep_only": "--only-snvs",
            "snvqual_filter": "mtc",
            "snvqual_mtc": "bonf",
            "snvqual_alpha": 0.01,
            "snvqual_ntests": 66,
            "cov_min": 0,
            "cov_max": 0,
            "af_min": 0.05,
            "af_max": 1,
            "strand_bias": "no",
            "output": "/work/lofreq_filter",
        }
    ) == [
        "lofreq",
        "filter",
        "-i",
        "calls.vcf",
        "--no-defaults",
        "--verbose",
        "--only-snvs",
        "-q",
        "bonf",
        "-r",
        "0.01",
        "-s",
        "66",
        "-v",
        "0",
        "-V",
        "0",
        "-a",
        "0.05",
        "-A",
        "1",
        "-o",
        "/work/lofreq_filter/filtered.vcf",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_filter" / "filtered.vcf"]


def test_lofreq_viterbi_renders_realignment_sort_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("lofreq_viterbi")
    info = _registry().object_info()["lofreq_viterbi"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["realigned_reads"]
    assert "10.1093/nar/gks918" in info["citation_dois"]
    assert info["input"]["optional"]["defqual"][1]["displayOptions"] == {
        "show": {"replace_bq2": ["fixed"]},
    }
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "keepflags": True,
            "replace_bq2": "fixed",
            "defqual": 17,
            "threads": 8,
            "output": "/work/lofreq_viterbi",
        }
    ) == [
        "lofreq",
        "viterbi",
        "--ref",
        "ref.fa",
        "--keepflags",
        "--defqual",
        "17",
        "--out",
        "/work/lofreq_viterbi/tmp.bam",
        "reads.bam",
        "&&",
        "samtools",
        "sort",
        "--no-PG",
        "-T",
        "${TMPDIR:-.}",
        "-@",
        "8",
        "-O",
        "BAM",
        "-o",
        "/work/lofreq_viterbi/realigned.bam",
        "/work/lofreq_viterbi/tmp.bam",
    ]
    assert node_class.render_command(
        {
            "reads": "reads.bam",
            "reference": "ref.fa",
            "replace_bq2": "dynamic",
            "output": "/work/lofreq_viterbi",
        }
    ) == [
        "lofreq",
        "viterbi",
        "--ref",
        "ref.fa",
        "--defqual",
        "-1",
        "--out",
        "/work/lofreq_viterbi/tmp.bam",
        "reads.bam",
        "&&",
        "samtools",
        "sort",
        "--no-PG",
        "-T",
        "${TMPDIR:-.}",
        "-@",
        "1",
        "-O",
        "BAM",
        "-o",
        "/work/lofreq_viterbi/realigned.bam",
        "/work/lofreq_viterbi/tmp.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "lofreq_viterbi" / "realigned.bam"]


def test_ivar_trim_renders_primer_trim_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_trim")
    info = _registry().object_info()["ivar_trim"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["trimmed_bam"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert info["input"]["optional"]["amplicon_info"][1]["displayOptions"] == {
        "show": {"amplicon_mode": ["provided"]},
    }
    assert info["input"]["optional"]["min_len"][1]["displayOptions"] == {
        "show": {"trimmed_length_filter": ["custom"]},
    }
    assert node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "input_bed": "primers.bed",
            "amplicon_mode": "provided",
            "amplicon_info": "pairs.tsv",
            "primer_pos_wiggle": 3,
            "include_reads_without_primers": True,
            "trimmed_length_filter": "custom",
            "min_len": 45,
            "min_qual": 25,
            "window_width": 6,
            "threads": 8,
            "output": "/work/ivar_trim",
        }
    ) == [
        "scheme-convert",
        "--to",
        "bed",
        "--bed-type",
        "ivar",
        "-o",
        "/work/ivar_trim/ivar.bed",
        "primers.bed",
        "&&",
        "scheme-convert",
        "-a",
        "pairs.tsv",
        "--to",
        "amplicon-info",
        "-r",
        "outer",
        "-o",
        "/work/ivar_trim/amplicon_info.tsv",
        "/work/ivar_trim/ivar.bed",
        "&&",
        "ivar",
        "trim",
        "-i",
        "aligned.sorted.bam",
        "-b",
        "/work/ivar_trim/ivar.bed",
        "-f",
        "/work/ivar_trim/amplicon_info.tsv",
        "-x",
        "3",
        "-e",
        "-m",
        "45",
        "-q",
        "25",
        "-s",
        "6",
        "|",
        "samtools",
        "sort",
        "-@",
        "8",
        "-T",
        "${TMPDIR:-.}",
        "-o",
        "/work/ivar_trim/trimmed.sorted.bam",
        "-",
    ]

    computed_cmd = node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "input_bed": "primers.bed",
            "amplicon_mode": "computed",
            "trimmed_length_filter": "auto",
            "output": "/work/ivar_trim",
        }
    )
    assert "-a" not in computed_cmd
    assert "-f" in computed_cmd
    assert "-1" in computed_cmd

    no_filter_cmd = node_class.render_command(
        {
            "input_bam": "aligned.sorted.bam",
            "input_bed": "primers.bed",
            "amplicon_mode": "none",
            "trimmed_length_filter": "off",
            "output": "/work/ivar_trim",
        }
    )
    assert "amplicon-info" not in no_filter_cmd
    assert "-f" not in no_filter_cmd
    assert no_filter_cmd[no_filter_cmd.index("-m") + 1] == "0"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_trim" / "trimmed.sorted.bam"]


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


def test_ivar_consensus_renders_mpileup_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_consensus")
    info = _registry().object_info()["ivar_consensus"]

    assert info["output"] == ["FASTA"]
    assert info["output_name"] == ["consensus_fasta"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bam": "sorted.bam",
            "min_qual": 25,
            "min_freq": 0.5,
            "min_indel_freq": 0.9,
            "min_depth": 12,
            "depth_action": "-n -",
            "output": "/work/ivar_consensus",
        }
    ) == [
        "samtools",
        "mpileup",
        "-A",
        "-a",
        "-d",
        "0",
        "-Q",
        "0",
        "sorted.bam",
        "|",
        "ivar",
        "consensus",
        "-p",
        "/work/ivar_consensus/consensus",
        "-q",
        "25",
        "-t",
        "0.5",
        "-c",
        "0.9",
        "-m",
        "12",
        "-n",
        "-",
    ]
    assert node_class.render_command(
        {
            "input_bam": "sorted.bam",
            "depth_action": "-k",
            "output": "/work/ivar_consensus",
        }
    )[-1] == "-k"

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_consensus" / "consensus.fa"]


def test_ivar_filtervariants_renders_replicate_filter_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_filtervariants")
    info = _registry().object_info()["ivar_filtervariants"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["filtered_variants"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert node_class.render_command(
        {
            "inputs": ["replicate-a.tsv", "replicate-b.tsv", "replicate-c.tsv"],
            "min_fraction": 0.5,
            "output": "/work/ivar_filtervariants",
        }
    ) == [
        "ivar",
        "filtervariants",
        "-t",
        "0.5",
        "-p",
        "/work/ivar_filtervariants/filtered",
        "replicate-a.tsv",
        "replicate-b.tsv",
        "replicate-c.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_filtervariants" / "filtered.tsv"]


def test_ivar_complete_mask_expands_masked_primers_to_full_amplicons(tmp_path: Path) -> None:
    from bionodulo.nodes.scripts.ivar_complete_mask import complete_mask_file

    masked = tmp_path / "masked_primers.txt"
    amplicons = tmp_path / "amplicon_info.tsv"
    masked.write_text("400_2_out_L\t400_3_out_R\n", encoding="utf-8")
    amplicons.write_text(
        "400_1_out_L\t400_1_out_R\n"
        "400_2_out_L\t400_2_out_R\n"
        "400_3_out_L\t400_3_out_R\n",
        encoding="utf-8",
    )

    result = complete_mask_file(masked, amplicons)

    assert result == ["400_2_out_L", "400_2_out_R", "400_3_out_L", "400_3_out_R"]
    assert masked.read_text(encoding="utf-8") == "400_2_out_L\t400_2_out_R\t400_3_out_L\t400_3_out_R\n"


def test_ivar_removereads_renders_mask_and_remove_pipeline_and_output(tmp_path: Path) -> None:
    node_class = _node_class("ivar_removereads")
    info = _registry().object_info()["ivar_removereads"]

    assert info["output"] == ["BAM"]
    assert info["output_name"] == ["filtered_bam"]
    assert "10.1186/s13059-018-1618-7" in info["citation_dois"]
    assert node_class.render_command(
        {
            "input_bam": "trimmed.sorted.bam",
            "variants_tsv": "primer_variants.tsv",
            "input_bed": "primers.bed",
            "amplicon_mode": "provided",
            "amplicon_info": "pairs.tsv",
            "output": "/work/ivar_removereads",
        }
    ) == [
        "scheme-convert",
        "--to",
        "bed",
        "--bed-type",
        "ivar",
        "-o",
        "/work/ivar_removereads/ivar.bed",
        "primers.bed",
        "&&",
        "scheme-convert",
        "-a",
        "pairs.tsv",
        "--to",
        "amplicon-info",
        "-o",
        "/work/ivar_removereads/amplicon_info.tsv",
        "/work/ivar_removereads/ivar.bed",
        "&&",
        "ivar",
        "getmasked",
        "-i",
        "primer_variants.tsv",
        "-b",
        "/work/ivar_removereads/ivar.bed",
        "-f",
        "/work/ivar_removereads/amplicon_info.tsv",
        "-p",
        "/work/ivar_removereads/masked_primers",
        "&&",
        "python",
        "-m",
        "bionodulo.nodes.scripts.ivar_complete_mask",
        "/work/ivar_removereads/masked_primers.txt",
        "/work/ivar_removereads/amplicon_info.tsv",
        "&&",
        "ivar",
        "removereads",
        "-i",
        "trimmed.sorted.bam",
        "-b",
        "/work/ivar_removereads/ivar.bed",
        "-p",
        "/work/ivar_removereads/removed_reads.bam",
        "-t",
        "/work/ivar_removereads/masked_primers.txt",
    ]

    computed_cmd = node_class.render_command(
        {
            "input_bam": "trimmed.sorted.bam",
            "variants_tsv": "primer_variants.tsv",
            "input_bed": "primers.bed",
            "amplicon_mode": "computed",
            "output": "/work/ivar_removereads",
        }
    )
    assert "-a" not in computed_cmd
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "ivar_removereads" / "removed_reads.bam"]


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
        "rseqc_fpkm_count": {
            "display_name": "RSeQC FPKM Count",
            "category": "rna_seq",
            "required_executables": ["FPKM_count.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_rpkm_saturation": {
            "display_name": "RSeQC RPKM Saturation",
            "category": "rna_seq",
            "required_executables": ["RPKM_saturation.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_bam2wig": {
            "display_name": "RSeQC BAM to Wiggle",
            "category": "rna_seq",
            "required_executables": ["bam2wig.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_clipping_profile": {
            "display_name": "RSeQC Clipping Profile",
            "category": "rna_seq",
            "required_executables": ["clipping_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_deletion_profile": {
            "display_name": "RSeQC Deletion Profile",
            "category": "rna_seq",
            "required_executables": ["deletion_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_gene_body_coverage": {
            "display_name": "RSeQC Gene Body Coverage",
            "category": "rna_seq",
            "required_executables": ["geneBody_coverage.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_gene_body_coverage2": {
            "display_name": "RSeQC Gene Body Coverage BigWig",
            "category": "rna_seq",
            "required_executables": ["geneBody_coverage2.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_inner_distance": {
            "display_name": "RSeQC Inner Distance",
            "category": "rna_seq",
            "required_executables": ["inner_distance.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_insertion_profile": {
            "display_name": "RSeQC Insertion Profile",
            "category": "rna_seq",
            "required_executables": ["insertion_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_hexamer": {
            "display_name": "RSeQC Read Hexamer",
            "category": "rna_seq",
            "required_executables": ["read_hexamer.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_quality": {
            "display_name": "RSeQC Read Quality",
            "category": "rna_seq",
            "required_executables": ["read_quality.py"],
            "required_conda_packages": ["rseqc", "r-base"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_rna_fragment_size": {
            "display_name": "RSeQC RNA Fragment Size",
            "category": "rna_seq",
            "required_executables": ["RNA_fragment_size.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_junction_annotation": {
            "display_name": "RSeQC Junction Annotation",
            "category": "rna_seq",
            "required_executables": ["junction_annotation.py"],
            "required_conda_packages": ["rseqc", "r-base"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_junction_saturation": {
            "display_name": "RSeQC Junction Saturation",
            "category": "rna_seq",
            "required_executables": ["junction_saturation.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_mismatch_profile": {
            "display_name": "RSeQC Mismatch Profile",
            "category": "rna_seq",
            "required_executables": ["mismatch_profile.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_gc": {
            "display_name": "RSeQC Read GC",
            "category": "rna_seq",
            "required_executables": ["read_GC.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_nvc": {
            "display_name": "RSeQC Read NVC",
            "category": "rna_seq",
            "required_executables": ["read_NVC.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_bam_stat": {
            "display_name": "RSeQC BAM Stat",
            "category": "rna_seq",
            "required_executables": ["bam_stat.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_distribution": {
            "display_name": "RSeQC Read Distribution",
            "category": "rna_seq",
            "required_executables": ["read_distribution.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_read_duplication": {
            "display_name": "RSeQC Read Duplication",
            "category": "rna_seq",
            "required_executables": ["read_duplication.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1093/bioinformatics/bts356",
        },
        "rseqc_tin": {
            "display_name": "RSeQC Transcript Integrity Number",
            "category": "rna_seq",
            "required_executables": ["tin.py"],
            "required_conda_packages": ["rseqc"],
            "doi": "10.1186/s12859-016-0922-z",
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


def test_rseqc_fpkm_count_renders_expression_quantification_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_fpkm_count")
    info = _registry().object_info()["rseqc_fpkm_count"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["fpkm_counts"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "strand_specific": "pair",
            "pair_type": "ds",
            "skip_multi_hits": True,
            "mapq": 20,
            "only_exonic": True,
            "single_read": "0.5",
            "output": "/work/rseqc_fpkm_count",
        }
    ) == [
        "FPKM_count.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_fpkm_count/output",
        "-r",
        "genes.bed12",
        "-d",
        "1+-,1-+,2++,2--",
        "--skip-multi-hits",
        "--mapq",
        "20",
        "--only-exonic",
        "--single-read=0.5",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_fpkm_count" / "output.FPKM.xls",
    ]


def test_rseqc_rpkm_saturation_renders_saturation_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_rpkm_saturation")
    info = _registry().object_info()["rseqc_rpkm_saturation"]

    assert info["output"] == ["IMAGE", "TSV", "TSV", "TEXT"]
    assert info["output_name"] == ["saturation_plot", "rpkm_values", "raw_counts", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed",
            "strand_specific": "none",
            "percentile_floor": 10,
            "percentile_ceiling": 90,
            "percentile_step": 10,
            "rpkm_cutoff": "0.05",
            "mapq": 25,
            "rscript_output": True,
            "output": "/work/rseqc_rpkm_saturation",
        }
    ) == [
        "RPKM_saturation.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_rpkm_saturation/output",
        "-r",
        "genes.bed",
        "-l",
        "10",
        "-u",
        "90",
        "-s",
        "10",
        "-c",
        "0.05",
        "--mapq",
        "25",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed",
            "strand_specific": "pair",
            "pair_type": "ds",
            "output": "/work/rseqc_rpkm_saturation",
        }
    ) == [
        "RPKM_saturation.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_rpkm_saturation/output",
        "-r",
        "genes.bed",
        "-d",
        "1+-,1-+,2++,2--",
        "-l",
        "5",
        "-u",
        "100",
        "-s",
        "5",
        "-c",
        "0.01",
        "--mapq",
        "30",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_rpkm_saturation" / "output.saturation.pdf",
        tmp_path / "rseqc_rpkm_saturation" / "output.eRPKM.xls",
        tmp_path / "rseqc_rpkm_saturation" / "output.rawCount.xls",
        tmp_path / "rseqc_rpkm_saturation" / "output.saturation.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_rpkm_saturation" / "output.saturation.pdf",
        tmp_path / "rseqc_rpkm_saturation" / "output.eRPKM.xls",
        tmp_path / "rseqc_rpkm_saturation" / "output.rawCount.xls",
    ]


def test_rseqc_bam2wig_renders_wiggle_commands_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_bam2wig")
    info = _registry().object_info()["rseqc_bam2wig"]

    assert info["output"] == ["WIG", "WIG", "WIG"]
    assert info["output_name"] == ["wiggle", "forward_wiggle", "reverse_wiggle"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "chromsize": "hg19.chrom.sizes",
            "normalize": True,
            "totalwig": 100,
            "skip_multi_hits": True,
            "mapq": 20,
            "strand_specific": "none",
            "output": "/work/rseqc_bam2wig",
        }
    ) == [
        "bam2wig.py",
        "-i",
        "aligned.bam",
        "-s",
        "hg19.chrom.sizes",
        "-o",
        "/work/rseqc_bam2wig/outfile",
        "-t",
        "100",
        "--skip-multi-hits",
        "--mapq",
        "20",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "chromsize": "hg19.chrom.sizes",
            "strand_specific": "pair",
            "pair_type": "ds",
            "output": "/work/rseqc_bam2wig",
        }
    ) == [
        "bam2wig.py",
        "-i",
        "aligned.bam",
        "-s",
        "hg19.chrom.sizes",
        "-o",
        "/work/rseqc_bam2wig/outfile",
        "-d",
        "1+-,1-+,2++,2--",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "chromsize": "hg19.chrom.sizes",
            "strand_specific": "single",
            "single_type": "d",
            "output": "/work/rseqc_bam2wig",
        }
    ) == [
        "bam2wig.py",
        "-i",
        "aligned.bam",
        "-s",
        "hg19.chrom.sizes",
        "-o",
        "/work/rseqc_bam2wig/outfile",
        "-d",
        "+-,-+",
    ]

    assert node_class.PLAN_OUTPUTS({"strand_specific": "none"}, tmp_path) == [
        tmp_path / "rseqc_bam2wig" / "outfile.wig",
    ]
    assert node_class.PLAN_OUTPUTS({"strand_specific": "pair"}, tmp_path) == [
        tmp_path / "rseqc_bam2wig" / "outfile.Forward.wig",
        tmp_path / "rseqc_bam2wig" / "outfile.Reverse.wig",
    ]


def test_rseqc_clipping_profile_renders_clipping_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_clipping_profile")
    info = _registry().object_info()["rseqc_clipping_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["clipping_profile_plot", "clipping_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "mapq": 20,
            "layout": "PE",
            "rscript_output": True,
            "output": "/work/rseqc_clipping_profile",
        }
    ) == [
        "clipping_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_clipping_profile/output",
        "-q",
        "20",
        "-s",
        "PE",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.pdf",
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.xls",
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.pdf",
        tmp_path / "rseqc_clipping_profile" / "output.clipping_profile.xls",
    ]


def test_rseqc_deletion_profile_renders_deletion_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_deletion_profile")
    info = _registry().object_info()["rseqc_deletion_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["deletion_profile_plot", "deletion_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "read_align_length": 101,
            "read_num": 500000,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_deletion_profile",
        }
    ) == [
        "deletion_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_deletion_profile/output",
        "-l",
        "101",
        "-n",
        "500000",
        "-q",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.pdf",
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.txt",
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.pdf",
        tmp_path / "rseqc_deletion_profile" / "output.deletion_profile.txt",
    ]


def test_rseqc_gene_body_coverage_renders_single_bam_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_gene_body_coverage")
    info = _registry().object_info()["rseqc_gene_body_coverage"]

    assert info["output"] == ["IMAGE", "IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["coverage_curves", "coverage_heatmap", "coverage_table", "r_script"]
    assert node_class.render_command(
        {
            "input": "sample.bam",
            "refgene": "genes.bed12",
            "minimum_length": 150,
            "rscript_output": True,
            "output": "/work/rseqc_gene_body_coverage",
        }
    ) == [
        "geneBody_coverage.py",
        "-i",
        "sample.bam",
        "-r",
        "genes.bed12",
        "--minimum_length",
        "150",
        "-o",
        "/work/rseqc_gene_body_coverage/output",
    ]

    assert node_class.PLAN_OUTPUTS({"input": "sample.bam", "rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.r",
    ]
    assert node_class.PLAN_OUTPUTS({"input": "sample.bam", "rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
    ]


def test_rseqc_gene_body_coverage_renders_merged_bam_command_and_heatmap(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_gene_body_coverage")

    assert node_class.render_command(
        {
            "input": ["sample A.bam", "sample-B.bam", "sample-B.bam"],
            "refgene": "genes.bed12",
            "minimum_length": 100,
            "output": "/work/rseqc_gene_body_coverage",
        }
    ) == [
        "mkdir",
        "-p",
        "/work/rseqc_gene_body_coverage/input_bams",
        "&&",
        "ln",
        "-sf",
        "sample A.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample_A.bam",
        "&&",
        "ln",
        "-sf",
        "sample-B.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.bam",
        "&&",
        "ln",
        "-sf",
        "sample-B.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.2.bam",
        "&&",
        "printf",
        "%s\\n",
        "/work/rseqc_gene_body_coverage/input_bams/sample_A.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.bam",
        "/work/rseqc_gene_body_coverage/input_bams/sample-B.2.bam",
        ">",
        "/work/rseqc_gene_body_coverage/input_list.txt",
        "&&",
        "geneBody_coverage.py",
        "-i",
        "/work/rseqc_gene_body_coverage/input_list.txt",
        "-r",
        "genes.bed12",
        "--minimum_length",
        "100",
        "-o",
        "/work/rseqc_gene_body_coverage/output",
    ]

    assert node_class.PLAN_OUTPUTS({"input": ["A.bam", "B.bam", "C.bam"], "rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.heatMap.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.r",
    ]
    assert node_class.PLAN_OUTPUTS({"input": ["A.bam", "B.bam"], "rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.r",
    ]


def test_rseqc_gene_body_coverage2_renders_bigwig_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_gene_body_coverage2")
    info = _registry().object_info()["rseqc_gene_body_coverage2"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["coverage_plot", "coverage_table", "r_script"]
    assert node_class.render_command(
        {
            "input": "coverage.bw",
            "refgene": "genes.bed12",
            "rscript_output": True,
            "output": "/work/rseqc_gene_body_coverage2",
        }
    ) == [
        "geneBody_coverage2.py",
        "-i",
        "coverage.bw",
        "-r",
        "genes.bed12",
        "-o",
        "/work/rseqc_gene_body_coverage2/output",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.pdf",
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.txt",
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.pdf",
        tmp_path / "rseqc_gene_body_coverage2" / "output.geneBodyCoverage.txt",
    ]


def test_rseqc_inner_distance_renders_insert_size_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_inner_distance")
    info = _registry().object_info()["rseqc_inner_distance"]

    assert info["output"] == ["IMAGE", "TSV", "TSV", "TEXT"]
    assert info["output_name"] == ["inner_distance_plot", "inner_distances", "inner_distance_frequency", "r_script"]
    assert node_class.render_command(
        {
            "input": "paired.bam",
            "refgene": "genes.bed12",
            "sample_size": 500000,
            "lower_bound": -200,
            "upper_bound": 300,
            "step": 10,
            "mapq": 25,
            "rscript_output": True,
            "output": "/work/rseqc_inner_distance",
        }
    ) == [
        "inner_distance.py",
        "-i",
        "paired.bam",
        "-o",
        "/work/rseqc_inner_distance/output",
        "-r",
        "genes.bed12",
        "--sample-size",
        "500000",
        "--lower-bound",
        "-200",
        "--upper-bound",
        "300",
        "--step",
        "10",
        "--mapq",
        "25",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_plot.pdf",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance.txt",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_freq.txt",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_plot.pdf",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance.txt",
        tmp_path / "rseqc_inner_distance" / "output.inner_distance_freq.txt",
    ]


def test_rseqc_insertion_profile_renders_inserted_base_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_insertion_profile")
    info = _registry().object_info()["rseqc_insertion_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["insertion_profile_plot", "insertion_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "mapq": 20,
            "layout": "PE",
            "rscript_output": True,
            "output": "/work/rseqc_insertion_profile",
        }
    ) == [
        "insertion_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_insertion_profile/output",
        "-q",
        "20",
        "-s",
        "PE",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.pdf",
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.xls",
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.pdf",
        tmp_path / "rseqc_insertion_profile" / "output.insertion_profile.xls",
    ]


def test_rseqc_read_hexamer_renders_multi_input_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_hexamer")
    info = _registry().object_info()["rseqc_read_hexamer"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["hexamer_frequencies"]
    assert node_class.render_command(
        {
            "inputs": ["reads/R1.fastq.gz", "reads/R1.fastq.gz", "transcripts.fa"],
            "refgenome": "genome.fa",
            "refgene": "mrna.fa",
            "output": "/work/rseqc_read_hexamer",
        }
    ) == (
        "gunzip -c reads/R1.fastq.gz > R1_fastq_gz && "
        "gunzip -c reads/R1.fastq.gz > R1_fastq_gz.1 && "
        "ln -sf transcripts.fa transcripts_fa && "
        "read_hexamer.py -i R1_fastq_gz,R1_fastq_gz.1,transcripts_fa "
        "-r genome.fa -g mrna.fa > /work/rseqc_read_hexamer/read_hexamer.tsv"
    )
    assert node_class.render_command(
        {
            "inputs": ["reads R2.fastq", "amplicons.fasta"],
            "output": "/work/rseqc_read_hexamer",
        }
    ) == (
        "ln -sf 'reads R2.fastq' reads_R2_fastq && "
        "ln -sf amplicons.fasta amplicons_fasta && "
        "read_hexamer.py -i reads_R2_fastq,amplicons_fasta > /work/rseqc_read_hexamer/read_hexamer.tsv"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_read_hexamer" / "read_hexamer.tsv",
    ]


def test_rseqc_read_quality_renders_phred_quality_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_quality")
    info = _registry().object_info()["rseqc_read_quality"]

    assert info["output"] == ["IMAGE", "IMAGE", "TEXT"]
    assert info["output_name"] == ["quality_heatmap", "quality_boxplot", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "reduce": 500,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_read_quality",
        }
    ) == [
        "read_quality.py",
        "--input-file",
        "aligned.bam",
        "--out-prefix",
        "/work/rseqc_read_quality/output",
        "-r",
        "500",
        "--mapq",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_quality" / "output.qual.heatmap.pdf",
        tmp_path / "rseqc_read_quality" / "output.qual.boxplot.pdf",
        tmp_path / "rseqc_read_quality" / "output.qual.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_quality" / "output.qual.heatmap.pdf",
        tmp_path / "rseqc_read_quality" / "output.qual.boxplot.pdf",
    ]


def test_rseqc_rna_fragment_size_renders_fragment_size_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_rna_fragment_size")
    info = _registry().object_info()["rseqc_rna_fragment_size"]

    assert info["output"] == ["TSV"]
    assert info["output_name"] == ["fragment_sizes"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "mapq": 20,
            "frag_num": 5,
            "output": "/work/rseqc_rna_fragment_size",
        }
    ) == [
        "RNA_fragment_size.py",
        "-i",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--mapq",
        "20",
        "--frag-num",
        "5",
        ">",
        "/work/rseqc_rna_fragment_size/fragment_sizes.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_rna_fragment_size" / "fragment_sizes.tsv",
    ]


def test_rseqc_junction_annotation_renders_splice_junction_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_junction_annotation")
    info = _registry().object_info()["rseqc_junction_annotation"]

    assert info["output"] == ["IMAGE", "IMAGE", "TSV", "TEXT", "STATS_FILE"]
    assert info["output_name"] == [
        "splice_events_plot",
        "splice_junction_plot",
        "junctions",
        "r_script",
        "stats",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "min_intron": 75,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_junction_annotation",
        }
    ) == [
        "junction_annotation.py",
        "--input-file",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--out-prefix",
        "/work/rseqc_junction_annotation/output",
        "--min-intron",
        "75",
        "--mapq",
        "20",
        "2>",
        "/work/rseqc_junction_annotation/stats.txt",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_junction_annotation" / "output.splice_events.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.splice_junction.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.junction.xls",
        tmp_path / "rseqc_junction_annotation" / "output.junction_plot.r",
        tmp_path / "rseqc_junction_annotation" / "stats.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_junction_annotation" / "output.splice_events.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.splice_junction.pdf",
        tmp_path / "rseqc_junction_annotation" / "output.junction.xls",
        tmp_path / "rseqc_junction_annotation" / "stats.txt",
    ]


def test_rseqc_junction_saturation_renders_saturation_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_junction_saturation")
    info = _registry().object_info()["rseqc_junction_saturation"]

    assert info["output"] == ["IMAGE", "TEXT"]
    assert info["output_name"] == ["junction_saturation_plot", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "min_intron": 75,
            "min_coverage": 2,
            "mapq": 20,
            "output": "/work/rseqc_junction_saturation",
        }
    ) == [
        "junction_saturation.py",
        "--input-file",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--out-prefix",
        "/work/rseqc_junction_saturation/output",
        "--min-intron",
        "75",
        "--min-coverage",
        "2",
        "--mapq",
        "20",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "min_intron": 75,
            "min_coverage": 2,
            "mapq": 20,
            "percentiles_mode": "specify",
            "percentile_floor": 10,
            "percentile_ceiling": 90,
            "percentile_step": 10,
            "output": "/work/rseqc_junction_saturation",
        }
    ) == [
        "junction_saturation.py",
        "--input-file",
        "aligned.bam",
        "--refgene",
        "genes.bed12",
        "--out-prefix",
        "/work/rseqc_junction_saturation/output",
        "--min-intron",
        "75",
        "--min-coverage",
        "2",
        "--mapq",
        "20",
        "--percentile-floor",
        "10",
        "--percentile-ceiling",
        "90",
        "--percentile-step",
        "10",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_junction_saturation" / "output.junctionSaturation_plot.pdf",
        tmp_path / "rseqc_junction_saturation" / "output.junctionSaturation_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_junction_saturation" / "output.junctionSaturation_plot.pdf",
    ]


def test_rseqc_mismatch_profile_renders_mismatch_profile_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_mismatch_profile")
    info = _registry().object_info()["rseqc_mismatch_profile"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["mismatch_profile_plot", "mismatch_profile", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "read_align_length": 101,
            "read_num": 500000,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_mismatch_profile",
        }
    ) == [
        "mismatch_profile.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_mismatch_profile/output",
        "-l",
        "101",
        "-n",
        "500000",
        "-q",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.pdf",
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.xls",
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.pdf",
        tmp_path / "rseqc_mismatch_profile" / "output.mismatch_profile.xls",
    ]


def test_rseqc_read_gc_renders_gc_content_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_gc")
    info = _registry().object_info()["rseqc_read_gc"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["gc_plot", "gc_counts", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.sam",
            "mapq": 15,
            "rscript_output": True,
            "output": "/work/rseqc_read_gc",
        }
    ) == [
        "read_GC.py",
        "--input-file",
        "aligned.sam",
        "--out-prefix",
        "/work/rseqc_read_gc/output",
        "--mapq",
        "15",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_gc" / "output.GC_plot.pdf",
        tmp_path / "rseqc_read_gc" / "output.GC.xls",
        tmp_path / "rseqc_read_gc" / "output.GC_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_gc" / "output.GC_plot.pdf",
        tmp_path / "rseqc_read_gc" / "output.GC.xls",
    ]


def test_rseqc_read_nvc_renders_nucleotide_cycle_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_nvc")
    info = _registry().object_info()["rseqc_read_nvc"]

    assert info["output"] == ["IMAGE", "TSV", "TEXT"]
    assert info["output_name"] == ["nvc_plot", "nvc_table", "r_script"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "nx": False,
            "mapq": 25,
            "rscript_output": True,
            "output": "/work/rseqc_read_nvc",
        }
    ) == [
        "read_NVC.py",
        "--input-file",
        "aligned.bam",
        "--out-prefix",
        "/work/rseqc_read_nvc/output",
        "--mapq",
        "25",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "nx": True,
            "mapq": 25,
            "output": "/work/rseqc_read_nvc",
        }
    ) == [
        "read_NVC.py",
        "--input-file",
        "aligned.bam",
        "--out-prefix",
        "/work/rseqc_read_nvc/output",
        "--nx",
        "--mapq",
        "25",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_nvc" / "output.NVC_plot.pdf",
        tmp_path / "rseqc_read_nvc" / "output.NVC.xls",
        tmp_path / "rseqc_read_nvc" / "output.NVC_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_nvc" / "output.NVC_plot.pdf",
        tmp_path / "rseqc_read_nvc" / "output.NVC.xls",
    ]


def test_rseqc_bam_stat_renders_mapping_stats_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_bam_stat")
    info = _registry().object_info()["rseqc_bam_stat"]

    assert info["output"] == ["STATS_FILE"]
    assert info["output_name"] == ["mapping_stats"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "mapq": 20,
            "output": "/work/rseqc_bam_stat",
        }
    ) == [
        "bam_stat.py",
        "-i",
        "aligned.bam",
        "-q",
        "20",
        ">",
        "/work/rseqc_bam_stat/bam_stat.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_bam_stat" / "bam_stat.txt",
    ]


def test_rseqc_read_distribution_renders_feature_distribution_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_distribution")
    info = _registry().object_info()["rseqc_read_distribution"]

    assert info["output"] == ["STATS_FILE"]
    assert info["output_name"] == ["read_distribution"]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "output": "/work/rseqc_read_distribution",
        }
    ) == [
        "read_distribution.py",
        "-i",
        "aligned.bam",
        "-r",
        "genes.bed12",
        ">",
        "/work/rseqc_read_distribution/read_distribution.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_read_distribution" / "read_distribution.txt",
    ]


def test_rseqc_read_duplication_renders_duplication_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_read_duplication")
    info = _registry().object_info()["rseqc_read_duplication"]

    assert info["output"] == ["IMAGE", "TSV", "TSV", "TEXT"]
    assert info["output_name"] == [
        "duplication_plot",
        "position_duplication",
        "sequence_duplication",
        "r_script",
    ]
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "up_limit": 750,
            "mapq": 20,
            "rscript_output": True,
            "output": "/work/rseqc_read_duplication",
        }
    ) == [
        "read_duplication.py",
        "-i",
        "aligned.bam",
        "-o",
        "/work/rseqc_read_duplication/output",
        "-u",
        "750",
        "-q",
        "20",
    ]

    assert node_class.PLAN_OUTPUTS({"rscript_output": True}, tmp_path) == [
        tmp_path / "rseqc_read_duplication" / "output.DupRate_plot.pdf",
        tmp_path / "rseqc_read_duplication" / "output.pos.DupRate.xls",
        tmp_path / "rseqc_read_duplication" / "output.seq.DupRate.xls",
        tmp_path / "rseqc_read_duplication" / "output.DupRate_plot.r",
    ]
    assert node_class.PLAN_OUTPUTS({"rscript_output": False}, tmp_path) == [
        tmp_path / "rseqc_read_duplication" / "output.DupRate_plot.pdf",
        tmp_path / "rseqc_read_duplication" / "output.pos.DupRate.xls",
        tmp_path / "rseqc_read_duplication" / "output.seq.DupRate.xls",
    ]


def test_rseqc_tin_renders_transcript_integrity_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rseqc_tin")
    info = _registry().object_info()["rseqc_tin"]

    assert info["output"] == ["TSV", "TSV"]
    assert info["output_name"] == ["tin_summary", "tin_table"]
    assert info["citation_dois"] == ["10.1186/s12859-016-0922-z", "10.1093/bioinformatics/bts356"]
    assert node_class.render_command(
        {
            "input": ["sample one.bam", "sample one.bam", "batch/sample-two.bam"],
            "refgene": "genes.bed12",
            "minCov": 12,
            "samplesize": 80,
            "subtractbackground": True,
            "output": "/work/rseqc_tin",
        }
    ) == (
        "mkdir -p /work/rseqc_tin/input_bams && "
        "ln -sf 'sample one.bam' /work/rseqc_tin/input_bams/sample_one.bam && "
        "ln -sf 'sample one.bam' /work/rseqc_tin/input_bams/sample_one.2.bam && "
        "ln -sf batch/sample-two.bam /work/rseqc_tin/input_bams/sample-two.bam && "
        "printf '%s\\n' /work/rseqc_tin/input_bams/sample_one.bam "
        "/work/rseqc_tin/input_bams/sample_one.2.bam /work/rseqc_tin/input_bams/sample-two.bam "
        "> /work/rseqc_tin/input_list.txt && "
        "tin.py -i /work/rseqc_tin/input_list.txt --refgene genes.bed12 --minCov 12 --sample-size 80 "
        "--subtract-background && mv *summary.txt /work/rseqc_tin/summary.tab && mv *tin.xls /work/rseqc_tin/tin.xls"
    )
    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "refgene": "genes.bed12",
            "output": "/work/rseqc_tin",
        }
    ) == (
        "mkdir -p /work/rseqc_tin/input_bams && "
        "ln -sf aligned.bam /work/rseqc_tin/input_bams/aligned.bam && "
        "printf '%s\\n' /work/rseqc_tin/input_bams/aligned.bam > /work/rseqc_tin/input_list.txt && "
        "tin.py -i /work/rseqc_tin/input_list.txt --refgene genes.bed12 --minCov 10 --sample-size 100 && "
        "mv *summary.txt /work/rseqc_tin/summary.tab && mv *tin.xls /work/rseqc_tin/tin.xls"
    )

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "rseqc_tin" / "summary.tab",
        tmp_path / "rseqc_tin" / "tin.xls",
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


def test_galaxy_parity_bedtools_legacy_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bedtools_bedtoigv": {
            "display_name": "BEDTools BED to IGV",
            "documentation_url": "https://github.com/galaxyproject/tools-iuc/blob/main/tools/bedtools/bedToIgv.xml",
            "output": ["TEXT"],
            "required_executables": ["bedToIgv"],
            "search_alias": "bedtoigv",
        },
        "bedtools_links": {
            "display_name": "BEDTools LinksBed",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/links.html",
            "output": ["HTML"],
            "required_executables": ["bedtools"],
            "search_alias": "linksbed ucsc",
        },
        "bedtools_overlapbed": {
            "display_name": "BEDTools OverlapBed",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/overlap.html",
            "output": ["BED"],
            "required_executables": ["bedtools"],
            "search_alias": "overlapbed custom score",
        },
        "bedtools_tagbed": {
            "display_name": "BEDTools TagBed",
            "documentation_url": "https://bedtools.readthedocs.io/en/latest/content/tools/tag.html",
            "output": ["BAM"],
            "required_executables": ["bedtools"],
            "search_alias": "tagbed bam tags",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == ["bedtools"]
        assert "10.1093/bioinformatics/btq033" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/bioinformatics/btq033" in node_info["citation_urls"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "Galaxy" in node_info["search_aliases"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bedtools_bedtoigv_renders_snapshot_batch_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_bedtoigv")

    assert node_class.render_command(
        {
            "input": "targets.bed",
            "sort": "base",
            "clps": True,
            "name": True,
            "slop": 250,
            "img": "svg",
            "output": "/work/bedtools_bedtoigv",
        }
    ) == [
        "bedToIgv",
        "-i",
        "targets.bed",
        "-sort",
        "base",
        "-clps",
        "-name",
        "-slop",
        "250",
        "-img",
        "svg",
        ">",
        "/work/bedtools_bedtoigv/igv_batch_script.txt",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_bedtoigv" / "igv_batch_script.txt",
    ]


def test_bedtools_links_renders_browser_links_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_links")

    assert node_class.render_command(
        {
            "input": "genes.bed",
            "basename": "http://mirror.example.edu",
            "org": "mouse",
            "db": "mm10",
            "output": "/work/bedtools_links",
        }
    ) == [
        "bedtools",
        "links",
        "-base",
        "http://mirror.example.edu",
        "-org",
        "mouse",
        "-db",
        "mm10",
        "-i",
        "genes.bed",
        ">",
        "/work/bedtools_links/links.html",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_links" / "links.html",
    ]


def test_bedtools_overlapbed_renders_column_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_overlapbed")

    assert node_class.render_command(
        {
            "input": "windowed.bed",
            "cols": [2, 3, 6, 7],
            "output": "/work/bedtools_overlapbed",
        }
    ) == [
        "bedtools",
        "overlap",
        "-i",
        "windowed.bed",
        "-cols",
        "2,3,6,7",
        ">",
        "/work/bedtools_overlapbed/overlap.bed",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_overlapbed" / "overlap.bed",
    ]


def test_bedtools_tagbed_renders_annotation_tag_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bedtools_tagbed")

    assert node_class.render_command(
        {
            "inputA": "alignments.bam",
            "inputB": ["genes.bed", "enhancers.gff"],
            "overlap": 0.75,
            "strand": "opposite",
            "tag": "ZG",
            "field": "-labels -intervals",
            "output": "/work/bedtools_tagbed",
        }
    ) == [
        "bedtools",
        "tag",
        "-i",
        "alignments.bam",
        "-files",
        "genes.bed",
        "enhancers.gff",
        "-f",
        "0.75",
        "-S",
        "-tag",
        "ZG",
        "-labels",
        "-intervals",
        ">",
        "/work/bedtools_tagbed/tagged.bam",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bedtools_tagbed" / "tagged.bam",
    ]


def test_galaxy_parity_bcftools_utility_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_concat": {
            "display_name": "BCFtools Concat",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#concat",
            "output": ["VCF_GZ"],
            "search_alias": "concatenate vcf",
        },
        "bcftools_consensus": {
            "display_name": "BCFtools Consensus",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#consensus",
            "output": ["FASTA"],
            "search_alias": "consensus fasta",
        },
        "bcftools_query": {
            "display_name": "BCFtools Query",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#query",
            "output": ["TSV"],
            "search_alias": "extract fields",
        },
        "bcftools_query_list_samples": {
            "display_name": "BCFtools List Samples",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#query",
            "output": ["TSV"],
            "search_alias": "list samples",
        },
        "bcftools_reheader": {
            "display_name": "BCFtools Reheader",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#reheader",
            "output": ["VCF_GZ"],
            "search_alias": "rename samples",
        },
        "bcftools_view": {
            "display_name": "BCFtools View",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#view",
            "output": ["VCF_GZ"],
            "search_alias": "subset vcf",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == ["bcftools"]
        assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert "https://doi.org/10.1093/gigascience/giab008" in node_info["citation_urls"]
        assert "https://doi.org/10.1093/bioinformatics/btp352" in node_info["citation_urls"]
        assert "Galaxy" in node_info["search_aliases"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_concat_renders_ligate_overlap_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_concat")

    assert node_class.render_command(
        {
            "input_files": ["chr1.vcf.gz", "chr2.vcf.gz"],
            "allow_overlaps": True,
            "rm_dups": "all",
            "ligate": True,
            "ligate_mode": "--ligate-force",
            "compact_ps": True,
            "min_pq": 40,
            "regions": "chr1,chr2",
            "output_type": "z",
            "threads": 8,
            "output": "/work/bcftools_concat",
        }
    ) == [
        "bcftools",
        "concat",
        "--allow-overlaps",
        "--rm-dups",
        "all",
        "--ligate",
        "--ligate-force",
        "--compact-PS",
        "--min-PQ",
        "40",
        "--regions",
        "chr1,chr2",
        "--output-type",
        "z",
        "--threads",
        "8",
        "chr1.vcf.gz",
        "chr2.vcf.gz",
        ">",
        "/work/bcftools_concat/concat.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_concat" / "concat.vcf.gz",
    ]


def test_bcftools_consensus_renders_masked_haplotype_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_consensus")

    assert node_class.render_command(
        {
            "input_file": "calls.vcf.gz",
            "reference": "ref.fa",
            "mode": "haplotype",
            "haplotype": "1pIu",
            "sample": "tumor",
            "mask": ["lowcov.bed", "repeats.bed"],
            "mask_with": "N,lc",
            "absent": "N",
            "mark_del": "-",
            "mark_ins": "uc",
            "mark_snv": "lc",
            "include": "QUAL>20",
            "exclude": "FILTER='LowQual'",
            "chain": True,
            "output": "/work/bcftools_consensus",
        }
    ) == [
        "bcftools",
        "consensus",
        "--fasta-ref",
        "ref.fa",
        "-H",
        "1pIu",
        "--sample",
        "tumor",
        "--mask",
        "lowcov.bed",
        "--mask-with",
        "N",
        "--mask",
        "repeats.bed",
        "--mask-with",
        "lc",
        "--absent",
        "N",
        "--mark-del",
        "-",
        "--mark-ins",
        "uc",
        "--mark-snv",
        "lc",
        "--include",
        "QUAL>20",
        "--exclude",
        "FILTER='LowQual'",
        "--chain",
        "/work/bcftools_consensus/consensus.chain",
        "--output",
        "/work/bcftools_consensus/consensus.fa",
        "calls.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({"chain": True}, tmp_path) == [
        tmp_path / "bcftools_consensus" / "consensus.fa",
        tmp_path / "bcftools_consensus" / "consensus.chain",
    ]


def test_bcftools_query_renders_multifile_restricted_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_query")

    assert node_class.render_command(
        {
            "input_files": ["case.vcf.gz", "control.vcf.gz"],
            "format": "%CHROM\\t%POS\\t%REF\\t%ALT[\\t%SAMPLE=%GT]\\n",
            "allow_undef_tags": True,
            "print_header": True,
            "samples": "S1,S2",
            "regions": "chr1:1-1000",
            "targets": "targets.bed",
            "include": "QUAL>30",
            "exclude": "TYPE='indel'",
            "collapse": "snps",
            "output": "/work/bcftools_query",
        }
    ) == [
        "bcftools",
        "query",
        "--format",
        "%CHROM\\t%POS\\t%REF\\t%ALT[\\t%SAMPLE=%GT]\\n",
        "--allow-undef-tags",
        "--print-header",
        "--collapse",
        "snps",
        "--regions",
        "chr1:1-1000",
        "--samples",
        "S1,S2",
        "--targets",
        "targets.bed",
        "--include",
        "QUAL>30",
        "--exclude",
        "TYPE='indel'",
        "case.vcf.gz",
        "control.vcf.gz",
        ">",
        "/work/bcftools_query/query.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_query" / "query.tsv",
    ]


def test_bcftools_list_samples_renders_query_list_samples_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_query_list_samples")

    assert node_class.render_command(
        {
            "input_file": "cohort.bcf",
            "output": "/work/bcftools_query_list_samples",
        }
    ) == [
        "bcftools",
        "query",
        "--list-samples",
        "cohort.bcf",
        ">",
        "/work/bcftools_query_list_samples/samples.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_query_list_samples" / "samples.tsv",
    ]


def test_bcftools_reheader_renders_header_and_sample_rename_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_reheader")

    assert node_class.render_command(
        {
            "input_file": "old.vcf.gz",
            "header": "new_header.vcf",
            "sample_file": "samples.tsv",
            "output_type": "z",
            "output": "/work/bcftools_reheader",
        }
    ) == [
        "bcftools",
        "reheader",
        "--header",
        "new_header.vcf",
        "--samples",
        "samples.tsv",
        "old.vcf.gz",
        "|",
        "bcftools",
        "view",
        "--output-type",
        "z",
        ">",
        "/work/bcftools_reheader/reheadered.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_reheader" / "reheadered.vcf.gz",
    ]


def test_bcftools_view_renders_subset_filter_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_view")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "samples": "S1,S2",
            "force_samples": True,
            "trim_alt_alleles": True,
            "no_update": True,
            "min_ac": 2,
            "max_af": 0.9,
            "select_genotype": "het",
            "types": ["snps", "indels"],
            "exclude_types": ["mnps"],
            "known_or_novel": "--known",
            "min_alleles": 2,
            "max_alleles": 4,
            "phased": "--phased",
            "uncalled": "--exclude-uncalled",
            "private": "--private",
            "drop_genotypes": True,
            "header": "--no-header",
            "compression_level": 6,
            "regions": "chr2",
            "targets": "targets.bed",
            "include": "QUAL>50",
            "exclude": "DP<10",
            "output_type": "z",
            "threads": 6,
            "output": "/work/bcftools_view",
        }
    ) == [
        "bcftools",
        "view",
        "--trim-alt-alleles",
        "--no-update",
        "--samples",
        "S1,S2",
        "--force-samples",
        "--min-ac",
        "2",
        "--genotype",
        "het",
        "--known",
        "--min-alleles",
        "2",
        "--max-alleles",
        "4",
        "--phased",
        "--max-af",
        "0.9",
        "--exclude-uncalled",
        "--types",
        "snps,indels",
        "--exclude-types",
        "mnps",
        "--private",
        "--drop-genotypes",
        "--no-header",
        "--compression-level",
        "6",
        "--regions",
        "chr2",
        "--targets",
        "targets.bed",
        "--include",
        "QUAL>50",
        "--exclude",
        "DP<10",
        "--output-type",
        "z",
        "--threads",
        "6",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_view/view.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_view" / "view.vcf.gz",
    ]


def test_galaxy_parity_bcftools_conversion_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_merge": {
            "display_name": "BCFtools Merge",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#merge",
            "output": ["VCF_GZ"],
            "search_alias": "merge samples",
        },
        "bcftools_isec": {
            "display_name": "BCFtools Isec",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#isec",
            "output": ["VCF_GZ"],
            "search_alias": "variant intersection",
        },
        "bcftools_gtcheck": {
            "display_name": "BCFtools GTcheck",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#gtcheck",
            "output": ["TSV"],
            "search_alias": "sample identity",
        },
        "bcftools_convert_to_vcf": {
            "display_name": "BCFtools Convert to VCF",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#convert",
            "output": ["VCF_GZ"],
            "search_alias": "gvcf to vcf",
        },
        "bcftools_convert_from_vcf": {
            "display_name": "BCFtools Convert from VCF",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#convert",
            "output": ["TSV", "TSV", "TSV"],
            "search_alias": "vcf to shapeit",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == ["bcftools"]
        assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_merge_renders_multisample_merge_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_merge")

    assert node_class.render_command(
        {
            "input_files": ["tumor.vcf.gz", "normal.bcf"],
            "force_samples": True,
            "info_rules": "DP:sum,AD:join",
            "merge": "both",
            "no_index": True,
            "print_header": True,
            "use_header": "merged_header.vcf",
            "apply_filters": "PASS,.",
            "regions": "chr1:1-1000",
            "regions_overlap": "1",
            "include": "QUAL>20",
            "exclude": "FILTER='LowQual'",
            "output_type": "z",
            "threads": 4,
            "output": "/work/bcftools_merge",
        }
    ) == [
        "bcftools",
        "merge",
        "--print-header",
        "--use-header",
        "merged_header.vcf",
        "--force-samples",
        "--info-rules",
        "DP:sum,AD:join",
        "--merge",
        "both",
        "--no-index",
        "--apply-filters",
        "PASS,.",
        "--regions",
        "chr1:1-1000",
        "--regions-overlap",
        "1",
        "--include",
        "QUAL>20",
        "--exclude",
        "FILTER='LowQual'",
        "--output-type",
        "z",
        "--threads",
        "4",
        "tumor.vcf.gz",
        "normal.bcf",
        ">",
        "/work/bcftools_merge/merged.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_merge" / "merged.vcf.gz",
    ]


def test_bcftools_isec_renders_intersection_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_isec")

    assert node_class.render_command(
        {
            "input_files": ["case.vcf.gz", "control.vcf.gz", "truth.vcf.gz"],
            "nfiles": "+2",
            "complement": True,
            "collapse": "all",
            "apply_filters": "PASS",
            "regions": "chr2",
            "targets": "targets.bed",
            "targets_overlap": "0",
            "include": "AF>0.05",
            "exclude": "TYPE='ref'",
            "output_type": "v",
            "threads": 2,
            "output": "/work/bcftools_isec",
        }
    ) == [
        "bcftools",
        "isec",
        "--complement",
        "--nfiles",
        "+2",
        "--regions",
        "chr2",
        "--targets",
        "targets.bed",
        "--targets-overlap",
        "0",
        "--collapse",
        "all",
        "--apply-filters",
        "PASS",
        "--include",
        "AF>0.05",
        "--exclude",
        "TYPE='ref'",
        "--output-type",
        "v",
        "--threads",
        "2",
        "case.vcf.gz",
        "control.vcf.gz",
        "truth.vcf.gz",
        ">",
        "/work/bcftools_isec/isec.vcf",
    ]

    assert node_class.PLAN_OUTPUTS({"output_type": "v"}, tmp_path) == [
        tmp_path / "bcftools_isec" / "isec.vcf",
    ]


def test_bcftools_gtcheck_renders_identity_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_gtcheck")

    assert node_class.render_command(
        {
            "input_file": "query.vcf.gz",
            "genotypes": "reference.bcf",
            "all_sites": True,
            "homs_only": True,
            "query_sample": "QUERY1",
            "target_sample": "TARGET1",
            "plot": "discordance",
            "regions": "chr3",
            "targets": "sites.bed",
            "output": "/work/bcftools_gtcheck",
        }
    ) == [
        "bcftools",
        "gtcheck",
        "--genotypes",
        "reference.bcf",
        "--all-sites",
        "--homs-only",
        "--plot",
        "discordance",
        "--query-sample",
        "QUERY1",
        "--target-sample",
        "TARGET1",
        "--regions",
        "chr3",
        "--targets",
        "sites.bed",
        "query.vcf.gz",
        ">",
        "/work/bcftools_gtcheck/gtcheck.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_gtcheck" / "gtcheck.tsv",
    ]


def test_bcftools_convert_to_vcf_renders_tsv_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_convert_to_vcf")

    assert node_class.render_command(
        {
            "convert_from": "tsv",
            "input_file": "variants.tsv",
            "reference": "ref.fa",
            "samples": "SAMPLE1,SAMPLE2",
            "columns": "ID,CHROM,POS,AA",
            "output_type": "z",
            "output": "/work/bcftools_convert_to_vcf",
        }
    ) == [
        "bcftools",
        "convert",
        "--output-type",
        "z",
        "--fasta-ref",
        "ref.fa",
        "--samples",
        "SAMPLE1,SAMPLE2",
        "--columns",
        "ID,CHROM,POS,AA",
        "--tsv2vcf",
        "variants.tsv",
        ">",
        "/work/bcftools_convert_to_vcf/converted.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_convert_to_vcf" / "converted.vcf.gz",
    ]


def test_bcftools_convert_from_vcf_renders_hap_legend_sample_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_convert_from_vcf")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "convert_to": "hap_legend_sample",
            "vcf_ids": True,
            "haploid2diploid": True,
            "sex_file": "sex.tsv",
            "keep_duplicates": True,
            "samples": "S1,S2",
            "regions": "chrX",
            "targets": "targets.bed",
            "include": "MAF>0.01",
            "exclude": "FILTER!='PASS'",
            "output": "/work/bcftools_convert_from_vcf",
        }
    ) == [
        "bcftools",
        "convert",
        "--vcf-ids",
        "--haploid2diploid",
        "--haplegendsample",
        "/work/bcftools_convert_from_vcf/converted.hap,/work/bcftools_convert_from_vcf/converted.legend,/work/bcftools_convert_from_vcf/converted.samples",
        "--sex",
        "sex.tsv",
        "--keep-duplicates",
        "--include",
        "MAF>0.01",
        "--exclude",
        "FILTER!='PASS'",
        "--regions",
        "chrX",
        "--targets",
        "targets.bed",
        "--samples",
        "S1,S2",
        "cohort.vcf.gz",
        ".",
    ]

    assert node_class.PLAN_OUTPUTS({"convert_to": "hap_legend_sample"}, tmp_path) == [
        tmp_path / "bcftools_convert_from_vcf" / "converted.hap",
        tmp_path / "bcftools_convert_from_vcf" / "converted.legend",
        tmp_path / "bcftools_convert_from_vcf" / "converted.samples",
    ]


def test_galaxy_parity_bcftools_analysis_nodes_expose_citation_and_dependency_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_cnv": {
            "display_name": "BCFtools CNV",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#cnv",
            "output": ["TSV", "TSV", "HTML"],
            "search_alias": "copy number variation",
            "required_conda_packages": ["bcftools", "htslib", "matplotlib"],
        },
        "bcftools_csq": {
            "display_name": "BCFtools CSQ",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#csq",
            "output": ["VCF_GZ"],
            "search_alias": "consequence prediction",
            "required_conda_packages": ["bcftools", "htslib"],
        },
        "bcftools_roh": {
            "display_name": "BCFtools ROH",
            "documentation_url": "https://www.htslib.org/doc/bcftools.html#roh",
            "output": ["TSV"],
            "search_alias": "runs of homozygosity",
            "required_conda_packages": ["bcftools", "htslib"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == ["bcftools"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_cnv_renders_pairwise_hmm_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_cnv")

    assert node_class.render_command(
        {
            "input_file": "intensity.vcf.gz",
            "query_sample": "tumor",
            "control_sample": "normal",
            "AF_file": "af.tsv",
            "plot_threshold": 15,
            "aberrant_query": 0.7,
            "aberrant_control": 0.95,
            "optimize": 0.3,
            "baf_weight": 0.8,
            "baf_dev_query": 0.05,
            "baf_dev_control": 0.04,
            "lrr_weight": 0.4,
            "lrr_dev_query": 0.3,
            "lrr_dev_control": 0.2,
            "lrr_smooth_win": 20,
            "same_prob": 0.6,
            "err_prob": 0.0002,
            "xy_prob": 1e-8,
            "regions": "chr10,chr11",
            "regions_overlap": "1",
            "targets": "cnv_targets.bed",
            "output": "/work/bcftools_cnv",
        }
    ) == [
        "bcftools",
        "cnv",
        "--output-dir",
        "/work/bcftools_cnv/cnv_tmp",
        "-c",
        "normal",
        "-s",
        "tumor",
        "--AF-file",
        "af.tsv",
        "--plot-threshold",
        "15",
        "--aberrant",
        "0.7,0.95",
        "--optimize",
        "0.3",
        "--BAF-weight",
        "0.8",
        "--BAF-dev",
        "0.05,0.04",
        "--LRR-weight",
        "0.4",
        "--LRR-dev",
        "0.3,0.2",
        "--LRR-smooth-win",
        "20",
        "--same-prob",
        "0.6",
        "--err-prob",
        "0.0002",
        "--xy-prob",
        "1e-08",
        "--regions",
        "chr10,chr11",
        "--regions-overlap",
        "1",
        "--targets",
        "cnv_targets.bed",
        "intensity.vcf.gz",
        "&&",
        "python",
        "-c",
        node_class.CNV_POSTPROCESS_SCRIPT,
        "/work/bcftools_cnv/cnv_tmp",
        "/work/bcftools_cnv/cnv.tab",
        "/work/bcftools_cnv/summary.tab",
        "/work/bcftools_cnv/plots.html",
        "1",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_cnv" / "cnv.tab",
        tmp_path / "bcftools_cnv" / "summary.tab",
        tmp_path / "bcftools_cnv" / "plots.html",
    ]
    assert node_class.PLAN_OUTPUTS({"generate_plots": True}, tmp_path) == [
        tmp_path / "bcftools_cnv" / "cnv.tab",
        tmp_path / "bcftools_cnv" / "summary.tab",
        tmp_path / "bcftools_cnv" / "plots.html",
    ]


def test_bcftools_csq_renders_haplotype_consequence_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_csq")

    assert node_class.render_command(
        {
            "input_file": "phased.vcf.gz",
            "reference": "ref.fa",
            "gff_annot": "genes.gff3",
            "ncsq": 32,
            "local_csq": True,
            "phase": "R",
            "custom_tag": "MYCSQ",
            "trim_protein_seq": 12,
            "genetic_code": "1",
            "samples": "S1,S2",
            "regions": "chr1",
            "targets": "coding.bed",
            "include": "QUAL>30",
            "exclude": "TYPE='ref'",
            "output_type": "z",
            "output": "/work/bcftools_csq",
        }
    ) == [
        "bcftools",
        "csq",
        "--fasta-ref",
        "ref.fa",
        "--gff-annot",
        "genes.gff3",
        "--ncsq",
        "32",
        "--local-csq",
        "--phase",
        "R",
        "--custom-tag",
        "MYCSQ",
        "--trim-protein-seq",
        "12",
        "--genetic-code",
        "1",
        "--samples",
        "S1,S2",
        "--include",
        "QUAL>30",
        "--exclude",
        "TYPE='ref'",
        "--regions",
        "chr1",
        "--targets",
        "coding.bed",
        "--output-type",
        "z",
        "phased.vcf.gz",
        ">",
        "/work/bcftools_csq/csq.vcf.gz",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_csq" / "csq.vcf.gz",
    ]


def test_bcftools_roh_renders_autozygosity_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_roh")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "sample": "S1",
            "AF_file": "af.tsv",
            "AF_tag": "AF",
            "AF_dflt": 0.4,
            "estimate_AF": "samples.txt",
            "GTs_only": 30,
            "skip_indels": True,
            "genetic_map": "map.txt",
            "rec_rate": 1e-8,
            "buffer_size": 10000,
            "buffer_overlap": 100,
            "ignore_homref": True,
            "include_noalt": True,
            "hw_to_az": 6.7e-8,
            "az_to_hw": 5e-9,
            "viterbi_training": True,
            "regions": "chr1",
            "targets": "roh_targets.bed",
            "samples": "S1",
            "output_type": "r",
            "output": "/work/bcftools_roh",
        }
    ) == [
        "bcftools",
        "roh",
        "--sample",
        "S1",
        "--AF-file",
        "af.tsv",
        "--AF-tag",
        "AF",
        "--AF-dflt",
        "0.4",
        "--estimate-AF",
        "samples.txt",
        "--GTs-only",
        "30",
        "--skip-indels",
        "--genetic-map",
        "map.txt",
        "--rec-rate",
        "1e-08",
        "--buffer-size",
        "10000,100",
        "--ignore-homref",
        "--include-noalt",
        "--hw-to-az",
        "6.7e-08",
        "--az-to-hw",
        "5e-09",
        "--viterbi-training",
        "--regions",
        "chr1",
        "--targets",
        "roh_targets.bed",
        "--samples",
        "S1",
        "--output-type",
        "r",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_roh/roh.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_roh" / "roh.tsv",
    ]


def test_bcftools_roh_accepts_fractional_gts_only_and_gates_buffer_overlap() -> None:
    node_class = _node_class("bcftools_roh")

    input_types = node_class.INPUT_TYPES()
    assert input_types["optional"]["GTs_only"][0] == "FLOAT"

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "GTs_only": 30.5,
            "buffer_size": 10000,
            "output": "/work/bcftools_roh",
        }
    ) == [
        "bcftools",
        "roh",
        "--GTs-only",
        "30.5",
        "--buffer-size",
        "10000",
        "--output-type",
        "r",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_roh/roh.tsv",
    ]

    assert "--buffer-size" not in node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "buffer_overlap": 100,
            "output": "/work/bcftools_roh",
        }
    )


def test_galaxy_parity_bcftools_plugin_nodes_expose_metadata() -> None:
    info = _registry().object_info()

    expected = {
        "bcftools_plugin_counts": {
            "display_name": "BCFtools +counts",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#counts",
            "output": ["TSV"],
            "search_alias": "variant counts",
        },
        "bcftools_plugin_dosage": {
            "display_name": "BCFtools +dosage",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#dosage",
            "output": ["TSV"],
            "search_alias": "genotype dosage",
        },
        "bcftools_plugin_missing2ref": {
            "display_name": "BCFtools +missing2ref",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#missing2ref",
            "output": ["VCF_GZ"],
            "search_alias": "set missing genotypes",
        },
        "bcftools_plugin_tag2tag": {
            "display_name": "BCFtools +tag2tag",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html#tag2tag",
            "output": ["VCF_GZ"],
            "search_alias": "convert genotype tags",
        },
        "bcftools_plugin_fill_an_ac": {
            "display_name": "BCFtools +fill-AN-AC",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "search_alias": "fill AN AC",
        },
        "bcftools_plugin_fill_tags": {
            "display_name": "BCFtools +fill-tags",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.fill-tags.html",
            "output": ["VCF_GZ"],
            "search_alias": "fill INFO tags",
        },
        "bcftools_plugin_setgt": {
            "display_name": "BCFtools +setGT",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.setGT.html",
            "output": ["VCF_GZ"],
            "search_alias": "set genotype calls",
        },
        "bcftools_plugin_fixploidy": {
            "display_name": "BCFtools +fixploidy",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "search_alias": "fix ploidy",
        },
        "bcftools_plugin_mendelian": {
            "display_name": "BCFtools +mendelian2",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.mendelian.html",
            "output": ["VCF_GZ"],
            "search_alias": "mendelian consistency",
        },
        "bcftools_plugin_impute_info": {
            "display_name": "BCFtools +impute-info",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "search_alias": "imputation info",
        },
        "bcftools_plugin_color_chrs": {
            "display_name": "BCFtools +color-chrs",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["TSV", "IMAGE"],
            "required_executables": ["bcftools", "color-chrs.pl"],
            "search_alias": "color shared chromosomal segments",
        },
        "bcftools_plugin_frameshifts": {
            "display_name": "BCFtools +frameshifts",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugins.html",
            "output": ["VCF_GZ"],
            "required_executables": ["bcftools", "bgzip", "tabix"],
            "search_alias": "frameshift indels",
        },
        "bcftools_plugin_split_vep": {
            "display_name": "BCFtools +split-vep",
            "documentation_url": "https://samtools.github.io/bcftools/howtos/plugin.split-vep.html",
            "output": ["VCF_GZ"],
            "search_alias": "split VEP annotations",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "variant"
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == metadata.get("required_executables", ["bcftools"])
        assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert "10.1093/gigascience/giab008" in node_info["citation_dois"]
        assert "10.1093/bioinformatics/btp352" in node_info["citation_dois"]
        assert metadata["search_alias"] in node_info["search_aliases"]


def test_bcftools_plugin_counts_renders_filtered_table_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_counts")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "include": "QUAL>20",
            "exclude": "TYPE='ref'",
            "regions": "chr1",
            "targets": "targets.bed",
            "output": "/work/bcftools_plugin_counts",
        }
    ) == [
        "bcftools",
        "plugin",
        "counts",
        "--include",
        "QUAL>20",
        "--exclude",
        "TYPE='ref'",
        "--regions",
        "chr1",
        "--targets",
        "targets.bed",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_plugin_counts/counts.raw.txt",
        "&&",
        "python",
        "-c",
        node_class.COUNTS_POSTPROCESS_SCRIPT,
        "/work/bcftools_plugin_counts/counts.raw.txt",
        "/work/bcftools_plugin_counts/counts.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_counts" / "counts.tsv",
    ]


def test_bcftools_plugin_counts_postprocesses_galaxy_table(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_counts")
    raw_counts = tmp_path / "counts.raw.txt"
    output = tmp_path / "counts.tsv"
    raw_counts.write_text(
        "Number of samples: 3\n"
        "Number of SNPs: 11\n"
        "Number of INDELs: 4\n"
        "Number of total sites: 15\n",
        encoding="utf-8",
    )

    old_argv = sys.argv
    sys.argv = ["counts-postprocess", str(raw_counts), str(output)]
    try:
        exec(node_class.COUNTS_POSTPROCESS_SCRIPT, {"__name__": "__main__"})
    finally:
        sys.argv = old_argv

    assert output.read_text(encoding="utf-8") == "#samples\tSNPs\tINDELs\tsites\n3\t11\t4\t15\n"


def test_bcftools_plugin_dosage_renders_plugin_options_after_separator(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_dosage")

    assert node_class.render_command(
        {
            "input_file": "calls.vcf.gz",
            "regions": "chr2",
            "targets": "targets.bed",
            "include": "N_ALT=1",
            "tags": "PL,GT",
            "output": "/work/bcftools_plugin_dosage",
        }
    ) == [
        "bcftools",
        "plugin",
        "dosage",
        "--include",
        "N_ALT=1",
        "--regions",
        "chr2",
        "--targets",
        "targets.bed",
        "calls.vcf.gz",
        "--",
        "--tags",
        "PL,GT",
        ">",
        "/work/bcftools_plugin_dosage/dosage.tsv",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_dosage" / "dosage.tsv",
    ]


def test_bcftools_plugin_missing2ref_renders_vcf_transform_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_missing2ref")

    assert node_class.render_command(
        {
            "input_file": "missing.vcf.gz",
            "phased": True,
            "major": True,
            "regions": "chr3",
            "threads": 6,
            "output": "/work/bcftools_plugin_missing2ref",
        }
    ) == [
        "bcftools",
        "plugin",
        "missing2ref",
        "--regions",
        "chr3",
        "--output-type",
        "z",
        "--threads",
        "6",
        "missing.vcf.gz",
        "--",
        "--phased",
        "--major",
        ">",
        "/work/bcftools_plugin_missing2ref/missing2ref.vcf.gz",
    ]

    input_types = node_class.INPUT_TYPES()
    assert "output_type" not in input_types["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_missing2ref" / "missing2ref.vcf.gz",
    ]


def test_bcftools_plugin_tag2tag_renders_conversion_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_tag2tag")

    assert node_class.render_command(
        {
            "input_file": "gp.vcf.gz",
            "conversion": "--gp-to-gt",
            "replace": True,
            "threshold": 0.2,
            "exclude": "FILTER='LowQual'",
            "threads": 3,
            "output": "/work/bcftools_plugin_tag2tag",
        }
    ) == [
        "bcftools",
        "plugin",
        "tag2tag",
        "--exclude",
        "FILTER='LowQual'",
        "--output-type",
        "z",
        "--threads",
        "3",
        "gp.vcf.gz",
        "--",
        "--gp-to-gt",
        "--replace",
        "--threshold",
        "0.2",
        ">",
        "/work/bcftools_plugin_tag2tag/tag2tag.vcf.gz",
    ]

    input_types = node_class.INPUT_TYPES()
    assert "output_type" not in input_types["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_tag2tag" / "tag2tag.vcf.gz",
    ]


def test_bcftools_plugin_fill_an_ac_renders_vcf_annotation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_fill_an_ac")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "include": "TYPE='snp'",
            "regions": "chr1:1-100",
            "targets": "targets.tsv.gz",
            "threads": 5,
            "output": "/work/bcftools_plugin_fill_an_ac",
        }
    ) == [
        "bcftools",
        "plugin",
        "fill-AN-AC",
        "--include",
        "TYPE='snp'",
        "--regions",
        "chr1:1-100",
        "--targets",
        "targets.tsv.gz",
        "--output-type",
        "z",
        "--threads",
        "5",
        "cohort.vcf.gz",
        ">",
        "/work/bcftools_plugin_fill_an_ac/fill_an_ac.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_fill_an_ac" / "fill_an_ac.vcf.gz",
    ]


def test_bcftools_plugin_fill_tags_renders_plugin_tags_samples_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_fill_tags")

    assert node_class.render_command(
        {
            "input_file": "cohort.bcf",
            "tags": ["AN", "AC", "AC_Het"],
            "samples": "S1,S2",
            "samples_file": "populations.tsv",
            "invert_samples_file": True,
            "drop_missing": True,
            "regions": "chr2",
            "exclude": "FILTER='LowQual'",
            "threads": 8,
            "output": "/work/bcftools_plugin_fill_tags",
        }
    ) == [
        "bcftools",
        "plugin",
        "fill-tags",
        "--exclude",
        "FILTER='LowQual'",
        "--regions",
        "chr2",
        "--output-type",
        "z",
        "--threads",
        "8",
        "cohort.bcf",
        "--",
        "--tags",
        "AN,AC,AC_Het",
        "--samples",
        "S1,S2",
        "--samples-file",
        "^populations.tsv",
        "--drop-missing",
        ">",
        "/work/bcftools_plugin_fill_tags/fill_tags.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_fill_tags" / "fill_tags.vcf.gz",
    ]


def test_bcftools_plugin_setgt_renders_genotype_filter_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_setgt")

    assert node_class.render_command(
        {
            "input_file": "calls.vcf.gz",
            "target_gt": "q",
            "new_gt": "0",
            "include": 'GT="." && FMT/DP>0',
            "exclude": "GQ<20",
            "seed": 13,
            "regions": "chr7",
            "targets": "targets.bed",
            "threads": 2,
            "output": "/work/bcftools_plugin_setgt",
        }
    ) == [
        "bcftools",
        "plugin",
        "setGT",
        "--regions",
        "chr7",
        "--targets",
        "targets.bed",
        "--output-type",
        "z",
        "--threads",
        "2",
        "calls.vcf.gz",
        "--",
        "--target-gt",
        "q",
        "--new-gt",
        "0",
        "--include",
        'GT="." && FMT/DP>0',
        "--exclude",
        "GQ<20",
        "--seed",
        "13",
        ">",
        "/work/bcftools_plugin_setgt/setgt.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_setgt" / "setgt.vcf.gz",
    ]


def test_bcftools_plugin_fixploidy_renders_ploidy_files_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_fixploidy")

    assert node_class.render_command(
        {
            "input_file": "cohort.vcf.gz",
            "ploidy_file": "ploidy.tsv",
            "sex": "sample_sex.tsv",
            "default_ploidy": 2,
            "force_ploidy": 4,
            "regions": "chrX",
            "include": "TYPE='snp'",
            "threads": 3,
            "output": "/work/bcftools_plugin_fixploidy",
        }
    ) == [
        "bcftools",
        "plugin",
        "fixploidy",
        "--include",
        "TYPE='snp'",
        "--regions",
        "chrX",
        "--output-type",
        "z",
        "--threads",
        "3",
        "cohort.vcf.gz",
        "--",
        "--ploidy",
        "ploidy.tsv",
        "--sex",
        "sample_sex.tsv",
        "--default-ploidy",
        "2",
        "--force-ploidy",
        "4",
        "--tags",
        "GT",
        ">",
        "/work/bcftools_plugin_fixploidy/fixploidy.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_fixploidy" / "fixploidy.vcf.gz",
    ]


def test_bcftools_plugin_mendelian_renders_inline_trio_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_mendelian")

    assert node_class.render_command(
        {
            "input_file": "family.vcf.gz",
            "trios_src": "trio",
            "child": "NA00006",
            "mother": "NA00001",
            "father": "NA00002",
            "num_x": "1X",
            "mode": ["a", "d", "e"],
            "rules": "GRCh38",
            "regions": "chr1",
            "targets": "targets.bed",
            "exclude": "QUAL<20",
            "output": "/work/bcftools_plugin_mendelian",
        }
    ) == [
        "bcftools",
        "plugin",
        "mendelian2",
        "--regions",
        "chr1",
        "--targets",
        "targets.bed",
        "--exclude",
        "QUAL<20",
        "--output-type",
        "z",
        "family.vcf.gz",
        "--",
        "--pfm",
        "1X:NA00006,NA00002,NA00001",
        "--rules",
        "GRCh38",
        "--mode",
        "ade",
        "2>",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
        ">",
        "/work/bcftools_plugin_mendelian/mendelian.vcf.gz",
        "&&",
        "cat",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_mendelian" / "mendelian.vcf.gz",
    ]


def test_bcftools_plugin_mendelian_renders_ped_file_command() -> None:
    node_class = _node_class("bcftools_plugin_mendelian")

    assert node_class.render_command(
        {
            "input_file": "family.vcf.gz",
            "trios_src": "trio_file",
            "trio_file": "family.ped",
            "rules_file": "inheritance.tsv",
            "mode": "M,S",
            "output": "/work/bcftools_plugin_mendelian",
        }
    ) == [
        "bcftools",
        "plugin",
        "mendelian2",
        "--output-type",
        "z",
        "family.vcf.gz",
        "--",
        "--ped",
        "family.ped",
        "--rules-file",
        "inheritance.tsv",
        "--mode",
        "MS",
        "2>",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
        ">",
        "/work/bcftools_plugin_mendelian/mendelian.vcf.gz",
        "&&",
        "cat",
        "/work/bcftools_plugin_mendelian/mendelian.stderr.txt",
    ]


def test_bcftools_plugin_impute_info_renders_vcf_transform_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_impute_info")

    assert node_class.render_command(
        {
            "input_file": "imputed.vcf.gz",
            "include": "N_ALT=1",
            "regions": "chr20",
            "targets": "impute_targets.tsv",
            "threads": 4,
            "output": "/work/bcftools_plugin_impute_info",
        }
    ) == [
        "bcftools",
        "plugin",
        "impute-info",
        "--include",
        "N_ALT=1",
        "--regions",
        "chr20",
        "--targets",
        "impute_targets.tsv",
        "--output-type",
        "z",
        "--threads",
        "4",
        "imputed.vcf.gz",
        ">",
        "/work/bcftools_plugin_impute_info/impute_info.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_impute_info" / "impute_info.vcf.gz",
    ]


def test_bcftools_plugin_color_chrs_renders_trio_plot_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_color_chrs")

    assert node_class.render_command(
        {
            "input_file": "phased.vcf.gz",
            "sample_rel_sel": "trio",
            "mother": "M",
            "father": "F",
            "child": "C",
            "regions": "chr1",
            "include": "N_ALT=1",
            "threads": 4,
            "output": "/work/bcftools_plugin_color_chrs",
        }
    ) == [
        "bcftools",
        "plugin",
        "color-chrs",
        "--include",
        "N_ALT=1",
        "--regions",
        "chr1",
        "--threads",
        "4",
        "phased.vcf.gz",
        "--",
        "--trio",
        "M,F,C",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "color-chrs.pl",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "/work/bcftools_plugin_color_chrs/color_chrs.tsv",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.svg",
        "/work/bcftools_plugin_color_chrs/color_chrs.svg",
    ]

    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_color_chrs" / "color_chrs.tsv",
        tmp_path / "bcftools_plugin_color_chrs" / "color_chrs.svg",
    ]


def test_bcftools_plugin_color_chrs_renders_unrelated_pair_command() -> None:
    node_class = _node_class("bcftools_plugin_color_chrs")

    assert node_class.render_command(
        {
            "input_file": "phased.vcf.gz",
            "sample_rel_sel": "unrelated",
            "sample_a": "A",
            "sample_b": "B",
            "output": "/work/bcftools_plugin_color_chrs",
        }
    ) == [
        "bcftools",
        "plugin",
        "color-chrs",
        "phased.vcf.gz",
        "--",
        "--unrelated",
        "A,B",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "color-chrs.pl",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "-p",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.dat",
        "/work/bcftools_plugin_color_chrs/color_chrs.tsv",
        "&&",
        "mv",
        "/work/bcftools_plugin_color_chrs/color_chrs_tmp.svg",
        "/work/bcftools_plugin_color_chrs/color_chrs.svg",
    ]


def test_bcftools_plugin_frameshifts_renders_indexed_exons_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_frameshifts")

    assert node_class.render_command(
        {
            "input_file": "indels.vcf.gz",
            "exons": "exons.bed",
            "include": "TYPE='indel'",
            "regions": "chr12",
            "targets": "coding.bed",
            "threads": 7,
            "output": "/work/bcftools_plugin_frameshifts",
        }
    ) == [
        "bgzip",
        "-c",
        "exons.bed",
        ">",
        "/work/bcftools_plugin_frameshifts/exons.bed.gz",
        "&&",
        "tabix",
        "/work/bcftools_plugin_frameshifts/exons.bed.gz",
        "&&",
        "bcftools",
        "plugin",
        "frameshifts",
        "--include",
        "TYPE='indel'",
        "--regions",
        "chr12",
        "--targets",
        "coding.bed",
        "--output-type",
        "z",
        "--threads",
        "7",
        "indels.vcf.gz",
        "--",
        "--exons",
        "/work/bcftools_plugin_frameshifts/exons.bed.gz",
        ">",
        "/work/bcftools_plugin_frameshifts/frameshifts.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_frameshifts" / "frameshifts.vcf.gz",
    ]


def test_bcftools_plugin_split_vep_renders_annotation_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("bcftools_plugin_split_vep")

    assert node_class.render_command(
        {
            "input_file": "annotated.vcf.gz",
            "a": "ANN",
            "c": "IMPACT,gnomAD_AF:Float",
            "d": True,
            "allow_undef_tags": True,
            "p": "vep",
            "s": "worst",
            "include": "IMPACT='HIGH'",
            "regions": "chr5",
            "output": "/work/bcftools_plugin_split_vep",
        }
    ) == [
        "bcftools",
        "plugin",
        "split-vep",
        "--include",
        "IMPACT='HIGH'",
        "--regions",
        "chr5",
        "--output-type",
        "z",
        "annotated.vcf.gz",
        "--",
        "-a",
        "ANN",
        "-c",
        "IMPACT,gnomAD_AF:Float",
        "-d",
        "--allow-undef-tags",
        "-p",
        "vep",
        "-s",
        "worst",
        ">",
        "/work/bcftools_plugin_split_vep/split_vep.vcf.gz",
    ]

    assert "output_type" not in node_class.INPUT_TYPES()["optional"]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "bcftools_plugin_split_vep" / "split_vep.vcf.gz",
    ]
