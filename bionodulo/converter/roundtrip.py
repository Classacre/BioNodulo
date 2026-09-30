"""Preserve the original graph only while an exported native source is unchanged.

These checks detect edits and damaged transport; they are not signatures or a
claim that arbitrary foreign workflows are scientifically equivalent.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
from typing import Any

_MARKER = "BIONODULO_ROUNDTRIP_V1 "
_DOCUMENT_KEY = "bionodulo_roundtrip"
_MANIFEST = "bionodulo-roundtrip.json"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(source: str, workflow: dict[str, Any]) -> str:
    return hashlib.sha256((source + "\n" + _canonical(workflow)).encode("utf-8")).hexdigest()


def _envelope(source: str, workflow: dict[str, Any]) -> dict[str, Any]:
    return {"version": 1, "workflow": copy.deepcopy(workflow), "sha256": _digest(source, workflow)}


def _restore(source: str, envelope: Any) -> dict[str, Any]:
    if not isinstance(envelope, dict) or type(envelope.get("version")) is not int or envelope["version"] != 1:
        raise ValueError("Unsupported BioNodulo round-trip metadata version")
    workflow = envelope.get("workflow")
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list) or not isinstance(workflow.get("edges"), list):
        raise ValueError("Invalid BioNodulo round-trip workflow metadata")
    if envelope.get("sha256") != _digest(source, workflow):
        raise ValueError(
            "Exported source or BioNodulo round-trip metadata changed; "
            "refusing to restore a stale workflow graph"
        )
    return copy.deepcopy(workflow)


def stamp_workflow_source(content: str, workflow: dict[str, Any], comment_prefix: str) -> str:
    """Append one native comment; keep a leading shebang in its original place."""
    if comment_prefix not in {"#", "//"}:
        raise ValueError("Unsupported native comment prefix")
    source = content.replace("\r\n", "\n").rstrip("\n") + "\n"
    if any(line.startswith(f"{comment_prefix} BIONODULO_ROUNDTRIP_") for line in source.splitlines()):
        raise ValueError("Native source already contains BioNodulo round-trip metadata")
    payload = base64.b64encode(_canonical(_envelope(source, workflow)).encode("utf-8")).decode("ascii")
    return source + f"{comment_prefix} {_MARKER}{payload}\n"


def restore_workflow_source(content: str, comment_prefix: str) -> dict[str, Any] | None:
    """Return None for an unmarked foreign source; reject changed marked exports."""
    if comment_prefix not in {"#", "//"}:
        raise ValueError("Unsupported native comment prefix")
    lines = content.replace("\r\n", "\n").splitlines(keepends=True)
    marker_lines = [i for i, line in enumerate(lines) if line.startswith(f"{comment_prefix} BIONODULO_ROUNDTRIP_")]
    if not marker_lines:
        return None
    if len(marker_lines) != 1:
        raise ValueError("Duplicate BioNodulo round-trip metadata")
    index = marker_lines[0]
    if any(line.strip() for line in lines[index + 1:]):
        raise ValueError("Native source changed after BioNodulo round-trip metadata")
    marker = lines[index].rstrip("\n")
    prefix = f"{comment_prefix} {_MARKER}"
    if not marker.startswith(prefix):
        raise ValueError("Unsupported BioNodulo round-trip metadata version")
    try:
        envelope = json.loads(base64.b64decode(marker[len(prefix):], validate=True).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise ValueError("Invalid BioNodulo round-trip metadata") from exc
    return _restore("".join(lines[:index]), envelope)


def stamp_workflow_document(
    document: dict[str, Any], workflow: dict[str, Any], metadata_key: str = _DOCUMENT_KEY,
) -> dict[str, Any]:
    """Preserve a JSON export such as Galaxy without mutating its source dict."""
    if metadata_key in document:
        raise ValueError("Document already contains BioNodulo round-trip metadata")
    result = copy.deepcopy(document)
    result[metadata_key] = _envelope(_canonical(document), workflow)
    return result


def restore_workflow_document(
    document: dict[str, Any], metadata_key: str = _DOCUMENT_KEY,
) -> dict[str, Any] | None:
    if metadata_key not in document:
        return None
    source = {key: value for key, value in document.items() if key != metadata_key}
    return _restore(_canonical(source), document[metadata_key])


def stamp_workflow_bundle(
    files: dict[str, str], workflow: dict[str, Any], manifest_name: str = _MANIFEST,
) -> dict[str, str]:
    """Use a sidecar so the CWL documents stay valid standard CWL."""
    if manifest_name in files:
        raise ValueError("Bundle already contains a BioNodulo round-trip manifest")
    source = {name: value.replace("\r\n", "\n") for name, value in files.items()}
    return {**files, manifest_name: _canonical(_envelope(_canonical(source), workflow)) + "\n"}


def restore_workflow_bundle(
    files: dict[str, str], manifest_name: str = _MANIFEST,
) -> dict[str, Any] | None:
    if manifest_name not in files:
        return None
    source = {name: value.replace("\r\n", "\n") for name, value in files.items() if name != manifest_name}
    try:
        envelope = json.loads(files[manifest_name])
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid BioNodulo round-trip manifest") from exc
    return _restore(_canonical(source), envelope)
