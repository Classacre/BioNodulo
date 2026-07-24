from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bionodulo.manager.example_data import EXAMPLE_DATA_MANIFEST
from bionodulo.nodes.builtin.inputs import InputFASTANode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node_by_id(workflow, node_id)
    return node.get("ui", {}).get("validation", {}).get("outputs", {}).get(output, {})


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def _target_input_count(workflow: dict[str, Any], target: str, target_input: str) -> int:
    return sum(edge.get("to") == {"node": target, "input": target_input} for edge in workflow["edges"])


def test_pangenomics_template_covers_pggb_odgi_qc_and_visualization() -> None:
    workflow = _load_template("pangenomics_graph_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Pangenomics Graph QC and Visualization"
    assert workflow["category"] == "Pangenomics"
    assert {"pangenomics", "pggb", "odgi", "graph", "visualization"}.issubset(set(workflow["tags"]))
    assert {
        "input_fasta",
        "pggb",
        "odgi_build",
        "odgi_viz",
        "odgi_stats",
        "image_preview",
    }.issubset(set(workflow["tools"]))

    assert node_types["haplotypes_001"] == "input_fasta"
    assert "validate_haplotypes_001" not in node_types
    assert node_types["pggb_001"] == "pggb"
    assert "validate_pggb_gfa_001" not in node_types
    assert node_types["odgi_build_001"] == "odgi_build"
    assert "validate_odgi_stats_001" not in node_types
    assert node_types["odgi_viz_001"] == "odgi_viz"
    assert node_types["odgi_stats_001"] == "odgi_stats"
    assert "validate_odgi_stats_json_001" not in node_types
    assert node_types["graph_image_preview_001"] == "image_preview"

    assert not _has_edge(workflow, "haplotypes_001", "reference", "validate_haplotypes_001", "input")
    assert _has_edge(workflow, "haplotypes_001", "reference", "pggb_001", "input_fasta")
    assert not _has_edge(workflow, "pggb_001", "smooth_gfa", "validate_pggb_gfa_001", "input")
    assert _has_edge(workflow, "pggb_001", "smooth_gfa", "odgi_build_001", "gfa_graph")
    assert _has_edge(workflow, "odgi_build_001", "graph_odgi", "odgi_viz_001", "gfa_graph")
    assert _has_edge(workflow, "odgi_build_001", "graph_odgi", "odgi_stats_001", "gfa_graph")
    assert not _has_edge(workflow, "odgi_build_001", "stats", "validate_odgi_stats_001", "input")
    assert not _has_edge(workflow, "odgi_stats_001", "stats_json", "validate_odgi_stats_json_001", "input")
    assert _has_edge(workflow, "odgi_viz_001", "viz_image", "graph_image_preview_001", "file")

    assert _target_input_count(workflow, "odgi_viz_001", "gfa_graph") == 1
    assert _target_input_count(workflow, "odgi_stats_001", "gfa_graph") == 1
    assert _target_input_count(workflow, "graph_image_preview_001", "file") == 1
    validation = validate_workflow(workflow, NodeRegistry.create_isolated())
    assert validation.valid, validation.errors


def test_pangenomics_template_validates_inputs_outputs_and_graph_parameters() -> None:
    workflow = _load_template("pangenomics_graph_pipeline.json")

    haplotype_validator = _output_validation(workflow, "haplotypes_001", "reference")
    pggb = _node_by_id(workflow, "pggb_001")
    gfa_validator = _output_validation(workflow, "pggb_001", "smooth_gfa")
    odgi_build = _node_by_id(workflow, "odgi_build_001")
    odgi_stats_validator = _output_validation(workflow, "odgi_build_001", "stats")
    odgi_viz = _node_by_id(workflow, "odgi_viz_001")
    odgi_stats = _node_by_id(workflow, "odgi_stats_001")

    assert _node_by_id(workflow, "haplotypes_001")["params"]["reference"] == (
        "templates/data/smoke/haplotypes.fasta"
    )
    assert haplotype_validator["expected_format"] == "fasta"
    assert haplotype_validator["min_records"] == 12
    assert haplotype_validator["min_size_bytes"] > 0
    assert haplotype_validator["fail_on_error"] is True
    assert pggb["params"]["num_haplotypes"] == 12
    assert pggb["params"]["threads"] >= 8
    assert pggb["params"]["map_pct_id"] == 90
    assert pggb["params"]["segment_length"] == 5000
    assert pggb["params"]["min_match_length"] == 23
    assert pggb["params"]["poa_length_target"] == "700,1100"
    assert pggb["params"]["do_viz"] is False
    assert "graph_poas" not in pggb["params"]
    assert "consensus_spec" not in pggb["params"]
    assert "do_layout" not in pggb["params"]
    assert gfa_validator["expected_format"] == "text"
    assert gfa_validator["fail_on_error"] is True
    assert odgi_build["params"]["output_name"] == "pangenome_graph"
    assert odgi_build["params"]["validate"] is True
    assert odgi_stats_validator["expected_format"] == "json"
    assert odgi_stats_validator["fail_on_error"] is True
    assert odgi_viz["params"]["width"] == 1600
    assert odgi_viz["params"]["height"] == 260
    assert odgi_viz["params"]["show_paths"] is True
    assert odgi_viz["params"]["viz_mode"] == "gradient"
    assert odgi_stats["params"]["threads"] >= 4

    fixture_path = ROOT / _node_by_id(workflow, "haplotypes_001")["params"]["reference"]
    fixture_text = fixture_path.read_text(encoding="utf-8")
    sequence_lengths: list[int] = []
    current_length = 0
    for line in fixture_text.splitlines():
        if line.startswith(">"):
            if current_length:
                sequence_lengths.append(current_length)
            current_length = 0
        else:
            current_length += len(line.strip())
    if current_length:
        sequence_lengths.append(current_length)

    assert len(sequence_lengths) == pggb["params"]["num_haplotypes"]
    assert min(sequence_lengths) >= pggb["params"]["segment_length"]
    assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == (
        "44d138b568b3eb5b588f3aaaaf6f5895c32ec5f7f2178a89c40b953fb7977943"
    )

    assert workflow["outputs"]["validated_haplotypes"] == "haplotypes_001"
    assert workflow["outputs"]["pggb_graph"] == "pggb_001"
    assert workflow["outputs"]["validated_graph_gfa"] == "pggb_001"
    assert workflow["outputs"]["odgi_graph"] == "odgi_build_001"
    assert workflow["outputs"]["odgi_build_stats"] == "odgi_build_001"
    assert workflow["outputs"]["odgi_stats"] == "odgi_stats_001"
    assert workflow["outputs"]["graph_visualization"] == "odgi_viz_001"


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
    assert listed["node_count"] >= 6
    assert "pggb" in listed["tools"]
    assert "odgi_viz" in listed["tools"]
    assert "PGGB Build" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Pangenomics Graph QC and Visualization"


@pytest.mark.asyncio
async def test_pangenomics_example_haplotypes_are_materialized_from_manifest(tmp_path: Path) -> None:
    fixture = next(
        spec for spec in EXAMPLE_DATA_MANIFEST if spec.category == "pangenomics" and spec.filename == "haplotypes.fa"
    )
    assert fixture.url == (
        "https://raw.githubusercontent.com/pangenome/pggb/"
        "e25486b9b219877eca82631a13953129386c8b09/data/HLA/DRB1-3123.fa.gz"
    )
    assert fixture.gunzip is True

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
    assert sum(line.startswith(">") for line in fasta_path.read_text(encoding="utf-8").splitlines()) == 12
    assert hashlib.sha256(fasta_path.read_bytes()).hexdigest() == (
        "ec471ac09235e0f9214eb46ebf2c0108cecdea52eca609de9e52ad51a6bf7a91"
    )
