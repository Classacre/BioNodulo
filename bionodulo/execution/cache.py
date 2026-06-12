"""
CacheStore for workflow result caching.

Provides deterministic cache key generation and persistent caching of
node execution results based on parameters, inputs, and upstream cache keys.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from diskcache import Cache as DiskCache

from bionodulo.core.credentials import redact_tree


def _marker_memory_limit() -> int:
    try:
        return max(128, int(os.environ.get("BIONODULO_CACHE_MARKER_MEMORY_LIMIT", "8192")))
    except ValueError:
        return 8192


class CacheStore:
    """Persistent cache store for workflow node execution results.

    Each cached entry stores metadata (key, inputs, params, outputs) in
    diskcache. Legacy ``.marker.json`` files are still read so older cache
    directories remain valid.

    Cache keys are SHA-256 hashes over the node's type, parameters,
    resolved inputs, and upstream cache keys, making them deterministic
    and sensitive to any change in the execution graph.
    """

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._metadata = DiskCache(str(self.cache_dir / "metadata"))
        self._known_limit = _marker_memory_limit()
        self._known_markers: OrderedDict[str, None] = OrderedDict()
        for key in self._metadata.iterkeys():
            self._remember(str(key))
        for path in self.cache_dir.glob("*.marker.json"):
            if path.is_file():
                self._remember(path.name.removesuffix(".marker.json"))

    def _marker_path(self, cache_key: str) -> Path:
        """Return the path to the marker file for *cache_key*."""
        return self.cache_dir / f"{cache_key}.marker.json"

    def _remember(self, cache_key: str) -> None:
        """Track a hot marker key without letting memory grow forever."""
        if cache_key in self._known_markers:
            self._known_markers.move_to_end(cache_key)
        self._known_markers[cache_key] = None
        while len(self._known_markers) > self._known_limit:
            self._known_markers.popitem(last=False)

    def _forget(self, cache_key: str) -> None:
        self._known_markers.pop(cache_key, None)

    def _is_remembered(self, cache_key: str) -> bool:
        if cache_key not in self._known_markers:
            return False
        self._known_markers.move_to_end(cache_key)
        return True

    def cache_key_for_node(
        self,
        node_id: str,
        node_type: str,
        params: dict[str, Any],
        inputs: dict[str, Any],
        upstream_keys: dict[str, str | None],
        tool_version: str | None = None,
        input_fingerprints: dict[str, Any] | None = None,
    ) -> str:
        """Generate a deterministic cache key for a node execution.

        The key incorporates:
        - ``node_type`` (so two nodes of different types with the same
          parameters do not collide)
        - ``params`` (sorted JSON)
        - ``inputs`` (sorted JSON of resolved input values)
        - ``upstream_keys`` (sorted mapping of input edge to upstream cache key)
        - ``tool_version`` (the node's declared version, when provided, so a
          node-implementation change invalidates stale results)
        - ``input_fingerprints`` (content fingerprints of input *files*, so the
          cache is content-addressed rather than path-addressed — editing a
          file in place no longer yields a false hit)

        Args:
            node_id: Unique node identifier (for logging, not part of key).
            node_type: The node's type / kind.
            params: Node parameters after defaults have been filled.
            inputs: Resolved input values from upstream nodes.
            upstream_keys: Mapping from input edge name to the cache key of
                the upstream node that produced it (or *None*).
            tool_version: Optional node/tool version string.
            input_fingerprints: Optional mapping of input identifier to a
                content fingerprint (see :meth:`fingerprint_inputs`).

        Returns:
            A 64-character hex SHA-256 string.
        """
        key_obj: dict[str, Any] = {
            "node_type": node_type,
            "params": _sorted_json(params),
            "inputs": _sorted_json(inputs),
            "upstream_keys": _sorted_json(upstream_keys),
        }
        # Only add the newer fields when present so keys (and unit tests that
        # call this directly without them) stay stable for path-only inputs.
        if tool_version is not None:
            key_obj["tool_version"] = tool_version
        if input_fingerprints:
            key_obj["input_fingerprints"] = _sorted_json(input_fingerprints)
        payload = json.dumps(
            key_obj,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def fingerprint_inputs(values: dict[str, Any] | None, mode: str = "fast") -> dict[str, str]:
        """Map any input value that resolves to an existing file to a fingerprint.

        ``mode`` selects the trade-off:
        - ``"fast"`` (default): ``size`` + ``mtime_ns`` — cheap, like make /
          Snakemake's default. Detects in-place edits without reading the file.
        - ``"strong"``: a SHA-256 of the file contents — robust against
          mtime-only changes, but reads every input (can be slow for the large
          files common in bioinformatics).
        - ``"off"``: no fingerprinting (legacy path-only behaviour).

        Nested lists/tuples/dicts are walked so multi-file ports are covered.
        """
        if not values or mode == "off":
            return {}

        result: dict[str, str] = {}

        def _fingerprint(path: str) -> str | None:
            try:
                stat = os.stat(path)
            except OSError:
                return None
            if mode == "strong":
                try:
                    digest = hashlib.sha256()
                    with open(path, "rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    return f"sha256:{digest.hexdigest()}"
                except OSError:
                    return None
            return f"fast:{stat.st_size}:{stat.st_mtime_ns}"

        def _walk(prefix: str, value: Any) -> None:
            if isinstance(value, str):
                # Bound the length so we never stat absurd blobs, and only treat
                # values that are actually existing files as content inputs.
                if value and len(value) < 4096:
                    try:
                        is_file = os.path.isfile(value)
                    except (OSError, ValueError):
                        is_file = False
                    if is_file:
                        fingerprint = _fingerprint(value)
                        if fingerprint is not None:
                            result[prefix] = fingerprint
            elif isinstance(value, (list, tuple)):
                for index, item in enumerate(value):
                    _walk(f"{prefix}[{index}]", item)
            elif isinstance(value, dict):
                for key, item in value.items():
                    _walk(f"{prefix}.{key}", item)

        for key, value in values.items():
            _walk(str(key), value)
        return result

    def is_hit(self, cache_key: str) -> bool:
        """Return *True* if a non-expired cached result exists for *cache_key*."""
        return self.read_marker(cache_key) is not None

    def read_marker(self, cache_key: str) -> dict[str, Any] | None:
        """Read and return the cached metadata for *cache_key*, or *None*."""
        marker = self._metadata.get(cache_key, default=None)
        if isinstance(marker, dict):
            if self._is_expired(marker):
                self._delete_marker(cache_key)
                return None
            self._remember(cache_key)
            return marker
        path = self._marker_path(cache_key)
        if not path.is_file():
            self._forget(cache_key)
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                marker = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(marker, dict):
            return None
        if self._is_expired(marker):
            self._delete_marker(cache_key)
            return None
        self._remember(cache_key)
        return marker

    def write_marker(
        self,
        cache_key: str,
        outputs: dict[str, Any],
        params: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        upstream_keys: dict[str, str | None] | None = None,
        inactive_outputs: list[str] | None = None,
        skip_downstream: list[str] | None = None,
    ) -> None:
        """Write metadata marker for a successful node execution.

        Args:
            cache_key: The cache key returned by :meth:`cache_key_for_node`.
            outputs: Mapping of output port names to final file paths / values.
            params: Node parameters (stored for provenance).
            inputs: Resolved inputs (stored for provenance).
            upstream_keys: Upstream cache keys (stored for provenance).
            inactive_outputs: Flow-control output ports that should not execute downstream branches.
            skip_downstream: Downstream node IDs that should be skipped when this cached result is reused.
        """
        marker = {
            "cache_key": cache_key,
            "outputs": outputs,
            "params": redact_tree(params or {}),
            "inputs": redact_tree(inputs or {}),
            "upstream_keys": upstream_keys or {},
        }
        if inactive_outputs is not None:
            marker["inactive_outputs"] = inactive_outputs
        if skip_downstream is not None:
            marker["skip_downstream"] = skip_downstream
        self._metadata.set(cache_key, marker)
        self._remember(cache_key)

    def write_marker_with_ttl(
        self,
        cache_key: str,
        outputs: dict[str, Any],
        params: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        upstream_keys: dict[str, str | None] | None = None,
        ttl_seconds: int | float | None = None,
        inactive_outputs: list[str] | None = None,
        skip_downstream: list[str] | None = None,
    ) -> None:
        """Write metadata marker with an optional TTL expiration."""
        self.write_marker(
            cache_key,
            outputs=outputs,
            params=params,
            inputs=inputs,
            upstream_keys=upstream_keys,
            inactive_outputs=inactive_outputs,
            skip_downstream=skip_downstream,
        )
        if ttl_seconds is None:
            return
        marker = self._metadata.get(cache_key, default=None)
        if not isinstance(marker, dict):
            return
        marker["expires_at"] = time.time() + float(ttl_seconds)
        self._metadata.set(cache_key, marker)
        self._remember(cache_key)

    @staticmethod
    def _is_expired(marker: dict[str, Any]) -> bool:
        expires_at = marker.get("expires_at")
        if expires_at is None:
            return False
        try:
            return time.time() >= float(expires_at)
        except (TypeError, ValueError):
            return False

    def _delete_marker(self, cache_key: str) -> None:
        self._metadata.delete(cache_key)
        path = self._marker_path(cache_key)
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        self._forget(cache_key)

    def clear(self) -> int:
        """Remove cache-owned metadata without touching unrelated files."""
        count = int(self._metadata.clear() or 0)
        for entry in self.cache_dir.glob("*.marker.json"):
            if not entry.is_file():
                continue
            try:
                entry.unlink()
                count += 1
                self._forget(entry.name.removesuffix(".marker.json"))
            except OSError:
                pass
        self._known_markers.clear()
        return count

    def close(self) -> None:
        """Close the disk-backed metadata store."""
        self._metadata.close()


def _sorted_json(obj: Any) -> Any:
    """Recursively sort dicts so that JSON serialization is deterministic."""
    if isinstance(obj, dict):
        return {k: _sorted_json(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sorted_json(v) for v in obj]
    return obj
