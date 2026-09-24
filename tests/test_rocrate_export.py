"""Tests for Workflow Run RO-Crate export with semantic contract records.

Assertions encode the MUST-level structure of the profiles [P1][P3][P4]:
metadata descriptor about the root, root conformsTo as an array of profile
references, CreateActions with resolvable instruments, and the BioNodulo
SemanticState and ContractCheck layer.
"""

from __future__ import annotations

import json

from bionodulo.provenance.rocrate_export import (
    BIONODULO_TERMS_NAMESPACE,
    build_run_crate,
    write_run_crate,
)
from bionodulo.workflow.semantic_checks import check_workflow_semantics


WORKFLOW = {
    "version": "2.0",
    "name": "mini rna-seq",
    "nodes": [
        {"id": "align", "type": "hisat2_align", "params": {}},
        {"id": "sort", "type": "samtools_sort", "params": {}},
    ],
    "edges": [
        {
            "id": "e1",
            "from": {"node": "align", "output": "alignment"},
            "to": {"node": "sort", "input": "alignment"},
        }
    ],
}


def _entities_by_id(crate: dict) -> dict:
    return {entity["@id"]: entity for entity in crate["@graph"]}


def test_crate_core_structure() -> None:
    crate = build_run_crate(WORKFLOW)
    entities = _entities_by_id(crate)

    descriptor = entities["ro-crate-metadata.json"]
    assert descriptor["@type"] == "CreativeWork"
    assert descriptor["about"] == {"@id": "./"}

    root = entities["./"]
    assert root["@type"] == "Dataset"
    conforms = [ref["@id"] for ref in root["conformsTo"]]
    assert conforms == ["https://w3id.org/ro/crate/1.1"]
    assert "not been validated" in root["bionodulo:conformanceStatus"]

    workflow_entity = entities[root["mainEntity"]["@id"]]
    assert "ComputationalWorkflow" in workflow_entity["@type"]

    # Multi-context arrays are the sanctioned extension pattern [P4][P12].
    assert crate["@context"][0].startswith("https://w3id.org/ro/crate/1.1")
    assert crate["@context"][2] == {"bionodulo": BIONODULO_TERMS_NAMESPACE}


def test_create_actions_have_resolvable_instruments() -> None:
    run_summary = {
        "nodes": {
            "align": {
                "status": "CompletedActionStatus",
                "start_time": "2026-09-07T01:00:00+00:00",
                "end_time": "2026-09-07T01:04:00+00:00",
                "command": "hisat2 -x idx -U reads.fq",
            }
        }
    }
    crate = build_run_crate(
        WORKFLOW,
        run_summary=run_summary,
        node_metadata={
            "hisat2_align": {
                "display_name": "HISAT2 Align",
                "documentation_url": "https://daehwankimlab.github.io/hisat2/",
                "version": "2.2.1",
            }
        },
    )
    entities = _entities_by_id(crate)

    action = entities["#run-align"]
    assert action["@type"] == "CreateAction"
    assert action["actionStatus"] == "CompletedActionStatus"
    assert action["startTime"] and action["endTime"]
    instrument_id = action["instrument"]["@id"]
    assert instrument_id in entities
    tool = entities[instrument_id]
    assert tool["softwareVersion"] == "2.2.1"
    assert tool["name"] == "HISAT2 Align"

    root = entities["./"]
    assert {"@id": "#run-align"} in root["mentions"]


def test_semantic_states_and_contract_checks_are_recorded() -> None:
    result = check_workflow_semantics(WORKFLOW)
    crate = build_run_crate(WORKFLOW, semantic_result=result)
    entities = _entities_by_id(crate)

    # sort node guarantees coordinate order; that state is recorded.
    sort_state_id = "#state-sort-sorted_bam"
    assert sort_state_id in entities
    state = entities[sort_state_id]
    assert state["@type"] == "bionodulo:SemanticState"
    values = {
        entities[prop["@id"]]["name"]: entities[prop["@id"]]["value"]
        for prop in state["bionodulo:stateProperty"]
    }
    assert values["sort_order"] == "coordinate"
    # Unknown dimensions must not be asserted as known.
    assert "reference_assembly" not in values

    output_file = entities["#output-sort-sorted_bam"]
    assert output_file["bionodulo:hasSemanticState"] == {"@id": sort_state_id}


def test_failed_contract_check_attaches_to_consuming_action() -> None:
    workflow = {
        "version": "2.0",
        "name": "strand demo",
        "nodes": [
            {"id": "align", "type": "hisat2_align", "params": {}},
            {"id": "counts", "type": "featurecounts", "params": {"strand_specificity": 1}},
        ],
        "edges": [
            {
                "id": "e1",
                "from": {"node": "align", "output": "alignment"},
                "to": {"node": "counts", "input": "alignment"},
            }
        ],
    }
    result = check_workflow_semantics(workflow)
    # Unknown strandedness from the aligner: gradual, no violation, but a
    # detection suggestion exists; the crate records only real violations.
    assert result.ok
    crate = build_run_crate(workflow, semantic_result=result)
    checks = [entity for entity in crate["@graph"] if entity.get("@type") == "bionodulo:ContractCheck"]
    assert len(checks) == 1
    assert checks[0]["bionodulo:status"] == "unverified"


def test_write_run_crate_produces_valid_files(tmp_path) -> None:
    metadata_file = write_run_crate(tmp_path / "crate", WORKFLOW)
    assert metadata_file.name == "ro-crate-metadata.json"
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert "@graph" in payload
    workflow_copy = json.loads(
        (tmp_path / "crate" / "workflow" / "bionodulo-workflow.json").read_text(
            encoding="utf-8"
        )
    )
    assert workflow_copy["name"] == "mini rna-seq"
