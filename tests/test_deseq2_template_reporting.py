from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_deseq2_template_combines_all_visualizations_in_final_report_preview() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["de_report_001"] == "html_report"
    assert node_types["de_report_preview_001"] == "html_preview"
    assert node_types["pca_plot_001"] == "scatter_plot"
    assert node_types["pathway_gene_sets_001"] == "input_file"
    assert node_types["pathway_enrichment_001"] == "intersect_genes"
    assert node_types["string_enrichment_001"] == "string_db"

    report = _node_by_id(workflow, "de_report_001")
    pca_plot = _node_by_id(workflow, "pca_plot_001")
    pathway_gene_sets = _node_by_id(workflow, "pathway_gene_sets_001")
    pathway_enrichment = _node_by_id(workflow, "pathway_enrichment_001")
    string_enrichment = _node_by_id(workflow, "string_enrichment_001")
    assert report["params"]["title"] == "DESeq2 Differential Expression Report"
    assert report["params"]["section_names"] == (
        "Volcano plot,MA plot,PCA plot,Expression heatmap,DESeq2 results,"
        "Normalized counts,Significant genes,Pathway overlaps,STRING enrichment"
    )
    assert pca_plot["params"]["x_column"] == "PC1"
    assert pca_plot["params"]["y_column"] == "PC2"
    assert pca_plot["params"]["color_column"] == "condition"
    assert pca_plot["params"]["format"] == "png"
    assert pathway_gene_sets["params"]["file"] == "templates/data/deseq2_gene_sets.json"
    assert pathway_enrichment["params"]["input_column"] == "gene"
    assert pathway_enrichment["params"]["database_format"] == "json"
    assert pathway_enrichment["params"]["case_sensitive"] is False
    assert string_enrichment["params"]["protein_ids"] == ""
    assert string_enrichment["params"]["protein_table"] == ""
    assert string_enrichment["params"]["id_column"] == "gene"
    assert string_enrichment["params"]["query_type"] == "enrichment"
    assert string_enrichment["params"]["species"] == 4932

    assert _has_edge(workflow, "volcano_001", "volcano_image", "de_report_001", "images")
    assert _has_edge(workflow, "ma_plot_001", "ma_image", "de_report_001", "images")
    assert _has_edge(workflow, "deseq2_001", "pca_scores_csv", "pca_plot_001", "table")
    assert _has_edge(workflow, "pca_plot_001", "plot_image", "de_report_001", "images")
    assert _has_edge(workflow, "heatmap_001", "plot_png", "de_report_001", "images")
    assert _has_edge(workflow, "deseq2_001", "results_csv", "de_report_001", "tables")
    assert _has_edge(workflow, "deseq2_001", "normalized_counts_csv", "de_report_001", "tables")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "de_report_001", "tables")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "pathway_enrichment_001", "input_genes")
    assert _has_edge(workflow, "pathway_gene_sets_001", "file", "pathway_enrichment_001", "database")
    assert _has_edge(workflow, "pathway_enrichment_001", "overlap", "de_report_001", "tables")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "string_enrichment_001", "protein_table")
    assert _has_edge(workflow, "string_enrichment_001", "interaction_network", "de_report_001", "tables")
    assert _has_edge(workflow, "de_report_001", "html_report", "de_report_preview_001", "file")

    assert workflow["outputs"]["normalized_counts"] == "deseq2_001"
    assert workflow["outputs"]["pca_plot"] == "pca_plot_001"
    assert workflow["outputs"]["pathway_overlaps"] == "pathway_enrichment_001"
    assert workflow["outputs"]["pathway_enrichment"] == "pathway_enrichment_001"
    assert workflow["outputs"]["string_enrichment"] == "string_enrichment_001"
    assert workflow["outputs"]["report"] == "de_report_001"
    assert workflow["outputs"]["report_preview"] == "de_report_preview_001"
