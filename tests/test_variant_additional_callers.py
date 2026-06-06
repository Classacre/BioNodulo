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


def test_deepvariant_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["deepvariant"]
    assert node_info["display_name"] == "DeepVariant"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call small variants with DeepVariant")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["vcf"]
    assert node_info["required_executables"] == ["run_deepvariant"]
    assert node_info["required_conda_packages"] == ["deepvariant"]
    assert "deep learning" in node_info["search_aliases"]
    assert "small variant" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference"}
    assert set(inputs["optional"]) == {
        "model_type",
        "regions",
        "num_shards",
        "sample_name",
        "intermediate_results_dir",
    }


def test_deepvariant_renders_small_variant_calling_command() -> None:
    node_class = _node_class("deepvariant")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "model_type": "WGS",
        "regions": "chr20:10,000,000-10,010,000",
        "num_shards": 8,
        "sample_name": "HG001",
        "intermediate_results_dir": "/tmp/deepvariant_intermediate",
        "output": "/tmp/run/deepvariant",
    })

    assert cmd == [
        "run_deepvariant",
        "--model_type=WGS",
        "--ref=GRCh38.fa",
        "--reads=sample.bam",
        "--output_vcf=/tmp/run/deepvariant/vcf.vcf.gz",
        "--num_shards=8",
        "--regions=chr20:10,000,000-10,010,000",
        "--sample_name=HG001",
        "--intermediate_results_dir=/tmp/deepvariant_intermediate",
    ]


def test_clair3_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["clair3"]
    assert node_info["display_name"] == "Clair3"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call small variants from long-read")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["vcf"]
    assert node_info["required_executables"] == ["run_clair3.sh"]
    assert node_info["required_conda_packages"] == ["clair3"]
    assert "nanopore" in node_info["search_aliases"]
    assert "deep learning" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "model_path"}
    assert set(inputs["optional"]) == {
        "platform",
        "threads",
        "regions_bed",
        "candidate_vcf",
        "contigs",
        "sample_name",
        "qual",
        "chunk_size",
        "include_all_ctgs",
        "pileup_only",
        "enable_phasing",
        "haploid_precise",
        "haploid_sensitive",
        "enable_dwell_time",
    }


def test_clair3_renders_long_read_variant_calling_command() -> None:
    node_class = _node_class("clair3")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "model_path": "/opt/models/r1041_e82_400bps_sup_v500",
        "platform": "ont",
        "threads": 16,
        "regions_bed": "targets.bed",
        "candidate_vcf": "known_sites.vcf.gz",
        "contigs": "chr20,chr21",
        "sample_name": "HG001",
        "qual": 5,
        "chunk_size": 1000000,
        "include_all_ctgs": True,
        "pileup_only": True,
        "enable_phasing": True,
        "haploid_precise": False,
        "haploid_sensitive": True,
        "enable_dwell_time": True,
        "output": "/tmp/run/clair3",
    })

    assert cmd == [
        "run_clair3.sh",
        "--bam_fn=sample.bam",
        "--ref_fn=GRCh38.fa",
        "--threads=16",
        "--platform=ont",
        "--model_path=/opt/models/r1041_e82_400bps_sup_v500",
        "--output=/tmp/run/clair3",
        "--bed_fn=targets.bed",
        "--vcf_fn=known_sites.vcf.gz",
        "--ctg_name=chr20,chr21",
        "--sample_name=HG001",
        "--qual=5",
        "--chunk_size=1000000",
        "--include_all_ctgs",
        "--pileup_only",
        "--enable_phasing",
        "--haploid_sensitive",
        "--enable_dwell_time",
    ]


def test_clair3_omits_empty_optional_flags_and_plans_merge_output() -> None:
    node_class = _node_class("clair3")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "model_path": "/models/hifi",
        "platform": "hifi",
        "threads": 8,
        "regions_bed": "",
        "candidate_vcf": "",
        "contigs": "",
        "sample_name": "",
        "include_all_ctgs": False,
        "pileup_only": False,
        "enable_phasing": False,
        "haploid_precise": False,
        "haploid_sensitive": False,
        "enable_dwell_time": False,
        "output": "/tmp/run/clair3",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "run_clair3.sh",
        "--bam_fn=sample.bam",
        "--ref_fn=GRCh38.fa",
        "--threads=8",
        "--platform=hifi",
        "--model_path=/models/hifi",
        "--output=/tmp/run/clair3",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/clair3/merge_output.vcf.gz"]


def test_clair3_rejects_unsupported_platform_and_non_positive_threads() -> None:
    node_class = _node_class("clair3")

    assert node_class.VALIDATE_INPUTS({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "model_path": "/models/ont",
        "platform": "clr",
        "threads": 4,
    }) == "Unsupported Clair3 platform: clr"
    assert node_class.VALIDATE_INPUTS({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "model_path": "/models/ont",
        "platform": "ont",
        "threads": 0,
    }) == "Clair3 threads must be greater than zero."


def test_clair3_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["run_clair3.sh"] == "clair3"
    assert PACKAGE_MIN_VERSIONS["clair3"] == ">=2.0.1"


def test_deepvariant_uses_default_model_and_plans_output() -> None:
    node_class = _node_class("deepvariant")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "output": "/tmp/run/deepvariant",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "run_deepvariant",
        "--model_type=WGS",
        "--ref=GRCh38.fa",
        "--reads=sample.bam",
        "--output_vcf=/tmp/run/deepvariant/vcf.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/deepvariant/vcf.vcf.gz"]


def test_deepvariant_dependency_metadata_is_available() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["run_deepvariant"] == "deepvariant"
    assert PACKAGE_MIN_VERSIONS["deepvariant"] == ">=1.6.0"
