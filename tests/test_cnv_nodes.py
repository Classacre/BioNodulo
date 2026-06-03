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
