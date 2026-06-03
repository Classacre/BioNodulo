from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_modkit_pileup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["modkit_pileup"]
    assert node_info["display_name"] == "Modkit Pileup"
    assert node_info["category"] == "long_read"
    assert node_info["description"].startswith("Generate bedMethyl pileup")
    assert node_info["output"] == ["BED"]
    assert node_info["output_name"] == ["bedmethyl"]
    assert node_info["required_executables"] == ["modkit"]
    assert node_info["required_conda_packages"] == ["modkit"]
    assert "methylation" in node_info["search_aliases"]
    assert "bedmethyl" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "threads"}
    assert set(inputs["optional"]) == {"combine_strands", "region", "bedgraph"}


def test_modkit_pileup_renders_bedmethyl_command() -> None:
    node_class = _node_class("modkit_pileup")

    cmd = node_class.render_command({
        "bam": "calls.bam",
        "reference": "hg38.fa",
        "threads": 12,
        "combine_strands": True,
        "region": "chr1:1-1000000",
        "bedgraph": True,
        "output": "/tmp/run/modkit_pileup",
    })

    assert cmd == [
        "modkit",
        "pileup",
        "calls.bam",
        "/tmp/run/modkit_pileup/bedmethyl.bed",
        "--ref",
        "hg38.fa",
        "--threads",
        "12",
        "--combine-strands",
        "--region",
        "chr1:1-1000000",
        "--bedgraph",
    ]


def test_modkit_pileup_omits_empty_optional_flags() -> None:
    node_class = _node_class("modkit_pileup")

    cmd = node_class.render_command({
        "bam": "calls.bam",
        "reference": "hg38.fa",
        "threads": 4,
        "combine_strands": False,
        "region": "",
        "bedgraph": False,
        "output": "/tmp/run/modkit_pileup",
    })

    assert cmd == [
        "modkit",
        "pileup",
        "calls.bam",
        "/tmp/run/modkit_pileup/bedmethyl.bed",
        "--ref",
        "hg38.fa",
        "--threads",
        "4",
    ]


def test_modkit_pileup_plans_bed_output() -> None:
    node_class = _node_class("modkit_pileup")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/modkit_pileup/bedmethyl.bed"]
