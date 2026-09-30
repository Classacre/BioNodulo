"""Round-trip checks must retain provenance and refuse changed native sources."""

import json

import pytest

from bionodulo.converter.roundtrip import (
    restore_workflow_bundle, restore_workflow_document, restore_workflow_source,
    stamp_workflow_bundle, stamp_workflow_document, stamp_workflow_source,
)


@pytest.fixture
def workflow() -> dict:
    return {
        "id": "original", "name": "QC — cohort α", "description": "Keep provenance",
        "nodes": [{"id": "qc", "type": "fastqc", "widgets": {"threads": 2, "nogroup": True},
                   "node_info": {"return_names": ["report_dir"]}, "pos": [10, 20]},
                  {"id": "summary", "type": "multiqc", "widgets": {"title": "Study one"}}],
        "edges": [{"id": "edge", "from": {"node": "qc", "output": "report_dir"},
                   "to": {"node": "summary", "input": "reports"}}],
        "references": [{"doi": "10.example/evidence", "title": "Original reference"}],
        "parameters": [{"name": "threads", "value": 2}], "groups": [],
    }


@pytest.mark.parametrize("prefix", ["#", "//"])
def test_native_source_retains_complete_graph_and_tolerates_crlf(workflow, prefix) -> None:
    source = stamp_workflow_source("#!/usr/bin/env tool\nexecute\n", workflow, prefix)
    assert source.startswith("#!/usr/bin/env tool\n")
    assert restore_workflow_source(source.replace("\n", "\r\n"), prefix) == workflow
    recovered = restore_workflow_source(source, prefix)
    recovered["nodes"][0]["widgets"]["threads"] = 9
    assert workflow["nodes"][0]["widgets"]["threads"] == 2


@pytest.mark.parametrize("prefix", ["#", "//"])
def test_changed_native_execution_cannot_restore_stale_graph(workflow, prefix) -> None:
    source = stamp_workflow_source("execute --threads 2\n", workflow, prefix)
    with pytest.raises(ValueError, match="changed"):
        restore_workflow_source(source.replace("--threads 2", "--threads 9"), prefix)
    with pytest.raises(ValueError, match="changed"):
        restore_workflow_source(source + "execute something_else\n", prefix)
    with pytest.raises(ValueError, match="Duplicate"):
        restore_workflow_source(source + source.splitlines()[-1] + "\n", prefix)


def test_unmarked_source_is_foreign_and_bad_markers_fail(workflow) -> None:
    assert restore_workflow_source("rule foreign:\n    shell: 'echo ok'", "#") is None
    with pytest.raises(ValueError, match="Invalid"):
        restore_workflow_source("# BIONODULO_ROUNDTRIP_V1 invalid!\n", "#")
    with pytest.raises(ValueError, match="version"):
        restore_workflow_source("# BIONODULO_ROUNDTRIP_V2 value\n", "#")
    with pytest.raises(ValueError, match="already"):
        stamp_workflow_source(stamp_workflow_source("execute", workflow, "#"), workflow, "#")


def test_json_document_preserves_graph_and_refuses_parameter_or_metadata_edits(workflow) -> None:
    original = {"steps": {"0": {"tool_state": {"threads": 2}}}}
    document = stamp_workflow_document(original, workflow)
    assert "bionodulo_roundtrip" not in original
    assert restore_workflow_document(document) == workflow
    document["steps"]["0"]["tool_state"]["threads"] = 9
    with pytest.raises(ValueError, match="changed"):
        restore_workflow_document(document)
    document = stamp_workflow_document(original, workflow)
    document["bionodulo_roundtrip"]["workflow"]["name"] = "Altered"
    with pytest.raises(ValueError, match="changed"):
        restore_workflow_document(document)


def test_cwl_bundle_manifest_covers_every_tool_and_stays_outside_cwl(workflow) -> None:
    files = {"workflow.cwl": '{"class":"Workflow"}\n', "tools/qc.cwl": '{"class":"CommandLineTool"}\n'}
    bundle = stamp_workflow_bundle(files, workflow)
    assert bundle["workflow.cwl"] == files["workflow.cwl"]
    assert restore_workflow_bundle({name: content.replace("\n", "\r\n") for name, content in bundle.items()}) == workflow
    assert restore_workflow_bundle(files) is None
    for change in ["edit", "remove", "add"]:
        altered = dict(bundle)
        if change == "edit":
            altered["tools/qc.cwl"] = '{}\n'
        elif change == "remove":
            del altered["tools/qc.cwl"]
        else:
            altered["tools/extra.cwl"] = '{}\n'
        with pytest.raises(ValueError, match="changed"):
            restore_workflow_bundle(altered)
    manifest = json.loads(bundle["bionodulo-roundtrip.json"])
    manifest["version"] = 2
    bundle["bionodulo-roundtrip.json"] = json.dumps(manifest)
    with pytest.raises(ValueError, match="version"):
        restore_workflow_bundle(bundle)
