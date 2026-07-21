from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.deeptools_family.bam_coverage import (
    DeepToolsBamCoverageNode,
)
from bionodulo.nodes.builtin.deeptools_family.compute_matrix import (
    DeepToolsComputeMatrixNode,
)
from bionodulo.nodes.builtin.deeptools_family.plot_heatmap import (
    DeepToolsPlotHeatmapNode,
)
from bionodulo.nodes.builtin.deeptools_family.plot_profile import (
    DeepToolsPlotProfileNode,
)


DEEPTOOLS_COMMIT = "ea0f68bb4a1587d713dacb3791861308751ef7d0"
NODES = (
    DeepToolsBamCoverageNode,
    DeepToolsComputeMatrixNode,
    DeepToolsPlotHeatmapNode,
    DeepToolsPlotProfileNode,
)
EXPECTED_EXECUTABLES = {
    "deeptools_bamcoverage": ["bamCoverage"],
    "deeptools_compute_matrix": ["computeMatrix"],
    "deeptools_plot_heatmap": ["plotHeatmap"],
    "deeptools_plot_profile": ["plotProfile"],
}


@pytest.mark.parametrize("node", NODES, ids=lambda node: node.NODE_ID)
def test_deeptools_nodes_record_exact_source_package_and_exit_evidence(node: type) -> None:
    assert node.VERSION == "3.5.6"
    assert node.GIT_TAG == "3.5.6"
    assert node.GIT_COMMIT == DEEPTOOLS_COMMIT
    assert node.SOURCE_REF == f"tag 3.5.6 at {DEEPTOOLS_COMMIT}"
    assert node.PACKAGE_CONSTRAINTS == ("deeptools==3.5.6",)
    assert node.CONDA_PACKAGE_CONSTRAINTS == {"deeptools": "3.5.6"}
    assert node.REQUIRED_EXECUTABLES == EXPECTED_EXECUTABLES[node.NODE_ID]
    assert node.SOURCE_PATHS[-1] == "pyproject.toml"
    assert all(f"/blob/{DEEPTOOLS_COMMIT}/" in url for url in node.SOURCE_URLS)
    assert node.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert "exit 0" in node.EXIT_SEMANTICS
    assert "planned artifact" in node.EXIT_SEMANTICS


def test_bamcoverage_maps_documented_options_and_keeps_bai_out_of_argv(
    tmp_path: Path,
) -> None:
    bam = tmp_path / "sample.bam"
    bam_index = Path(f"{bam}.bai")
    command = DeepToolsBamCoverageNode.render_command(
        {
            "bam": bam,
            "bam_index": bam_index,
            "threads": 6,
            "normalize_using": "RPGC",
            "bin_size": 25,
            "effective_genome_size": 2_913_022_398,
            "center_reads": True,
            "ignore_duplicates": True,
            "extend_reads": 200,
            "blacklist": [tmp_path / "exclude one.bed", tmp_path / "exclude-two.gtf"],
            "output": tmp_path,
        }
    )

    assert command == [
        "bamCoverage",
        "-b",
        str(bam),
        "-o",
        str(tmp_path / "coverage_bw.bw"),
        "-p",
        "6",
        "--binSize",
        "25",
        "--normalizeUsing",
        "RPGC",
        "--effectiveGenomeSize",
        "2913022398",
        "--centerReads",
        "--ignoreDuplicates",
        "--extendReads",
        "200",
        "--blackListFileName",
        str(tmp_path / "exclude one.bed"),
        str(tmp_path / "exclude-two.gtf"),
    ]
    assert str(bam_index) not in command
    assert "deeptools/bamHandler.py" in DeepToolsBamCoverageNode.SOURCE_PATHS


def test_bamcoverage_optional_integer_absence_matches_argparse_defaults() -> None:
    optional = DeepToolsBamCoverageNode.INPUT_TYPES()["optional"]
    inputs = {
        "bam": "sample.bam",
        "bam_index": "sample.bam.bai",
        "threads": 1,
        "normalize_using": "None",
    }

    assert optional["effective_genome_size"][1]["default"] is None
    assert optional["extend_reads"][0] == "STRING"
    assert optional["extend_reads"][1]["default"] == ""
    assert optional["blacklist"][0] == "FILE"
    assert optional["blacklist"][1]["multiple"] is True
    assert DeepToolsBamCoverageNode.VALIDATE_INPUTS(inputs) is True
    assert (
        DeepToolsBamCoverageNode.VALIDATE_INPUTS({**inputs, "effective_genome_size": 0})
        == "effective_genome_size must be a positive integer when supplied"
    )
    assert DeepToolsBamCoverageNode.VALIDATE_INPUTS({**inputs, "extend_reads": 0}) == (
        "extend_reads must be 'auto' or a positive integer when supplied"
    )


def test_bamcoverage_preserves_optional_value_semantics_for_extend_reads(
    tmp_path: Path,
) -> None:
    base = {
        "bam": tmp_path / "sample.bam",
        "bam_index": tmp_path / "sample.bam.bai",
        "threads": 1,
        "normalize_using": "None",
        "output": tmp_path,
    }

    auto_command = DeepToolsBamCoverageNode.render_command({**base, "extend_reads": "auto"})
    fixed_command = DeepToolsBamCoverageNode.render_command({**base, "extend_reads": 175})

    assert auto_command[-1] == "--extendReads"
    assert fixed_command[-2:] == ["--extendReads", "175"]
    assert (
        DeepToolsBamCoverageNode.VALIDATE_INPUTS({**base, "extend_reads": "estimate"})
        == "extend_reads must be 'auto' or a positive integer when supplied"
    )


def test_compute_matrix_expands_multiple_files_and_uses_scale_region_defaults(
    tmp_path: Path,
) -> None:
    command = DeepToolsComputeMatrixNode.render_command(
        {
            "bigwig": ["control signal.bw", "treated.bw"],
            "regions": ["promoters.bed", "genes.gtf"],
            "mode": "scale-regions",
            "threads": 3,
            "output": tmp_path,
        }
    )

    assert command == [
        "computeMatrix",
        "scale-regions",
        "-S",
        "control signal.bw",
        "treated.bw",
        "-R",
        "promoters.bed",
        "genes.gtf",
        "-o",
        str(tmp_path / "matrix.gz"),
        "-p",
        "3",
        "--binSize",
        "10",
        "-b",
        "0",
        "-a",
        "0",
        "--regionBodyLength",
        "1000",
    ]


def test_compute_matrix_ports_match_upstream_nargs_and_conditional_defaults() -> None:
    inputs = DeepToolsComputeMatrixNode.INPUT_TYPES()

    assert inputs["required"]["bigwig"] == (
        "BIGWIG",
        {"multiple": True, "description": "One or more input bigWig signal tracks"},
    )
    assert inputs["required"]["regions"][0] == "FILE"
    assert inputs["required"]["regions"][1]["multiple"] is True
    assert inputs["optional"]["before_region"][1]["default"] is None
    assert inputs["optional"]["after_region"][1]["default"] is None
    assert (
        DeepToolsComputeMatrixNode.VALIDATE_INPUTS(
            {"bigwig": [], "regions": ["genes.bed"], "mode": "reference-point", "threads": 1}
        )
        == "Input 'bigwig' must contain one or more non-empty path-like values"
    )


def test_plot_heatmap_maps_multiple_colormaps_and_optional_kmeans(tmp_path: Path) -> None:
    command = DeepToolsPlotHeatmapNode.render_command(
        {
            "matrix": "matrix.gz",
            "heatmap_height": 30.0,
            "heatmap_width": 5.0,
            "colormap": ["Reds", "Blues"],
            "sort_regions": "keep",
            "kmeans": 4,
            "plot_title": "Signal by region",
            "output": tmp_path,
        }
    )

    assert command == [
        "plotHeatmap",
        "-m",
        "matrix.gz",
        "--outFileName",
        str(tmp_path / "heatmap.png"),
        "--heatmapHeight",
        "30.0",
        "--heatmapWidth",
        "5.0",
        "--colorMap",
        "Reds",
        "Blues",
        "--sortRegions",
        "keep",
        "--kmeans",
        "4",
        "--plotTitle",
        "Signal by region",
    ]
    assert (
        DeepToolsPlotHeatmapNode.VALIDATE_INPUTS({"matrix": "matrix.gz", "kmeans": 0})
        == "kmeans must be a positive integer when supplied"
    )
    assert DeepToolsPlotHeatmapNode.INPUT_TYPES()["optional"]["heatmap_height"][1]["exclusive_min"] == 3.0


def test_plot_profile_rejects_known_broken_none_legend_without_invented_width_cap() -> None:
    assert DeepToolsPlotProfileNode.VALIDATE_INPUTS({"matrix": "matrix.gz", "plot_width": 250.0}) is True
    assert (
        DeepToolsPlotProfileNode.VALIDATE_INPUTS({"matrix": "matrix.gz", "legend_location": "none"})
        == "Unsupported plotProfile legend location: none"
    )
    assert "none" not in DeepToolsPlotProfileNode.INPUT_TYPES()["optional"]["legend_location"][1]["options"]


def test_deeptools_stable_ids_and_native_formats_are_unchanged() -> None:
    assert {node.NODE_ID for node in NODES} == {
        "deeptools_bamcoverage",
        "deeptools_compute_matrix",
        "deeptools_plot_heatmap",
        "deeptools_plot_profile",
    }
    assert [node.OUTPUT_FILENAMES for node in NODES] == [
        ("coverage_bw.bw",),
        ("matrix.gz",),
        ("heatmap.png",),
        ("profile.png",),
    ]
