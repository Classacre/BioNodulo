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
