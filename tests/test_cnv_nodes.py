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
