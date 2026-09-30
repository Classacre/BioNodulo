"""API round trips and safe CWL bundle import."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient


def _workflow(metadata: dict) -> dict:
    return {
        "id": "portable-qc", "name": "Portable QC", "description": "Keep this annotation",
        "parameters": [{"name": "sample", "type": "STRING", "default": "S 1"}],
        "nodes": [
            {"id": "qc", "type": "fastqc", "position": [42, 64],
             "node_info": metadata["fastqc"],
             "params": {"reads": "sample.fastq", "threads": 2, "kmers": 5,
                        "nogroup": True, "extract": False, "format": ""}},
            {"id": "summary", "type": "multiqc", "position": [312, 64],
             "node_info": metadata["multiqc"],
             "params": {"reports": "", "title": "QC summary", "filename": "multiqc_report",
                        "force": True}},
            {"id": "note", "type": "note", "position": [500, 64],
             "params": {"text": "Do not lose this"}},
        ],
        "edges": [{"id": "qc-summary", "from": {"node": "qc", "output": "report_dir"},
                   "to": {"node": "summary", "input": "reports"}}],
    }


def _cwl_workflow(metadata: dict) -> dict:
    return {
        "id": "portable-transform", "name": "Portable transform", "description": "Keep this annotation",
        "parameters": [{"name": "columns", "type": "STRING", "default": "sample,status"}],
        "nodes": [{"id": "extract", "type": "extract_columns", "position": [42, 64],
                   "node_info": metadata["extract_columns"],
                   "params": {"table": "", "columns": "sample,status", "delimiter": "tsv"}},
                  {"id": "note", "type": "note", "position": [500, 64],
                   "params": {"text": "Do not lose this"}}],
        "edges": [],
    }


@pytest.mark.parametrize("fmt,extension", [
    ("snakemake", ".smk"), ("nextflow", ".nf"),
    ("cwl", ".cwl-bundle.json"), ("galaxy", ".ga"),
])
def test_api_export_import_preserves_original_graph(fmt: str, extension: str) -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        metadata = client.get("/api/object_info").json()
        original = _cwl_workflow(metadata) if fmt == "cwl" else _workflow(metadata)
        exported = client.post("/api/workflow/export", json={
            "workflow": original, "format": fmt, "name": "qc",
        })
        assert exported.status_code == 200, exported.text
        assert exported.json()["filename"] == "qc" + extension
        content = exported.json()["content"]
        if fmt == "snakemake":
            assert "--threads 2" in content and "--kmers 5" in content and "--nogroup" in content
            assert "sample.fastq" in content and "title=lambda wildcards: 'QC summary'" in content
        elif fmt == "nextflow":
            assert "--threads 2" in content and "--kmers 5" in content and "--nogroup" in content
            assert "params.qc_input = 'sample.fastq'" in content
            assert "--title 'QC summary'" in content
        elif fmt == "cwl":
            tool = json.loads(json.loads(content)["tools/extract.cwl"])
            assert tool["inputs"]["columns"]["default"] == "sample,status"
            assert tool["inputs"]["delimiter"]["default"] == "tsv"
        elif fmt == "galaxy":
            steps = json.loads(content)["steps"]
            assert steps["1"]["position"] == {"left": 42, "top": 64}
            assert steps["2"]["position"] == {"left": 312, "top": 64}
        imported = client.post("/api/workflow/import", json={
            "source": fmt, "content": content,
        })
        assert imported.status_code == 200, imported.text
        assert imported.json()["workflow"] == original


def test_api_cwl_bundle_rejects_path_traversal_and_changed_tool() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        metadata = client.get("/api/object_info").json()
        exported = client.post("/api/workflow/export", json={
            "workflow": _cwl_workflow(metadata), "format": "cwl", "name": "qc",
        })
        assert exported.status_code == 200, exported.text
        files = json.loads(exported.json()["content"])

        traversal = {**files, "tools/../../escape.cwl": "{}"}
        response = client.post("/api/workflow/import", json={
            "source": "cwl", "content": json.dumps(traversal),
        })
        assert response.status_code == 400
        assert "Unsafe" in response.json()["detail"]

        files["tools/extract.cwl"] = files["tools/extract.cwl"] + "\n"
        changed = client.post("/api/workflow/import", json={
            "source": "cwl", "content": json.dumps(files),
        })
        assert changed.status_code == 400
        assert "changed" in changed.json()["detail"]


def test_api_foreign_cwl_bundle_validates_shapes_and_sources() -> None:
    from server import create_app

    workflow = {
        "class": "Workflow", "cwlVersion": "v1.2",
        "inputs": {"data": "File"},
        "outputs": {"result": {"type": "File", "outputSource": "convert/out"}},
        "steps": {"convert": {"run": "tools/convert.cwl", "in": {"data": "data"}, "out": ["out"]}},
    }
    tool = {"class": "CommandLineTool", "baseCommand": ["cat"],
            "inputs": {"data": "File"}, "outputs": {"out": {"type": "File"}}}

    def bundle(wf: object, tl: object) -> dict[str, str]:
        return {"workflow.cwl": json.dumps(wf), "tools/convert.cwl": json.dumps(tl)}

    with TestClient(create_app()) as client:
        valid = client.post("/api/workflow/import", json={
            "source": "cwl", "content": json.dumps(bundle(workflow, tool)),
        })
        assert valid.status_code == 200, valid.text
        assert valid.json()["workflow"]["nodes"][0]["type"] == "generic_command"
        assert "structural draft" in valid.json()["warnings"][0]

        cases: list[tuple[str, object, object]] = [("Workflow object", [], tool)]
        for label, change in [
            ("named workflow steps", lambda wf: wf.update(steps=[])),
            ("inputs must be a named object", lambda wf: wf["steps"]["convert"].update({"in": []})),
            ("requires one string source", lambda wf: wf["steps"]["convert"].update({"in": {"data": [7]}})),
            ("unknown source", lambda wf: wf["steps"]["convert"].update({"in": {"data": "missing/out"}})),
            ("unknown tool output", lambda wf: wf["steps"]["convert"].update(out=["missing"])),
            ("unknown source", lambda wf: wf["outputs"]["result"].update(outputSource="convert/missing")),
        ]:
            altered = deepcopy(workflow)
            change(altered)
            cases.append((label, altered, tool))
        cases.extend([
            ("tool must be an object", workflow, []),
            ("tool outputs must be a named object", workflow, {**tool, "outputs": []}),
        ])
        for expected, wf, tl in cases:
            response = client.post("/api/workflow/import", json={
                "source": "cwl", "content": json.dumps(bundle(wf, tl)),
            })
            assert response.status_code == 400, (expected, response.text)
            assert expected.lower() in response.json()["detail"].lower()


def test_api_import_unsupported_format_and_yaml_are_client_errors() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        unknown = client.post("/api/workflow/import", json={"source": "wdl", "content": "workflow X {}"})
        assert unknown.status_code == 400
        yaml = client.post("/api/workflow/import", json={
            "source": "cwl", "content": "class: Workflow\ncwlVersion: v1.2\nsteps: {}\n",
        })
        assert yaml.status_code == 400
        assert "JSON" in yaml.json()["detail"]


def test_api_foreign_shell_is_a_warned_structural_draft() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        imported = client.post("/api/workflow/import", json={
            "source": "snakemake",
            "content": ('rule qc:\n    input:\n        "sample.fastq"\n    output:\n'
                        '        "qc.html"\n    shell:\n        "fastqc sample.fastq"\n'
                        'rule summary:\n    input:\n        "qc.html"\n    output:\n'
                        '        "summary.html"\n    shell:\n        "multiqc qc.html"\n'),
        })
    assert imported.status_code == 200, imported.text
    assert "structural draft" in imported.json()["warnings"][0]
    workflow = imported.json()["workflow"]
    assert all(node["type"] == "generic_command" for node in workflow["nodes"])
    assert all("position" in node and "params" in node and "node_info" in node for node in workflow["nodes"])
    assert workflow["edges"] == [{
        "id": "edge_qc_summary",
        "from": {"node": "node_qc", "output": "output_0"},
        "to": {"node": "node_summary", "input": "input_0"},
    }]
    assert workflow["version"] == "2.0" and workflow["app"] == "bionodulo"
    assert workflow["groups"] == [] and workflow["outputs"] == {}


def test_editor_params_conflicts_and_unrepresentable_qc_edge_return_400() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        metadata = client.get("/api/object_info").json()
        workflow = _workflow(metadata)
        workflow["nodes"][0]["widgets"] = {"threads": 99}
        conflict = client.post("/api/workflow/export", json={
            "workflow": workflow, "format": "snakemake", "name": "qc",
        })
        assert conflict.status_code == 400
        assert "conflicting params/widgets" in conflict.json()["detail"]

        del workflow["nodes"][0]["widgets"]
        workflow["nodes"][0]["ui"] = {"promotedInputs": ["threads"]}
        workflow["edges"][0] = {"id": "bad", "from": {"node": "summary", "output": "report"},
                                "to": {"node": "qc", "input": "threads"}}
        bad_edge = client.post("/api/workflow/export", json={
            "workflow": workflow, "format": "nextflow", "name": "qc",
        })
        assert bad_edge.status_code == 400
        assert "cannot bind" in bad_edge.json()["detail"]
