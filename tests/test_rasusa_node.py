from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_rasusa_exposes_bionodulo_builtin_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["rasusa"]
    assert node_info["display_name"] == "Rasusa"
    assert node_info["category"] == "qc"
    assert node_info["output"] == ["FASTQ_LIST", "FASTQ", "BAM"]
    assert node_info["output_name"] == ["paired_reads", "single_reads", "subsampled_bam"]
    assert node_info["required_executables"] == ["rasusa", "samtools"]
    assert node_info["required_conda_packages"] == ["rasusa", "samtools"]
    assert node_info["documentation_url"] == "https://github.com/mbhall88/rasusa"
    assert node_info["citation_dois"] == ["10.21105/joss.03941", "10.46471/gigabyte.180"]
    assert "https://doi.org/10.21105/joss.03941" in node_info["citation_urls"]
    assert "https://doi.org/10.46471/gigabyte.180" in node_info["citation_urls"]
    assert "Randomly subsample sequencing reads" in node_info["citation_text"]
    assert "Efficient downsampling of genome alignments" in node_info["citation_text"]
    assert "BioNodulo builtin" in node_info["search_aliases"]
    assert "subsample reads" in node_info["search_aliases"]


def test_rasusa_renders_single_fastq_coverage_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rasusa")

    assert node_class.render_command(
        {
            "input_selector": "single",
            "reads": "reads.fastq.gz",
            "subsample_type": "coverage",
            "genome_size": 4.6,
            "genome_size_unit": "m",
            "coverage": 30,
            "seed": 7,
            "output": "/work/rasusa",
        }
    ) == [
        "rasusa",
        "reads",
        "-s",
        "7",
        "-o",
        "/work/rasusa/single.fastq.gz",
        "--genome-size",
        "4.6m",
        "--coverage",
        "30",
        "--compress-type",
        "g",
        "reads.fastq.gz",
    ]

    assert node_class.PLAN_OUTPUTS(
        {"input_selector": "single", "reads": "reads.fastq.gz", "output_ext": "fastq.gz"},
        tmp_path,
    ) == [
        tmp_path / "rasusa" / "single.fastq.gz",
    ]


def test_rasusa_renders_paired_fastq_number_of_reads_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("rasusa")

    assert node_class.render_command(
        {
            "input_selector": "paired",
            "reads1": "r1.fq",
            "reads2": "r2.fq",
            "subsample_type": "num_reads",
            "num": 10000,
            "seed": 11,
            "output_ext": "fastq",
            "compress_type": "u",
            "output": "/work/rasusa",
        }
    ) == [
        "rasusa",
        "reads",
        "-s",
        "11",
        "-o",
        "/work/rasusa/paired_R1.fastq",
        "-o",
        "/work/rasusa/paired_R2.fastq",
        "--num",
        "10000",
        "--compress-type",
        "u",
        "r1.fq",
        "r2.fq",
    ]

    assert node_class.PLAN_OUTPUTS({"input_selector": "paired", "output_ext": "fastq"}, tmp_path) == [
        tmp_path / "rasusa" / "paired_R1.fastq",
        tmp_path / "rasusa" / "paired_R2.fastq",
    ]


def test_rasusa_renders_aligned_bam_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("rasusa")

    assert node_class.render_command(
        {
            "input_selector": "aligned",
            "aligned_input": "aligned.bam",
            "coverage": 50,
            "seed": 13,
            "strategy": "fetch",
            "step_size": 200,
            "batch_size": 20000,
            "swap_distance": 10,
            "output": "/work/rasusa",
        }
    ) == [
        "rasusa",
        "aln",
        "-s",
        "13",
        "--coverage",
        "50",
        "--strategy",
        "fetch",
        "--step-size",
        "200",
        "--batch-size",
        "20000",
        "--swap-distance",
        "10",
        "--output-format",
        "bam",
        "aligned.bam",
        "|",
        "samtools",
        "sort",
        "--no-PG",
        "-@",
        "1",
        "-T",
        "/work/rasusa/tmp",
        "-O",
        "bam",
        "-o",
        "/work/rasusa/subsampled.bam",
        "-",
    ]

    assert node_class.PLAN_OUTPUTS({"input_selector": "aligned"}, tmp_path) == [
        tmp_path / "rasusa" / "subsampled.bam",
    ]
