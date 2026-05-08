from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

from bionodulo.workflow.schema import Workflow


TAG = "BIONODULO_WORKFLOW_JSON"


def embed_workflow_in_outputs(outputs: dict[str, Any], workflow: Workflow) -> list[dict[str, str]]:
    embedded: list[dict[str, str]] = []
    payload = json.dumps(workflow.model_dump(by_alias=True), separators=(",", ":"), default=str)
    for value in _flatten(outputs):
        if not isinstance(value, str):
            continue
        path = Path(value)
        if not path.exists() or not path.is_file():
            continue
        embedded.append(embed_workflow(path, payload))
    return embedded


def embed_workflow(path: Path, workflow_json: str) -> dict[str, str]:
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith((".vcf", ".sam")):
        _prepend_header(path, f"##{TAG}={workflow_json}\n")
        return {"path": str(path), "mode": "header"}
    sidecar = path.with_suffix(path.suffix + ".bionodulo.json")
    sidecar.write_text(workflow_json + "\n", encoding="utf-8")
    return {"path": str(path), "mode": "sidecar", "sidecar": str(sidecar)}


def extract_workflow(path: Path, *, content: str | None = None, content_bytes: bytes | None = None) -> dict[str, Any]:
    if content_bytes is not None or path.suffix.lower() in {".png"}:
        image_bytes = content_bytes if content_bytes is not None else path.read_bytes()
        workflow = _extract_png_workflow(image_bytes)
        if workflow is not None:
            return {"workflow": workflow, "source": "png_metadata"}
    if content_bytes is not None:
        text = content_bytes.decode("utf-8", errors="replace")
    else:
        text = content if content is not None else _read_text(path)
    for line in text.splitlines():
        if TAG in line:
            _, value = line.split("=", 1)
            return {"workflow": json.loads(value), "source": "header"}
    sidecar = path.with_suffix(path.suffix + ".bionodulo.json")
    if sidecar.exists():
        return {"workflow": json.loads(sidecar.read_text(encoding="utf-8")), "source": "sidecar", "sidecar": str(sidecar)}
    if path.suffix.lower() == ".json":
        return {"workflow": json.loads(text), "source": "json"}
    raise ValueError("No embedded BioNodulo workflow metadata found.")


def _extract_png_workflow(data: bytes) -> dict[str, Any] | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    offset = 8
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"tEXt":
            text = _decode_png_text(chunk_data)
        elif chunk_type == b"zTXt":
            text = _decode_png_ztxt(chunk_data)
        elif chunk_type == b"iTXt":
            text = _decode_png_itxt(chunk_data)
        else:
            continue
        workflow = _workflow_from_metadata_text(text)
        if workflow is not None:
            return workflow
    return None


def _decode_png_text(data: bytes) -> tuple[str, str] | None:
    if b"\x00" not in data:
        return None
    key, value = data.split(b"\x00", 1)
    return key.decode("latin-1", errors="replace"), value.decode("utf-8", errors="replace")


def _decode_png_ztxt(data: bytes) -> tuple[str, str] | None:
    if b"\x00" not in data:
        return None
    key, rest = data.split(b"\x00", 1)
    if not rest:
        return None
    try:
        value = zlib.decompress(rest[1:]).decode("utf-8", errors="replace")
    except zlib.error:
        return None
    return key.decode("latin-1", errors="replace"), value


def _decode_png_itxt(data: bytes) -> tuple[str, str] | None:
    parts = data.split(b"\x00", 5)
    if len(parts) < 6:
        return None
    key, compression_flag, compression_method, _language, _translated, value = parts
    try:
        text_bytes = zlib.decompress(value) if compression_flag == b"\x01" and compression_method == b"\x00" else value
    except zlib.error:
        return None
    return key.decode("latin-1", errors="replace"), text_bytes.decode("utf-8", errors="replace")


def _workflow_from_metadata_text(entry: tuple[str, str] | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    key, value = entry
    if TAG in value:
        _, workflow_json = value.split("=", 1)
        return json.loads(workflow_json)
    if key.lower() in {"workflow", "bionodulo_workflow", TAG.lower()}:
        payload = json.loads(value)
        if isinstance(payload, dict) and "workflow" in payload and isinstance(payload["workflow"], dict):
            return payload["workflow"]
        if isinstance(payload, dict):
            return payload
    return None


def _prepend_header(path: Path, header: str) -> None:
    existing = path.read_text(encoding="utf-8", errors="replace")
    if TAG in existing[:10000]:
        return
    path.write_text(header + existing, encoding="utf-8")


def _read_text(path: Path) -> str:
    if path.suffix.lower() in {".bam", ".cram"}:
        try:
            import pysam  # type: ignore

            with pysam.AlignmentFile(str(path), "rb") as alignment:
                return str(alignment.header)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, dict):
        items: list[Any] = []
        for nested in value.values():
            items.extend(_flatten(nested))
        return items
    if isinstance(value, (list, tuple)):
        items = []
        for nested in value:
            items.extend(_flatten(nested))
        return items
    return [value]
