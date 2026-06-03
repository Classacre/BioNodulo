from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_spaceranger_count_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["spaceranger_count"]
    assert node_info["display_name"] == "Space Ranger Count"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Process 10x Genomics Visium")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["spaceranger_out"]
    assert node_info["required_executables"] == ["spaceranger"]
    assert node_info["required_conda_packages"] == ["spaceranger"]
    assert node_info["experimental"] is True
    assert "spaceranger" in node_info["search_aliases"]
    assert "10x visium" in node_info["search_aliases"]
    assert "spatial transcriptomics" in node_info["search_aliases"]
    assert "visium" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {
        "sample_id",
        "transcriptome",
        "fastqs_dir",
        "sample_prefix",
        "he_image",
        "slide",
        "area",
        "threads",
        "memory",
    }
    assert set(inputs["optional"]) == {"create_bam"}


def test_spaceranger_count_renders_full_count_command() -> None:
    node_class = _node_class("spaceranger_count")

    cmd = node_class.render_command({
        "sample_id": "visium_sample",
        "transcriptome": "/refs/spaceranger_GRCh38",
        "fastqs_dir": "/data/fastqs",
        "sample_prefix": "sampleA",
        "he_image": "/data/tissue.tif",
        "slide": "V19L01-041",
        "area": "A1",
        "threads": 12,
        "memory": 48,
        "create_bam": True,
        "output": "/tmp/run/spaceranger_count",
    })

    assert cmd == [
        "spaceranger",
        "count",
        "--id",
        "visium_sample",
        "--transcriptome",
        "/refs/spaceranger_GRCh38",
        "--fastqs",
        "/data/fastqs",
        "--sample",
        "sampleA",
        "--image",
        "/data/tissue.tif",
        "--slide",
        "V19L01-041",
        "--area",
        "A1",
        "--localcores",
        "12",
        "--localmem",
        "48",
        "--output-dir",
        "/tmp/run/spaceranger_count",
        "--create-bam=true",
    ]


def test_spaceranger_count_omits_create_bam_when_disabled() -> None:
    node_class = _node_class("spaceranger_count")

    cmd = node_class.render_command({
        "sample_id": "visium_sample",
        "transcriptome": "/refs/spaceranger_GRCh38",
        "fastqs_dir": "/data/fastqs",
        "sample_prefix": "sampleA",
        "he_image": "/data/tissue.tif",
        "slide": "V19L01-041",
        "area": "A1",
        "threads": 8,
        "memory": 32,
        "create_bam": False,
        "output": "/tmp/run/spaceranger_count",
    })

    assert "--create-bam=true" not in cmd
    assert cmd[-2:] == ["--output-dir", "/tmp/run/spaceranger_count"]


def test_spaceranger_count_plans_output_directory() -> None:
    node_class = _node_class("spaceranger_count")

    outputs = node_class.PLAN_OUTPUTS({"sample_id": "visium_sample"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/spaceranger_count/visium_sample",
    ]


def test_spaceranger_count_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["spaceranger"] == "spaceranger"
    assert PACKAGE_MIN_VERSIONS["spaceranger"] == ">=3.1"
