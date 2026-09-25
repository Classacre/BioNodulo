"""Complete-registry acquisition must never silently publish a partial crawl."""
import hashlib
import json
import sqlite3

import pytest

from scripts import link_biotools, sync_biotools_registry as registry
from scripts import audit_biotools_coverage as coverage
from scripts.infer_contracts import _format_fragments


def records(start, stop):
    return [{"biotoolsID": f"tool{i:03d}", "name": f"Tool {i}",
             "description": "Sequence alignment metadata"} for i in range(start, stop)]


def test_sync_all_pages_and_search_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.time, "sleep", lambda _: None)
    pages = {1: {"count": 101, "list": records(0, 100)},
             2: {"count": 101, "list": records(100, 101)}}
    calls = []

    def fetch(page):
        calls.append(page)
        return pages[page]

    monkeypatch.setattr(registry, "fetch_page", fetch)
    manifest = registry.sync(tmp_path)
    assert calls == [1, 2, 1]
    assert manifest["records"] == manifest["unique_casefold_ids"] == 101
    assert manifest["complete"] is True
    contents = (tmp_path / "registry.jsonl").read_bytes()
    assert manifest["sha256"] == hashlib.sha256(contents).hexdigest()
    assert len(contents.splitlines()) == 101
    matches = registry.search(tmp_path / "registry.sqlite", "alignment", 200)
    assert len(matches) == 101
    assert all(match["execution_status"] == "metadata_only" for match in matches)
    assert registry.search(tmp_path / "registry.sqlite", "") == []


@pytest.mark.parametrize("failure", ["duplicate", "missing", "count_changed"])
def test_failed_crawl_preserves_previous_published_snapshot(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(registry.time, "sleep", lambda _: None)
    previous = b"previous verified snapshot\n"
    (tmp_path / "registry.jsonl").write_bytes(previous)
    (tmp_path / "manifest.json").write_text('{"complete":true}')
    second = {"count": 101, "list": records(100, 101)}
    if failure == "duplicate":
        second["list"][0]["biotoolsID"] = "TOOL000"
    elif failure == "missing":
        second["list"] = []
    else:
        second["count"] = 102
    monkeypatch.setattr(registry, "fetch_page", lambda page:
                        {"count": 101, "list": records(0, 100)} if page == 1 else second)
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        registry.sync(tmp_path)
    assert (tmp_path / "registry.jsonl").read_bytes() == previous
    assert json.loads((tmp_path / "manifest.json").read_text()) == {"complete": True}


def test_linker_reads_canonical_edam_operation_data_and_documentation():
    result = link_biotools.summarize({
        "biotoolsID": "aligner", "documentation": [{"url": "https://example.org/manual", "type": ["Manual"]}],
        "function": [{"operation": [{"uri": "http://edamontology.org/operation_0292"}],
                      "input": [{"data": {"uri": "http://edamontology.org/data_2044"},
                                 "format": [{"uri": "http://edamontology.org/format_1930"}]}]}],
    })
    assert result["functions"][0]["operations"] == ["http://edamontology.org/operation_0292"]
    assert result["functions"][0]["inputs"][0]["data"] == ["http://edamontology.org/data_2044"]
    assert result["documentation"] == "https://example.org/manual"
    assert _format_fragments({"function": [{"input": [{"format": [
        {"uri": "http://edamontology.org/format_2572"}]}]}]}) == {"format_2572"}


def test_ledger_covers_every_record_without_promoting_name_candidates(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    nodes = root / "bionodulo/nodes"
    (nodes / "generated").mkdir(parents=True)
    index = {"wrapped": "builtin.demo.node", "candidate": "builtin.other.node"}
    (nodes / "node_index.json").write_text(json.dumps(index))
    (nodes / "node_metadata.json").write_text(json.dumps({key: {} for key in index}))
    (nodes / "generated/catalog.operational.json").write_text(json.dumps({"nodes": {}, "summary": {}}))
    monkeypatch.setattr(coverage, "declared_links", lambda _: {"wrapped": "linked"})
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "registry.jsonl").write_text(''.join(json.dumps({"biotoolsID": id, "name": id}) + '\n'
                                                  for id in ['linked', 'candidate', 'unmapped']))
    manifest = {"complete": True, "records": 3, "sha256": coverage.sha256(snapshot / "registry.jsonl"),
                "source": registry.API, "license": "CC-BY-4.0", "completed_at": "2026-09-19"}
    (snapshot / "manifest.json").write_text(json.dumps(manifest))
    output = tmp_path / "output"
    summary = coverage.audit(snapshot, output, root=root)
    assert summary["ledger_rows"] == summary["registry_records_compared"] == 3
    assert summary["counts"]["with_declared_node_links"] == 1
    assert summary["counts"]["metadata_only_no_declared_node"] == 2
    ledger = [json.loads(line) for line in (output / "biotools-gap-ledger.jsonl").read_text().splitlines()]
    assert ledger[1]["candidate_node_ids_requires_review"] == ["candidate"]
    assert ledger[1]["catalog_status"] == "metadata_only"
    assert summary["registry_entries_execution_validated_this_catalog_audit"] == 0
    discovery = json.loads((output / "biotools-discovery.json").read_text())
    assert len(discovery["tools"]) == 3
    assert discovery["tools"][1]["nodes"] == []
    repeated = coverage.audit(snapshot, tmp_path / "repeated", root=root)
    assert repeated["evidence_files"] == summary["evidence_files"]
