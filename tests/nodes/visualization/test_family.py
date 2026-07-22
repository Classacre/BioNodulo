from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import visualization
from bionodulo.nodes.builtin.visualization_family import (
    BarChartNode,
    CircosPlotNode,
    CoveragePlotNode,
    ForestPlotNode,
    HeatmapNode,
    IGVSnapshotNode,
    LineChartNode,
    MAPlotNode,
    ManhattanPlotNode,
    PhylogeneticTreeViewerCompatibilityNode,
    PhylogeneticTreeViewerNode,
    ScatterPlotNode,
    VCFStatsChartNode,
    VolcanoPlotNode,
)
from bionodulo.nodes.builtin.visualization_family import adapter


ROOT = Path(__file__).resolve().parents[3]
FOCUSED_OWNERS = {
    "bar_chart": ("bar_chart", BarChartNode),
    "circos_plot": ("circos_plot", CircosPlotNode),
    "coverage_plot": ("coverage_plot", CoveragePlotNode),
    "forest_plot": ("forest_plot", ForestPlotNode),
    "heatmap": ("heatmap", HeatmapNode),
    "igv_snapshot": ("igv_snapshot", IGVSnapshotNode),
    "line_chart": ("line_chart", LineChartNode),
    "ma_plot": ("ma_plot", MAPlotNode),
    "manhattan_plot": ("manhattan_plot", ManhattanPlotNode),
    "phylo_tree_viewer": ("phylo_tree_viewer", PhylogeneticTreeViewerNode),
    "phylogenetic_tree_viewer": (
        "phylogenetic_tree_viewer",
        PhylogeneticTreeViewerCompatibilityNode,
    ),
    "scatter_plot": ("scatter_plot", ScatterPlotNode),
    "vcf_stats_chart": ("vcf_stats_chart", VCFStatsChartNode),
    "volcano_plot": ("volcano_plot", VolcanoPlotNode),
}


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        candidate
        for _name, candidate in inspect.getmembers(module, inspect.isclass)
        if issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and candidate.__module__ == module.__name__
        and candidate.NODE_ID
    ]


def test_each_stable_id_has_one_focused_owner() -> None:
    assert _owned_node_classes(adapter) == []

    for node_id, (module_name, expected_class) in FOCUSED_OWNERS.items():
        module = importlib.import_module(f"bionodulo.nodes.builtin.visualization_family.{module_name}")
        assert _owned_node_classes(module) == [expected_class]
        assert expected_class.NODE_ID == node_id
        assert getattr(visualization, expected_class.__name__) is expected_class

    assert issubclass(
        PhylogeneticTreeViewerCompatibilityNode,
        PhylogeneticTreeViewerNode,
    )


def test_visualization_authorities_and_backend_semantics_are_pinned() -> None:
    for _module_name, node_class in FOCUSED_OWNERS.values():
        assert node_class.GIT_COMMIT == "a32a426c03ce4c925bf7dcdbd2cf08fbdedd55e9"
        assert node_class.INTERACTIVE_GIT_COMMIT == "22efc2fb76f4c890a2c33448e6f1485ecab77f26"
        assert node_class.INTERACTIVE_RENDERER == "Plotly.js 2.35.2 loaded from cdn.plot.ly"
        assert node_class.REQUIRED_EXECUTABLES == []
        expected_packages = ["pysam", "pybigwig"] if node_class is CoveragePlotNode else []
        assert node_class.REQUIRED_CONDA_PACKAGES == expected_packages
        assert node_class.GIT_COMMIT in node_class.SOURCE_URL

    assert CoveragePlotNode.OPTIONAL_PYSAM_GIT_COMMIT == "cefbaa9079b0b2ad65dd8d60a532bc3eb31389ee"
    assert CoveragePlotNode.OPTIONAL_PYBIGWIG_GIT_COMMIT == "7300b0a4599e7f72085c3c27c19b375e3a2c2cc0"
    assert CoveragePlotNode.CONDA_PACKAGE_CONSTRAINTS == {"pysam": "0.23.3", "pybigwig": "0.3.24"}
    assert CoveragePlotNode.PACKAGE_CONSTRAINTS == ("pysam==0.23.3", "pybigwig==0.3.24")
    assert PACKAGE_MIN_VERSIONS["pysam"] == "0.23.3"
    assert PACKAGE_MIN_VERSIONS["pybigwig"] == "0.3.24"
    assert VCFStatsChartNode.FORMAT_SPEC_GIT_COMMIT == "da617203a9527537746e200abda2885bec3a822c"
    assert "not invoked" in CircosPlotNode.BACKEND_SEMANTICS
    assert "not launched" in IGVSnapshotNode.BACKEND_SEMANTICS


@pytest.mark.parametrize(
    ("node_class", "expected_names"),
    [
        (BarChartNode, ("bar_chart.svg",)),
        (CircosPlotNode, ("circos_plot.svg",)),
        (CoveragePlotNode, ("coverage_plot.svg",)),
        (ForestPlotNode, ("forest_plot.svg",)),
        (HeatmapNode, ("heatmap.svg",)),
        (IGVSnapshotNode, ("igv_snapshot.svg",)),
        (LineChartNode, ("line_chart.svg",)),
        (MAPlotNode, ("ma_plot.svg",)),
        (ManhattanPlotNode, ("manhattan_plot.svg",)),
        (PhylogeneticTreeViewerNode, ("phylo_tree.svg",)),
        (PhylogeneticTreeViewerCompatibilityNode, ("phylo_tree.svg",)),
        (ScatterPlotNode, ("scatter_plot.svg",)),
        (VCFStatsChartNode, ("vcf_stats.svg", "vcf_stats.json")),
        (VolcanoPlotNode, ("volcano_plot.svg",)),
    ],
)
def test_output_planning_matches_runtime_filenames(
    node_class: type[BaseNode],
    expected_names: tuple[str, ...],
) -> None:
    outputs = node_class.PLAN_OUTPUTS({"format": "svg"}, Path("/tmp/visualization-plan"))

    assert tuple(path.name for path in outputs) == expected_names
    assert all(path.parent.name == node_class.NODE_ID for path in outputs)


@pytest.mark.parametrize(
    ("node_class", "inputs"),
    [
        (BarChartNode, {"table": "table.tsv", "width": 0}),
        (CircosPlotNode, {"chromosome_sizes": "chrom.tsv", "outer_gap": 21}),
        (CoveragePlotNode, {"alignment": "depth.tsv", "region": "chr1:1-10", "window_size": 0}),
        (ForestPlotNode, {"table": "forest.tsv", "dpi": 29}),
        (HeatmapNode, {"matrix": "matrix.tsv", "scale": "gene"}),
        (IGVSnapshotNode, {"region": "chr1:1-10", "track_height": 0}),
        (LineChartNode, {"table": "line.tsv", "marker": "triangle"}),
        (MAPlotNode, {"results_table": "de.tsv", "pvalue_threshold": 1.1}),
        (ManhattanPlotNode, {"results_table": "gwas.tsv", "point_size": 0}),
        (PhylogeneticTreeViewerNode, {"tree_file": "tree.nwk", "branch_width": 0.4}),
        (PhylogeneticTreeViewerCompatibilityNode, {"tree_file": "tree.nwk", "tip_label_size": 25}),
        (ScatterPlotNode, {"table": "scatter.tsv", "alpha": 0.01}),
        (VCFStatsChartNode, {"vcf": "variants.vcf", "quality_bins": 201}),
        (VolcanoPlotNode, {"results_table": "de.tsv", "pvalue_threshold": 1.1}),
    ],
)
def test_declared_modes_and_numeric_bounds_fail_closed(
    node_class: type[BaseNode],
    inputs: dict[str, Any],
) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is not True


def _workflow(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _has_edge(
    workflow: dict[str, Any],
    source_node: str,
    source_output: str,
    target_node: str,
    target_input: str,
) -> bool:
    return any(
        edge.get("from") == {"node": source_node, "output": source_output}
        and edge.get("to") == {"node": target_node, "input": target_input}
        for edge in workflow["edges"]
    )


def test_official_templates_keep_visualization_inputs_explicit() -> None:
    variant = _workflow("variant_calling_pipeline.json")
    phylogeny = _workflow("phylogenetics_pipeline.json")
    differential_expression = _workflow("deseq2_differential_expression.json")

    assert _has_edge(variant, "filter_001", "filtered_vcf", "vcf_stats_001", "vcf")
    assert _has_edge(variant, "index_001", "indexed_bam", "coverage_plot_001", "alignment")
    assert _has_edge(variant, "index_001", "bai", "coverage_plot_001", "alignment_index")
    assert _has_edge(phylogeny, "iqtree_001", "tree", "tree_viewer_001", "tree_file")
    assert _has_edge(differential_expression, "deseq2_001", "results_csv", "volcano_001", "results_table")
    assert _has_edge(differential_expression, "deseq2_001", "results_csv", "ma_plot_001", "results_table")
    assert _has_edge(differential_expression, "deseq2_001", "pca_scores_csv", "pca_plot_001", "table")
