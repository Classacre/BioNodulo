"""Tests for the GA4GH WES 1.1 client and DRS custodian-pinning policy.

The WES endpoints are served by a local ``http.server`` mock bound to an
ephemeral port, so the client is exercised over real HTTP without network
access or extra dependencies.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.wes_client import (
    CustodianPinViolation,
    DRSCustodianPolicy,
    WESClient,
    WESClientError,
    build_wes_request,
    enforce_custodian_policy,
)

_BASE = "/ga4gh/wes/v1"


class _MockWESServer(ThreadingHTTPServer):
    """Records requests and replays a RUNNING -> COMPLETE status sequence."""

    daemon_threads = True

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        # Header names lowercased: urllib normalizes "Content-Type" to
        # "Content-type" on the wire, so lookups must be case-insensitive.
        self.captured_requests: list[tuple[dict[str, str], bytes]] = []
        self.status_sequence: list[str] = ["RUNNING", "COMPLETE"]

    def capture(self, headers: Any, body: bytes) -> None:
        self.captured_requests.append(({key.lower(): value for key, value in headers.items()}, body))


class _MockWESHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, doc: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(doc).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _server(self) -> _MockWESServer:
        server = self.server
        assert isinstance(server, _MockWESServer)
        return server

    def do_GET(self) -> None:
        if self.path == f"{_BASE}/service-info":
            self._send_json(
                {
                    "id": "org.mock.wes",
                    "version": "1.1.0",
                    "workflow_type_versions": {"CWL": ["v1.2"]},
                }
            )
        elif self.path == f"{_BASE}/runs/run-1/status":
            states = self._server().status_sequence
            state = states.pop(0) if states else "COMPLETE"
            self._send_json({"run_id": "run-1", "state": state})
        elif self.path == f"{_BASE}/runs/run-1":
            self._send_json(
                {
                    "run_id": "run-1",
                    "state": "COMPLETE",
                    "request": {"workflow_type": "CWL"},
                }
            )
        else:
            self._send_json({"msg": f"no route for {self.path}"}, status=404)

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        server = self._server()
        if self.path == f"{_BASE}/runs":
            if not self.headers.get("Content-Type", "").startswith("multipart/form-data"):
                self._send_json({"msg": "POST /runs requires multipart/form-data"}, status=400)
                return
            if b"workflow_params" not in body:
                self._send_json({"msg": "POST /runs body missing workflow_params"}, status=400)
                return
            server.capture(self.headers, body)
            self._send_json({"run_id": "run-1"})
        elif self.path == f"{_BASE}/runs/run-1/cancel":
            server.capture(self.headers, body)
            self._send_json({"run_id": "run-1"})
        else:
            self._send_json({"msg": f"no route for {self.path}"}, status=404)


@pytest.fixture()
def wes_server() -> Any:
    server = _MockWESServer(("127.0.0.1", 0), _MockWESHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _base_url(server: _MockWESServer) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}{_BASE}"


def _two_node_workflow() -> dict[str, Any]:
    """samtools_view -> samtools_sort with nested edges and a sensitive input."""
    return {
        "id": "wes-demo",
        "nodes": [
            {
                "id": "view",
                "type": "samtools_view",
                "inputs": {
                    "alignment": {
                        "type": "FILE",
                        "value": "/data/patient1.bam",
                        "sensitive": True,
                    },
                },
                "outputs": {"bam": {"type": "FILE"}},
                "widgets": {"command": "samtools view -b"},
                "meta": {},
            },
            {
                "id": "sort",
                "type": "samtools_sort",
                "inputs": {"alignment": {"type": "FILE"}},
                "outputs": {"sorted_bam": {"type": "FILE"}},
                "widgets": {},
                "meta": {},
            },
        ],
        "edges": [
            {"from": {"node": "view", "output": "bam"}, "to": {"node": "sort", "input": "alignment"}},
        ],
    }


# ---------------------------------------------------------------------------
# WESClient round-trip against the local mock
# ---------------------------------------------------------------------------


def test_run_workflow_round_trips_over_mock_server(wes_server: Any) -> None:
    client = WESClient(_base_url(wes_server), timeout=10.0, auth_token="secret-token")

    info = client.get_service_info()
    assert info["id"] == "org.mock.wes"
    assert info["workflow_type_versions"]["CWL"] == ["v1.2"]

    result = client.run_workflow(
        workflow_params={"view/alignment": "drs://fid.example/patient1"},
        workflow_type="CWL",
        workflow_type_version="v1.2",
        workflow_url="workflow.cwl",
        workflow_attachment=[("workflow.cwl", json.dumps({"class": "Workflow"}))],
        tags={"origin": "bionodulo"},
    )
    assert result == {"run_id": "run-1"}

    headers, body = wes_server.captured_requests[-1]
    assert headers.get("authorization") == "Bearer secret-token"
    assert headers.get("content-type", "").startswith("multipart/form-data; boundary=")
    assert b"workflow_params" in body
    assert b"drs://fid.example/patient1" in body
    assert b'name="workflow_attachment"; filename="workflow.cwl"' in body

    assert client.get_run_status("run-1") == {"run_id": "run-1", "state": "RUNNING"}
    assert client.get_run_status("run-1") == {"run_id": "run-1", "state": "COMPLETE"}
    assert client.get_run_log("run-1")["state"] == "COMPLETE"
    assert client.cancel_run("run-1") == {"run_id": "run-1"}


def test_http_error_surfaces_as_wes_client_error_with_status(wes_server: Any) -> None:
    client = WESClient(_base_url(wes_server), timeout=10.0)
    with pytest.raises(WESClientError) as excinfo:
        client.get_run_log("missing-run")
    assert excinfo.value.status_code == 404
    assert "HTTP 404" in str(excinfo.value)


def test_run_workflow_rejects_invalid_arguments() -> None:
    client = WESClient("https://wes.example.org/ga4gh/wes/v1")
    with pytest.raises(ValueError, match="workflow_type"):
        client.run_workflow(
            workflow_params={},
            workflow_type="smk",
            workflow_type_version="7",
            workflow_url="Snakefile",
        )
    with pytest.raises(ValueError, match="workflow_url or workflow_attachment"):
        client.run_workflow(
            workflow_params={},
            workflow_type="CWL",
            workflow_type_version="v1.2",
        )


# ---------------------------------------------------------------------------
# DRSCustodianPolicy
# ---------------------------------------------------------------------------


def _policy() -> DRSCustodianPolicy:
    return DRSCustodianPolicy(pin_map={"drs://fid.example": "wes.example.org"})


def test_sensitive_input_referenced_by_local_path_is_rejected() -> None:
    with pytest.raises(CustodianPinViolation, match="view/alignment") as excinfo:
        enforce_custodian_policy(
            _policy(),
            _two_node_workflow(),
            input_refs={},
            endpoint_url="https://wes.example.org/ga4gh/wes/v1",
        )
    assert "/data/patient1.bam" in str(excinfo.value)
    assert excinfo.value.input_ref == "view/alignment"


def test_sensitive_input_referenced_by_http_url_is_rejected() -> None:
    workflow = _two_node_workflow()
    workflow["nodes"][0]["inputs"]["alignment"]["value"] = "https://files.example.org/patient1.bam"
    with pytest.raises(CustodianPinViolation, match="view/alignment"):
        enforce_custodian_policy(
            _policy(),
            workflow,
            input_refs={},
            endpoint_url="https://wes.example.org/ga4gh/wes/v1",
        )


def test_pinned_drs_uri_passes_and_resolves_to_drs_references() -> None:
    payload = enforce_custodian_policy(
        _policy(),
        _two_node_workflow(),
        input_refs={"/data/patient1.bam": "drs://fid.example/patient1"},
        endpoint_url="https://wes.example.org/ga4gh/wes/v1",
    )
    assert payload["endpoint"] == "https://wes.example.org/ga4gh/wes/v1"
    assert payload["workflow_params"]["view/alignment"] == "drs://fid.example/patient1"


def test_unpinned_drs_uri_is_rejected() -> None:
    with pytest.raises(CustodianPinViolation, match="no custodian pin"):
        enforce_custodian_policy(
            _policy(),
            _two_node_workflow(),
            input_refs={"/data/patient1.bam": "drs://other-archive.example/patient1"},
            endpoint_url="https://wes.example.org/ga4gh/wes/v1",
        )


def test_wrong_host_endpoint_is_rejected_with_required_endpoint_named() -> None:
    with pytest.raises(CustodianPinViolation, match="wes.example.org") as excinfo:
        enforce_custodian_policy(
            _policy(),
            _two_node_workflow(),
            input_refs={"/data/patient1.bam": "drs://fid.example/patient1"},
            endpoint_url="https://wes.other.org/ga4gh/wes/v1",
        )
    assert "view/alignment" in str(excinfo.value)
    assert excinfo.value.required_host == "wes.example.org"


# ---------------------------------------------------------------------------
# build_wes_request
# ---------------------------------------------------------------------------


def _editor_node(node_id: str, node_type: str, params: dict[str, Any]) -> dict[str, Any]:
    catalog_path = Path(__file__).resolve().parents[2] / "bionodulo" / "nodes" / "node_metadata.json"
    metadata = json.loads(catalog_path.read_text(encoding="utf-8"))[node_type]
    input_types = {
        section: {
            name: {"type": spec[0], **spec[1]}
            for name, spec in metadata["input"].get(section, {}).items()
        }
        for section in ("required", "optional", "hidden")
    }
    return {
        "id": node_id,
        "type": node_type,
        "position": [100, 100],
        "params": params,
        "node_info": {
            "id": node_type,
            "input_types": input_types,
            "return_names": metadata["output_name"],
            "return_types": metadata["output"],
        },
    }


def test_build_wes_request_compiles_cwl_for_two_node_workflow(wes_server: _MockWESServer) -> None:
    workflow = {
        "id": "table_workflow",
        "nodes": [
            _editor_node("extract", "extract_columns", {"columns": "sample,status", "delimiter": "tsv"}),
            _editor_node("filter", "filter_rows", {"column": "status", "operator": "equals", "value": "case"}),
        ],
        "edges": [{"id": "e1", "from": {"node": "extract", "output": "extracted_table"},
                   "to": {"node": "filter", "input": "table"}}],
    }
    payload = build_wes_request(workflow, input_bindings={"extract_table": "https://data.example/table.tsv"})

    assert payload["workflow_type"] == "CWL"
    assert payload["workflow_type_version"] == "v1.2"
    assert payload["workflow_url"] == "workflow.cwl"
    assert payload["tags"]["bionodulo:converter"] == "cwl"

    assert payload["workflow_params"] == {
        "extract_table": {"class": "File", "location": "https://data.example/table.tsv"},
    }

    attachments = dict(payload["workflow_attachment"])
    assert set(attachments) == {"workflow.cwl", "tools/extract.cwl", "tools/filter.cwl", "bionodulo-roundtrip.json"}

    wf_doc = json.loads(attachments["workflow.cwl"])
    assert wf_doc["class"] == "Workflow"
    assert wf_doc["cwlVersion"] == "v1.2"
    assert set(wf_doc["inputs"]) == {"extract_table"}
    assert set(wf_doc["steps"]) == {"extract", "filter"}
    assert wf_doc["steps"]["filter"]["in"]["table"] == "extract/extracted_table"

    extract_tool = json.loads(attachments["tools/extract.cwl"])
    assert extract_tool["class"] == "CommandLineTool"
    assert extract_tool["baseCommand"] == ["python", "-m", "bionodulo.converter.cwl_node_runner"]
    assert extract_tool["inputs"]["columns"]["default"] == "sample,status"
    assert extract_tool["inputs"]["delimiter"]["default"] == "tsv"

    # Verify the generated attachment and exact CWL job key survive WES multipart encoding.
    assert WESClient(_base_url(wes_server)).run_workflow(**payload) == {"run_id": "run-1"}
    body = wes_server.captured_requests[0][1]
    assert b'"extract_table": {"class": "File", "location": "https://data.example/table.tsv"}' in body
    assert b'tools/extract.cwl' in body


def test_build_wes_request_supports_snakemake_single_document_export() -> None:
    workflow = {"id": "qc_workflow", "nodes": [
        _editor_node("qc", "fastqc", {"threads": 2}),
        _editor_node("summary", "multiqc", {"title": "Tiny QC"}),
    ], "edges": [{"id": "e1", "from": {"node": "qc", "output": "report_dir"},
                  "to": {"node": "summary", "input": "reports"}}]}
    payload = build_wes_request(workflow, converter="snakemake", input_bindings={"qc_input": "https://data.example/sample.fastq"})
    assert payload["workflow_type"] == "snakemake"
    assert payload["workflow_url"] == "Snakefile"
    assert payload["workflow_params"] == {"qc_input": "https://data.example/sample.fastq"}
    assert [filename for filename, _ in payload["workflow_attachment"]] == ["Snakefile"]
    document = payload["workflow_attachment"][0][1]
    assert document.startswith("# Auto-generated by BioNodulo")
    assert 'config["qc_input"]' in document
    assert "rule qc:" in document and "rule summary:" in document
    assert payload["tags"]["bionodulo:converter"] == "snakemake"

    nextflow = build_wes_request(workflow, converter="nextflow", input_bindings={"qc_input": "https://data.example/sample.fastq"})
    assert nextflow["workflow_params"] == {"qc_input": "https://data.example/sample.fastq"}
    assert "Channel.fromPath(params.qc_input)" in nextflow["workflow_attachment"][0][1]


def test_build_wes_request_rejects_missing_unknown_and_unsupported_bindings() -> None:
    workflow = {"id": "extract", "nodes": [_editor_node("extract", "extract_columns", {"columns": "sample"})], "edges": []}
    with pytest.raises(ValueError, match="missing: extract_table"):
        build_wes_request(workflow)
    with pytest.raises(ValueError, match="unexpected: extract/table"):
        build_wes_request(workflow, input_bindings={"extract/table": "https://data.example/table.tsv"})
    with pytest.raises(ValueError, match="absolute URI"):
        build_wes_request(workflow, input_bindings={"extract_table": "/local/table.tsv"})
    with pytest.raises(ValueError, match="must be an object"):
        build_wes_request(workflow, input_bindings=[])
    with pytest.raises(ValueError, match="Unknown converter"):
        build_wes_request(workflow, converter="galaxy")
    with pytest.raises(ValueError, match="unsupported node type"):
        build_wes_request(_two_node_workflow(), input_bindings={"view_alignment": "https://data.example/patient.bam"})


def test_build_wes_request_rejects_overriding_embedded_nextflow_path() -> None:
    workflow = {"id": "inline_qc", "nodes": [
        _editor_node("qc", "fastqc", {"reads": "sample.fastq"}),
    ], "edges": []}
    with pytest.raises(ValueError, match="cannot override embedded input paths: qc_input"):
        build_wes_request(workflow, converter="nextflow", input_bindings={"qc_input": "https://data.example/other.fastq"})


def test_build_wes_request_accepts_explicit_service_version() -> None:
    workflow = {"id": "qc", "nodes": [_editor_node("qc", "fastqc", {})], "edges": []}
    payload = build_wes_request(
        workflow, converter="snakemake", input_bindings={"qc_input": "https://data.example/sample.fastq"},
        workflow_type_version="9.12.0",
    )
    assert payload["workflow_type_version"] == "9.12.0"
