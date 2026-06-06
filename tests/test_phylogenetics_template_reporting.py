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


def test_phylogenetics_template_embeds_alignment_image_in_final_report() -> None:
    workflow = _load_template("phylogenetics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["msa_view_001"] == "bp_msa_view"
    assert node_types["phylo_report_001"] == "html_report"
    assert node_types["phylo_report_preview_001"] == "html_preview"

    report = _node(workflow, "phylo_report_001")
    assert report["params"]["section_names"] == "Phylogenetic tree,Alignment visualization"

    assert _has_edge(workflow, "tree_viewer_001", "tree_image", "phylo_report_001", "images")
    assert _has_edge(workflow, "msa_view_001", "alignment_image", "phylo_report_001", "images")
    assert _has_edge(workflow, "phylo_report_001", "html_report", "phylo_report_preview_001", "file")
    assert not _has_edge(workflow, "mafft_001", "alignment", "phylo_report_001", "tables")
    assert workflow["outputs"]["report_preview"] == "phylo_report_preview_001"
