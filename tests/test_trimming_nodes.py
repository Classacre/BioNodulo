from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_trim_galore_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["trim_galore"]
    assert node_info["display_name"] == "Trim Galore"
    assert node_info["category"] == "trimming"
    assert node_info["description"].startswith("Adapter and quality trimming")
    assert node_info["output"] == ["FASTQ_LIST", "HTML_REPORT"]
    assert node_info["output_name"] == ["trimmed_reads", "fastqc_report"]
    assert node_info["required_executables"] == ["trim_galore"]
    assert node_info["required_conda_packages"] == ["trim-galore"]
    assert "bisulfite" in node_info["search_aliases"]
    assert "rrbs" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "threads"}
    assert set(inputs["optional"]) == {
        "paired",
        "quality",
        "length",
        "clip_r1",
        "clip_r2",
        "three_prime_clip_r1",
        "three_prime_clip_r2",
        "rrbs",
        "non_directional",
        "gzip",
        "fastqc",
    }


def test_trim_galore_renders_paired_bisulfite_command() -> None:
    node_class = _node_class("trim_galore")

    cmd = node_class.render_command({
        "reads": ["reads_1.fq", "reads_2.fq"],
        "threads": 4,
        "paired": True,
        "quality": 20,
        "length": 30,
        "clip_r1": 10,
        "clip_r2": 10,
        "three_prime_clip_r1": 5,
        "three_prime_clip_r2": 5,
        "rrbs": True,
        "non_directional": True,
        "gzip": True,
        "fastqc": True,
        "output": "/tmp/run/trim_galore",
    })

    assert cmd == [
        "trim_galore",
        "--paired",
        "--cores",
        "4",
        "--quality",
        "20",
        "--length",
        "30",
        "--clip_R1",
        "10",
        "--clip_R2",
        "10",
        "--three_prime_clip_R1",
        "5",
        "--three_prime_clip_R2",
        "5",
        "--rrbs",
        "--non_directional",
        "--gzip",
        "--fastqc",
        "-o",
        "/tmp/run/trim_galore",
        "reads_1.fq",
        "reads_2.fq",
    ]


def test_trim_galore_renders_single_end_command_and_omits_disabled_flags() -> None:
    node_class = _node_class("trim_galore")

    cmd = node_class.render_command({
        "reads": "reads.fq.gz",
        "threads": 1,
        "paired": False,
        "quality": 0,
        "length": 0,
        "clip_r1": 0,
        "clip_r2": 0,
        "three_prime_clip_r1": 0,
        "three_prime_clip_r2": 0,
        "rrbs": False,
        "non_directional": False,
        "gzip": False,
        "fastqc": False,
        "output": "/tmp/run/trim_galore",
    })

    assert "--paired" not in cmd
    assert "--quality" not in cmd
    assert "--length" not in cmd
    assert "--clip_R1" not in cmd
    assert "--clip_R2" not in cmd
    assert "--three_prime_clip_R1" not in cmd
    assert "--three_prime_clip_R2" not in cmd
    assert "--rrbs" not in cmd
    assert "--non_directional" not in cmd
    assert "--gzip" not in cmd
    assert "--fastqc" not in cmd
    assert cmd == [
        "trim_galore",
        "--cores",
        "1",
        "-o",
        "/tmp/run/trim_galore",
        "reads.fq.gz",
    ]


def test_trim_galore_plans_paired_trimmed_reads_and_report() -> None:
    node_class = _node_class("trim_galore")

    outputs = node_class.PLAN_OUTPUTS({"reads": ["reads_1.fq.gz", "reads_2.fq.gz"], "paired": True}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/trim_galore/reads_1_val_1.fq.gz",
        "/tmp/run/trim_galore/reads_2_val_2.fq.gz",
        "/tmp/run/trim_galore/fastqc_report.html",
    ]


def test_trim_galore_plans_single_end_trimmed_read_and_report() -> None:
    node_class = _node_class("trim_galore")

    outputs = node_class.PLAN_OUTPUTS({"reads": "sample.fastq.gz", "paired": False}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/trim_galore/sample_trimmed.fq.gz",
        "/tmp/run/trim_galore/fastqc_report.html",
    ]


def test_trim_galore_rejects_invalid_paired_reads_and_threads() -> None:
    node_class = _node_class("trim_galore")

    assert node_class.VALIDATE_INPUTS({"reads": ["r1.fq"], "paired": True, "threads": 1}) == "paired mode requires exactly two reads."
    assert node_class.VALIDATE_INPUTS({"reads": ["r1.fq", "r2.fq"], "paired": False, "threads": 1}) == "single-end mode requires exactly one read."
    assert node_class.VALIDATE_INPUTS({"reads": "r1.fq", "paired": False, "threads": 0}) == "threads must be at least 1."


def test_trim_galore_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["trim_galore"] == "trim-galore"
    assert PACKAGE_MIN_VERSIONS["trim-galore"] == ">=0.6.10"

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    assert workflow_to_packages({"nodes": [{"id": "trim", "type": "trim_galore"}]}, registry) == ["trim-galore"]
