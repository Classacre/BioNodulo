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

    assert "render_volcano_ima_6" not in node_types
    assert "render_pca_plot_ima_8" not in node_types
    assert node_types["render_deseq2_tab_0"] == "table_preview"
    assert node_types["render_deseq2_tab_1"] == "table_preview"
    assert node_types["render_normalized_counts_transpose_tab_2"] == "table_preview"
    assert node_types["render_significant_genes_tab_3"] == "table_preview"
    assert node_types["render_pathway_enrichment_tab_4"] == "table_preview"
    assert node_types["render_string_enrichment_tab_5"] == "table_preview"
    assert node_types["pca_plot_001"] == "scatter_plot"
    assert node_types["pathway_gene_sets_001"] == "input_file"
    assert node_types["pathway_enrichment_001"] == "intersect_genes"
    assert node_types["string_enrichment_001"] == "string_db"
    assert node_types["normalized_counts_transpose_001"] == "transpose_table"

    pca_plot = _node_by_id(workflow, "pca_plot_001")
    pathway_gene_sets = _node_by_id(workflow, "pathway_gene_sets_001")
    pathway_enrichment = _node_by_id(workflow, "pathway_enrichment_001")
    string_enrichment = _node_by_id(workflow, "string_enrichment_001")
    normalized_counts_transpose = _node_by_id(workflow, "normalized_counts_transpose_001")
    assert pca_plot["params"]["x_column"] == "PC1"
    assert pca_plot["params"]["y_column"] == "PC2"
    assert pca_plot["params"]["color_column"] == "condition"
    assert pca_plot["params"]["format"] == "html"
    assert pathway_gene_sets["params"]["file"] == "templates/data/deseq2_gene_sets.json"
    assert pathway_enrichment["params"]["input_column"] == "gene"
    assert pathway_enrichment["params"]["database_format"] == "json"
    assert pathway_enrichment["params"]["case_sensitive"] is False
    assert string_enrichment["params"]["protein_ids"] == ""
    assert string_enrichment["params"]["protein_table"] == ""
    assert string_enrichment["params"]["id_column"] == "gene"
    assert string_enrichment["params"]["query_type"] == "enrichment"
    assert string_enrichment["params"]["species"] == 4932
    assert normalized_counts_transpose["params"]["id_column"] == "gene"
    assert normalized_counts_transpose["params"]["new_header"] == "sample"
    assert normalized_counts_transpose["params"]["output_type"] == "CSV"

    assert _has_edge(workflow, "deseq2_001", "pca_scores_csv", "pca_plot_001", "table")
    assert _has_edge(workflow, "deseq2_001", "results_csv", "render_deseq2_tab_0", "file")
    assert _has_edge(workflow, "deseq2_001", "normalized_counts_csv", "render_deseq2_tab_1", "file")
    assert _has_edge(workflow, "deseq2_001", "normalized_counts_csv", "normalized_counts_transpose_001", "table")
    assert _has_edge(workflow, "normalized_counts_transpose_001", "transposed_table", "render_normalized_counts_transpose_tab_2", "file")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "render_significant_genes_tab_3", "file")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "pathway_enrichment_001", "input_genes")
    assert _has_edge(workflow, "pathway_gene_sets_001", "file", "pathway_enrichment_001", "database")
    assert _has_edge(workflow, "pathway_enrichment_001", "overlap", "render_pathway_enrichment_tab_4", "file")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "string_enrichment_001", "protein_table")
    assert _has_edge(workflow, "string_enrichment_001", "interaction_network", "render_string_enrichment_tab_5", "file")

    assert workflow["outputs"]["normalized_counts"] == "deseq2_001"
    assert workflow["outputs"]["pca_plot"] == "pca_plot_001"
    assert workflow["outputs"]["pathway_overlaps"] == "pathway_enrichment_001"
    assert workflow["outputs"]["pathway_enrichment"] == "pathway_enrichment_001"
    assert workflow["outputs"]["string_enrichment"] == "string_enrichment_001"
    assert workflow["outputs"]["normalized_counts_transposed"] == "normalized_counts_transpose_001"
