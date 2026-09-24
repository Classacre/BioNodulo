"""Whole-registry discovery uses explicit metadata and preserves every gap."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

from bionodulo.nodes.generation.discovery import (
    DiscoveryError,
    discover_record,
    discover_registry,
    discover_iuc_with_official_parser,
    inventory_iuc_repository,
)


def _snapshot(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    snapshot = tmp_path / "registry.jsonl"
    content = b"".join(
        json.dumps(item, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for item in records
    )
    snapshot.write_bytes(content)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "complete": True,
                "records": len(records),
                "sha256": hashlib.sha256(content).hexdigest(),
                "source": "https://bio.tools/api/tool/",
                "completed_at": "2026-09-19T14:30:04+00:00",
            }
        ),
        encoding="utf-8",
    )
    return snapshot, manifest


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _iuc_fixture(tmp_path: Path):
    root = tmp_path / "tools-iuc"
    tool = root / "tools" / "explicit_repo"
    tool.mkdir(parents=True)
    (tool / ".shed.yml").write_text("name: explicit_repo\n", encoding="utf-8")
    (tool / "tool.xml").write_text('<tool id="fixture" version="1.0"><macros><import>macros.xml</import></macros></tool>\n', encoding="utf-8")
    (tool / "macros.xml").write_text("<macros/>\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "user.email", "test@example.test")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    revision = _git(root, "rev-parse", "HEAD")
    return inventory_iuc_repository(
        root,
        revision=revision,
        source_url="https://github.com/galaxyproject/tools-iuc",
    )


def test_explicit_metadata_discovers_sources_without_name_guessing(tmp_path: Path) -> None:
    iuc = _iuc_fixture(tmp_path)
    records = [
        {
            "biotoolsID": "explicit",
            "name": "Same Display Name",
            "toolType": ["Command-line tool"],
            "download": [
                {"type": "Tool wrapper (CWL)", "url": "https://example.test/tool.cwl"},
                {
                    "type": "Command-line specification",
                    "url": "https://example.test/boutiques/descriptor.json",
                },
                {"type": "Software package", "url": "https://pypi.org/project/explicit-package/"},
            ],
            "link": [{"type": ["Repository"], "url": "https://github.com/example/explicit"}],
        },
        {
            "biotoolsID": "same_name_without_evidence",
            "name": "Same Display Name",
            "toolType": ["Command-line tool"],
        },
        {
            "biotoolsID": "iuc_explicit",
            "toolType": ["Command-line tool"],
            "link": [
                {
                    "type": ["Galaxy service"],
                    "url": "https://toolshed.g2.bx.psu.edu/repos/iuc/explicit_repo/tool/1.0",
                }
            ],
        },
        {
            "biotoolsID": "api",
            "documentation": [
                {"type": ["API documentation"], "url": "https://example.test/openapi.json"}
            ],
        },
    ]
    snapshot, manifest = _snapshot(tmp_path, records)
    summary = discover_registry(snapshot, manifest, tmp_path / "output", iuc=iuc)
    assert summary["registry"]["records"] == 4
    assert sum(summary["status_counts"].values()) == 4
    lines = [json.loads(line) for line in (tmp_path / "output/registry-discovery.jsonl").read_text().splitlines()]
    by_id = {item["biotools_accession"]: item for item in lines}
    assert {item.get("format") for item in by_id["explicit"]["source_candidates"]} >= {
        "cwl",
        "boutiques",
    }
    package = next(item for item in by_id["explicit"]["source_candidates"] if item["kind"] == "package")
    assert package["ecosystem"] == "pypi" and package["package_id"] == "explicit-package"
    assert by_id["same_name_without_evidence"]["source_candidates"] == []
    assert by_id["same_name_without_evidence"]["status"] == "no_structured_source"
    pinned = next(
        item for item in by_id["iuc_explicit"]["source_candidates"]
        if item["kind"] == "pinned_repository_descriptors"
    )
    assert pinned["repository_name"] == "explicit_repo"
    assert pinned["descriptor_count"] == 2
    assert pinned["semantics_status"] == "not_parsed_requires_official_galaxy_parser"
    assert any(item.get("format") == "openapi" for item in by_id["api"]["source_candidates"])


def test_iuc_github_join_requires_explicit_repository_url(tmp_path: Path) -> None:
    iuc = _iuc_fixture(tmp_path)
    exact = discover_record(
        {
            "biotoolsID": "exact",
            "homepage": "https://github.com/galaxyproject/tools-iuc/tree/main/tools/explicit_repo",
        },
        iuc=iuc,
    )
    guessed = discover_record(
        {"biotoolsID": "explicit_repo", "name": "explicit repo"},
        iuc=iuc,
    )
    assert any(item["kind"] == "pinned_repository_descriptors" for item in exact["source_candidates"])
    assert guessed["source_candidates"] == []


def test_bad_snapshot_never_publishes_partial_audit(tmp_path: Path) -> None:
    snapshot, manifest = _snapshot(tmp_path, [{"biotoolsID": "one"}])
    value = json.loads(manifest.read_text())
    value["sha256"] = "0" * 64
    manifest.write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "output"
    with pytest.raises(DiscoveryError, match="digest or record count"):
        discover_registry(snapshot, manifest, output)
    assert not (output / "registry-discovery.jsonl").exists()


def test_official_iuc_parser_receipts_closure_and_exact_xref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _iuc_fixture(tmp_path)

    class FakeSource:
        def __init__(self, path: Path) -> None:
            if path.name != "tool.xml":
                raise ValueError("not a Galaxy tool wrapper")
            self.macro_paths = ("macros.xml",)

        def parse_xrefs(self):
            return [{"type": "bio.tools", "value": "ExactAccession"}]

        def parse_id(self):
            return "fixture"

        def parse_tests_to_dict(self):
            return [{"inputs": {"input": "fixture.txt"}, "outputs": ["out"]}]

    class FakeModel:
        def model_dump(self, *, mode: str, by_alias: bool):
            assert mode == "json" and by_alias is True
            return {
                "id": "fixture",
                "name": "Fixture",
                "version": "1.0",
                "profile": "24.0",
                "inputs": [{"name": "input", "type": "data"}],
                "outputs": [{"name": "out", "type": "data"}],
                "stdio": [],
                "requirements": [{"name": "fixture", "version": "1.0"}],
            }

    galaxy = types.ModuleType("galaxy")
    tool_util = types.ModuleType("galaxy.tool_util")
    parser = types.ModuleType("galaxy.tool_util.parser")
    model_factory = types.ModuleType("galaxy.tool_util.model_factory")
    parser.get_tool_source = lambda path: FakeSource(Path(path))
    model_factory.parse_tool = lambda source: FakeModel()
    monkeypatch.setitem(sys.modules, "galaxy", galaxy)
    monkeypatch.setitem(sys.modules, "galaxy.tool_util", tool_util)
    monkeypatch.setitem(sys.modules, "galaxy.tool_util.parser", parser)
    monkeypatch.setitem(sys.modules, "galaxy.tool_util.model_factory", model_factory)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "26.1.1")

    output = tmp_path / "official-output"
    summary = discover_iuc_with_official_parser(
        inventory,
        tmp_path / "tools-iuc",
        tmp_path / "staging",
        output,
        registry_accessions={"exactaccession"},
    )

    assert summary["status_counts"] == {"parsed": 1, "parser_error": 1}
    assert summary["registry_matched_xrefs"] == 1
    rows = [json.loads(line) for line in (output / "galaxy-iuc-parser.jsonl").read_text().splitlines()]
    parsed = next(item for item in rows if item["status"] == "parsed")
    assert [item["path"] for item in parsed["source_closure"]] == [
        "tools/explicit_repo/tool.xml",
        "tools/explicit_repo/macros.xml",
    ]
    assert all(item["sha256"].startswith("sha256:") for item in parsed["source_closure"])
    assert parsed["gap_states"] == [
        "not_execution_admitted",
        "galaxy_runtime_adapter_not_implemented",
        "galaxy_test_and_data_table_closure_not_inventoried",
    ]
