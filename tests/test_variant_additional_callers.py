from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_platypus_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["platypus"]
    assert node_info["display_name"] == "Platypus"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call haplotype-based variants")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["vcf"]
    assert node_info["required_executables"] == ["Platypus.py"]
    assert node_info["required_conda_packages"] == ["platypus-variant"]
    assert "haplotype" in node_info["search_aliases"]
    assert "small variant" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference"}
    assert set(inputs["optional"]) == {
        "regions",
        "threads",
        "min_reads",
        "assemble",
        "filter_duplicates",
    }


def test_platypus_renders_haplotype_calling_command() -> None:
    node_class = _node_class("platypus")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "regions": "targets.bed",
        "threads": 8,
        "min_reads": 3,
        "assemble": True,
        "filter_duplicates": False,
        "output": "/tmp/run/platypus",
    })

    assert cmd == [
        "Platypus.py",
        "callVariants",
        "--bamFiles=sample.bam",
        "--refFile=GRCh38.fa",
        "--output=/tmp/run/platypus/vcf.vcf.gz",
        "--regions=targets.bed",
        "--nCPU=8",
        "--minReads=3",
        "--assemble=1",
        "--filterDuplicates=0",
    ]


def test_platypus_supports_multiple_bams_and_plans_output() -> None:
    node_class = _node_class("platypus")

    cmd = node_class.render_command({
        "bam": ["tumor.bam", "normal.bam"],
        "reference": "GRCh38.fa",
        "output": "/tmp/run/platypus",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "Platypus.py",
        "callVariants",
        "--bamFiles=tumor.bam,normal.bam",
        "--refFile=GRCh38.fa",
        "--output=/tmp/run/platypus/vcf.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/platypus/vcf.vcf.gz"]


def test_platypus_dependency_metadata_is_available() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["Platypus.py"] == "platypus-variant"
    assert PACKAGE_MIN_VERSIONS["platypus-variant"] == ">=0.8.1"
