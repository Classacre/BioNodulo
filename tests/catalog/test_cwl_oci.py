"""Digest-locked OCI admission never infers registry identity or execution proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bionodulo.nodes.contract.cwl_oci import CwlOciImportError, import_cwl_oci, import_cwl_oci_spec
from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.generation.oci import OciResolutionError, resolve_oci_pull
from scripts.audit_oci_reference_coverage import audit_oci_coverage


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _source(pull: str = "example.org/lab/sequence:v1") -> bytes:
    return json.dumps({
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "seqtool",
        "requirements": [{"class": "DockerRequirement", "dockerPull": pull}],
        "inputs": {"reads": {"type": "File", "inputBinding": {"position": 1}}},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "output.fa"}}},
    }).encode()


def _contract(source: bytes | None = None):
    return import_cwl_oci(
        source or _source(),
        source_uri="https://example.org/tool.cwl",
        image_index="example.org/lab/sequence@sha256:" + "a" * 64,
        image_platform="example.org/lab/sequence@sha256:" + "b" * 64,
        platform=ExecutionPlatform.LINUX_AMD64,
    )


def test_oci_contract_retains_source_and_rewrites_only_effective_image() -> None:
    contract = _contract()
    assert contract.source_sha256 == _digest(_source())
    assert contract.verification == "source_only_unverified"
    assert contract.inspection.outputs[0].port_id == "result"
    effective, digest = contract.effective_source()
    assert b"example.org/lab/sequence@sha256:" + b"b" * 64 in effective
    assert digest == _digest(effective)
    assert b"example.org/lab/sequence:v1" in contract.source_text.encode()


def test_multiarch_resolution_remains_source_only_without_retained_linkage() -> None:
    with pytest.raises(CwlOciImportError, match="multiarch index requires retained index-to-platform proof"):
        import_cwl_oci_spec(_contract(), node_id="sequence")


@pytest.mark.parametrize("image", ["example.org/lab/sequence:v1", "other.org/lab/sequence@sha256:" + "a" * 64])
def test_oci_contract_rejects_mutable_or_different_image(image: str) -> None:
    with pytest.raises(ValueError, match="digest|repository"):
        import_cwl_oci(
            _source(), source_uri="https://example.org/tool.cwl",
            image_index=image, image_platform="example.org/lab/sequence@sha256:" + "b" * 64,
            platform=ExecutionPlatform.LINUX_AMD64,
        )


def test_oci_contract_rejects_missing_source_docker_pull() -> None:
    with pytest.raises(CwlOciImportError, match="DockerRequirement.dockerPull"):
        _contract(_source().replace(b'"dockerPull": "example.org/lab/sequence:v1"', b'"dockerImageId": "x"'))


def test_oci_contract_cannot_rebind_a_source_pinned_digest() -> None:
    source = _source("example.org/lab/sequence@sha256:" + "c" * 64)
    with pytest.raises(ValueError, match="source-declared image digest differs"):
        _contract(source)


def test_public_registry_resolution_verifies_index_manifest_and_config() -> None:
    configuration = json.dumps({"os": "linux", "architecture": "amd64"}).encode()
    config_digest = _digest(configuration)
    manifest = json.dumps({
        "schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"digest": config_digest}, "layers": [],
    }).encode()
    manifest_digest = _digest(manifest)
    index = json.dumps({
        "schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [{"digest": manifest_digest, "platform": {"os": "linux", "architecture": "amd64"}}],
    }).encode()
    metadata = {
        "/manifests/v1": index,
        "/manifests/" + manifest_digest: manifest,
        "/blobs/" + config_digest: configuration,
    }

    def fetch(url: str, _accept: str) -> bytes:
        return next(content for suffix, content in metadata.items() if url.endswith(suffix))

    resolution = resolve_oci_pull("example.org/lab/sequence:v1", platform=ExecutionPlatform.LINUX_AMD64, fetch=fetch)
    assert resolution.image_index == "example.org/lab/sequence@" + _digest(index)
    assert resolution.image_platform == "example.org/lab/sequence@" + manifest_digest
    assert resolution.provenance == "registry_metadata_only"
    metadata["/blobs/" + config_digest] = b"{}"
    with pytest.raises(OciResolutionError, match="digest does not match"):
        resolve_oci_pull("example.org/lab/sequence:v1", platform=ExecutionPlatform.LINUX_AMD64, fetch=fetch)


def test_complete_source_ledger_retains_unresolved_status_and_rejects_drift(tmp_path: Path) -> None:
    repository = tmp_path / "upstream"
    repository.mkdir()
    source = _source()
    (repository / "tool.cwl").write_bytes(source)
    coverage = {
        "source": {"revision": "a" * 40},
        "candidates": [{
            "descriptor": "tool.cwl", "source_uri": "https://example.org/tool.cwl",
            "source_sha256": _digest(source), "status": "unsupported",
            "reason": "no machine-readable SoftwareRequirement",
        }],
    }
    result = audit_oci_coverage(coverage, repository)
    assert result["source_denominator"] == 1
    assert result["counts"] == {"oci_image_unresolved": 1}
    assert "contract" not in result["records"][0]
    (repository / "tool.cwl").write_bytes(source + b"\n")
    with pytest.raises(ValueError, match="differs from pinned coverage"):
        audit_oci_coverage(coverage, repository)
