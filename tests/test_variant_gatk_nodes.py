from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_gatk_genotype_gvcfs_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["gatk_genotype_gvcfs"]
    assert node_info["display_name"] == "GATK GenotypeGVCFs"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Joint genotype")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["vcf"]
    assert node_info["required_executables"] == ["gatk"]
    assert node_info["required_conda_packages"] == ["gatk4"]
    assert "joint genotyping" in node_info["search_aliases"]
    assert "gvcf" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"gvcfs", "reference"}
    assert set(inputs["optional"]) == {"intervals", "dbsnp", "standard_min_confidence"}


def test_gatk_genotype_gvcfs_renders_joint_genotyping_command() -> None:
    node_class = _node_class("gatk_genotype_gvcfs")

    cmd = node_class.render_command({
        "gvcfs": ["sample_a.g.vcf.gz", "sample_b.g.vcf.gz"],
        "reference": "GRCh38.fa",
        "intervals": "chr1:1-100000",
        "dbsnp": "dbsnp.vcf.gz",
        "standard_min_confidence": 20,
        "output": "/tmp/run/gatk_genotype_gvcfs",
    })

    assert cmd == [
        "gatk",
        "GenotypeGVCFs",
        "-R",
        "GRCh38.fa",
        "-V",
        "sample_a.g.vcf.gz",
        "-V",
        "sample_b.g.vcf.gz",
        "-L",
        "chr1:1-100000",
        "--dbsnp",
        "dbsnp.vcf.gz",
        "--standard-min-confidence-threshold-for-calling",
        "20",
        "-O",
        "/tmp/run/gatk_genotype_gvcfs/vcf.vcf.gz",
    ]


def test_gatk_genotype_gvcfs_accepts_comma_separated_gvcfs() -> None:
    node_class = _node_class("gatk_genotype_gvcfs")

    cmd = node_class.render_command({
        "gvcfs": "sample_a.g.vcf.gz, sample_b.g.vcf.gz",
        "reference": "GRCh38.fa",
        "output": "/tmp/run/gatk_genotype_gvcfs",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "gatk",
        "GenotypeGVCFs",
        "-R",
        "GRCh38.fa",
        "-V",
        "sample_a.g.vcf.gz",
        "-V",
        "sample_b.g.vcf.gz",
        "-O",
        "/tmp/run/gatk_genotype_gvcfs/vcf.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/gatk_genotype_gvcfs/vcf.vcf.gz"]


def test_mutect2_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mutect2"]
    assert node_info["display_name"] == "Mutect2"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call somatic variants")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["vcf"]
    assert node_info["required_executables"] == ["gatk"]
    assert node_info["required_conda_packages"] == ["gatk4"]
    assert "somatic variant" in node_info["search_aliases"]
    assert "tumor normal" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"tumor_bam", "reference"}
    assert set(inputs["optional"]) == {
        "normal_bam",
        "tumor_sample",
        "normal_sample",
        "germline_resource",
        "panel_of_normals",
        "intervals",
    }


def test_mutect2_renders_tumor_normal_command() -> None:
    node_class = _node_class("mutect2")

    cmd = node_class.render_command({
        "tumor_bam": "tumor.bam",
        "normal_bam": "normal.bam",
        "reference": "GRCh38.fa",
        "tumor_sample": "TUMOR",
        "normal_sample": "NORMAL",
        "germline_resource": "af-only-gnomad.vcf.gz",
        "panel_of_normals": "pon.vcf.gz",
        "intervals": "chr7:1-100000",
        "output": "/tmp/run/mutect2",
    })

    assert cmd == [
        "gatk",
        "Mutect2",
        "-R",
        "GRCh38.fa",
        "-I",
        "tumor.bam",
        "-tumor",
        "TUMOR",
        "-I",
        "normal.bam",
        "-normal",
        "NORMAL",
        "--germline-resource",
        "af-only-gnomad.vcf.gz",
        "--panel-of-normals",
        "pon.vcf.gz",
        "-L",
        "chr7:1-100000",
        "-O",
        "/tmp/run/mutect2/vcf.vcf.gz",
    ]


def test_mutect2_supports_tumor_only_mode_and_plans_output() -> None:
    node_class = _node_class("mutect2")

    cmd = node_class.render_command({
        "tumor_bam": "tumor.bam",
        "reference": "GRCh38.fa",
        "output": "/tmp/run/mutect2",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "gatk",
        "Mutect2",
        "-R",
        "GRCh38.fa",
        "-I",
        "tumor.bam",
        "-O",
        "/tmp/run/mutect2/vcf.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/mutect2/vcf.vcf.gz"]
