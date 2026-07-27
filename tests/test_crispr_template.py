from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from fastapi.routing import APIRoute

from bionodulo.api.routes import get_workflow_template, list_workflow_templates, router
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


def test_crispr_template_covers_editing_design_and_screen_analysis() -> None:
    workflow = _load_template("crispr_editing_pipeline.json")
    node_types = _node_types(workflow)

    assert workflow["name"] == "CRISPR Editing and Screen Analysis"
    assert workflow["category"] == "CRISPR"
    assert {"crispr", "guide-rna", "crispresso2", "mageck", "cas-offinder"}.issubset(set(workflow["tags"]))
    assert {
        "guide_rna_design",
        "cas_offinder",
        "crispresso2",
        "mageck_count",
        "mageck_test",
    }.issubset(set(workflow["tools"]))

    assert node_types["genome_001"] == "input_fasta"
    assert node_types["amplicon_r1_001"] == "input_fastq"
    assert node_types["amplicon_r2_001"] == "input_fastq"
    assert node_types["screen_reads_001"] == "input_fastq"
    assert node_types["library_001"] == "input_file"
    assert node_types["guide_design_001"] == "guide_rna_design"
    assert node_types["cas_offinder_001"] == "cas_offinder"
    assert node_types["crispresso2_001"] == "crispresso2"
    assert node_types["gate_crispresso_report_001"] == "gate"
    assert node_types["mageck_count_001"] == "mageck_count"
    assert node_types["mageck_test_001"] == "mageck_test"
    assert node_types["render_guide_design_tab_0"] == "table_preview"
    assert node_types["render_guide_design_tab_1"] == "table_preview"
    assert node_types["render_cas_offinder_tab_2"] == "table_preview"
    assert node_types["render_gate_crispresso_report_tab_3"] == "table_preview"
    assert node_types["render_mageck_test_tab_4"] == "table_preview"
    assert "data_validator" not in node_types.values()

    assert _has_edge(workflow, "genome_001", "reference", "guide_design_001", "genome")
    assert _has_edge(workflow, "genome_001", "reference", "cas_offinder_001", "genome_fasta")
    assert _has_edge(workflow, "amplicon_r1_001", "read1", "crispresso2_001", "r1")
    assert _has_edge(workflow, "amplicon_r2_001", "read1", "crispresso2_001", "r2")
    assert _has_edge(workflow, "crispresso2_001", "report", "gate_crispresso_report_001", "value")
    assert _has_edge(workflow, "screen_reads_001", "reads", "mageck_count_001", "fastq_files")
    assert _has_edge(workflow, "library_001", "file", "mageck_count_001", "library_file")
    assert _has_edge(workflow, "mageck_count_001", "count_table", "mageck_test_001", "count_table")
    assert _has_edge(workflow, "guide_design_001", "guides", "render_guide_design_tab_0", "file")
    assert _has_edge(workflow, "guide_design_001", "off_targets", "render_guide_design_tab_1", "file")
    assert _has_edge(workflow, "cas_offinder_001", "offtarget_sites", "render_cas_offinder_tab_2", "file")
    assert _has_edge(workflow, "gate_crispresso_report_001", "output", "render_gate_crispresso_report_tab_3", "file")
    assert _has_edge(workflow, "mageck_test_001", "gene_summary", "render_mageck_test_tab_4", "file")


def test_crispr_template_validates_inputs_outputs_and_quality_gates() -> None:
    workflow = _load_template("crispr_editing_pipeline.json")

    crispresso_gate = _node_by_id(workflow, "gate_crispresso_report_001")
    guide_design = _node_by_id(workflow, "guide_design_001")
    cas_offinder = _node_by_id(workflow, "cas_offinder_001")
    crispresso2 = _node_by_id(workflow, "crispresso2_001")
    mageck_test = _node_by_id(workflow, "mageck_test_001")

    assert _output_validation(workflow, "genome_001", "reference")["expected_format"] == "fasta"
    assert _output_validation(workflow, "genome_001", "reference")["min_records"] >= 1
    assert _output_validation(workflow, "amplicon_r1_001", "read1")["expected_format"] == "fastq"
    assert _output_validation(workflow, "amplicon_r2_001", "read1")["expected_format"] == "fastq"
    # Amplicon reads must be a real CRISPR edit experiment, not sarscov2 WGS:
    # CRISPResso2 aligns them against a human TRAC amplicon, so unrelated reads
    # simply never match.
    assert _node_by_id(workflow, "amplicon_r1_001")["params"]["reads"] == [
        "https://raw.githubusercontent.com/nf-core/test-datasets/6057ae142db3b9f4f1a40d1b909168261806c089/testdata-edition/hCas9-TRAC-a_R1.fastq.gz"
    ]
    assert _node_by_id(workflow, "amplicon_r2_001")["params"]["reads"] == [
        "https://raw.githubusercontent.com/nf-core/test-datasets/6057ae142db3b9f4f1a40d1b909168261806c089/testdata-edition/hCas9-TRAC-a_R2.fastq.gz"
    ]
    assert _output_validation(workflow, "screen_reads_001", "reads")["expected_format"] == "fastq"
    assert _output_validation(workflow, "library_001", "file")["expected_format"] == "tsv"
    # No required_fields: the real MAGeCK demo library ships headerless (sgRNA/sequence/gene columns).
    assert "required_fields" not in _output_validation(workflow, "library_001", "file")
    assert _output_validation(workflow, "guide_design_001", "guides")["expected_format"] == "tsv"
    cas_validation = _output_validation(workflow, "cas_offinder_001", "offtarget_sites")
    assert cas_validation["expected_format"] == "text"
    assert "min_size_bytes" not in cas_validation
    assert _output_validation(workflow, "mageck_count_001", "count_table")["expected_format"] == "tsv"
    assert _output_validation(workflow, "mageck_test_001", "gene_summary")["expected_format"] == "tsv"

    assert crispresso_gate["params"]["condition_mode"] == "file_exists"
    assert crispresso_gate["params"]["on_fail"] == "halt"
    assert "CRISPResso2 HTML report" in crispresso_gate["params"]["error_message"]

    # smallGenome carries chr9 + chr11. "chr9" was correct all along -- it was
    # the GENOME that had drifted to sarscov2, not the target.
    assert guide_design["params"]["target"] == "chr9:1-1000"
    assert guide_design["params"]["pam"] == "NGG"
    assert guide_design["params"]["guide_length"] == 20
    assert guide_design["params"]["mismatches"] == 3
    assert cas_offinder["params"]["guide_seq"] == "AGGCGGATCACCTGAGGTCA"
    assert cas_offinder["params"]["pam_sequence"] == "NNG"
    assert crispresso2["params"]["name"] == "edited_locus"
    assert crispresso2["params"]["guide_seq"] == "ACAAAACTGTGCTAGACATG"
    assert mageck_test["params"]["treatment_labels"] == "treated"
    assert mageck_test["params"]["control_labels"] == "control"

    assert workflow["outputs"]["validated_genome"] == "genome_001"
    assert workflow["outputs"]["designed_guides"] == "guide_design_001"
    assert workflow["outputs"]["cas_offinder_sites"] == "cas_offinder_001"
    assert workflow["outputs"]["crispresso_report_gate"] == "gate_crispresso_report_001"
    assert workflow["outputs"]["mageck_counts"] == "mageck_count_001"
    assert workflow["outputs"]["mageck_gene_summary"] == "mageck_test_001"


def test_crispr_fastq_edges_match_backend_and_editor_port_types() -> None:
    workflow = _load_template("crispr_editing_pipeline.json")
    registry = NodeRegistry.create_isolated()
    result = validate_workflow(workflow, registry)
    assert result.valid, result.errors

    provider = registry.get("input_fastq")
    crispresso = registry.get("crispresso2")
    assert provider is not None
    assert crispresso is not None
    source_type = provider.RETURN_TYPES[provider.RETURN_NAMES.index("read1")]
    assert source_type == crispresso.INPUT_TYPES()["required"]["r1"][0] == "FASTQ"
    assert source_type == crispresso.INPUT_TYPES()["optional"]["r2"][0] == "FASTQ"

    editor_registry = NodeRegistry.create_isolated()
    assert editor_registry.get("mageck_count") is not None
    editor_info = editor_registry.object_info()
    provider_info = editor_info["input_fastq"]
    editor_source_type = provider_info["output"][provider_info["output_name"].index("read1")]
    assert editor_source_type == editor_info["crispresso2"]["input"]["required"]["r1"][0] == "FASTQ"
    assert editor_source_type == editor_info["crispresso2"]["input"]["optional"]["r2"][0] == "FASTQ"
    assert editor_info["mageck_count"]["input"]["required"]["fastq_files"][0] == "FILE"


def test_crispr_template_is_discoverable_from_workflow_templates_api() -> None:
    routes = {(route.path, frozenset(route.methods or set())) for route in router.routes if isinstance(route, APIRoute)}
    assert ("/workflow_templates", frozenset({"GET"})) in routes
    assert ("/workflow_templates/{filename}", frozenset({"GET"})) in routes

    list_payload = asyncio.run(list_workflow_templates(cast(Any, None)))
    template_payload = asyncio.run(get_workflow_template(cast(Any, None), "crispr_editing_pipeline.json"))
    listed = next(
        template for template in list_payload["templates"] if template["filename"] == "crispr_editing_pipeline.json"
    )
    assert listed["name"] == "CRISPR Editing and Screen Analysis"
    assert listed["category"] == "CRISPR"
    assert 12 <= listed["node_count"] < 18
    assert "guide_rna_design" in listed["tools"]
    assert "mageck_test" in listed["tools"]
    assert "Guide RNA Design" in listed["preview_steps"]

    assert template_payload["name"] == "CRISPR Editing and Screen Analysis"
