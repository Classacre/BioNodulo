from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_filter_vcf_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["filter_vcf"]
    assert node_info["display_name"] == "Filter VCF"
    assert node_info["category"] == "data_transform"
    assert node_info["output_name"] == ["filtered_vcf"]
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["required_executables"] == ["bcftools"]
    assert node_info["required_conda_packages"] == ["bcftools"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf"}
    assert set(inputs["optional"]) == {
        "regions",
        "targets",
        "min_qual",
        "min_dp",
        "max_dp",
        "min_af",
        "max_af",
        "pass_only",
        "biallelic_only",
        "snp_only",
        "indel_only",
        "custom_filter",
        "samples",
        "output_type",
        "threads",
    }


def test_filter_vcf_renders_realistic_bcftools_filter_command() -> None:
    node_class = _node_class("filter_vcf")

    cmd = node_class.render_command({
        "vcf": "cohort.vcf.gz",
        "regions": "chr1:100-200,chr2:500-900",
        "samples": "S1,S2",
        "min_qual": 30.0,
        "min_dp": 10,
        "pass_only": True,
        "biallelic_only": True,
        "snp_only": True,
        "output_type": "VCF_GZ",
        "threads": 4,
        "output": "/tmp/run/filter_vcf",
    })

    assert cmd == [
        "bcftools",
        "view",
        "--regions",
        "chr1:100-200,chr2:500-900",
        "--samples",
        "S1,S2",
        "--min-alleles",
        "2",
        "--max-alleles",
        "2",
        "--types",
        "snps",
        "cohort.vcf.gz",
        "|",
        "bcftools",
        "filter",
        "--include",
        'QUAL >= 30.0 && INFO/DP >= 10 && FILTER == "PASS"',
        "|",
        "bcftools",
        "view",
        "--threads",
        "4",
        "-Oz",
        "-o",
        "/tmp/run/filter_vcf/filtered_vcf.vcf.gz",
    ]


def test_filter_vcf_rejects_contradictory_variant_type_filters() -> None:
    node_class = _node_class("filter_vcf")

    validation = node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "snp_only": True,
        "indel_only": True,
    })

    assert validation == "snp_only and indel_only cannot both be enabled"


def test_filter_vcf_uses_output_type_specific_extension() -> None:
    node_class = _node_class("filter_vcf")

    outputs = node_class.PLAN_OUTPUTS({"output_type": "BCF"}, "/tmp/run")
    cmd = node_class.render_command({
        "vcf": "cohort.vcf.gz",
        "output_type": "BCF",
        "output": "/tmp/run/filter_vcf",
    })

    assert str(outputs[0]) == "/tmp/run/filter_vcf/filtered_vcf.bcf"
    assert cmd[-2:] == ["-o", "/tmp/run/filter_vcf/filtered_vcf.bcf"]
