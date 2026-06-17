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


def test_wgs_variant_template_previews_final_variant_reports() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["vep_001"] == "vep"
    assert "render_vcf_stats_ima_2" not in node_types
    assert "render_coverage_plot_ima_3" not in node_types
    assert node_types["render_gate_prioritized_vcf_tab_0"] == "table_preview"
    assert node_types["render_vep_tab_1"] == "table_preview"
    assert node_types["render_manta_sv_tab_0"] == "table_preview"
    assert node_types["render_delly_sv_tab_1"] == "table_preview"

    assert _has_edge(workflow, "filter_001", "filtered_vcf", "vep_001", "vcf")
    assert _has_edge(workflow, "vep_001", "annotated_vcf", "render_vep_tab_1", "file")
    assert _has_edge(workflow, "manta_sv_001", "sv_vcf", "render_manta_sv_tab_0", "file")
    assert _has_edge(workflow, "delly_sv_001", "sv_vcf", "render_delly_sv_tab_1", "file")
    assert workflow["outputs"]["vep_annotation"] == "vep_001"
