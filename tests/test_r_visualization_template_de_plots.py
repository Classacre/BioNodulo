from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_r_visualization_template_adds_de_volcano_and_ma_demo_branches() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["de_results_df_001"] == "r_dataframe_builder"
    assert node_types["volcano_001"] == "volcano_plot"
    assert node_types["ma_plot_001"] == "ma_plot"
    assert "volcano_preview_001" not in node_types
    assert "ma_preview_001" not in node_types
    assert "volcano_plot" in workflow["tools"]
    assert "ma_plot" in workflow["tools"]

    de_results = _node(workflow, "de_results_df_001")
    assert de_results["params"]["x_column"] == "baseMean"
    assert de_results["params"]["y_column"] == "log2FoldChange"
    assert de_results["params"]["group_column"] == "padj"

    volcano = _node(workflow, "volcano_001")
    assert volcano["params"]["format"] == "html"
    assert volcano["params"]["logfc_column"] == "log2FoldChange"
    assert volcano["params"]["pvalue_column"] == "padj"

    ma_plot = _node(workflow, "ma_plot_001")
    assert ma_plot["params"]["format"] == "html"
    assert ma_plot["params"]["mean_column"] == "baseMean"
    assert ma_plot["params"]["logfc_column"] == "log2FoldChange"
    assert ma_plot["params"]["pvalue_column"] == "padj"

    assert _has_edge(workflow, "de_results_df_001", "csv", "volcano_001", "results_table")
    assert _has_edge(workflow, "de_results_df_001", "csv", "ma_plot_001", "results_table")

    assert workflow["outputs"]["volcano_plot"] == "volcano_001"
    assert workflow["outputs"]["ma_plot"] == "ma_plot_001"
