"""Full-cohort OCI audit attempts eligible images once without execution claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.error import URLError

import pytest

from bionodulo.nodes.contract.cwl_oci import import_cwl_oci
from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.generation.oci import OciResolution
from scripts import audit_oci_reference_coverage as audit


def _source(pull: str | None) -> bytes:
    requirements = [{"class": "DockerRequirement", "dockerPull": pull}] if pull else []
    return json.dumps({
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "tool",
        "requirements": requirements,
        "inputs": {"reads": {"type": "File", "inputBinding": {"position": 1}}},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "output.fa"}}},
    }).encode()


def test_resolve_all_caches_success_and_failure_per_pull_without_widening_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = {
        "one.cwl": _source("example.org/ok:v1"),
        "two.cwl": _source("example.org/ok:v1"),
        "three.cwl": _source("example.org/offline:v1"),
        "four.cwl": _source("example.org/offline:v1"),
        "five.cwl": _source(None),
    }
    entries = []
    for descriptor, source in sources.items():
        (tmp_path / descriptor).write_bytes(source)
        entries.append({
            "descriptor": descriptor,
            "source_uri": f"https://example.org/{descriptor}",
            "source_sha256": "sha256:" + hashlib.sha256(source).hexdigest(),
            "status": "unsupported", "reason": "no machine-readable SoftwareRequirement",
        })
    coverage = {"source": {"tracked_cwl_descriptors": len(entries)}, "candidates": entries}
    calls: list[tuple[str, ExecutionPlatform]] = []

    def resolve(pull: str, *, platform: ExecutionPlatform) -> OciResolution:
        calls.append((pull, platform))
        if "offline" in pull:
            raise URLError("private URL must not appear in the report")
        return OciResolution(
            source_pull=pull,
            image_index="example.org/ok@sha256:" + "a" * 64,
            image_platform="example.org/ok@sha256:" + "b" * 64,
            platform=platform,
            index_media_type="application/vnd.oci.image.index.v1+json",
            manifest_media_type="application/vnd.oci.image.manifest.v1+json",
            config_digest="sha256:" + "c" * 64,
        )

    monkeypatch.setattr(audit, "resolve_oci_pull", resolve)
    result = audit.audit_oci_coverage(coverage, tmp_path, resolve_all=True)
    assert result["source_denominator"] == 5
    assert result["counts"] == {
        "oci_source_only_unverified": 2,
        "oci_resolution_failed": 2,
        "oci_profile_unsupported": 1,
    }
    assert calls == [
        ("example.org/ok:v1", ExecutionPlatform.LINUX_AMD64),
        ("example.org/offline:v1", ExecutionPlatform.LINUX_AMD64),
    ]
    assert result["registry_resolution"]["unique_source_pulls_attempted"] == 2
    assert result["registry_resolution"]["descriptor_attempts"] == 4
    assert [record.get("resolution_reused") for record in result["records"]] == [False, True, False, True, None]
    assert result["records"][2]["oci_reason"] == "registry network error: URLError"
    assert "private URL" not in json.dumps(result)
    assert all(record.get("oci_status") != "executable" for record in result["records"])

    selected = audit.audit_oci_coverage(coverage, tmp_path, resolve_descriptors=frozenset({"one.cwl"}))
    assert selected["counts"]["oci_image_unresolved"] == 3
    with pytest.raises(ValueError, match="mutually exclusive"):
        audit.audit_oci_coverage(coverage, tmp_path, resolve_all=True,
                                 resolve_descriptors=frozenset({"one.cwl"}))


def test_offline_catalog_projects_every_resolved_source_and_records_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_registry(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("projection must not access a registry")

    monkeypatch.setattr(audit, "resolve_oci_pull", forbidden_registry)
    records = []
    for descriptor, index_digest, platform_digest in (
        ("tools/accepted.cwl", "a" * 64, "a" * 64),
        ("tools/denied.cwl", "b" * 64, "c" * 64),
    ):
        source = _source("example.org/sequence:v1")
        contract = import_cwl_oci(
            source, source_uri=f"https://example.org/{descriptor}",
            image_index="example.org/sequence@sha256:" + index_digest,
            image_platform="example.org/sequence@sha256:" + platform_digest,
            platform=ExecutionPlatform.LINUX_AMD64,
        )
        records.append({
            "descriptor": descriptor,
            "source_sha256": contract.source_sha256,
            "oci_status": "oci_source_only_unverified",
            "resolution": {
                "image_index": contract.image_index,
                "image_platform": contract.image_platform,
            },
            "contract": contract.model_dump(mode="json"),
        })
    report = {
        "schema_version": 1, "source_revision": "a" * 40,
        "source_denominator": 2, "counts": {"oci_source_only_unverified": 2},
        "registry_resolution": {"mode": "all_structurally_eligible"},
        "records": records,
    }
    catalog, ledger = audit.project_oci_catalog(report)
    assert catalog["schema_version"] == 1
    assert len(catalog["specs"]) == 1
    assert catalog["specs"][0]["cwl_oci"]["verification"] == "source_only_unverified"
    assert catalog["specs"][0]["identity"]["machine_id"].startswith("generated_oci_tools_accepted_")
    assert ledger["counts"] == {"source_only_unverified": 1, "denied": 1}
    assert "multiarch index" in ledger["records"][1]["reason"]
    assert "execution proof" in ledger["boundary"]
    assert audit.project_oci_catalog(report) == (catalog, ledger)

    input_report = tmp_path / "resolution.json"
    input_report.write_text(json.dumps(report), encoding="utf-8")
    output_catalog = tmp_path / "catalog.json"
    output_ledger = tmp_path / "projection.json"
    assert audit.main([
        "--resolution-report", str(input_report),
        "--catalog-output", str(output_catalog),
        "--projection-output", str(output_ledger),
    ]) == 0
    assert json.loads(output_catalog.read_text(encoding="utf-8")) == catalog
    assert json.loads(output_ledger.read_text(encoding="utf-8")) == ledger
    assert b"\r\n" not in output_catalog.read_bytes()
    assert b"\r\n" not in output_ledger.read_bytes()
    with pytest.raises(ValueError, match="complete --resolve-all"):
        audit.project_oci_catalog({**report, "source_denominator": 3})
