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
    # The phylo_report_001 html_report and its html_preview were removed by design;
    # the tree and alignment images render into dedicated image_preview nodes.
    assert "phylo_report_001" not in node_types
    assert "phylo_report_preview_001" not in node_types
    assert "render_tree_viewer_ima_0" not in node_types
    assert node_types["image_preview_001"] == "image_preview"

    assert _has_edge(workflow, "msa_view_001", "alignment_image", "image_preview_001", "file")
    assert "report_preview" not in workflow["outputs"]
