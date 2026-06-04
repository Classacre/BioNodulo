from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_sniffles2_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["sniffles2"]
    assert node_info["display_name"] == "Sniffles2 SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Long-read SV caller")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["sniffles"]
    assert node_info["required_conda_packages"] == ["sniffles"]
    assert "long-read sv" in node_info["search_aliases"]
    assert "nanopore sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "threads"}
    assert set(inputs["optional"]) == {
        "tandem_repeats",
        "minsvlen",
        "minsupport",
        "phase",
    }


def test_sniffles2_renders_long_read_sv_command() -> None:
    node_class = _node_class("sniffles2")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "threads": 12,
        "tandem_repeats": "human_hs37d5.trf.bed",
        "minsvlen": 75,
        "minsupport": 6,
        "phase": True,
        "output": "/tmp/run/sniffles2",
    })

    assert cmd == [
        "sniffles",
        "--input",
        "sample.sorted.bam",
        "--vcf",
        "/tmp/run/sniffles2/sv_vcf.vcf.gz",
        "--reference",
        "GRCh38.fa",
        "--threads",
        "12",
        "--tandem-repeats",
        "human_hs37d5.trf.bed",
        "--minsvlen",
        "75",
        "--minsupport",
        "6",
        "--phase",
    ]


def test_sniffles2_plans_compressed_vcf_output() -> None:
    node_class = _node_class("sniffles2")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/sniffles2/sv_vcf.vcf.gz"]


def test_sv_stats_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["sv_stats"]
    assert node_info["display_name"] == "SV Stats"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Compute structural variant statistics")
    assert node_info["output"] == ["JSON", "IMAGE"]
    assert node_info["output_name"] == ["stats_json", "stats_plot"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["pysam", "matplotlib"]
    assert "sv stats" in node_info["search_aliases"]
    assert "size distribution" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sv_vcf", "reference"}
    assert set(inputs["optional"]) == {"min_size", "max_size", "plot_format"}


def test_sv_stats_renders_embedded_python_command() -> None:
    node_class = _node_class("sv_stats")

    cmd = node_class.render_command({
        "sv_vcf": "calls.vcf.gz",
        "reference": "GRCh38.fa",
        "min_size": 50,
        "max_size": 100000,
        "plot_format": "png",
        "output": "/tmp/run/sv_stats",
    })

    assert cmd[:3] == ["python", "-c", cmd[2]]
    script = cmd[2]
    assert "import pysam" in script
    assert "matplotlib.use('Agg')" in script
    assert "SVTYPE" in script
    assert "SVLEN" in script
    assert "json.dump(summary" in script
    assert "fig.savefig(stats_plot)" in script
    assert cmd[3:] == [
        "calls.vcf.gz",
        "GRCh38.fa",
        "/tmp/run/sv_stats/stats_json.json",
        "/tmp/run/sv_stats/stats_plot.png",
        "50",
        "100000",
    ]


def test_sv_stats_plans_json_and_image_outputs() -> None:
    node_class = _node_class("sv_stats")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/sv_stats/stats_json.json",
        "/tmp/run/sv_stats/stats_plot.png",
    ]


def test_vcf_comparison_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vcf_comparison"]
    assert node_info["display_name"] == "VCF Comparison"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Compare variant callsets")
    assert node_info["output"] == ["JSON", "IMAGE"]
    assert node_info["output_name"] == ["comparison", "venn_plot"]
    assert node_info["required_executables"] == ["rtg"]
    assert node_info["required_conda_packages"] == ["rtg-tools", "matplotlib"]
    assert "benchmark" in node_info["search_aliases"]
    assert "precision recall" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf_a", "vcf_b", "reference"}
    assert set(inputs["optional"]) == {"sample", "squash_ploidy", "plot_format"}


def test_vcf_comparison_renders_rtg_vcfeval_command() -> None:
    node_class = _node_class("vcf_comparison")

    cmd = node_class.render_command({
        "vcf_a": "truth.vcf.gz",
        "vcf_b": "calls.vcf.gz",
        "reference": "GRCh38.fa",
        "sample": "tumor-01",
        "squash_ploidy": True,
        "plot_format": "png",
        "output": "/tmp/run/vcf_comparison",
    })

    assert cmd[:3] == ["bash", "-c", cmd[2]]
    script = cmd[2]
    assert "rtg format -o" in script
    assert "rtg vcfeval" in script
    assert "--squash-ploidy" in script
    assert "--sample tumor-01" in script
    assert "summary.txt" in script
    assert "comparison.json" in script
    assert "venn_plot.png" in script
    assert "truth.vcf.gz" in script
    assert "calls.vcf.gz" in script
    assert "GRCh38.fa" in script


def test_vcf_comparison_plans_json_and_image_outputs() -> None:
    node_class = _node_class("vcf_comparison")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/vcf_comparison/comparison.json",
        "/tmp/run/vcf_comparison/venn_plot.png",
    ]


def test_vcf_comparison_dependency_metadata_is_available() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["rtg"] == "rtg-tools"
    assert PACKAGE_MIN_VERSIONS["rtg-tools"] == ">=3.12"


def test_strelka2_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["strelka2"]
    assert node_info["display_name"] == "Strelka2"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call germline or somatic small variants")
    assert node_info["output"] == ["VCF_GZ", "VCF_GZ"]
    assert node_info["output_name"] == ["snv_vcf", "indel_vcf"]
    assert node_info["required_executables"] == ["configureStrelkaGermlineWorkflow.py"]
    assert node_info["required_conda_packages"] == ["strelka"]
    assert "small variant" in node_info["search_aliases"]
    assert "somatic" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference"}
    assert set(inputs["optional"]) == {"normal_bam", "mode", "threads", "exome", "call_regions"}


def test_strelka2_renders_germline_workflow_command() -> None:
    node_class = _node_class("strelka2")

    cmd = node_class.render_command({
        "bam": "sample.bam",
        "reference": "GRCh38.fa",
        "mode": "germline",
        "threads": 12,
        "exome": True,
        "call_regions": "targets.bed.gz",
        "output": "/tmp/run/strelka2",
    })

    assert cmd[:3] == ["bash", "-c", cmd[2]]
    script = cmd[2]
    assert "configureStrelkaGermlineWorkflow.py" in script
    assert "--bam sample.bam" in script
    assert "--referenceFasta GRCh38.fa" in script
    assert "--runDir /tmp/run/strelka2/strelka_run" in script
    assert "--exome" in script
    assert "--callRegions targets.bed.gz" in script
    assert "runWorkflow.py -m local -j 12" in script
    assert "variants.vcf.gz" in script
    assert "indels.vcf.gz" in script


def test_strelka2_renders_somatic_workflow_command() -> None:
    node_class = _node_class("strelka2")

    cmd = node_class.render_command({
        "bam": "tumor.bam",
        "normal_bam": "normal.bam",
        "reference": "GRCh38.fa",
        "mode": "somatic",
        "threads": 4,
        "output": "/tmp/run/strelka2",
    })

    script = cmd[2]
    assert "configureStrelkaSomaticWorkflow.py" in script
    assert "--tumorBam tumor.bam" in script
    assert "--normalBam normal.bam" in script
    assert "somatic.snvs.vcf.gz" in script
    assert "somatic.indels.vcf.gz" in script


def test_strelka2_plans_small_variant_outputs() -> None:
    node_class = _node_class("strelka2")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/strelka2/snv_vcf.vcf.gz",
        "/tmp/run/strelka2/indel_vcf.vcf.gz",
    ]


def test_strelka2_dependency_metadata_is_available() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["configureStrelkaGermlineWorkflow.py"] == "strelka"
    assert EXECUTABLE_TO_CONDA_PACKAGE["configureStrelkaSomaticWorkflow.py"] == "strelka"
    assert PACKAGE_MIN_VERSIONS["strelka"] == ">=2.9.10"


def test_gridss_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["gridss"]
    assert node_info["display_name"] == "GRIDSS SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call structural variants with GRIDSS")
    assert node_info["output"] == ["VCF_GZ", "BAM"]
    assert node_info["output_name"] == ["sv_vcf", "assembly_bam"]
    assert node_info["required_executables"] == ["gridss"]
    assert node_info["required_conda_packages"] == ["gridss"]
    assert "breakend" in node_info["search_aliases"]
    assert "assembly sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bams", "reference", "threads"}
    assert set(inputs["optional"]) == {"blacklist", "labels", "steps", "gridss_jar", "jvm_heap"}


def test_gridss_renders_joint_calling_command_with_optional_flags() -> None:
    node_class = _node_class("gridss")

    cmd = node_class.render_command({
        "bams": ["tumor.bam", "normal.bam"],
        "reference": "GRCh38.fa",
        "threads": 12,
        "blacklist": "encode_blacklist.bed",
        "labels": "tumor,normal",
        "steps": "all",
        "gridss_jar": "/opt/gridss/gridss.jar",
        "jvm_heap": "31g",
        "output": "/tmp/run/gridss",
    })

    assert cmd == [
        "gridss",
        "--reference",
        "GRCh38.fa",
        "--output",
        "/tmp/run/gridss/sv_vcf.vcf.gz",
        "--assembly",
        "/tmp/run/gridss/assembly_bam.bam",
        "--threads",
        "12",
        "--workingdir",
        "/tmp/run/gridss/gridss_working",
        "--blacklist",
        "encode_blacklist.bed",
        "--labels",
        "tumor,normal",
        "--steps",
        "all",
        "--jar",
        "/opt/gridss/gridss.jar",
        "--jvmheap",
        "31g",
        "tumor.bam",
        "normal.bam",
    ]


def test_gridss_omits_optional_flags_for_single_sample_calling() -> None:
    node_class = _node_class("gridss")

    cmd = node_class.render_command({
        "bams": "sample.bam",
        "reference": "GRCh38.fa",
        "threads": 4,
        "blacklist": "",
        "labels": "",
        "steps": "all",
        "gridss_jar": "",
        "jvm_heap": "",
        "output": "/tmp/run/gridss",
    })

    assert "--blacklist" not in cmd
    assert "--labels" not in cmd
    assert "--jar" not in cmd
    assert "--jvmheap" not in cmd
    assert cmd == [
        "gridss",
        "--reference",
        "GRCh38.fa",
        "--output",
        "/tmp/run/gridss/sv_vcf.vcf.gz",
        "--assembly",
        "/tmp/run/gridss/assembly_bam.bam",
        "--threads",
        "4",
        "--workingdir",
        "/tmp/run/gridss/gridss_working",
        "--steps",
        "all",
        "sample.bam",
    ]


def test_gridss_plans_vcf_and_assembly_bam_outputs() -> None:
    node_class = _node_class("gridss")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/gridss/sv_vcf.vcf.gz",
        "/tmp/run/gridss/assembly_bam.bam",
    ]


def test_gridss_rejects_empty_bams_reference_threads_and_mismatched_labels() -> None:
    node_class = _node_class("gridss")

    assert (
        node_class.VALIDATE_INPUTS({"bams": [], "reference": "GRCh38.fa", "threads": 4})
        == "At least one BAM is required"
    )
    assert (
        node_class.VALIDATE_INPUTS({"bams": "sample.bam", "reference": "", "threads": 4})
        == "Input 'reference' must not be empty"
    )
    assert (
        node_class.VALIDATE_INPUTS({"bams": "sample.bam", "reference": "GRCh38.fa", "threads": 0})
        == "Input 'threads' must be at least 1"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "bams": ["tumor.bam", "normal.bam"],
            "reference": "GRCh38.fa",
            "threads": 4,
            "labels": "tumor",
        })
        == "Number of GRIDSS labels must match number of BAM inputs"
    )


def test_gridss_environment_metadata_is_available() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["gridss"] == "gridss"
    assert PACKAGE_MIN_VERSIONS["gridss"] == ">=2.13.2"
    assert workflow_to_packages({"nodes": [{"id": "gridss", "type": "gridss"}]}, registry) == ["gridss"]


def test_melt_mobile_elements_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["melt_mobile_elements"]
    assert node_info["display_name"] == "MELT Mobile Elements"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call mobile element insertions")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["melt_output"]
    assert node_info["required_executables"] == ["java"]
    assert node_info["required_conda_packages"] == []
    assert "mobile element" in node_info["search_aliases"]
    assert "mei" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {
        "bam",
        "reference",
        "melt_jar",
        "mei_list",
        "genome_annotation",
        "output_prefix",
        "coverage",
    }
    assert set(inputs["optional"]) == {"exome"}


def test_melt_mobile_elements_renders_single_command() -> None:
    node_class = _node_class("melt_mobile_elements")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "melt_jar": "/opt/MELT/MELT.jar",
        "mei_list": "/refs/melt/mei_list",
        "genome_annotation": "/refs/melt/Hg38.genes.bed",
        "output_prefix": "tumor-01",
        "coverage": 30,
        "exome": False,
        "output": "/tmp/run/melt_mobile_elements",
    })

    assert cmd == [
        "java",
        "-jar",
        "/opt/MELT/MELT.jar",
        "Single",
        "-bamfile",
        "sample.sorted.bam",
        "-h",
        "GRCh38.fa",
        "-n",
        "/refs/melt/Hg38.genes.bed",
        "-t",
        "/refs/melt/mei_list",
        "-c",
        "30",
        "-w",
        "/tmp/run/melt_mobile_elements/tumor-01",
        "-exome",
        "false",
    ]


def test_melt_mobile_elements_supports_exome_mode_and_plans_output_directory() -> None:
    node_class = _node_class("melt_mobile_elements")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "melt_jar": "MELT.jar",
        "mei_list": "mei_list",
        "genome_annotation": "genes.bed",
        "output_prefix": "sample",
        "coverage": 8,
        "exome": True,
        "output": "/tmp/run/melt_mobile_elements",
    })
    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "sample"}, "/tmp/run")

    assert cmd[-2:] == ["-exome", "true"]
    assert [str(path) for path in outputs] == ["/tmp/run/melt_mobile_elements/sample"]


def test_melt_mobile_elements_rejects_empty_paths_prefix_and_invalid_threads() -> None:
    node_class = _node_class("melt_mobile_elements")
    valid_inputs = {
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "melt_jar": "MELT.jar",
        "mei_list": "mei_list",
        "genome_annotation": "genes.bed",
        "output_prefix": "sample",
        "coverage": 4,
    }

    assert node_class.VALIDATE_INPUTS(valid_inputs) is True
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"bam": " "}) == "Input 'bam' must not be empty"
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"reference": ""}) == "Input 'reference' must not be empty"
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"melt_jar": "  "}) == "Input 'melt_jar' must not be empty"
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"mei_list": ""}) == "Input 'mei_list' must not be empty"
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"genome_annotation": ""}) == (
        "Input 'genome_annotation' must not be empty"
    )
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"output_prefix": " "}) == (
        "Input 'output_prefix' must not be empty"
    )
    assert node_class.VALIDATE_INPUTS(valid_inputs | {"coverage": 0}) == "Input 'coverage' must be at least 1"


def test_melt_mobile_elements_environment_metadata_uses_java_without_fake_melt_package() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["java"] == "openjdk"
    assert PACKAGE_MIN_VERSIONS["openjdk"] == ">=17"
    assert workflow_to_packages({"nodes": [{"id": "melt", "type": "melt_mobile_elements"}]}, registry) == ["openjdk"]


def test_survivor_merge_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["survivor_merge"]
    assert node_info["display_name"] == "SURVIVOR Merge"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Merge SV calls")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["merged_sv"]
    assert node_info["required_executables"] == ["SURVIVOR"]
    assert node_info["required_conda_packages"] == ["survivor"]
    assert "consensus sv" in node_info["search_aliases"]
    assert "multi-caller" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf_files", "max_distance", "min_callers"}
    assert set(inputs["optional"]) == {"use_type", "use_strand", "min_sv_size"}


def test_survivor_merge_writes_input_list_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("survivor_merge")
    output_dir = tmp_path / "survivor_merge"
    output_dir.mkdir()

    cmd = node_class.render_command({
        "vcf_files": ["manta.vcf.gz", "delly.vcf.gz", "sniffles.vcf.gz"],
        "max_distance": 500,
        "min_callers": 2,
        "use_type": 1,
        "use_strand": 0,
        "min_sv_size": 50,
        "output": str(output_dir),
    })

    sample_list = output_dir / "sample_files.txt"
    assert sample_list.read_text(encoding="utf-8") == "manta.vcf.gz\ndelly.vcf.gz\nsniffles.vcf.gz\n"
    assert cmd == [
        "SURVIVOR",
        "merge",
        str(sample_list),
        "500",
        "2",
        "1",
        "0",
        "50",
        str(output_dir / "merged_sv.vcf"),
    ]


def test_survivor_merge_accepts_single_vcf_string(tmp_path: Path) -> None:
    node_class = _node_class("survivor_merge")
    output_dir = tmp_path / "survivor_merge"
    output_dir.mkdir()

    cmd = node_class.render_command({
        "vcf_files": "sniffles.vcf.gz",
        "output": str(output_dir),
    })

    assert (output_dir / "sample_files.txt").read_text(encoding="utf-8") == "sniffles.vcf.gz\n"
    assert cmd[2] == str(output_dir / "sample_files.txt")
    assert cmd[-1] == str(output_dir / "merged_sv.vcf")


def test_cutesv_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cutesv"]
    assert node_info["display_name"] == "cuteSV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Efficient long-read SV caller")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["cuteSV"]
    assert node_info["required_conda_packages"] == ["cute-sv"]
    assert "long-read sv" in node_info["search_aliases"]
    assert "pacbio sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name", "threads"}
    assert set(inputs["optional"]) == {"max_cluster_bias_ins", "min_size", "max_size"}


def test_cutesv_renders_long_read_sv_command() -> None:
    node_class = _node_class("cutesv")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "sample_name": "tumor-01",
        "threads": 16,
        "max_cluster_bias_ins": 750,
        "min_size": 40,
        "max_size": 50000,
        "output": "/tmp/run/cutesv",
    })

    assert cmd == [
        "cuteSV",
        "--threads",
        "16",
        "--genome",
        "GRCh38.fa",
        "--sample",
        "tumor-01",
        "--max_cluster_bias_INS",
        "750",
        "--min_size",
        "40",
        "--max_size",
        "50000",
        "sample.sorted.bam",
        "/tmp/run/cutesv/sv_vcf.vcf",
        "/tmp/run/cutesv",
    ]


def test_cutesv_plans_vcf_output() -> None:
    node_class = _node_class("cutesv")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/cutesv/sv_vcf.vcf"]


def test_svim_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["svim"]
    assert node_info["display_name"] == "SVIM SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Long-read SV caller")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["svim"]
    assert node_info["required_conda_packages"] == ["svim"]
    assert "long-read sv" in node_info["search_aliases"]
    assert "nanopore sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name"}
    assert set(inputs["optional"]) == {
        "min_sv_size",
        "max_sv_size",
        "sequence_alleles",
        "symbolic_alleles",
    }


def test_svim_renders_long_read_sv_command() -> None:
    node_class = _node_class("svim")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "sample_name": "tumor-01",
        "min_sv_size": 75,
        "max_sv_size": 250000,
        "sequence_alleles": True,
        "symbolic_alleles": True,
        "output": "/tmp/run/svim",
    })

    assert cmd == [
        "svim",
        "alignment",
        "--sample",
        "tumor-01",
        "--min_sv_size",
        "75",
        "--max_sv_size",
        "250000",
        "--sequence_alleles",
        "--symbolic_alleles",
        "--interspersed_duplications_as_insertions",
        "--tandem_duplications_as_insertions",
        "/tmp/run/svim",
        "sample.sorted.bam",
        "GRCh38.fa",
    ]


def test_svim_plans_vcf_output() -> None:
    node_class = _node_class("svim")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/svim/sv_vcf.vcf"]


def test_smoove_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["smoove"]
    assert node_info["display_name"] == "Smoove SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Automated SV calling")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["genotyped_sv"]
    assert node_info["required_executables"] == ["smoove"]
    assert node_info["required_conda_packages"] == ["smoove", "lumpy-sv", "svtyper"]
    assert "lumpy" in node_info["search_aliases"]
    assert "genotyped sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name", "threads"}
    assert set(inputs["optional"]) == {"exclude", "genotype"}


def test_smoove_renders_structural_variant_command() -> None:
    node_class = _node_class("smoove")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "sample_name": "tumor-01",
        "threads": 12,
        "exclude": "exclude.bed",
        "genotype": True,
        "output": "/tmp/run/smoove",
    })

    assert cmd == [
        "smoove",
        "call",
        "--name",
        "tumor-01",
        "--fasta",
        "GRCh38.fa",
        "-p",
        "12",
        "--outdir",
        "/tmp/run/smoove",
        "--genotype",
        "--exclude",
        "exclude.bed",
        "sample.sorted.bam",
    ]


def test_smoove_plans_genotyped_vcf_output() -> None:
    node_class = _node_class("smoove")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/smoove/genotyped_sv.vcf.gz"]


def test_delly_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["delly"]
    assert node_info["display_name"] == "DELLY SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Paired-end + split-read SV caller")
    assert node_info["output"] == ["BCF"]
    assert node_info["output_name"] == ["sv_calls"]
    assert node_info["required_executables"] == ["delly"]
    assert node_info["required_conda_packages"] == ["delly"]
    assert "somatic sv" in node_info["search_aliases"]
    assert "long-read sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "mode"}
    assert set(inputs["optional"]) == {"exclude_regions", "map_qual"}


def test_delly_renders_short_read_structural_variant_command() -> None:
    node_class = _node_class("delly")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "reference": "GRCh38.fa",
        "mode": "call",
        "exclude_regions": "exclude.bed",
        "map_qual": 20,
        "output": "/tmp/run/delly",
    })

    assert cmd == [
        "delly",
        "call",
        "-g",
        "GRCh38.fa",
        "-o",
        "/tmp/run/delly/sv_calls.bcf",
        "-x",
        "exclude.bed",
        "-q",
        "20",
        "tumor.sorted.bam",
    ]


def test_delly_renders_long_read_mode_command() -> None:
    node_class = _node_class("delly")

    cmd = node_class.render_command({
        "bam": "ont.sorted.bam",
        "reference": "GRCh38.fa",
        "mode": "lr",
        "output": "/tmp/run/delly",
    })

    assert cmd == [
        "delly",
        "lr",
        "-g",
        "GRCh38.fa",
        "-o",
        "/tmp/run/delly/sv_calls.bcf",
        "ont.sorted.bam",
    ]


def test_delly_plans_bcf_output() -> None:
    node_class = _node_class("delly")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/delly/sv_calls.bcf"]


def test_manta_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["manta"]
    assert node_info["display_name"] == "Manta SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Call structural variants")
    assert node_info["output"] == ["VCF_GZ", "VCF_GZ"]
    assert node_info["output_name"] == ["candidate_sv", "diploid_sv"]
    assert node_info["required_executables"] == ["configManta.py", "runWorkflow.py"]
    assert node_info["required_conda_packages"] == ["manta"]
    assert "germline sv" in node_info["search_aliases"]
    assert "somatic sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "threads"}
    assert set(inputs["optional"]) == {"normal_bam", "exome", "rna"}


def test_manta_renders_configure_and_run_workflow_command() -> None:
    node_class = _node_class("manta")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "reference": "GRCh38.fa",
        "threads": 16,
        "normal_bam": "normal.sorted.bam",
        "exome": True,
        "rna": True,
        "output": "/tmp/run/manta",
    })

    assert cmd == [
        "configManta.py",
        "--bam",
        "tumor.sorted.bam",
        "--referenceFasta",
        "GRCh38.fa",
        "--runDir",
        "/tmp/run/manta",
        "--normalBam",
        "normal.sorted.bam",
        "--exome",
        "--rna",
        "&&",
        "/tmp/run/manta/runWorkflow.py",
        "-m",
        "local",
        "-j",
        "16",
    ]


def test_manta_plans_nested_variant_outputs() -> None:
    node_class = _node_class("manta")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/manta/results/variants/candidateSV.vcf.gz",
        "/tmp/run/manta/results/variants/diploidSV.vcf.gz",
    ]
