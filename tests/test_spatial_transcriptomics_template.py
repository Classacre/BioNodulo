from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)



def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node_by_id(workflow, node_id)
    return (
        node.get("ui", {})
        .get("validation", {})
        .get("outputs", {})
        .get(output, {})
    )

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


def test_spatial_transcriptomics_template_covers_visium_qc_and_scanpy_clustering() -> None:
    workflow = _load_template("spatial_transcriptomics_qc_clustering.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "Spatial Transcriptomics QC and Clustering"
    assert workflow["category"] == "Spatial Transcriptomics"
    assert {
        "spatial-transcriptomics",
        "visium",
        "squidpy",
        "scanpy",
        "qc",
        "clustering",
        "umap",
    }.issubset(set(workflow["tags"]))
    assert {
        "input_directory",
        "squidpy_qc",
        "scanpy_spatial",
        "image_preview",
    }.issubset(set(workflow["tools"]))

    # Both stages now consume explicit native artifacts: Squidpy reads the full
    # Visium directory, then Scanpy consumes the resulting H5AD.
    assert node_types["visium_outs_001"] == "input_directory"
    assert node_types["squidpy_qc_001"] == "squidpy_qc"
    assert node_types["spatial_plot_preview_001"] == "image_preview"
    assert "count_matrix_001" not in node_types
    assert "coordinates_001" not in node_types
    assert node_types["scanpy_spatial_001"] == "scanpy_spatial"
    assert node_types["scanpy_umap_preview_001"] == "image_preview"

    assert _has_edge(workflow, "visium_outs_001", "directory", "squidpy_qc_001", "visium_path")
    assert _has_edge(workflow, "squidpy_qc_001", "spatial_plot", "spatial_plot_preview_001", "file")
    assert _has_edge(workflow, "squidpy_qc_001", "adata", "scanpy_spatial_001", "adata")
    assert _has_edge(workflow, "scanpy_spatial_001", "umap", "scanpy_umap_preview_001", "file")


def test_spatial_transcriptomics_template_validates_outputs_and_analysis_parameters() -> None:
    workflow = _load_template("spatial_transcriptomics_qc_clustering.json")

    visium_input = _node_by_id(workflow, "visium_outs_001")
    visium_validator = _output_validation(workflow, "visium_outs_001", "directory")
    squidpy = _node_by_id(workflow, "squidpy_qc_001")
    squidpy_validator = _output_validation(workflow, "squidpy_qc_001", "adata")
    scanpy = _node_by_id(workflow, "scanpy_spatial_001")
    clusters_validator = _output_validation(workflow, "scanpy_spatial_001", "clusters")

    assert visium_input["params"]["directory"] == "examples/data/spatial_transcriptomics/visium_outs"
    assert visium_validator["expected_format"] == "directory"
    assert visium_validator["min_size_bytes"] > 0
    assert visium_validator["fail_on_error"] is True

    assert squidpy["params"]["min_counts"] == 500
    assert squidpy["params"]["min_cells"] == 3
    assert squidpy["params"]["max_mt_pct"] == 20.0
    assert squidpy["params"]["n_hvg"] == 2000
    assert squidpy["params"]["n_pcs"] == 15
    assert squidpy["params"]["resolution"] == 0.8
    assert squidpy_validator["expected_format"] == "auto"
    assert squidpy_validator["fail_on_error"] is True

    assert _has_edge(workflow, "squidpy_qc_001", "adata", "scanpy_spatial_001", "adata")
    assert scanpy["params"]["sample_name"] == "visium_sample"
    assert "delimiter" not in scanpy["params"]
    assert scanpy["params"]["min_cells"] == 3
    assert scanpy["params"]["min_genes"] == 200
    assert scanpy["params"]["n_hvg"] == 2000
    assert scanpy["params"]["n_pcs"] == 15
    assert scanpy["params"]["resolution"] == 0.8
    assert clusters_validator["expected_format"] == "csv"
    assert clusters_validator["fail_on_error"] is True

    assert workflow["outputs"]["validated_visium_outs"] == "visium_outs_001"
    assert workflow["outputs"]["squidpy_adata"] == "squidpy_qc_001"
    assert workflow["outputs"]["spatial_plot_preview"] == "spatial_plot_preview_001"
    assert workflow["outputs"]["scanpy_clusters"] == "scanpy_spatial_001"
    assert workflow["outputs"]["scanpy_umap_preview"] == "scanpy_umap_preview_001"


def test_spatial_transcriptomics_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/spatial_transcriptomics_qc_clustering.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "spatial_transcriptomics_qc_clustering.json"
    )
    assert listed["name"] == "Spatial Transcriptomics QC and Clustering"
    assert listed["category"] == "Spatial Transcriptomics"
    assert listed["node_count"] >= 5
    assert "squidpy_qc" in listed["tools"]
    assert "scanpy_spatial" in listed["tools"]
    assert "Squidpy QC" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "Spatial Transcriptomics QC and Clustering"
