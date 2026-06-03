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


def test_mageck_count_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mageck_count"]
    assert node_info["display_name"] == "MAGeCK Count"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Count sgRNA reads")
    assert node_info["output"] == ["TSV", "TSV"]
    assert node_info["output_name"] == ["count_table", "normalized_counts"]
    assert node_info["required_executables"] == ["mageck"]
    assert node_info["required_conda_packages"] == ["mageck"]
    assert "crispr screen" in node_info["search_aliases"]
    assert "sgrna" in node_info["search_aliases"]
    assert "pooled screen" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"library_file", "fastq_files", "output_prefix"}
    assert set(inputs["optional"]) == {"sample_labels", "day0_label"}
    assert _node_class("mageck_count").INPUT_TYPES()["required"]["fastq_files"][0] == "FASTQ_LIST"


def test_mageck_count_renders_fastq_count_command_with_labels() -> None:
    node_class = _node_class("mageck_count")

    cmd = node_class.render_command({
        "library_file": "library.tsv",
        "fastq_files": ["control.fastq.gz", "treated.fastq.gz"],
        "output_prefix": "screen",
        "sample_labels": "control,treated",
        "day0_label": "control",
        "output": "/tmp/run/mageck_count",
    })

    assert cmd == [
        "mageck",
        "count",
        "-l",
        "library.tsv",
        "-n",
        "/tmp/run/mageck_count/screen",
        "--fastq",
        "control.fastq.gz",
        "treated.fastq.gz",
        "--sample-label",
        "control,treated",
        "--day0-label",
        "control",
    ]


def test_mageck_count_omits_empty_optional_flags_and_accepts_single_fastq() -> None:
    node_class = _node_class("mageck_count")

    cmd = node_class.render_command({
        "library_file": "library.tsv",
        "fastq_files": "control.fastq.gz",
        "output_prefix": "screen",
        "sample_labels": "",
        "day0_label": "",
        "output": "/tmp/run/mageck_count",
    })

    assert "--sample-label" not in cmd
    assert "--day0-label" not in cmd
    assert cmd == [
        "mageck",
        "count",
        "-l",
        "library.tsv",
        "-n",
        "/tmp/run/mageck_count/screen",
        "--fastq",
        "control.fastq.gz",
    ]


def test_mageck_count_plans_outputs() -> None:
    node_class = _node_class("mageck_count")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "screen"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/mageck_count/screen.count.txt",
        "/tmp/run/mageck_count/screen.count_normalized.txt",
    ]


def test_mageck_test_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mageck_test"]
    assert node_info["display_name"] == "MAGeCK Test"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Identify essential genes")
    assert node_info["output"] == ["TSV", "TSV"]
    assert node_info["output_name"] == ["gene_summary", "sgrna_summary"]
    assert node_info["required_executables"] == ["mageck"]
    assert node_info["required_conda_packages"] == ["mageck"]
    assert "essential genes" in node_info["search_aliases"]
    assert "gene ranking" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"count_table", "treatment_labels", "control_labels", "output_prefix"}
    assert set(inputs["optional"]) == {"norm_method", "adjust_method", "sort_criteria"}


def test_mageck_test_renders_ranking_command_with_analysis_options() -> None:
    node_class = _node_class("mageck_test")

    cmd = node_class.render_command({
        "count_table": "screen.count.txt",
        "treatment_labels": "treated_a,treated_b",
        "control_labels": "control_a,control_b",
        "output_prefix": "screen_test",
        "norm_method": "median",
        "adjust_method": "fdr",
        "sort_criteria": "neg",
        "output": "/tmp/run/mageck_test",
    })

    assert cmd == [
        "mageck",
        "test",
        "-k",
        "screen.count.txt",
        "-t",
        "treated_a,treated_b",
        "-c",
        "control_a,control_b",
        "-n",
        "/tmp/run/mageck_test/screen_test",
        "--norm-method",
        "median",
        "--adjust-method",
        "fdr",
        "--sort-criteria",
        "neg",
    ]


def test_mageck_test_omits_empty_optional_flags() -> None:
    node_class = _node_class("mageck_test")

    cmd = node_class.render_command({
        "count_table": "screen.count.txt",
        "treatment_labels": "treated",
        "control_labels": "control",
        "output_prefix": "screen_test",
        "norm_method": "",
        "adjust_method": "",
        "sort_criteria": "",
        "output": "/tmp/run/mageck_test",
    })

    assert "--norm-method" not in cmd
    assert "--adjust-method" not in cmd
    assert "--sort-criteria" not in cmd
    assert cmd == [
        "mageck",
        "test",
        "-k",
        "screen.count.txt",
        "-t",
        "treated",
        "-c",
        "control",
        "-n",
        "/tmp/run/mageck_test/screen_test",
    ]


def test_mageck_test_plans_outputs() -> None:
    node_class = _node_class("mageck_test")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "screen_test"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/mageck_test/screen_test.gene_summary.txt",
        "/tmp/run/mageck_test/screen_test.sgrna_summary.txt",
    ]


def test_mageck_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["mageck"] == "mageck"
    assert PACKAGE_MIN_VERSIONS["mageck"] == ">=0.5.9"
