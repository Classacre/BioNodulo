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
    assert node_info["display_name"] == "BCFtools Mpileup"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Generate VCF or BCF containing genotype likelihoods")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["mpileup_vcf"]
    assert node_info["required_executables"] == ["bcftools", "samtools"]
    assert node_info["required_conda_packages"] == ["bcftools", "htslib", "samtools"]
    assert node_info["documentation_url"] == "https://www.htslib.org/doc/bcftools.html#mpileup"
    assert "genotype likelihoods" in node_info["search_aliases"]
    assert "BAM CRAM pileup" in node_info["search_aliases"]
    assert info["bcftools_call"]["display_name"] == "BCFtools Call"
    assert info["bcftools_call"]["category"] == "variant"
    assert info["bcftools_call"]["output"] == ["VCF_GZ"]
    assert info["bcftools_call"]["output_name"] == ["called_vcf"]
    assert info["bcftools_call"]["required_executables"] == ["bcftools"]
    assert info["bcftools_call"]["required_conda_packages"] == ["bcftools", "htslib"]
    assert info["bcftools_call"]["documentation_url"] == "https://www.htslib.org/doc/bcftools.html#call"
    assert "SNP indel calling" in info["bcftools_call"]["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_bams"}
    assert {"reference", "reference_source", "max_reads_per_bam", "output_type", "threads"}.issubset(inputs["optional"])


def test_bcftools_norm_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bcftools_norm"]
    assert node_info["display_name"] == "BCFtools Norm"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Left-align and normalize")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["normalized_vcf"]
    assert node_info["required_executables"] == ["bcftools", "samtools"]
    assert node_info["required_conda_packages"] == ["bcftools", "htslib", "samtools"]
    assert node_info["documentation_url"] == "https://www.htslib.org/doc/bcftools.html#norm"
    assert "left-align indels" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_file"}
    assert {"reference", "check_ref", "multiallelic_mode", "output_type", "threads"}.issubset(inputs["optional"])


def test_bcftools_norm_renders_left_align_split_and_deduplicate_command() -> None:
    node_class = _node_class("bcftools_norm")

    cmd = node_class.render_command({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "multiallelics": "split",
        "deduplicate": "snps",
        "check_ref": "w",
        "threads": 4,
        "output": "/tmp/run/bcftools_norm",
    })

    assert cmd == [
        "bcftools",
        "norm",
        "--fasta-ref",
        "GRCh38.fa",
        "--check-ref",
        "w",
        "--rm-dup",
        "snps",
        "--multiallelics",
        "-both",
        "--sort",
        "pos",
        "--output-type",
        "z",
        "--threads",
        "4",
        "cohort.vcf.gz",
        ">",
        "/tmp/run/bcftools_norm/normalized.vcf.gz",
    ]


def test_bcftools_norm_supports_join_mode_without_deduplication() -> None:
    node_class = _node_class("bcftools_norm")

    cmd = node_class.render_command({
        "vcf": "split.vcf.gz",
        "reference": "GRCh38.fa",
        "multiallelics": "join",
        "deduplicate": "none",
        "check_ref": "e",
        "threads": 0,
        "output": "/tmp/run/bcftools_norm",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "bcftools",
        "norm",
        "--fasta-ref",
        "GRCh38.fa",
        "--check-ref",
        "e",
        "--multiallelics",
        "+both",
        "--sort",
        "pos",
        "--output-type",
        "z",
        "split.vcf.gz",
        ">",
        "/tmp/run/bcftools_norm/normalized.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/bcftools_norm/normalized.vcf.gz"]


def test_bcftools_norm_rejects_unsupported_modes() -> None:
    node_class = _node_class("bcftools_norm")

    assert node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "multiallelics": "explode",
    }) == "multiallelic_mode must be one of: -, +"
    assert node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "deduplicate": "records",
    }) == "rm_dup must be one of: snps, indels, both, any"
    assert node_class.VALIDATE_INPUTS({
        "vcf": "cohort.vcf.gz",
        "reference": "GRCh38.fa",
        "check_ref": "ignore",
    }) == "check_ref must be one of: w, wx, ws, e"
