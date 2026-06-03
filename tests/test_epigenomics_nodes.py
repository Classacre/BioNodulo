from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_bismark_align_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bismark_align"]
    assert node_info["display_name"] == "Bismark Align"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Align bisulfite sequencing reads")
    assert node_info["output"] == ["BAM"]
    assert node_info["output_name"] == ["aligned_bam"]
    assert node_info["required_executables"] == ["bismark"]
    assert node_info["required_conda_packages"] == ["bismark"]
    assert "bisulfite" in node_info["search_aliases"]
    assert "methylation" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"r1", "genome_folder", "parallel_instances"}
    assert set(inputs["optional"]) == {"r2", "non_directional"}


def test_bismark_align_renders_paired_end_command() -> None:
    node_class = _node_class("bismark_align")

    cmd = node_class.render_command({
        "r1": "sample_R1.fastq.gz",
        "r2": "sample_R2.fastq.gz",
        "genome_folder": "bismark_genome/",
        "parallel_instances": 4,
        "non_directional": True,
        "output": "/tmp/run/bismark_align",
    })

    assert cmd == [
        "bismark",
        "--genome",
        "bismark_genome/",
        "-o",
        "/tmp/run/bismark_align",
        "--parallel",
        "4",
        "-p",
        "-1",
        "sample_R1.fastq.gz",
        "-2",
        "sample_R2.fastq.gz",
        "--non_directional",
    ]


def test_bismark_align_renders_single_end_command() -> None:
    node_class = _node_class("bismark_align")

    cmd = node_class.render_command({
        "r1": "sample.fastq.gz",
        "r2": "",
        "genome_folder": "bismark_genome/",
        "parallel_instances": 1,
        "non_directional": False,
        "output": "/tmp/run/bismark_align",
    })

    assert cmd == [
        "bismark",
        "--genome",
        "bismark_genome/",
        "-o",
        "/tmp/run/bismark_align",
        "--parallel",
        "1",
        "-p",
        "sample.fastq.gz",
    ]


def test_bismark_align_plans_bam_output() -> None:
    node_class = _node_class("bismark_align")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/bismark_align/aligned_bam.bam"]


def test_bismark_methylation_extractor_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bismark_methylation_extractor"]
    assert node_info["display_name"] == "Bismark Methylation Extractor"
    assert node_info["category"] == "epigenomics"
    assert node_info["description"].startswith("Extract methylation calls")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["methylation_output"]
    assert node_info["required_executables"] == ["bismark_methylation_extractor"]
    assert node_info["required_conda_packages"] == ["bismark"]
    assert "bedgraph" in node_info["search_aliases"]
    assert "methylation" in node_info["search_aliases"]
    assert "cytosine" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "multicore"}
    assert set(inputs["optional"]) == {"cytosine_report", "genome_folder", "no_overlap", "merge_non_cpg"}


def test_bismark_methylation_extractor_renders_default_command() -> None:
    node_class = _node_class("bismark_methylation_extractor")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "multicore": 4,
        "cytosine_report": True,
        "genome_folder": "bismark_genome/",
        "no_overlap": True,
        "merge_non_cpg": False,
        "output": "/tmp/run/bismark_methylation_extractor",
    })

    assert cmd == [
        "bismark_methylation_extractor",
        "--bedGraph",
        "--comprehensive",
        "--gzip",
        "--multicore",
        "4",
        "--output",
        "/tmp/run/bismark_methylation_extractor",
        "--cytosine_report",
        "--genome_folder",
        "bismark_genome/",
        "--no_overlap",
        "sample.bam",
    ]


def test_bismark_methylation_extractor_omits_optional_flags() -> None:
    node_class = _node_class("bismark_methylation_extractor")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "multicore": 1,
        "cytosine_report": False,
        "no_overlap": False,
        "merge_non_cpg": True,
        "output": "/tmp/run/bismark_methylation_extractor",
    })

    assert cmd == [
        "bismark_methylation_extractor",
        "--bedGraph",
        "--comprehensive",
        "--gzip",
        "--multicore",
        "1",
        "--output",
        "/tmp/run/bismark_methylation_extractor",
        "--merge_non_CpG",
        "sample.bam",
    ]


def test_bismark_methylation_extractor_plans_output_directory() -> None:
    node_class = _node_class("bismark_methylation_extractor")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/bismark_methylation_extractor/methylation_output"]
