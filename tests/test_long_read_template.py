from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

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
    return _node_by_id(workflow, node_id).get("ui", {}).get("validation", {}).get("outputs", {}).get(output, {})


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_long_read_ont_template_wires_explicit_models_and_sidecars() -> None:
    workflow = _load_template("long_read_ont_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "ONT Long-Read Sequencing"
    assert workflow["category"] == "Long Read"
    assert {"long-read", "nanopore", "dorado", "modkit"}.issubset(workflow["tags"])
    assert {
        "samtools_faidx",
        "samtools_fastx",
        "dorado_basecaller",
        "dorado_demux",
        "data_validator",
        "chopper_filter",
        "nanoplot",
        "modkit_pileup",
    }.issubset(workflow["tools"])

    assert node_types["pod5_001"] == "input_directory"
    assert node_types["reference_001"] == "input_fasta"
    assert node_types["basecaller_model_001"] == "input_directory"
    assert node_types["modified_model_001"] == "input_directory"
    assert node_types["ref_sidecars_001"] == "samtools_faidx"
    assert node_types["dorado_basecaller_001"] == "dorado_basecaller"
    assert node_types["dorado_demux_001"] == "dorado_demux"
    assert node_types["samtools_fastx_001"] == "samtools_fastx"
    assert node_types["validate_selected_fastq_001"] == "data_validator"
    assert node_types["chopper_001"] == "chopper_filter"
    assert node_types["nanoplot_001"] == "nanoplot"
    assert node_types["modkit_001"] == "modkit_pileup"

    assert _has_edge(workflow, "reference_001", "reference", "ref_sidecars_001", "reference")
    assert _has_edge(workflow, "pod5_001", "directory", "dorado_basecaller_001", "pod5_dir")
    assert _has_edge(workflow, "basecaller_model_001", "directory", "dorado_basecaller_001", "model")
    assert _has_edge(
        workflow,
        "modified_model_001",
        "directory",
        "dorado_basecaller_001",
        "modified_bases_models",
    )
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "dorado_basecaller_001", "reference")
    assert _has_edge(workflow, "dorado_basecaller_001", "basecalled_bam", "gate_basecalled_bam_001", "value")
    assert _has_edge(workflow, "gate_basecalled_bam_001", "output", "dorado_demux_001", "reads")
    assert _has_edge(workflow, "dorado_demux_001", "selected_bam", "samtools_fastx_001", "input")
    assert _has_edge(workflow, "samtools_fastx_001", "reads", "validate_selected_fastq_001", "input")
    assert _has_edge(workflow, "validate_selected_fastq_001", "validated_fastq", "chopper_001", "reads")
    assert not _has_edge(workflow, "dorado_demux_001", "demux_dir", "chopper_001", "reads")
    assert "selected_demux_fastq_001" not in node_types
    assert _has_edge(workflow, "chopper_001", "filtered_reads", "gate_filtered_reads_001", "value")
    assert _has_edge(workflow, "gate_filtered_reads_001", "output", "nanoplot_001", "fastq")
    assert _has_edge(workflow, "nanoplot_001", "qc_stats", "render_nanoplot_tab_0", "file")
    assert not _has_edge(workflow, "nanoplot_001", "qc_report", "render_nanoplot_tab_0", "file")
    assert _has_edge(workflow, "dorado_basecaller_001", "basecalled_bam", "modkit_001", "bam")
    assert _has_edge(
        workflow,
        "dorado_basecaller_001",
        "basecalled_bam_index",
        "modkit_001",
        "bam_index",
    )
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "modkit_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "fai_index", "modkit_001", "reference_index")


def test_long_read_ont_template_uses_source_native_options_and_explicit_selection() -> None:
    workflow = _load_template("long_read_ont_pipeline.json")

    basecaller = _node_by_id(workflow, "dorado_basecaller_001")
    demux = _node_by_id(workflow, "dorado_demux_001")
    fastx = _node_by_id(workflow, "samtools_fastx_001")
    fastq_validator = _node_by_id(workflow, "validate_selected_fastq_001")
    chopper = _node_by_id(workflow, "chopper_001")
    nanoplot = _node_by_id(workflow, "nanoplot_001")
    modkit = _node_by_id(workflow, "modkit_001")
    basecall_gate = _node_by_id(workflow, "gate_basecalled_bam_001")
    reads_gate = _node_by_id(workflow, "gate_filtered_reads_001")

    assert "model" not in basecaller["params"]
    assert "modified_bases" not in basecaller["params"]
    assert basecaller["params"]["device"] == "auto"
    assert demux["params"] == {
        "no_classify": True,
        "selected_barcode": "SQK-NBD114-24_barcode01",
        "threads": 8,
    }
    assert {"mode", "emit_summary", "output_name", "kit_name"}.isdisjoint(demux["params"])
    assert "emit_fastq" not in demux["params"]
    assert fastx["params"] == {"threads": 8, "output_format": "fastq", "outputs": ["other"]}
    assert fastq_validator["params"] == {
        "expected_format": "fastq",
        "min_records": 1,
        "min_size_bytes": 1,
        "fail_on_error": True,
    }
    assert "max_length" not in chopper["params"]
    assert nanoplot["params"]["tsv_stats"] is True
    assert modkit["params"]["cpg"] is True
    assert modkit["params"]["combine_strands"] is True
    assert modkit["params"]["with_header"] is True
    assert "bedgraph" not in modkit["params"]

    assert _output_validation(workflow, "pod5_001", "directory")["expected_format"] == "directory"
    assert _output_validation(workflow, "basecaller_model_001", "directory")["expected_format"] == "directory"
    assert _output_validation(workflow, "modified_model_001", "directory")["expected_format"] == "directory"
    assert _output_validation(workflow, "reference_001", "reference")["expected_format"] == "fasta"
    assert _output_validation(workflow, "chopper_001", "filtered_reads") == {
        "expected_format": "fastq",
        "min_records": 1,
        "min_size_bytes": 1,
        "fail_on_error": True,
    }
    assert _output_validation(workflow, "nanoplot_001", "qc_report")["expected_format"] == "text"

    assert basecall_gate["params"]["condition_mode"] == "file_exists"
    assert basecall_gate["params"]["on_fail"] == "halt"
    assert reads_gate["params"]["condition_mode"] == "is_not_empty"
    assert reads_gate["params"]["on_fail"] == "halt"

    assert workflow["outputs"]["prepared_reference"] == "ref_sidecars_001"
    assert workflow["outputs"]["reference_fai"] == "ref_sidecars_001"
    assert workflow["outputs"]["sequence_dictionary"] == "ref_sidecars_001"
    assert workflow["outputs"]["basecalled_bam_index"] == "dorado_basecaller_001"
    assert workflow["outputs"]["selected_demux_bam"] == "dorado_demux_001"
    assert workflow["outputs"]["selected_demux_fastq"] == "samtools_fastx_001"
    assert workflow["outputs"]["validated_selected_demux_fastq"] == "validate_selected_fastq_001"
    assert workflow["outputs"]["bedmethyl"] == "modkit_001"


def test_long_read_selected_fastq_path_uses_explicit_type_refinement() -> None:
    workflow = _load_template("long_read_ont_pipeline.json")
    registry = NodeRegistry.create_isolated()
    result = validate_workflow(workflow, registry)
    assert result.valid, result.errors

    demux = registry.get("dorado_demux")
    fastx = registry.get("samtools_fastx")
    validator = registry.get("data_validator")
    chopper = registry.get("chopper_filter")
    assert demux is not None and fastx is not None and validator is not None and chopper is not None
    assert demux.RETURN_TYPES[demux.RETURN_NAMES.index("selected_bam")] == "BAM"
    assert "BAM" in fastx.INPUT_TYPES()["required"]["input"][0]
    assert fastx.RETURN_TYPES[fastx.RETURN_NAMES.index("reads")] == "FILE"
    assert validator.INPUT_TYPES()["required"]["input"][0] == "ANY"
    assert validator.RETURN_TYPES[validator.RETURN_NAMES.index("validated_fastq")] == "FASTQ"
    assert chopper.INPUT_TYPES()["required"]["reads"][0] == "FASTQ"

    editor_info = registry.object_info()
    demux_info = editor_info["dorado_demux"]
    assert demux_info["output"][demux_info["output_name"].index("selected_bam")] == "BAM"
    assert "BAM" in editor_info["samtools_fastx"]["input"]["required"]["input"][1]["options"]
    assert editor_info["samtools_fastx"]["output"][0] == "FILE"
    assert editor_info["data_validator"]["input"]["required"]["input"][0] == "*"
    validated_fastq_index = editor_info["data_validator"]["output_name"].index("validated_fastq")
    assert editor_info["data_validator"]["output"][validated_fastq_index] == "FASTQ"
    assert editor_info["chopper_filter"]["input"]["required"]["reads"][0] == "FASTQ"


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
    assert listed["node_count"] >= 16
    assert "dorado_basecaller" in listed["tools"]
    assert "modkit_pileup" in listed["tools"]
    assert "Reference FAI + Dictionary" in listed["preview_steps"]

    assert template_response.status_code == 200
    assert template_response.json()["name"] == "ONT Long-Read Sequencing"
