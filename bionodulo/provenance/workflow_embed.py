"""
Workflow provenance embedding.

Embeds workflow JSON metadata into output files (PNG, JSON) and provides
extraction capabilities for provenance tracking.
"""

from __future__ import annotations

import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def embed_workflow_in_outputs(
    workflow: dict[str, Any],
    artifact_paths: list[dict[str, Any]] | list[str],
    custom_metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Embed workflow provenance into output files.

    Supports embedding into:
    - PNG files (via a custom tEXt chunk)
    - JSON files (via a ``_provenance`` comment field)
    - Text files (via a trailing comment block)

    Args:
        workflow: The workflow dict to embed.
        artifact_paths: List of artifact dicts (with ``path`` key) or
            plain file path strings.
        custom_metadata: Additional metadata to include alongside workflow.

    Returns:
        List of file paths that were successfully embedded.
    """
    provenance_payload = _build_provenance_payload(workflow, custom_metadata)
    embedded: list[str] = []

    for artifact in artifact_paths:
        path_str = artifact["path"] if isinstance(artifact, dict) else artifact
        path = Path(path_str)
        if not path.is_file():
            continue

        ext = path.suffix.lower()
        try:
            if ext == ".png":
                _embed_in_png(path, provenance_payload)
                embedded.append(str(path))
            elif ext == ".json":
                _embed_in_json(path, provenance_payload)
                embedded.append(str(path))
            elif ext in (".txt", ".log", ".csv", ".tsv", ".html", ".xml", ".md"):
                _embed_in_text(path, provenance_payload)
                embedded.append(str(path))
        except (OSError, ValueError, KeyError):
            continue

    return embedded


def extract_workflow(
    file_path: str | Path,
) -> dict[str, Any] | None:
    """Extract embedded workflow provenance from a file.

    Args:
        file_path: Path to the file to inspect.

    Returns:
        The embedded provenance dict, or *None* if no provenance was found.
    """
    path = Path(file_path)
    if not path.is_file():
        return None

    ext = path.suffix.lower()
    try:
        if ext == ".png":
            return _extract_from_png(path)
        elif ext == ".json":
            return _extract_from_json(path)
        elif ext in (".txt", ".log", ".csv", ".tsv", ".html", ".xml", ".md"):
            return _extract_from_text(path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        pass

    return None


def _embed_in_png(path: Path, payload: dict[str, Any]) -> None:
    """Embed provenance into a PNG file by adding a tEXt chunk."""
    data = path.read_bytes()
    provenance_text = json.dumps(payload, ensure_ascii=True)
    text_data = b"BioNodulo\x00" + provenance_text.encode("utf-8")
    chunk = _png_chunk(b"tEXt", text_data)
    ihdr_end = _find_ihdr_end(data)
    if ihdr_end == 0:
        raise ValueError("Invalid PNG: IHDR chunk not found")
    new_data = data[:ihdr_end] + chunk + data[ihdr_end:]
    path.write_bytes(new_data)


def _extract_from_png(path: Path) -> dict[str, Any] | None:
    """Extract provenance from a PNG tEXt chunk."""
    data = path.read_bytes()
    pos = 8  # Skip PNG signature
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"tEXt":
            text = chunk_data.decode("utf-8", errors="replace")
            if "BioNodulo\x00" in text:
                json_part = text.split("\x00", 1)[1]
                return json.loads(json_part)
    return None


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk with type and data (includes length + CRC)."""
    import zlib
    chunk = chunk_type + data
    crc = zlib.crc32(chunk) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)


def _find_ihdr_end(data: bytes) -> int:
    """Find the byte position right after the IHDR chunk in a PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        pos += 12 + length
        if chunk_type == b"IHDR":
            return pos
    return 0


def _embed_in_json(path: Path, payload: dict[str, Any]) -> None:
    """Embed provenance into a JSON file via a ``_provenance`` top-level key."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data["_provenance"] = payload
    else:
        data = {"_value": data, "_provenance": payload}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=True)


def _extract_from_json(path: Path) -> dict[str, Any] | None:
    """Extract provenance from a JSON ``_provenance`` key."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "_provenance" in data:
        return data["_provenance"]
    return None


def _embed_in_text(path: Path, payload: dict[str, Any]) -> None:
    """Embed provenance as a trailing comment block in a text file."""
    provenance_text = json.dumps(payload, ensure_ascii=True)
    comment_block = (
        "\n\n<!-- BioNodulo Provenance START -->\n"
        + provenance_text
        + "\n<!-- BioNodulo Provenance END -->\n"
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(comment_block)


def _extract_from_text(path: Path) -> dict[str, Any] | None:
    """Extract provenance from a trailing comment block in a text file."""
    content = path.read_text(encoding="utf-8")
    start_marker = "<!-- BioNodulo Provenance START -->"
    end_marker = "<!-- BioNodulo Provenance END -->"
    start_idx = content.rfind(start_marker)
    end_idx = content.rfind(end_marker)
    if start_idx >= 0 and end_idx > start_idx:
        json_text = content[start_idx + len(start_marker) : end_idx].strip()
        return json.loads(json_text)
    return None


def _build_provenance_payload(
    workflow: dict[str, Any],
    custom_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the provenance payload dict."""
    payload = {
        "workflow": workflow,
        "embedded_at": datetime.now(timezone.utc).isoformat(),
        "bionodulo_version": "Alpha 1.2",
    }
    if custom_metadata:
        payload["metadata"] = custom_metadata
    return payload
