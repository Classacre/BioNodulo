from __future__ import annotations

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_cnvkit_call_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvkit_call"]
    assert node_info["display_name"] == "CNVkit Call"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Convert segmented CNV ratios")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["cnv_calls"]
    assert node_info["required_executables"] == ["cnvkit.py"]
    assert node_info["required_conda_packages"] == ["cnvkit"]
    assert "copy number" in node_info["search_aliases"]
    assert "cnv call" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"cns_file"}
    assert set(inputs["optional"]) == {"vcf", "sample_sex", "ploidy", "purity", "method"}


def test_cnvkit_call_renders_copy_number_command() -> None:
    node_class = _node_class("cnvkit_call")

    cmd = node_class.render_command({
        "cns_file": "tumor.cns",
        "vcf": "tumor.snvs.vcf.gz",
        "sample_sex": "female",
        "ploidy": 3,
        "purity": 0.72,
        "method": "clonal",
        "output": "/tmp/run/cnvkit_call",
    })

    assert cmd == [
        "cnvkit.py",
        "call",
        "tumor.cns",
        "-o",
        "/tmp/run/cnvkit_call/cnv_calls.vcf",
        "--vcf",
        "tumor.snvs.vcf.gz",
        "--sample-sex",
        "female",
        "--ploidy",
        "3",
        "--purity",
        "0.72",
        "--method",
        "clonal",
    ]


def test_cnvkit_call_omits_empty_optional_flags() -> None:
    node_class = _node_class("cnvkit_call")

    cmd = node_class.render_command({
        "cns_file": "tumor.cns",
        "sample_sex": "",
        "output": "/tmp/run/cnvkit_call",
    })

    assert cmd == [
        "cnvkit.py",
        "call",
        "tumor.cns",
        "-o",
        "/tmp/run/cnvkit_call/cnv_calls.vcf",
    ]


def test_cnvkit_call_plans_vcf_output() -> None:
    node_class = _node_class("cnvkit_call")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/cnvkit_call/cnv_calls.vcf"]


def test_cnvkit_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvkit_plot"]
    assert node_info["display_name"] == "CNVkit Plot"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Generate scatter plots and heatmaps")
    assert node_info["output"] == ["PDF_REPORT", "PDF_REPORT"]
    assert node_info["output_name"] == ["scatter_plot", "heatmap_plot"]
    assert node_info["required_executables"] == ["cnvkit.py"]
    assert node_info["required_conda_packages"] == ["cnvkit"]
    assert "cnv plot" in node_info["search_aliases"]
    assert "heatmap" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"cnr_file", "cns_file"}
    assert set(inputs["optional"]) == {"chromosome", "gene"}


def test_cnvkit_plot_renders_scatter_and_heatmap_commands() -> None:
    node_class = _node_class("cnvkit_plot")

    cmd = node_class.render_command({
        "cnr_file": "tumor.cnr",
        "cns_file": "tumor.cns",
        "chromosome": "chr7",
        "gene": "EGFR",
        "output": "/tmp/run/cnvkit_plot",
    })

    assert cmd == [
        "cnvkit.py",
        "scatter",
        "tumor.cnr",
        "-s",
        "tumor.cns",
        "-o",
        "/tmp/run/cnvkit_plot/scatter_plot.pdf",
        "-c",
        "chr7",
        "-g",
        "EGFR",
        "&&",
        "cnvkit.py",
        "heatmap",
        "tumor.cns",
        "-o",
        "/tmp/run/cnvkit_plot/heatmap_plot.pdf",
        "-c",
        "chr7",
    ]


def test_cnvkit_plot_omits_empty_optional_flags() -> None:
    node_class = _node_class("cnvkit_plot")

    cmd = node_class.render_command({
        "cnr_file": "tumor.cnr",
        "cns_file": "tumor.cns",
        "chromosome": "",
        "gene": "",
        "output": "/tmp/run/cnvkit_plot",
    })

    assert cmd == [
        "cnvkit.py",
        "scatter",
        "tumor.cnr",
        "-s",
        "tumor.cns",
        "-o",
        "/tmp/run/cnvkit_plot/scatter_plot.pdf",
        "&&",
        "cnvkit.py",
        "heatmap",
        "tumor.cns",
        "-o",
        "/tmp/run/cnvkit_plot/heatmap_plot.pdf",
    ]


def test_cnvkit_plot_plans_pdf_outputs() -> None:
    node_class = _node_class("cnvkit_plot")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvkit_plot/scatter_plot.pdf",
        "/tmp/run/cnvkit_plot/heatmap_plot.pdf",
    ]


def test_cnvkit_batch_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvkit_batch"]
    assert node_info["display_name"] == "CNVkit Batch Pipeline"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Complete CNVkit pipeline")
    assert node_info["output"] == ["DIRECTORY", "DIRECTORY"]
    assert node_info["output_name"] == ["cnr_files", "cns_files"]
    assert node_info["required_executables"] == ["cnvkit.py"]
    assert node_info["required_conda_packages"] == ["cnvkit"]
    assert "copy number" in node_info["search_aliases"]
    assert "batch" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"tumor_bams", "reference", "threads"}
    assert set(inputs["optional"]) == {"normal_bams", "targets", "method", "diagram", "scatter"}


def test_cnvkit_batch_renders_complete_batch_command() -> None:
    node_class = _node_class("cnvkit_batch")

    cmd = node_class.render_command({
        "tumor_bams": "tumor.bam",
        "normal_bams": "normal.bam",
        "reference": "hg38.fa",
        "targets": "targets.bed",
        "threads": 8,
        "method": "wgs",
        "diagram": True,
        "scatter": True,
        "output": "/tmp/run/cnvkit_batch",
    })

    assert cmd == [
        "cnvkit.py",
        "batch",
        "tumor.bam",
        "--fasta",
        "hg38.fa",
        "--output-reference",
        "/tmp/run/cnvkit_batch/reference.cnn",
        "--output-dir",
        "/tmp/run/cnvkit_batch",
        "--processes",
        "8",
        "--normal",
        "normal.bam",
        "--targets",
        "targets.bed",
        "--method",
        "wgs",
        "--diagram",
        "--scatter",
    ]


def test_cnvkit_batch_omits_empty_optional_flags() -> None:
    node_class = _node_class("cnvkit_batch")

    cmd = node_class.render_command({
        "tumor_bams": "tumor.bam",
        "reference": "hg38.fa",
        "threads": 4,
        "normal_bams": "",
        "targets": "",
        "method": "",
        "diagram": False,
        "scatter": False,
        "output": "/tmp/run/cnvkit_batch",
    })

    assert cmd == [
        "cnvkit.py",
        "batch",
        "tumor.bam",
        "--fasta",
        "hg38.fa",
        "--output-reference",
        "/tmp/run/cnvkit_batch/reference.cnn",
        "--output-dir",
        "/tmp/run/cnvkit_batch",
        "--processes",
        "4",
    ]


def test_cnvkit_batch_plans_output_directories() -> None:
    node_class = _node_class("cnvkit_batch")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvkit_batch/cnr_files",
        "/tmp/run/cnvkit_batch/cns_files",
    ]


def test_cnvnator_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cnvnator"]
    assert node_info["display_name"] == "CNVnator"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Read-depth based CNV caller")
    assert node_info["output"] == ["FILE", "FILE"]
    assert node_info["output_name"] == ["cnv_calls", "root_file"]
    assert node_info["required_executables"] == ["cnvnator"]
    assert node_info["required_conda_packages"] == ["cnvnator"]
    assert "read depth" in node_info["search_aliases"]
    assert "copy number" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "chrom_dir", "bin_size"}
    assert set(inputs["optional"]) == set()


def test_cnvnator_renders_multistep_command_with_chrom_dir() -> None:
    node_class = _node_class("cnvnator")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "reference": "hg38.fa",
        "chrom_dir": "/refs/chroms",
        "bin_size": 250,
        "output": "/tmp/run/cnvnator",
    })

    assert cmd == [
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-tree",
        "tumor.sorted.bam",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-his",
        "250",
        "-d",
        "/refs/chroms",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-stat",
        "250",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-partition",
        "250",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-call",
        "250",
        ">",
        "/tmp/run/cnvnator/cnv_calls.txt",
    ]


def test_cnvnator_omits_empty_chrom_dir_flag() -> None:
    node_class = _node_class("cnvnator")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "chrom_dir": "",
        "output": "/tmp/run/cnvnator",
    })

    assert "-d" not in cmd
    assert cmd == [
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-tree",
        "tumor.sorted.bam",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-his",
        "100",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-stat",
        "100",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-partition",
        "100",
        "&&",
        "cnvnator",
        "-root",
        "/tmp/run/cnvnator/cnvnator.root",
        "-call",
        "100",
        ">",
        "/tmp/run/cnvnator/cnv_calls.txt",
    ]


def test_cnvnator_plans_call_and_root_outputs() -> None:
    node_class = _node_class("cnvnator")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cnvnator/cnv_calls.out",
        "/tmp/run/cnvnator/root_file.out",
    ]


def test_control_freec_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["control_freec"]
    assert node_info["display_name"] == "Control-FREEC"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("CNV caller with tumor purity")
    assert node_info["output"] == ["FILE", "FILE"]
    assert node_info["output_name"] == ["cnv_profile", "baf_profile"]
    assert node_info["required_executables"] == ["freec"]
    assert node_info["required_conda_packages"] == ["control-freec"]
    assert "freec" in node_info["search_aliases"]
    assert "allelic imbalance" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"tumor_bam", "chrom_lengths", "chrom_dir", "window", "threads"}
    assert set(inputs["optional"]) == {"normal_bam", "ploidy"}


def test_control_freec_writes_config_and_renders_command(tmp_path) -> None:
    node_class = _node_class("control_freec")
    out_dir = tmp_path / "control_freec"

    cmd = node_class.render_command({
        "tumor_bam": "tumor.bam",
        "normal_bam": "normal.bam",
        "chrom_lengths": "hg38.chrom.sizes",
        "chrom_dir": "/refs/chroms",
        "ploidy": 3,
        "window": 100000,
        "threads": 12,
        "output": str(out_dir),
    })

    config_file = out_dir / "freec_config.txt"
    assert cmd == ["freec", "-conf", str(config_file)]
    assert config_file.read_text() == (
        "[general]\n"
        "chrLenFile = hg38.chrom.sizes\n"
        "ploidy = 3\n"
        "window = 100000\n"
        "chrFiles = /refs/chroms\n"
        f"outputDir = {out_dir}\n"
        "maxThreads = 12\n"
        "[sample]\n"
        "mateFile = tumor.bam\n"
        "inputFormat = BAM\n"
        "mateOrientation = FR\n"
        "[control]\n"
        "mateFile = normal.bam\n"
        "inputFormat = BAM\n"
        "mateOrientation = FR\n"
    )


def test_control_freec_omits_control_section_without_normal(tmp_path) -> None:
    node_class = _node_class("control_freec")
    out_dir = tmp_path / "control_freec"

    node_class.render_command({
        "tumor_bam": "tumor.bam",
        "chrom_lengths": "hg38.chrom.sizes",
        "chrom_dir": "/refs/chroms",
        "window": 50000,
        "threads": 4,
        "output": str(out_dir),
    })

    config_text = (out_dir / "freec_config.txt").read_text()
    assert "[control]" not in config_text
    assert "ploidy = 2\n" in config_text
    assert "maxThreads = 4\n" in config_text


def test_control_freec_plans_profile_outputs() -> None:
    node_class = _node_class("control_freec")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/control_freec/cnv_profile.out",
        "/tmp/run/control_freec/baf_profile.out",
    ]
