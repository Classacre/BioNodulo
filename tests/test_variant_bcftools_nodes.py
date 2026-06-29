from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_bcftools_mpileup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bcftools_mpileup"]
    assert node_info["display_name"] == "bcftools mpileup + call"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Generate VCF variant calls")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["vcf"]
    assert node_info["required_executables"] == ["bcftools"]
    assert node_info["required_conda_packages"] == ["bcftools"]
    assert "variant call" in node_info["search_aliases"]
    assert "snp calling" in node_info["search_aliases"]
    assert info["bcftools_call"]["display_name"] == "BCFtools Call"
    assert info["bcftools_call"]["category"] == "variant"
    assert info["bcftools_call"]["output"] == ["VCF_GZ"]
    assert info["bcftools_call"]["output_name"] == ["called_vcf"]
    assert info["bcftools_call"]["required_executables"] == ["bcftools"]
    assert info["bcftools_call"]["required_conda_packages"] == ["bcftools", "htslib"]
    assert info["bcftools_call"]["documentation_url"] == "https://www.htslib.org/doc/bcftools.html#call"
    assert "SNP indel calling" in info["bcftools_call"]["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference"}
    assert set(inputs["optional"]) == {"max_depth", "min_bq", "ploidy"}


def test_bcftools_norm_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bcftools_norm"]
    assert node_info["display_name"] == "bcftools Norm"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Normalize VCF")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["normalized_vcf"]
    assert node_info["required_executables"] == ["bcftools"]
    assert node_info["required_conda_packages"] == ["bcftools"]
    assert "left-align" in node_info["search_aliases"]
    assert "split multiallelic" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "reference"}
    assert set(inputs["optional"]) == {"multiallelics", "deduplicate", "check_ref", "threads"}


def test_bcftools_norm_renders_left_align_split_and_deduplicate_command() -> None:
    node_class = _node_class("bcftools_norm")

    cmd = node_class.render_command({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "multiallelics": "split",
        "deduplicate": "exact",
        "check_ref": "warn",
        "threads": 4,
        "output": "/tmp/run/bcftools_norm",
    })

    assert cmd == [
        "bcftools",
        "norm",
        "-f",
        "GRCh38.fa",
        "-m",
        "-any",
        "-d",
        "exact",
        "--check-ref",
        "w",
        "--threads",
        "4",
        "-Oz",
        "-o",
        "/tmp/run/bcftools_norm/normalized_vcf.vcf.gz",
        "cohort.vcf.gz",
    ]


def test_bcftools_norm_supports_join_mode_without_deduplication() -> None:
    node_class = _node_class("bcftools_norm")

    cmd = node_class.render_command({
        "vcf": "split.vcf.gz",
        "reference": "GRCh38.fa",
        "multiallelics": "join",
        "deduplicate": "none",
        "check_ref": "exit",
        "threads": 0,
        "output": "/tmp/run/bcftools_norm",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "bcftools",
        "norm",
        "-f",
        "GRCh38.fa",
        "-m",
        "+any",
        "--check-ref",
        "e",
        "-Oz",
        "-o",
        "/tmp/run/bcftools_norm/normalized_vcf.vcf.gz",
        "split.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/bcftools_norm/normalized_vcf.vcf.gz"]


def test_bcftools_norm_rejects_unsupported_modes() -> None:
    node_class = _node_class("bcftools_norm")

    assert node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "multiallelics": "explode",
    }) == "Unsupported multiallelics mode: explode"
    assert node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "deduplicate": "records",
    }) == "Unsupported deduplicate mode: records"
    assert node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "check_ref": "ignore",
    }) == "Unsupported check_ref mode: ignore"
