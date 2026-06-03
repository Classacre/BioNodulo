from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_crispresso2_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["crispresso2"]
    assert node_info["display_name"] == "CRISPRESSO2"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Analyze CRISPR editing")
    assert node_info["output"] == ["HTML_REPORT", "DIRECTORY"]
    assert node_info["output_name"] == ["report", "results_dir"]
    assert node_info["required_executables"] == ["CRISPResso"]
    assert node_info["required_conda_packages"] == ["crispresso2"]
    assert "crispresso" in node_info["search_aliases"]
    assert "crispr" in node_info["search_aliases"]
    assert "editing analysis" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"r1", "amplicon_seq", "name"}
    assert set(inputs["optional"]) == {"r2", "guide_seq", "quant_window_center", "quant_window_size"}


def test_crispresso2_renders_paired_end_command_with_quantification_options() -> None:
    node_class = _node_class("crispresso2")

    cmd = node_class.render_command({
        "r1": "sample_R1.fastq.gz",
        "r2": "sample_R2.fastq.gz",
        "amplicon_seq": "ACGTACGTACGT",
        "name": "edited_locus",
        "guide_seq": "GATTACAGATTACAGATTAC",
        "quant_window_center": -3,
        "quant_window_size": 5,
        "output": "/tmp/run/crispresso2",
    })

    assert cmd == [
        "CRISPResso",
        "-r1",
        "sample_R1.fastq.gz",
        "-a",
        "ACGTACGTACGT",
        "-o",
        "/tmp/run/crispresso2",
        "--name",
        "edited_locus",
        "-r2",
        "sample_R2.fastq.gz",
        "-g",
        "GATTACAGATTACAGATTAC",
        "-qc",
        "-3",
        "-w",
        "5",
    ]


def test_crispresso2_omits_empty_optional_flags() -> None:
    node_class = _node_class("crispresso2")

    cmd = node_class.render_command({
        "r1": "sample_R1.fastq.gz",
        "amplicon_seq": "ACGTACGTACGT",
        "name": "crispresso_run",
        "r2": "",
        "guide_seq": "",
        "quant_window_center": 0,
        "quant_window_size": 0,
        "output": "/tmp/run/crispresso2",
    })

    assert "-r2" not in cmd
    assert "-g" not in cmd
    assert "-qc" not in cmd
    assert "-w" not in cmd
    assert cmd == [
        "CRISPResso",
        "-r1",
        "sample_R1.fastq.gz",
        "-a",
        "ACGTACGTACGT",
        "-o",
        "/tmp/run/crispresso2",
        "--name",
        "crispresso_run",
    ]


def test_crispresso2_plans_outputs() -> None:
    node_class = _node_class("crispresso2")

    outputs = node_class.PLAN_OUTPUTS({"name": "edited_locus"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/crispresso2/CRISPResso_on_edited_locus.html",
        "/tmp/run/crispresso2/CRISPResso_on_edited_locus",
    ]


def test_crispresso2_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["CRISPResso"] == "crispresso2"
    assert PACKAGE_MIN_VERSIONS["crispresso2"] == ">=2.3.2"
