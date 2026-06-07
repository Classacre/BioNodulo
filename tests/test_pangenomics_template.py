from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bionodulo.nodes.builtin.inputs import InputFASTANode


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


def _target_input_count(workflow: dict[str, Any], target: str, target_input: str) -> int:
    return sum(
        edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_pangenomics_template_covers_pggb_odgi_qc_and_visualization() -> None:
    workflow = _load_template("pangenomics_graph_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Pangenomics Graph QC and Visualization"
    assert workflow["category"] == "Pangenomics"
    assert {"pangenomics", "pggb", "odgi", "graph", "visualization"}.issubset(set(workflow["tags"]))
    assert {
        "input_fasta",
        "data_validator",
        "pggb",
        "odgi_build",
        "odgi_viz",
        "odgi_stats",
        "html_report",
        "html_preview",
        "image_preview",
    }.issubset(set(workflow["tools"]))

    assert node_types["haplotypes_001"] == "input_fasta"
    assert node_types["validate_haplotypes_001"] == "data_validator"
    assert node_types["pggb_001"] == "pggb"
    assert node_types["validate_pggb_gfa_001"] == "data_validator"
    assert node_types["odgi_build_001"] == "odgi_build"
    assert node_types["validate_odgi_stats_001"] == "data_validator"
    assert node_types["odgi_viz_001"] == "odgi_viz"
    assert node_types["odgi_stats_001"] == "odgi_stats"
    assert node_types["validate_odgi_stats_json_001"] == "data_validator"
    assert node_types["graph_image_preview_001"] == "image_preview"
    assert node_types["pangenomics_report_001"] == "html_report"
    assert node_types["pangenomics_report_preview_001"] == "html_preview"

    assert _has_edge(workflow, "haplotypes_001", "reference", "validate_haplotypes_001", "input")
    assert _has_edge(workflow, "validate_haplotypes_001", "passthrough", "pggb_001", "input_fasta")
    assert _has_edge(workflow, "pggb_001", "smooth_gfa", "validate_pggb_gfa_001", "input")
    assert _has_edge(workflow, "validate_pggb_gfa_001", "passthrough", "odgi_build_001", "gfa_graph")
    assert _has_edge(workflow, "validate_pggb_gfa_001", "passthrough", "odgi_viz_001", "gfa_graph")
    assert _has_edge(workflow, "validate_pggb_gfa_001", "passthrough", "odgi_stats_001", "gfa_graph")
    assert _has_edge(workflow, "odgi_build_001", "stats", "validate_odgi_stats_001", "input")
    assert _has_edge(workflow, "odgi_stats_001", "stats_json", "validate_odgi_stats_json_001", "input")
    assert _has_edge(workflow, "odgi_viz_001", "viz_image", "graph_image_preview_001", "file")
    assert _has_edge(workflow, "odgi_viz_001", "viz_image", "pangenomics_report_001", "images")
    assert _has_edge(workflow, "pangenomics_report_001", "html_report", "pangenomics_report_preview_001", "file")

    assert not _has_edge(workflow, "haplotypes_001", "reference", "pggb_001", "input_fasta")
    assert not _has_edge(workflow, "pggb_001", "smooth_gfa", "odgi_build_001", "gfa_graph")
    assert not _has_edge(workflow, "pggb_001", "smooth_gfa", "odgi_viz_001", "gfa_graph")
    assert not _has_edge(workflow, "odgi_build_001", "stats", "pangenomics_report_001", "tables")
    assert not _has_edge(workflow, "validate_odgi_stats_001", "passthrough", "pangenomics_report_001", "tables")
    assert not _has_edge(workflow, "validate_odgi_stats_json_001", "passthrough", "pangenomics_report_001", "tables")
    assert _target_input_count(workflow, "pangenomics_report_001", "tables") == 0
    assert _target_input_count(workflow, "pangenomics_report_001", "images") == 1


def test_pangenomics_template_validates_inputs_outputs_and_graph_parameters() -> None:
    workflow = _load_template("pangenomics_graph_pipeline.json")

    haplotype_validator = _node_by_id(workflow, "validate_haplotypes_001")
    pggb = _node_by_id(workflow, "pggb_001")
    gfa_validator = _node_by_id(workflow, "validate_pggb_gfa_001")
    odgi_build = _node_by_id(workflow, "odgi_build_001")
    odgi_stats_validator = _node_by_id(workflow, "validate_odgi_stats_001")
    odgi_viz = _node_by_id(workflow, "odgi_viz_001")
    odgi_stats = _node_by_id(workflow, "odgi_stats_001")
    report = _node_by_id(workflow, "pangenomics_report_001")

    assert _node_by_id(workflow, "haplotypes_001")["params"]["reference"] == "examples/data/pangenomics/haplotypes.fa"
    assert haplotype_validator["params"]["expected_format"] == "fasta"
    assert haplotype_validator["params"]["min_records"] >= 2
    assert haplotype_validator["params"]["min_size_bytes"] > 0
    assert haplotype_validator["params"]["fail_on_error"] is True
    assert pggb["params"]["num_haplotypes"] == 2
    assert pggb["params"]["threads"] >= 8
    assert pggb["params"]["map_pct_id"] == 90
    assert pggb["params"]["segment_length"] == 5000
    assert pggb["params"]["graph_poas"] == 2
    assert gfa_validator["params"]["expected_format"] == "text"
    assert gfa_validator["params"]["fail_on_error"] is True
    assert odgi_build["params"]["output_name"] == "pangenome_graph"
    assert odgi_build["params"]["validate"] is True
    assert odgi_stats_validator["params"]["expected_format"] == "json"
    assert odgi_stats_validator["params"]["fail_on_error"] is True
    assert odgi_viz["params"]["width"] == 1600
    assert odgi_viz["params"]["height"] == 260
    assert odgi_viz["params"]["show_paths"] is True
    assert odgi_viz["params"]["viz_mode"] == "gradient"
    assert odgi_stats["params"]["threads"] >= 4
    assert report["params"]["title"] == "Pangenomics Graph QC Report"
    assert "PGGB" in report["params"]["text_sections"]
    assert report["params"]["section_names"] == "ODGI visualization"

    assert workflow["outputs"]["validated_haplotypes"] == "validate_haplotypes_001"
    assert workflow["outputs"]["pggb_graph"] == "pggb_001"
    assert workflow["outputs"]["validated_graph_gfa"] == "validate_pggb_gfa_001"
    assert workflow["outputs"]["odgi_graph"] == "odgi_build_001"
    assert workflow["outputs"]["odgi_build_stats"] == "validate_odgi_stats_001"
    assert workflow["outputs"]["odgi_stats"] == "validate_odgi_stats_json_001"
    assert workflow["outputs"]["graph_visualization"] == "odgi_viz_001"
    assert workflow["outputs"]["report"] == "pangenomics_report_001"
    assert workflow["outputs"]["report_preview"] == "pangenomics_report_preview_001"


def test_pangenomics_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/pangenomics_graph_pipeline.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "pangenomics_graph_pipeline.json"
    )
    assert listed["name"] == "Pangenomics Graph QC and Visualization"
    assert listed["category"] == "Pangenomics"
    assert listed["node_count"] >= 12
    assert "pggb" in listed["tools"]
    assert "odgi_viz" in listed["tools"]
    assert "PGGB Build" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Pangenomics Graph QC and Visualization"


@pytest.mark.asyncio
async def test_pangenomics_example_haplotypes_are_materialized_from_manifest(tmp_path: Path) -> None:
    node = InputFASTANode()
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        workspace_dir=tmp_path,
        node_dir=tmp_path / "input_fasta",
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node.run(
        reference="examples/data/pangenomics/haplotypes.fa",
        output_dir=tmp_path / "node-output",
        context=context,
    )

    fasta_path = Path(result["outputs"]["reference"])
    assert fasta_path.exists()
    assert fasta_path.name == "haplotypes.fa"
    assert fasta_path.read_text(encoding="utf-8").count(">") >= 2
