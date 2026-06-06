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

    assert node_types["variant_report_001"] == "html_report"
    assert node_types["variant_report_preview_001"] == "html_preview"
    assert node_types["sv_report_001"] == "html_report"
    assert node_types["sv_report_preview_001"] == "html_preview"

    variant_report = _node_by_id(workflow, "variant_report_001")
    sv_report = _node_by_id(workflow, "sv_report_001")
    assert variant_report["params"]["section_names"] == "VCF statistics,Coverage plot,Annotated variants"
    assert sv_report["params"]["section_names"] == "Manta SV calls,DELLY SV calls"

    assert _has_edge(workflow, "variant_report_001", "html_report", "variant_report_preview_001", "file")
    assert _has_edge(workflow, "sv_report_001", "html_report", "sv_report_preview_001", "file")
    assert workflow["outputs"]["variant_report_preview"] == "variant_report_preview_001"
    assert workflow["outputs"]["structural_variant_report_preview"] == "sv_report_preview_001"
