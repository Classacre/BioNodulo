from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_volcano_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("volcano_plot")
    assert node_class is not None

    info = registry.object_info()

    assert info["volcano_plot"]["display_name"] == "Volcano Plot"
    assert info["volcano_plot"]["category"] == "visualization"
    assert info["volcano_plot"]["output_name"] == ["volcano_image"]
    assert info["volcano_plot"]["output"] == ["IMAGE"]
    assert info["volcano_plot"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_ma_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("ma_plot")
    assert node_class is not None

    info = registry.object_info()

    assert info["ma_plot"]["display_name"] == "MA Plot"
    assert info["ma_plot"]["category"] == "visualization"
    assert info["ma_plot"]["output_name"] == ["ma_image"]
    assert info["ma_plot"]["output"] == ["IMAGE"]
    assert info["ma_plot"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_scatter_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("scatter_plot")
    assert node_class is not None

    info = registry.object_info()

    assert info["scatter_plot"]["display_name"] == "Scatter Plot"
    assert info["scatter_plot"]["category"] == "visualization"
    assert info["scatter_plot"]["output_name"] == ["plot_image"]
    assert info["scatter_plot"]["output"] == ["IMAGE"]
    assert info["scatter_plot"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_bar_chart_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("bar_chart")
    assert node_class is not None

    info = registry.object_info()

    assert info["bar_chart"]["display_name"] == "Bar Chart"
    assert info["bar_chart"]["category"] == "visualization"
    assert info["bar_chart"]["output_name"] == ["chart_image"]
    assert info["bar_chart"]["output"] == ["IMAGE"]
    assert info["bar_chart"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_line_chart_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("line_chart")
    assert node_class is not None

    info = registry.object_info()

    assert info["line_chart"]["display_name"] == "Line Chart"
    assert info["line_chart"]["category"] == "visualization"
    assert info["line_chart"]["output_name"] == ["chart_image"]
    assert info["line_chart"]["output"] == ["IMAGE"]
    assert info["line_chart"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_heatmap_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("heatmap")
    assert node_class is not None

    info = registry.object_info()

    assert info["heatmap"]["display_name"] == "Heatmap"
    assert info["heatmap"]["category"] == "visualization"
    assert info["heatmap"]["output_name"] == ["heatmap_image"]
    assert info["heatmap"]["output"] == ["IMAGE"]
    assert info["heatmap"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_manhattan_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("manhattan_plot")
    assert node_class is not None

    info = registry.object_info()

    assert info["manhattan_plot"]["display_name"] == "Manhattan Plot"
    assert info["manhattan_plot"]["category"] == "visualization"
    assert info["manhattan_plot"]["output_name"] == ["manhattan_image"]
    assert info["manhattan_plot"]["output"] == ["IMAGE"]
    assert info["manhattan_plot"]["output_node"] is True
    assert node_class.metadata()["input_types"]["optional"]["format"][0] == ["png", "svg", "html"]


def test_forest_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["forest_plot"]["display_name"] == "Forest Plot"
    assert info["forest_plot"]["category"] == "visualization"
    assert info["forest_plot"]["output_name"] == ["forest_image"]
    assert info["forest_plot"]["output"] == ["IMAGE"]
    assert info["forest_plot"]["output_node"] is True


def test_coverage_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["coverage_plot"]["display_name"] == "Coverage Plot"
    assert info["coverage_plot"]["category"] == "visualization"
    assert info["coverage_plot"]["output_name"] == ["coverage_image"]
    assert info["coverage_plot"]["output"] == ["IMAGE"]
    assert info["coverage_plot"]["output_node"] is True


def test_phylogenetic_tree_viewer_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["phylo_tree_viewer"]["display_name"] == "Phylogenetic Tree Viewer"
    assert info["phylo_tree_viewer"]["category"] == "visualization"
    assert info["phylo_tree_viewer"]["output_name"] == ["tree_image"]
    assert info["phylo_tree_viewer"]["output"] == ["IMAGE"]
    assert info["phylo_tree_viewer"]["output_node"] is True


def test_vcf_stats_chart_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["vcf_stats_chart"]["display_name"] == "VCF Stats Chart"
    assert info["vcf_stats_chart"]["category"] == "visualization"
    assert info["vcf_stats_chart"]["output_name"] == ["stats_image", "stats_json"]
    assert info["vcf_stats_chart"]["output"] == ["IMAGE", "JSON"]
    assert info["vcf_stats_chart"]["output_node"] is True


def test_circos_plot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["circos_plot"]["display_name"] == "Circos Plot"
    assert info["circos_plot"]["category"] == "visualization"
    assert info["circos_plot"]["output_name"] == ["circos_image"]
    assert info["circos_plot"]["output"] == ["IMAGE"]
    assert info["circos_plot"]["output_node"] is True


def test_igv_snapshot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["igv_snapshot"]["display_name"] == "IGV Snapshot"
    assert info["igv_snapshot"]["category"] == "visualization"
    assert info["igv_snapshot"]["output_name"] == ["snapshot_image"]
    assert info["igv_snapshot"]["output"] == ["IMAGE"]
    assert info["igv_snapshot"]["output_node"] is True


@pytest.mark.asyncio
async def test_volcano_plot_writes_svg_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("volcano_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text(
        "gene\tlog2FoldChange\tpadj\n"
        "TP53\t2.5\t0.0001\n"
        "BRCA1\t-2.0\t0.001\n"
        "ACTB\t0.1\t0.8\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        results_table=str(table),
        logfc_column="log2FoldChange",
        pvalue_column="padj",
        gene_column="gene",
        logfc_threshold=1.0,
        pvalue_threshold=0.05,
        title="Treatment vs Control",
        label_top_n=2,
        format="svg",
        width=8,
        height=6,
        context=context,
    )

    svg_path = Path(result["outputs"]["volcano_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "volcano_plot.svg"
    assert "<svg" in svg
    assert "Treatment vs Control" in svg
    assert 'data-regulation="Up"' in svg
    assert 'data-regulation="Down"' in svg
    assert 'data-regulation="NS"' in svg
    assert "TP53" in svg
    assert "BRCA1" in svg
    assert previews == [(str(svg_path), "Volcano Plot")]


@pytest.mark.asyncio
async def test_volcano_plot_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("volcano_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text(
        "gene\tlog2FoldChange\tpadj\n"
        "TP53\t2.5\t0.0001\n"
        "BRCA1\t-2.0\t0.001\n"
        "ACTB\t0.1\t0.8\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        results_table=str(table),
        logfc_column="log2FoldChange",
        pvalue_column="padj",
        gene_column="gene",
        logfc_threshold=1.0,
        pvalue_threshold=0.05,
        title="Treatment vs Control",
        label_top_n=2,
        format="html",
        width=8,
        height=6,
        context=context,
    )

    html_path = Path(result["outputs"]["volcano_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "volcano_plot.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "Treatment vs Control" in document
    assert '"type": "scatter"' in document
    assert '"name": "Up"' in document
    assert '"name": "Down"' in document
    assert '"name": "NS"' in document
    assert '"TP53"' in document
    assert '"BRCA1"' in document
    assert previews == [(str(html_path), "Volcano Plot")]


@pytest.mark.asyncio
async def test_ma_plot_writes_svg_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("ma_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text(
        "gene\tbaseMean\tlog2FoldChange\tpadj\n"
        "TP53\t120\t2.5\t0.0001\n"
        "BRCA1\t55\t-2.0\t0.001\n"
        "ACTB\t400\t0.1\t0.8\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        results_table=str(table),
        mean_column="baseMean",
        logfc_column="log2FoldChange",
        pvalue_column="padj",
        gene_column="gene",
        logfc_threshold=1.0,
        pvalue_threshold=0.05,
        title="MA: Treatment vs Control",
        label_top_n=2,
        format="svg",
        width=8,
        height=6,
        context=context,
    )

    svg_path = Path(result["outputs"]["ma_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "ma_plot.svg"
    assert "<svg" in svg
    assert "MA: Treatment vs Control" in svg
    assert 'data-significant="true"' in svg
    assert 'data-significant="false"' in svg
    assert "TP53" in svg
    assert "BRCA1" in svg
    assert previews == [(str(svg_path), "MA Plot")]


@pytest.mark.asyncio
async def test_ma_plot_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("ma_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text(
        "gene\tbaseMean\tlog2FoldChange\tpadj\n"
        "TP53\t120\t2.5\t0.0001\n"
        "BRCA1\t55\t-2.0\t0.001\n"
        "ACTB\t400\t0.1\t0.8\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        results_table=str(table),
        mean_column="baseMean",
        logfc_column="log2FoldChange",
        pvalue_column="padj",
        gene_column="gene",
        logfc_threshold=1.0,
        pvalue_threshold=0.05,
        title="MA: Treatment vs Control",
        label_top_n=2,
        format="html",
        width=8,
        height=6,
        context=context,
    )

    html_path = Path(result["outputs"]["ma_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "ma_plot.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "MA: Treatment vs Control" in document
    assert '"type": "scatter"' in document
    assert '"name": "Significant"' in document
    assert '"name": "Not significant"' in document
    assert '"TP53"' in document
    assert '"BRCA1"' in document
    assert previews == [(str(html_path), "MA Plot")]


@pytest.mark.asyncio
async def test_scatter_plot_writes_svg_with_groups_regression_and_preview(tmp_path: Path) -> None:
    node_class = _node_class("scatter_plot")
    table = tmp_path / "pca.tsv"
    table.write_text(
        "sample\tPC1\tPC2\tcondition\tvariance\n"
        "S1\t-1.0\t-0.5\tcontrol\t10\n"
        "S2\t-0.4\t0.1\tcontrol\t15\n"
        "S3\t0.5\t0.8\ttreated\t20\n"
        "S4\t1.2\t1.4\ttreated\t25\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        x_column="PC1",
        y_column="PC2",
        color_column="condition",
        size_column="variance",
        title="PCA Samples",
        xlabel="PC1",
        ylabel="PC2",
        regression=True,
        format="svg",
        width=8,
        height=7,
        context=context,
    )

    svg_path = Path(result["outputs"]["plot_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "scatter_plot.svg"
    assert "<svg" in svg
    assert "PCA Samples" in svg
    assert 'data-category="control"' in svg
    assert 'data-category="treated"' in svg
    assert 'class="regression-line"' in svg
    assert previews == [(str(svg_path), "Scatter Plot")]


@pytest.mark.asyncio
async def test_scatter_plot_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("scatter_plot")
    table = tmp_path / "pca.tsv"
    table.write_text(
        "sample\tPC1\tPC2\tcondition\tvariance\n"
        "S1\t-1.0\t-0.5\tcontrol\t10\n"
        "S2\t-0.4\t0.1\tcontrol\t15\n"
        "S3\t0.5\t0.8\ttreated\t20\n"
        "S4\t1.2\t1.4\ttreated\t25\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        x_column="PC1",
        y_column="PC2",
        color_column="condition",
        size_column="variance",
        title="PCA Samples",
        xlabel="PC1",
        ylabel="PC2",
        regression=True,
        format="html",
        width=8,
        height=7,
        context=context,
    )

    html_path = Path(result["outputs"]["plot_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "scatter_plot.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "PCA Samples" in document
    assert '"type": "scatter"' in document
    assert '"control"' in document
    assert '"treated"' in document
    assert '"name": "Regression"' in document
    assert previews == [(str(html_path), "Scatter Plot")]


@pytest.mark.asyncio
async def test_bar_chart_writes_grouped_svg_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("bar_chart")
    table = tmp_path / "read_counts.tsv"
    table.write_text(
        "sample\tread_count\tcondition\n"
        "S1\t120\tcontrol\n"
        "S2\t150\tcontrol\n"
        "S3\t210\ttreated\n"
        "S4\t240\ttreated\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        x_column="sample",
        y_column="read_count",
        group_column="condition",
        title="Read Counts by Sample",
        format="svg",
        width=10,
        height=6,
        context=context,
    )

    svg_path = Path(result["outputs"]["chart_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "bar_chart.svg"
    assert "<svg" in svg
    assert "Read Counts by Sample" in svg
    assert 'data-category="S1"' in svg
    assert 'data-group="control"' in svg
    assert 'data-group="treated"' in svg
    assert "120" in svg
    assert previews == [(str(svg_path), "Bar Chart")]


@pytest.mark.asyncio
async def test_bar_chart_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("bar_chart")
    table = tmp_path / "read_counts.tsv"
    table.write_text(
        "sample\tread_count\tcondition\n"
        "S1\t120\tcontrol\n"
        "S2\t150\tcontrol\n"
        "S3\t210\ttreated\n"
        "S4\t240\ttreated\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        x_column="sample",
        y_column="read_count",
        group_column="condition",
        title="Read Counts by Sample",
        orientation="vertical",
        format="html",
        width=10,
        height=6,
        context=context,
    )

    html_path = Path(result["outputs"]["chart_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "bar_chart.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "Read Counts by Sample" in document
    assert '"type": "bar"' in document
    assert '"name": "control"' in document
    assert '"name": "treated"' in document
    assert '"S1"' in document
    assert "120" in document
    assert previews == [(str(html_path), "Bar Chart")]


@pytest.mark.asyncio
async def test_line_chart_writes_multiseries_svg_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("line_chart")
    table = tmp_path / "expression.tsv"
    table.write_text(
        "timepoint\tgene_A\tgene_B\n"
        "0\t10\t7\n"
        "1\t14\t9\n"
        "2\t18\t15\n"
        "3\t17\t20\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        x_column="timepoint",
        y_columns="gene_A,gene_B",
        title="Expression Over Time",
        xlabel="Hours",
        ylabel="Expression",
        line_style="dashed",
        marker="o",
        show_grid=True,
        format="svg",
        width=10,
        height=6,
        context=context,
    )

    svg_path = Path(result["outputs"]["chart_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "line_chart.svg"
    assert "<svg" in svg
    assert "Expression Over Time" in svg
    assert "Hours" in svg
    assert "Expression" in svg
    assert 'data-series="gene_A"' in svg
    assert 'data-series="gene_B"' in svg
    assert 'class="line-series"' in svg
    assert 'class="line-marker"' in svg
    assert previews == [(str(svg_path), "Line Chart")]


@pytest.mark.asyncio
async def test_line_chart_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("line_chart")
    table = tmp_path / "expression.tsv"
    table.write_text(
        "timepoint\tgene_A\tgene_B\n"
        "0\t10\t7\n"
        "1\t14\t9\n"
        "2\t18\t15\n"
        "3\t17\t20\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        x_column="timepoint",
        y_columns="gene_A,gene_B",
        title="Expression Over Time",
        xlabel="Hours",
        ylabel="Expression",
        line_style="dashed",
        marker="o",
        show_grid=True,
        format="html",
        width=10,
        height=6,
        context=context,
    )

    html_path = Path(result["outputs"]["chart_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "line_chart.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "Expression Over Time" in document
    assert '"type": "scatter"' in document
    assert '"mode": "lines+markers"' in document
    assert '"name": "gene_A"' in document
    assert '"name": "gene_B"' in document
    assert '"dash": "dash"' in document
    assert previews == [(str(html_path), "Line Chart")]


@pytest.mark.asyncio
async def test_heatmap_writes_scaled_svg_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("heatmap")
    matrix = tmp_path / "expression.tsv"
    matrix.write_text(
        "gene\tS1\tS2\tS3\n"
        "TP53\t10\t15\t30\n"
        "BRCA1\t25\t20\t5\n"
        "ACTB\t100\t105\t110\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        matrix=str(matrix),
        colormap="viridis",
        cluster_rows=True,
        cluster_cols=True,
        scale="row",
        title="Expression Heatmap",
        show_rownames=True,
        show_colnames=True,
        format="svg",
        width=9,
        height=7,
        context=context,
    )

    svg_path = Path(result["outputs"]["heatmap_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "heatmap.svg"
    assert "<svg" in svg
    assert "Expression Heatmap" in svg
    assert 'data-row="TP53"' in svg
    assert 'data-column="S1"' in svg
    assert 'class="heatmap-cell"' in svg
    assert "BRCA1" in svg
    assert "S3" in svg
    assert previews == [(str(svg_path), "Heatmap")]


@pytest.mark.asyncio
async def test_heatmap_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("heatmap")
    matrix = tmp_path / "expression.tsv"
    matrix.write_text(
        "gene\tS1\tS2\tS3\n"
        "TP53\t10\t15\t30\n"
        "BRCA1\t25\t20\t5\n"
        "ACTB\t100\t105\t110\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        matrix=str(matrix),
        colormap="viridis",
        cluster_rows=True,
        cluster_cols=True,
        scale="row",
        title="Expression Heatmap",
        show_rownames=True,
        show_colnames=True,
        format="html",
        width=9,
        height=7,
        context=context,
    )

    html_path = Path(result["outputs"]["heatmap_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "heatmap.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "Expression Heatmap" in document
    assert '"type": "heatmap"' in document
    assert '"TP53"' in document
    assert '"BRCA1"' in document
    assert '"S1"' in document
    assert '"colorscale": "Viridis"' in document
    assert previews == [(str(html_path), "Heatmap")]


@pytest.mark.asyncio
async def test_manhattan_plot_writes_svg_with_thresholds_labels_and_preview(tmp_path: Path) -> None:
    node_class = _node_class("manhattan_plot")
    table = tmp_path / "gwas.tsv"
    table.write_text(
        "CHR\tBP\tP\tSNP\n"
        "1\t100\t0.00001\trs1\n"
        "1\t200\t0.2\trs2\n"
        "2\t150\t0.000000001\trs3\n"
        "X\t80\t0.0001\trsX\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        results_table=str(table),
        chr_column="CHR",
        pos_column="BP",
        pvalue_column="P",
        snp_column="SNP",
        significance_threshold=5e-8,
        suggestive_threshold=1e-4,
        title="GWAS Manhattan",
        label_top_n=2,
        format="svg",
        width=12,
        height=6,
        context=context,
    )

    svg_path = Path(result["outputs"]["manhattan_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "manhattan_plot.svg"
    assert "<svg" in svg
    assert "GWAS Manhattan" in svg
    assert 'data-chromosome="1"' in svg
    assert 'data-chromosome="2"' in svg
    assert 'data-significant="true"' in svg
    assert 'class="genome-wide-threshold"' in svg
    assert 'class="suggestive-threshold"' in svg
    assert "rs3" in svg
    assert previews == [(str(svg_path), "Manhattan Plot")]


@pytest.mark.asyncio
async def test_manhattan_plot_writes_interactive_html_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("manhattan_plot")
    table = tmp_path / "gwas.tsv"
    table.write_text(
        "CHR\tBP\tP\tSNP\n"
        "1\t100\t0.00001\trs1\n"
        "1\t200\t0.2\trs2\n"
        "2\t150\t0.000000001\trs3\n"
        "X\t80\t0.0001\trsX\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        results_table=str(table),
        chr_column="CHR",
        pos_column="BP",
        pvalue_column="P",
        snp_column="SNP",
        significance_threshold=5e-8,
        suggestive_threshold=1e-4,
        title="GWAS Manhattan",
        label_top_n=2,
        format="html",
        width=12,
        height=6,
        context=context,
    )

    html_path = Path(result["outputs"]["manhattan_image"])
    document = html_path.read_text(encoding="utf-8")

    assert html_path.name == "manhattan_plot.html"
    assert "<!DOCTYPE html>" in document
    assert "Plotly.newPlot" in document
    assert "GWAS Manhattan" in document
    assert '"type": "scattergl"' in document
    assert '"rs3"' in document
    assert '"rsX"' in document
    assert '"ticktext": ["1", "2", "X"]' in document
    assert '"Genome-wide"' in document
    assert '"Suggestive"' in document
    assert previews == [(str(html_path), "Manhattan Plot")]


@pytest.mark.asyncio
async def test_forest_plot_writes_svg_with_intervals_pooled_row_and_preview(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "meta_analysis.tsv"
    table.write_text(
        "study\tlogFC\tci_lower\tci_upper\tweight\tpooled\n"
        "GSE12345\t0.42\t0.10\t0.74\t26.5\tfalse\n"
        "GSE67890\t0.80\t0.28\t1.32\t21.0\tfalse\n"
        "GSE24680\t-0.12\t-0.50\t0.26\t18.5\tfalse\n"
        "Pooled\t0.39\t0.15\t0.63\t100\ttrue\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        table=str(table),
        label_column="study",
        effect_column="logFC",
        lower_column="ci_lower",
        upper_column="ci_upper",
        weight_column="weight",
        pooled_column="pooled",
        title="Meta-Analysis Forest Plot",
        x_label="Log fold change",
        format="svg",
        width=9,
        height=5,
        context=context,
    )

    svg_path = Path(result["outputs"]["forest_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "forest_plot.svg"
    assert "<svg" in svg
    assert "Meta-Analysis Forest Plot" in svg
    assert "Log fold change" in svg
    assert 'class="forest-ci"' in svg
    assert 'class="forest-effect"' in svg
    assert 'class="forest-pooled"' in svg
    assert 'data-label="GSE12345"' in svg
    assert 'data-effect="0.39"' in svg
    assert "Pooled" in svg
    assert previews == [(str(svg_path), "Forest Plot")]


@pytest.mark.asyncio
async def test_forest_plot_derives_intervals_from_standard_error(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "meta_analysis.tsv"
    table.write_text(
        "study\tlogFC\tSE\n"
        "GSE12345\t0.42\t0.10\n"
        "Pooled\t0.39\t0.05\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(table=str(table), format="svg", context=context)

    svg = Path(result["outputs"]["forest_image"]).read_text(encoding="utf-8")

    assert 'data-label="GSE12345"' in svg
    assert 'data-lower="0.224"' in svg
    assert 'data-upper="0.616"' in svg
    assert 'class="forest-pooled"' in svg


@pytest.mark.asyncio
async def test_forest_plot_uses_standard_error_when_row_interval_is_missing(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "meta_analysis.tsv"
    table.write_text(
        "study\tlogFC\tci_lower\tci_upper\tSE\n"
        "GSE12345\t0.42\t0.10\t0.74\t0.10\n"
        "GSE67890\t0.80\t\t\t0.20\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(table=str(table), format="svg", context=context)

    svg = Path(result["outputs"]["forest_image"]).read_text(encoding="utf-8")

    assert 'data-label="GSE12345"' in svg
    assert 'data-label="GSE67890"' in svg
    assert 'data-lower="0.408"' in svg
    assert 'data-upper="1.192"' in svg


@pytest.mark.asyncio
async def test_coverage_plot_writes_svg_from_bedgraph_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("coverage_plot")
    coverage = tmp_path / "sample.bedgraph"
    coverage.write_text(
        "chr1\t100\t110\t5\n"
        "chr1\t110\t120\t8\n"
        "chr1\t120\t130\t3\n"
        "chr2\t100\t110\t20\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        alignment=str(coverage),
        region="chr1:100-130",
        window_size=10,
        title="Coverage chr1",
        format="svg",
        width=10,
        height=4,
        context=context,
    )

    svg_path = Path(result["outputs"]["coverage_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "coverage_plot.svg"
    assert "<svg" in svg
    assert "Coverage chr1" in svg
    assert 'data-chromosome="chr1"' in svg
    assert 'class="coverage-segment"' in svg
    assert 'data-start="100"' in svg
    assert 'data-end="110"' in svg
    assert previews == [(str(svg_path), "Coverage Plot")]


@pytest.mark.asyncio
async def test_phylogenetic_tree_viewer_writes_svg_with_bootstrap_and_preview(tmp_path: Path) -> None:
    node_class = _node_class("phylo_tree_viewer")
    tree = tmp_path / "tree.nwk"
    tree.write_text("((Sample_A:0.1,Sample_B:0.2)95:0.3,Sample_C:0.4);", encoding="utf-8")
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        tree_file=str(tree),
        layout="rectangular",
        show_bootstrap=True,
        bootstrap_threshold=70.0,
        title="Example Phylogeny",
        format="svg",
        width=8,
        height=5,
        context=context,
    )

    svg_path = Path(result["outputs"]["tree_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "phylo_tree.svg"
    assert "<svg" in svg
    assert "Example Phylogeny" in svg
    assert 'class="tree-branch"' in svg
    assert 'class="tree-tip"' in svg
    assert 'data-tip="Sample_A"' in svg
    assert 'data-bootstrap="95"' in svg
    assert "Sample_C" in svg
    assert previews == [(str(svg_path), "Phylogenetic Tree")]


@pytest.mark.asyncio
async def test_vcf_stats_chart_writes_svg_json_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("vcf_stats_chart")
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t100\trs1\tA\tG\t50\tPASS\tDP=12\n"
        "chr1\t120\trs2\tC\tA\t80\tPASS\tDP=30\n"
        "chr2\t200\trs3\tA\tAT\t60\tPASS\tDP=9\n"
        "chr2\t240\trs4\tAT\tA\t20\tPASS\tDP=4\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        vcf=str(vcf),
        title="Variant QC",
        format="svg",
        quality_bins=4,
        min_quality=0,
        max_quality=100,
        width=10,
        height=7,
        context=context,
    )

    svg_path = Path(result["outputs"]["stats_image"])
    json_path = Path(result["outputs"]["stats_json"])
    svg = svg_path.read_text(encoding="utf-8")
    stats = json.loads(json_path.read_text(encoding="utf-8"))

    assert svg_path.name == "vcf_stats.svg"
    assert json_path.name == "vcf_stats.json"
    assert "<svg" in svg
    assert "Variant QC" in svg
    assert 'class="variant-type-bar"' in svg
    assert 'data-type="SNP"' in svg
    assert 'class="quality-bin"' in svg
    assert 'class="chromosome-count-bar"' in svg
    assert stats["total_variants"] == 4
    assert stats["variant_types"]["SNP"] == 2
    assert stats["variant_types"]["INS"] == 1
    assert stats["variant_types"]["DEL"] == 1
    assert stats["transitions"] == 1
    assert stats["transversions"] == 1
    assert stats["titv_ratio"] == 1.0
    assert stats["chromosome_counts"] == {"chr1": 2, "chr2": 2}
    assert previews == [(str(svg_path), "VCF Stats Chart")]


@pytest.mark.asyncio
async def test_circos_plot_writes_svg_with_tracks_and_preview(tmp_path: Path) -> None:
    node_class = _node_class("circos_plot")
    chrom_sizes = tmp_path / "chrom_sizes.tsv"
    chrom_sizes.write_text("chr1\t0\t1000\nchr2\t0\t800\n", encoding="utf-8")
    genes = tmp_path / "genes.bed"
    genes.write_text("chr1\t100\t220\tGENE1\nchr2\t300\t450\tGENE2\n", encoding="utf-8")
    variants = tmp_path / "variants.vcf"
    variants.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t150\trs1\tA\tG\t50\tPASS\tDP=12\n"
        "chr2\t500\trs2\tC\tT\t40\tPASS\tDP=10\n",
        encoding="utf-8",
    )
    cnv = tmp_path / "cnv.tsv"
    cnv.write_text("chr1\t400\t700\t0.8\nchr2\t100\t260\t-0.6\n", encoding="utf-8")
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        chromosome_sizes=str(chrom_sizes),
        gene_track=str(genes),
        variant_track=str(variants),
        cnv_track=str(cnv),
        title="Genome Overview",
        format="svg",
        width=8,
        height=8,
        context=context,
    )

    svg_path = Path(result["outputs"]["circos_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "circos_plot.svg"
    assert "<svg" in svg
    assert "Genome Overview" in svg
    assert 'class="circos-chromosome"' in svg
    assert 'data-chromosome="chr1"' in svg
    assert 'class="circos-gene"' in svg
    assert 'data-gene="GENE1"' in svg
    assert 'class="circos-variant"' in svg
    assert 'data-id="rs1"' in svg
    assert 'class="circos-cnv"' in svg
    assert previews == [(str(svg_path), "Circos Plot")]


@pytest.mark.asyncio
async def test_igv_snapshot_writes_svg_with_variant_and_annotation_tracks(tmp_path: Path) -> None:
    node_class = _node_class("igv_snapshot")
    variants = tmp_path / "variants.vcf"
    variants.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t150\trs1\tA\tG\t50\tPASS\tDP=12\n"
        "chr1\t350\trs2\tC\tT\t40\tPASS\tDP=10\n",
        encoding="utf-8",
    )
    annotation = tmp_path / "genes.gtf"
    annotation.write_text(
        "chr1\tBioNodulo\tgene\t100\t220\t.\t+\t.\tgene_id \"GENE1\";\n"
        "chr1\tBioNodulo\tgene\t300\t420\t.\t-\t.\tgene_id \"GENE2\";\n",
        encoding="utf-8",
    )
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        region="chr1:50-500",
        variant_track=str(variants),
        annotation_track=str(annotation),
        title="Region Overview",
        format="svg",
        width=10,
        context=context,
    )

    svg_path = Path(result["outputs"]["snapshot_image"])
    svg = svg_path.read_text(encoding="utf-8")

    assert svg_path.name == "igv_snapshot.svg"
    assert "<svg" in svg
    assert "Region Overview" in svg
    assert 'class="igv-track"' in svg
    assert 'data-track="variants"' in svg
    assert 'class="igv-variant"' in svg
    assert 'data-id="rs1"' in svg
    assert 'data-track="annotations"' in svg
    assert 'class="igv-gene"' in svg
    assert 'data-gene="GENE1"' in svg
    assert previews == [(str(svg_path), "IGV Snapshot")]


@pytest.mark.asyncio
async def test_volcano_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("volcano_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text(
        "gene\tlog2FoldChange\tpadj\n"
        "TP53\t2.5\t0.0001\n"
        "BRCA1\t-2.0\t0.001\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        results_table=str(table),
        logfc_column="log2FoldChange",
        pvalue_column="padj",
        context=context,
    )

    png_path = Path(result["outputs"]["volcano_image"])

    assert png_path.name == "volcano_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_ma_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("ma_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text(
        "gene\tbaseMean\tlog2FoldChange\tpadj\n"
        "TP53\t120\t2.5\t0.0001\n"
        "BRCA1\t55\t-2.0\t0.001\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        results_table=str(table),
        mean_column="baseMean",
        logfc_column="log2FoldChange",
        pvalue_column="padj",
        context=context,
    )

    png_path = Path(result["outputs"]["ma_image"])

    assert png_path.name == "ma_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_scatter_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("scatter_plot")
    table = tmp_path / "points.tsv"
    table.write_text(
        "x\ty\n"
        "0\t0\n"
        "1\t1\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        table=str(table),
        x_column="x",
        y_column="y",
        context=context,
    )

    png_path = Path(result["outputs"]["plot_image"])

    assert png_path.name == "scatter_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_bar_chart_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("bar_chart")
    table = tmp_path / "counts.tsv"
    table.write_text(
        "sample\tread_count\n"
        "S1\t120\n"
        "S2\t150\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        table=str(table),
        x_column="sample",
        y_column="read_count",
        context=context,
    )

    png_path = Path(result["outputs"]["chart_image"])

    assert png_path.name == "bar_chart.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_line_chart_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("line_chart")
    table = tmp_path / "expression.tsv"
    table.write_text(
        "timepoint\tgene_A\n"
        "0\t10\n"
        "1\t14\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        table=str(table),
        x_column="timepoint",
        y_columns="gene_A",
        context=context,
    )

    png_path = Path(result["outputs"]["chart_image"])

    assert png_path.name == "line_chart.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_heatmap_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("heatmap")
    matrix = tmp_path / "matrix.tsv"
    matrix.write_text(
        "gene\tS1\tS2\n"
        "TP53\t10\t15\n"
        "BRCA1\t25\t20\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(matrix=str(matrix), context=context)

    png_path = Path(result["outputs"]["heatmap_image"])

    assert png_path.name == "heatmap.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_manhattan_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("manhattan_plot")
    table = tmp_path / "gwas.tsv"
    table.write_text(
        "CHR\tBP\tP\n"
        "1\t100\t0.01\n"
        "2\t200\t0.02\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(results_table=str(table), context=context)

    png_path = Path(result["outputs"]["manhattan_image"])

    assert png_path.name == "manhattan_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_forest_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "meta_analysis.tsv"
    table.write_text(
        "study\tlogFC\tci_lower\tci_upper\n"
        "GSE12345\t0.42\t0.10\t0.74\n"
        "Pooled\t0.39\t0.15\t0.63\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(table=str(table), context=context)

    png_path = Path(result["outputs"]["forest_image"])

    assert png_path.name == "forest_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_coverage_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("coverage_plot")
    coverage = tmp_path / "sample.bedgraph"
    coverage.write_text(
        "chr1\t100\t110\t5\n"
        "chr1\t110\t120\t8\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        alignment=str(coverage),
        region="chr1:100-120",
        context=context,
    )

    png_path = Path(result["outputs"]["coverage_image"])

    assert png_path.name == "coverage_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_phylogenetic_tree_viewer_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("phylo_tree_viewer")
    tree = tmp_path / "tree.nwk"
    tree.write_text("(A:0.1,B:0.2,C:0.3);", encoding="utf-8")
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(tree_file=str(tree), context=context)

    png_path = Path(result["outputs"]["tree_image"])

    assert png_path.name == "phylo_tree.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_vcf_stats_chart_writes_default_png_and_json(tmp_path: Path) -> None:
    node_class = _node_class("vcf_stats_chart")
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t100\t.\tA\tG\t50\tPASS\tDP=12\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(vcf=str(vcf), context=context)

    png_path = Path(result["outputs"]["stats_image"])
    json_path = Path(result["outputs"]["stats_json"])

    assert png_path.name == "vcf_stats.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert json.loads(json_path.read_text(encoding="utf-8"))["total_variants"] == 1


@pytest.mark.asyncio
async def test_circos_plot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("circos_plot")
    chrom_sizes = tmp_path / "chrom_sizes.tsv"
    chrom_sizes.write_text("chr1\t0\t1000\nchr2\t0\t800\n", encoding="utf-8")
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(chromosome_sizes=str(chrom_sizes), context=context)

    png_path = Path(result["outputs"]["circos_image"])

    assert png_path.name == "circos_plot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_igv_snapshot_writes_default_png(tmp_path: Path) -> None:
    node_class = _node_class("igv_snapshot")
    variants = tmp_path / "variants.vcf"
    variants.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t150\trs1\tA\tG\t50\tPASS\tDP=12\n",
        encoding="utf-8",
    )
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(region="chr1:50-250", variant_track=str(variants), context=context)

    png_path = Path(result["outputs"]["snapshot_image"])

    assert png_path.name == "igv_snapshot.png"
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_volcano_plot_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("volcano_plot")
    table = tmp_path / "bad.tsv"
    table.write_text("gene\tfold_change\tq\nTP53\t2.5\t0.001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            results_table=str(table),
            logfc_column="log2FoldChange",
            pvalue_column="padj",
        )


@pytest.mark.asyncio
async def test_volcano_plot_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("volcano_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text("gene\tlog2FoldChange\tpadj\nTP53\t2.5\t0.001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported volcano plot format"):
        await node_class().run(
            results_table=str(table),
            logfc_column="log2FoldChange",
            pvalue_column="padj",
            format="pdf",
        )


@pytest.mark.asyncio
async def test_bar_chart_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("bar_chart")
    table = tmp_path / "bad.tsv"
    table.write_text("sample\tcount\nS1\t120\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            table=str(table),
            x_column="sample",
            y_column="read_count",
        )


@pytest.mark.asyncio
async def test_bar_chart_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("bar_chart")
    table = tmp_path / "counts.tsv"
    table.write_text("sample\tread_count\nS1\t120\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported bar chart format"):
        await node_class().run(
            table=str(table),
            x_column="sample",
            y_column="read_count",
            format="pdf",
        )


@pytest.mark.asyncio
async def test_line_chart_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("line_chart")
    table = tmp_path / "bad.tsv"
    table.write_text("timepoint\tgene_A\n0\t10\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            table=str(table),
            x_column="timepoint",
            y_columns="gene_A,gene_B",
        )


@pytest.mark.asyncio
async def test_line_chart_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("line_chart")
    table = tmp_path / "expression.tsv"
    table.write_text("timepoint\tgene_A\n0\t10\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported line chart format"):
        await node_class().run(
            table=str(table),
            x_column="timepoint",
            y_columns="gene_A",
            format="pdf",
        )


@pytest.mark.asyncio
async def test_heatmap_rejects_non_numeric_matrix(tmp_path: Path) -> None:
    node_class = _node_class("heatmap")
    matrix = tmp_path / "bad.tsv"
    matrix.write_text(
        "gene\tS1\tS2\n"
        "TP53\thigh\tlow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No numeric heatmap cells found"):
        await node_class().run(matrix=str(matrix))


@pytest.mark.asyncio
async def test_heatmap_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("heatmap")
    matrix = tmp_path / "matrix.tsv"
    matrix.write_text("gene\tS1\nTP53\t10\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported heatmap format"):
        await node_class().run(matrix=str(matrix), format="pdf")


@pytest.mark.asyncio
async def test_manhattan_plot_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("manhattan_plot")
    table = tmp_path / "bad.tsv"
    table.write_text("CHR\tP\n1\t0.01\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            results_table=str(table),
            chr_column="CHR",
            pos_column="BP",
            pvalue_column="P",
        )


@pytest.mark.asyncio
async def test_manhattan_plot_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("manhattan_plot")
    table = tmp_path / "gwas.tsv"
    table.write_text("CHR\tBP\tP\n1\t100\t0.01\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported Manhattan plot format"):
        await node_class().run(results_table=str(table), format="pdf")


@pytest.mark.asyncio
async def test_forest_plot_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "bad.tsv"
    table.write_text("study\teffect\tlower\nGSE12345\t0.42\t0.10\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            table=str(table),
            label_column="study",
            effect_column="effect",
            lower_column="lower",
            upper_column="upper",
        )


@pytest.mark.asyncio
async def test_forest_plot_rejects_non_numeric_intervals(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "bad.tsv"
    table.write_text(
        "study\tlogFC\tci_lower\tci_upper\n"
        "GSE12345\thigh\tlow\twide\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No numeric rows found"):
        await node_class().run(table=str(table))


@pytest.mark.asyncio
async def test_forest_plot_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("forest_plot")
    table = tmp_path / "meta_analysis.tsv"
    table.write_text("study\tlogFC\tci_lower\tci_upper\nGSE12345\t0.42\t0.10\t0.74\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported forest plot format"):
        await node_class().run(table=str(table), format="pdf")


@pytest.mark.asyncio
async def test_coverage_plot_rejects_invalid_region(tmp_path: Path) -> None:
    node_class = _node_class("coverage_plot")
    coverage = tmp_path / "sample.bedgraph"
    coverage.write_text("chr1\t100\t110\t5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Region must use"):
        await node_class().run(alignment=str(coverage), region="chr1")


@pytest.mark.asyncio
async def test_coverage_plot_rejects_missing_alignment(tmp_path: Path) -> None:
    node_class = _node_class("coverage_plot")

    with pytest.raises(FileNotFoundError, match="Coverage input not found"):
        await node_class().run(alignment=str(tmp_path / "missing.bedgraph"), region="chr1:1-10")


@pytest.mark.asyncio
async def test_phylogenetic_tree_viewer_rejects_bad_layout(tmp_path: Path) -> None:
    node_class = _node_class("phylo_tree_viewer")
    tree = tmp_path / "tree.nwk"
    tree.write_text("(A:0.1,B:0.2);", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported phylogenetic tree layout"):
        await node_class().run(tree_file=str(tree), layout="diagonal")


@pytest.mark.asyncio
async def test_phylogenetic_tree_viewer_rejects_missing_tree(tmp_path: Path) -> None:
    node_class = _node_class("phylo_tree_viewer")

    with pytest.raises(FileNotFoundError, match="Phylogenetic tree file not found"):
        await node_class().run(tree_file=str(tmp_path / "missing.nwk"))


@pytest.mark.asyncio
async def test_vcf_stats_chart_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("vcf_stats_chart")
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t100\t.\tA\tG\t50\tPASS\tDP=12\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported VCF stats chart format"):
        await node_class().run(vcf=str(vcf), format="pdf")


@pytest.mark.asyncio
async def test_vcf_stats_chart_rejects_missing_vcf(tmp_path: Path) -> None:
    node_class = _node_class("vcf_stats_chart")

    with pytest.raises(FileNotFoundError, match="VCF file not found"):
        await node_class().run(vcf=str(tmp_path / "missing.vcf"))


@pytest.mark.asyncio
async def test_circos_plot_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("circos_plot")
    chrom_sizes = tmp_path / "chrom_sizes.tsv"
    chrom_sizes.write_text("chr1\t0\t1000\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported Circos plot format"):
        await node_class().run(chromosome_sizes=str(chrom_sizes), format="pdf")


@pytest.mark.asyncio
async def test_circos_plot_rejects_missing_chromosome_sizes(tmp_path: Path) -> None:
    node_class = _node_class("circos_plot")

    with pytest.raises(FileNotFoundError, match="Chromosome sizes file not found"):
        await node_class().run(chromosome_sizes=str(tmp_path / "missing.tsv"))


@pytest.mark.asyncio
async def test_igv_snapshot_rejects_no_tracks(tmp_path: Path) -> None:
    node_class = _node_class("igv_snapshot")

    with pytest.raises(ValueError, match="At least one IGV snapshot track"):
        await node_class().run(region="chr1:1-100")


@pytest.mark.asyncio
async def test_igv_snapshot_rejects_invalid_region(tmp_path: Path) -> None:
    node_class = _node_class("igv_snapshot")
    variants = tmp_path / "variants.vcf"
    variants.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t150\trs1\tA\tG\t50\tPASS\tDP=12\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Region must use"):
        await node_class().run(region="chr1", variant_track=str(variants))


@pytest.mark.asyncio
async def test_igv_snapshot_rejects_missing_track(tmp_path: Path) -> None:
    node_class = _node_class("igv_snapshot")

    with pytest.raises(FileNotFoundError, match="IGV track file not found"):
        await node_class().run(region="chr1:1-100", variant_track=str(tmp_path / "missing.vcf"))


@pytest.mark.asyncio
async def test_scatter_plot_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("scatter_plot")
    table = tmp_path / "bad.tsv"
    table.write_text("x\tgroup\n1\tcontrol\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            table=str(table),
            x_column="x",
            y_column="y",
        )


@pytest.mark.asyncio
async def test_scatter_plot_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("scatter_plot")
    table = tmp_path / "points.tsv"
    table.write_text("x\ty\n0\t0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported scatter plot format"):
        await node_class().run(
            table=str(table),
            x_column="x",
            y_column="y",
            format="pdf",
        )


@pytest.mark.asyncio
async def test_ma_plot_rejects_missing_columns(tmp_path: Path) -> None:
    node_class = _node_class("ma_plot")
    table = tmp_path / "bad.tsv"
    table.write_text("gene\tmean\tfold_change\tq\nTP53\t120\t2.5\t0.001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Column\\(s\\) not found"):
        await node_class().run(
            results_table=str(table),
            mean_column="baseMean",
            logfc_column="log2FoldChange",
            pvalue_column="padj",
        )


@pytest.mark.asyncio
async def test_ma_plot_rejects_bad_format(tmp_path: Path) -> None:
    node_class = _node_class("ma_plot")
    table = tmp_path / "deseq2_results.tsv"
    table.write_text("gene\tbaseMean\tlog2FoldChange\tpadj\nTP53\t120\t2.5\t0.001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported MA plot format"):
        await node_class().run(
            results_table=str(table),
            mean_column="baseMean",
            logfc_column="log2FoldChange",
            pvalue_column="padj",
            format="pdf",
        )
