from __future__ import annotations

import hashlib
import json

import pytest

from bionodulo.nodes.generation import source_links


def _snapshot(tmp_path, records=None):
    if records is None:
        records = [
            {
                "biotoolsID": "alpha",
                "download": [
                    {"type": ["Tool wrapper (CWL)"], "url": "https://example.org/alpha.cwl"},
                    {"type": ["Tool wrapper (CWL)"], "url": "https://github.com/owner/repo/tree/main/cwl"},
                ],
            },
            {"biotoolsID": "beta", "download": []},
        ]
    snapshot = tmp_path / "registry.jsonl"
    raw = b"".join((json.dumps(record) + "\n").encode() for record in records)
    snapshot.write_bytes(raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "records": len(records), "complete": True})
    )
    return snapshot, manifest


def test_inventory_preserves_full_denominator_and_unsupported_link(tmp_path):
    snapshot, manifest = _snapshot(tmp_path)
    rows, summary = source_links.inventory_typed_cwl(snapshot, manifest)
    assert summary["registry_records"] == 2
    assert summary["typed_cwl_links"] == 2
    assert rows[1]["fetch_url"] is None
    assert rows[1]["link_classification"] == "not_a_direct_cwl_file"
    assert all(row["biotools_accession"] == "alpha" for row in rows)


def test_inventory_requires_verified_snapshot_before_acquisition(tmp_path, monkeypatch):
    snapshot, manifest = _snapshot(tmp_path)
    snapshot.write_bytes(snapshot.read_bytes().replace(b'"alpha"', b'"alphb"'))
    monkeypatch.setattr(source_links, "_retrieve", lambda *_args, **_kwargs: pytest.fail("network request"))
    with pytest.raises(ValueError, match="digest or record count"):
        source_links.acquire_typed_cwl(snapshot, manifest, tmp_path / "out")


def test_acquisition_retains_source_and_resumes_without_network(tmp_path, monkeypatch):
    snapshot, manifest = _snapshot(tmp_path)
    raw = b"cwlVersion: v1.2\nclass: CommandLineTool\nbaseCommand: echo\ninputs: {}\noutputs: {}\n"
    called = []

    def fake_retrieve(url, *, timeout):
        called.append(url)
        return raw, {"status": "fetched", "http_status": 200}

    monkeypatch.setattr(source_links, "_retrieve", fake_retrieve)
    output = tmp_path / "out"
    first = source_links.acquire_typed_cwl(snapshot, manifest, output, delay=0)
    second = source_links.acquire_typed_cwl(snapshot, manifest, output, delay=0)
    assert first["network_requests"] == 1
    assert second["network_requests"] == 0
    assert called == ["https://example.org/alpha.cwl"]
    rows = [json.loads(line) for line in (output / "typed-cwl-links.jsonl").read_text().splitlines()]
    assert [row["acquisition"]["status"] for row in rows] == ["fetched", "unsupported_link"]
    digest = hashlib.sha256(raw).hexdigest()
    assert (output / "sources" / f"{digest}.cwl").read_bytes() == raw


def test_url_rules_never_expand_directory_or_accept_local_target():
    assert source_links._source_url("https://github.com/org/repo/blob/main/tools/x.cwl") == (
        "https://raw.githubusercontent.com/org/repo/main/tools/x.cwl",
        "github_blob_to_raw",
    )
    assert source_links._source_url("https://github.com/org/repo/tree/main/tools")[0] is None
    assert source_links._source_url("https://127.0.0.1/tool.cwl")[0] is None
    assert source_links._source_url("http://example.org/tool.cwl")[0] is None


class _Response:
    def __init__(self, status, payload=b"", length=None):
        self.status = status
        self.payload = payload
        self.length = length
        self.read_calls = 0

    def getheader(self, name):
        if name == "Content-Length":
            return self.length
        return None

    def read(self, limit):
        self.read_calls += 1
        return self.payload[:limit]


class _Connection:
    def __init__(self, response):
        self.response = response
        self.closed = False

    def request(self, method, path, headers):
        assert method == "GET"
        assert path.endswith(".cwl")

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def test_network_refuses_redirects_and_private_dns(tmp_path, monkeypatch):
    monkeypatch.setattr(
        source_links.socket, "getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 443))]
    )
    raw, receipt = source_links._retrieve("https://example.org/tool.cwl", timeout=1)
    assert raw is None and receipt["status"] == "private_target_refused"

    monkeypatch.setattr(source_links, "_public_address", lambda _host: "93.184.215.14")
    response = _Response(302)
    connection = _Connection(response)
    monkeypatch.setattr(source_links, "_connect_pinned", lambda *_args: connection)
    raw, receipt = source_links._retrieve("https://example.org/tool.cwl", timeout=1)
    assert raw is None and receipt == {"status": "redirect_refused", "http_status": 302}
    assert response.read_calls == 0 and connection.closed


def test_oversize_and_failed_http_receipts(monkeypatch):
    monkeypatch.setattr(source_links, "_public_address", lambda _host: "93.184.215.14")
    for response, expected in [
        (_Response(200, length=str(source_links.MAX_SOURCE_BYTES + 1)), "too_large"),
        (_Response(200, payload=b"x" * (source_links.MAX_SOURCE_BYTES + 1)), "too_large"),
        (_Response(404), "http_error"),
    ]:
        connection = _Connection(response)
        monkeypatch.setattr(source_links, "_connect_pinned", lambda *_args: connection)
        raw, receipt = source_links._retrieve("https://example.org/tool.cwl", timeout=1)
        assert raw is None and receipt["status"] == expected
        assert connection.closed
    assert response.read_calls == 0


def test_tampered_cache_refetched_and_duplicate_links_share_one_request(tmp_path, monkeypatch):
    records = [
        {
            "biotoolsID": "some_record",
            "download": [
                {"type": ["Tool wrapper (CWL)"], "url": "https://example.org/tool.cwl"},
                {"type": ["Tool wrapper (CWL)"], "url": "https://example.org/tool.cwl"},
            ],
        }
    ]
    snapshot, manifest = _snapshot(tmp_path, records)
    output = tmp_path / "out"
    raw = b"cwlVersion: v1.2\nclass: CommandLineTool\ninputs: {}\noutputs: {}\n"
    calls = []

    def fake_retrieve(url, *, timeout):
        calls.append(url)
        return raw, {"status": "fetched", "http_status": 200}

    monkeypatch.setattr(source_links, "_retrieve", fake_retrieve)
    first = source_links.acquire_typed_cwl(snapshot, manifest, output, delay=0)
    assert first["typed_cwl_links"] == 2 and first["network_requests"] == 1
    assert len(calls) == 1
    digest = hashlib.sha256(raw).hexdigest()
    (output / "sources" / f"{digest}.cwl").write_bytes(b"tampered")
    second = source_links.acquire_typed_cwl(snapshot, manifest, output, delay=0)
    assert second["network_requests"] == 1 and len(calls) == 2
    assert (output / "sources" / f"{digest}.cwl").read_bytes() == raw
    rows = [json.loads(line) for line in (output / "typed-cwl-links.jsonl").read_text().splitlines()]
    assert len(rows) == 2 and all(row["acquisition"]["status"] == "fetched" for row in rows)


def test_failed_download_retained_and_retried(tmp_path, monkeypatch):
    snapshot, manifest = _snapshot(tmp_path)
    calls = []

    def fake_retrieve(url, *, timeout):
        calls.append(url)
        return None, {"status": "http_error", "http_status": 503}

    monkeypatch.setattr(source_links, "_retrieve", fake_retrieve)
    output = tmp_path / "out"
    first = source_links.acquire_typed_cwl(snapshot, manifest, output, delay=0)
    assert first["acquisition_status_counts"] == {"http_error": 1, "unsupported_link": 1}
    second = source_links.acquire_typed_cwl(snapshot, manifest, output, delay=0)
    assert second["network_requests"] == 1 and len(calls) == 2
