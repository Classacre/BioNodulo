from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SMALL_FILE_HASH_LIMIT = 1024 * 1024


class CacheStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def marker_path(self, cache_key: str) -> Path:
        return self.root / f"{cache_key}.json"

    def is_hit(self, cache_key: str, outputs: dict[str, Any]) -> bool:
        marker = self.read_marker(cache_key)
        if marker is None:
            return False
        marker_outputs = marker.get("outputs", outputs)
        for value in _flatten(marker_outputs):
            if isinstance(value, str) and _looks_like_generated_path(value) and not Path(value).exists():
                return False
        return True

    def read_marker(self, cache_key: str) -> dict[str, Any] | None:
        path = self.marker_path(cache_key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_marker(self, cache_key: str, payload: dict[str, Any]) -> None:
        self.marker_path(cache_key).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def cache_key_for_node(
    *,
    node_type: str,
    node_version: str,
    command_template: list[str] | None,
    params: dict[str, Any],
    inputs: dict[str, Any],
    upstream_cache_keys: list[str],
    change_fingerprint: Any | None = None,
    strong_hashing: bool = False,
) -> str:
    payload = {
        "node_type": node_type,
        "node_version": node_version,
        "command_template": command_template,
        "params": params,
        "inputs": fingerprint_value(inputs, strong_hashing=strong_hashing),
        "change_fingerprint": fingerprint_value(change_fingerprint, strong_hashing=strong_hashing),
        "upstream_cache_keys": upstream_cache_keys,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def fingerprint_value(value: Any, *, strong_hashing: bool = False) -> Any:
    if isinstance(value, dict):
        return {key: fingerprint_value(val, strong_hashing=strong_hashing) for key, val in sorted(value.items())}
    if isinstance(value, list):
        return [fingerprint_value(item, strong_hashing=strong_hashing) for item in value]
    if isinstance(value, tuple):
        return [fingerprint_value(item, strong_hashing=strong_hashing) for item in value]
    if isinstance(value, str) and _looks_like_path(value):
        if _looks_like_generated_path(value):
            path = Path(value)
            return {"generated_output": path.name}
        path = Path(value)
        if path.exists() and path.is_file():
            stat = path.stat()
            result: dict[str, Any] = {
                "path": str(path),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
            if strong_hashing or stat.st_size <= SMALL_FILE_HASH_LIMIT:
                result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            return result
        return {"path": value, "exists": False}
    return value


def _looks_like_path(value: str) -> bool:
    return any(token in value for token in ("/", "\\", ".")) or value.startswith("runs")


def _looks_like_generated_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return "/runs/" in normalized or normalized.startswith("runs/") or "/.bionodulo_cache/" in normalized


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
