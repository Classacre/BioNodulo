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


def test_long_read_ont_template_covers_basecalling_filtering_qc_and_methylation() -> None:
    workflow = _load_template("long_read_ont_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "ONT Long-Read Sequencing"
    assert workflow["category"] == "Long Read"
    assert {"long-read", "nanopore", "dorado", "modkit"}.issubset(set(workflow["tags"]))
    assert {"dorado_basecaller", "chopper_filter", "nanoplot", "modkit_pileup"}.issubset(set(workflow["tools"]))

    assert node_types["pod5_001"] == "input_directory"
    assert node_types["reference_001"] == "input_fasta"
    assert "validate_pod5_001" not in node_types
    assert "validate_reference_001" not in node_types
    assert node_types["dorado_basecaller_001"] == "dorado_basecaller"
    assert node_types["dorado_demux_001"] == "dorado_demux"
    assert node_types["chopper_001"] == "chopper_filter"
    assert node_types["nanoplot_001"] == "nanoplot"
    assert node_types["modkit_001"] == "modkit_pileup"
    assert "validate_nanoplot_report_001" not in node_types
    assert node_types["render_nanoplot_tab_0"] == "table_preview"
    assert node_types["render_modkit_tab_1"] == "table_preview"
    assert node_types["render_dorado_demux_tab_2"] == "table_preview"

    assert not _has_edge(workflow, "pod5_001", "directory", "validate_pod5_001", "input")
    assert not _has_edge(workflow, "reference_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "pod5_001", "directory", "dorado_basecaller_001", "pod5_dir")
    assert _has_edge(workflow, "reference_001", "reference", "dorado_basecaller_001", "reference")
    assert _has_edge(workflow, "dorado_basecaller_001", "basecalled_bam", "gate_basecalled_bam_001", "value")
    assert _has_edge(workflow, "gate_basecalled_bam_001", "output", "dorado_demux_001", "reads")
    assert _has_edge(workflow, "dorado_demux_001", "demux_dir", "chopper_001", "reads")
    assert _has_edge(workflow, "chopper_001", "filtered_reads", "gate_filtered_reads_001", "value")
    assert _has_edge(workflow, "gate_filtered_reads_001", "output", "nanoplot_001", "fastq")
    assert _has_edge(workflow, "dorado_basecaller_001", "basecalled_bam", "modkit_001", "bam")
    assert _has_edge(workflow, "reference_001", "reference", "modkit_001", "reference")
    assert not _has_edge(workflow, "nanoplot_001", "qc_report", "validate_nanoplot_report_001", "input")
    assert _has_edge(workflow, "nanoplot_001", "qc_report", "render_nanoplot_tab_0", "file")
    assert _has_edge(workflow, "modkit_001", "bedmethyl", "render_modkit_tab_1", "file")
    assert _has_edge(workflow, "dorado_demux_001", "barcode_summary", "render_dorado_demux_tab_2", "file")

    assert _has_edge(workflow, "pod5_001", "directory", "dorado_basecaller_001", "pod5_dir")
    assert _has_edge(workflow, "reference_001", "reference", "dorado_basecaller_001", "reference")
    assert _has_edge(workflow, "nanoplot_001", "qc_report", "render_nanoplot_tab_0", "file")


def test_long_read_ont_template_validates_and_gates_core_outputs() -> None:
    workflow = _load_template("long_read_ont_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_basecalled_bam_001"] == "gate"
    assert node_types["gate_filtered_reads_001"] == "gate"
    assert "validate_nanoplot_report_001" not in node_types

    pod5_validator = _output_validation(workflow, "pod5_001", "directory")
    reference_validator = _output_validation(workflow, "reference_001", "reference")
    report_validator = _output_validation(workflow, "nanoplot_001", "qc_report")
    basecall_gate = _node_by_id(workflow, "gate_basecalled_bam_001")
    reads_gate = _node_by_id(workflow, "gate_filtered_reads_001")

    assert pod5_validator["expected_format"] == "directory"
    assert pod5_validator["min_size_bytes"] > 0
    assert pod5_validator["fail_on_error"] is True
    assert reference_validator["expected_format"] == "fasta"
    assert reference_validator["min_records"] >= 1
    assert reference_validator["fail_on_error"] is True
    assert report_validator["expected_format"] == "text"
    assert report_validator["min_size_bytes"] > 0
    assert report_validator["fail_on_error"] is True

    assert basecall_gate["params"]["condition_mode"] == "file_exists"
    assert basecall_gate["params"]["on_fail"] == "halt"
    assert "basecalled BAM" in basecall_gate["params"]["error_message"]
    assert reads_gate["params"]["condition_mode"] == "is_not_empty"
    assert reads_gate["params"]["on_fail"] == "halt"
    assert "filtered reads" in reads_gate["params"]["error_message"]

    assert _has_edge(workflow, "dorado_basecaller_001", "basecalled_bam", "gate_basecalled_bam_001", "value")
    assert _has_edge(workflow, "gate_basecalled_bam_001", "output", "dorado_demux_001", "reads")
    assert _has_edge(workflow, "chopper_001", "filtered_reads", "gate_filtered_reads_001", "value")
    assert _has_edge(workflow, "gate_filtered_reads_001", "output", "nanoplot_001", "fastq")
    assert not _has_edge(workflow, "dorado_basecaller_001", "basecalled_bam", "dorado_demux_001", "reads")
    assert not _has_edge(workflow, "chopper_001", "filtered_reads", "nanoplot_001", "fastq")

    assert workflow["outputs"]["validated_pod5_dir"] == "pod5_001"
    assert workflow["outputs"]["validated_reference"] == "reference_001"
    assert workflow["outputs"]["basecalled_bam_quality_gate"] == "gate_basecalled_bam_001"
    assert workflow["outputs"]["filtered_reads_quality_gate"] == "gate_filtered_reads_001"
    assert workflow["outputs"]["basecalled_bam"] == "dorado_basecaller_001"
    assert workflow["outputs"]["demux_dir"] == "dorado_demux_001"
    assert workflow["outputs"]["filtered_reads"] == "chopper_001"
    assert workflow["outputs"]["qc_report"] == "nanoplot_001"
    assert workflow["outputs"]["bedmethyl"] == "modkit_001"


def test_long_read_ont_template_is_discoverable_from_workflow_templates_api() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        list_response = client.get("/api/workflow_templates")
        template_response = client.get("/api/workflow_templates/long_read_ont_pipeline.json")

    assert list_response.status_code == 200
    listed = next(
        template
        for template in list_response.json()["templates"]
        if template["filename"] == "long_read_ont_pipeline.json"
    )
    assert listed["name"] == "ONT Long-Read Sequencing"
    assert listed["category"] == "Long Read"
    assert listed["node_count"] >= 11
    assert "dorado_basecaller" in listed["tools"]
    assert "modkit_pileup" in listed["tools"]
    assert "Dorado Basecaller" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "ONT Long-Read Sequencing"
