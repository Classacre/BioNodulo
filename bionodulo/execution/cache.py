"""
CacheStore for workflow result caching.

Provides deterministic cache key generation and persistent caching of
node execution results based on parameters, inputs, and upstream cache keys.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class CacheStore:
    """Persistent cache store for workflow node execution results.

    Each cached entry consists of:
      - A ``.marker.json`` file with metadata (key, inputs, params, outputs)
      - The actual output files written by the node

    Cache keys are SHA-256 hashes over the node's type, parameters,
    resolved inputs, and upstream cache keys, making them deterministic
    and sensitive to any change in the execution graph.
    """

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _marker_path(self, cache_key: str) -> Path:
        """Return the path to the marker file for *cache_key*."""
        return self.cache_dir / f"{cache_key}.marker.json"

    def cache_key_for_node(
        self,
        node_id: str,
        node_type: str,
        params: dict[str, Any],
        inputs: dict[str, Any],
        upstream_keys: dict[str, str | None],
    ) -> str:
        """Generate a deterministic cache key for a node execution.

        The key incorporates:
        - ``node_type`` (so two nodes of different types with the same
          parameters do not collide)
        - ``params`` (sorted JSON)
        - ``inputs`` (sorted JSON of resolved input values)
        - ``upstream_keys`` (sorted mapping of input edge to upstream cache key)

        Args:
            node_id: Unique node identifier (for logging, not part of key).
            node_type: The node's type / kind.
            params: Node parameters after defaults have been filled.
            inputs: Resolved input values from upstream nodes.
            upstream_keys: Mapping from input edge name to the cache key of
                the upstream node that produced it (or *None*).

        Returns:
            A 64-character hex SHA-256 string.
        """
        payload = json.dumps(
            {
                "node_type": node_type,
                "params": _sorted_json(params),
                "inputs": _sorted_json(inputs),
                "upstream_keys": _sorted_json(upstream_keys),
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def is_hit(self, cache_key: str) -> bool:
        """Return *True* if a cached result exists for *cache_key*."""
        return self._marker_path(cache_key).is_file()

    def read_marker(self, cache_key: str) -> dict[str, Any] | None:
        """Read and return the cached metadata for *cache_key*, or *None*."""
        path = self._marker_path(cache_key)
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    def write_marker(
        self,
        cache_key: str,
        outputs: dict[str, Any],
        params: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        upstream_keys: dict[str, str | None] | None = None,
    ) -> None:
        """Write metadata marker for a successful node execution.

        Args:
            cache_key: The cache key returned by :meth:`cache_key_for_node`.
            outputs: Mapping of output port names to final file paths / values.
            params: Node parameters (stored for provenance).
            inputs: Resolved inputs (stored for provenance).
            upstream_keys: Upstream cache keys (stored for provenance).
        """
        marker = {
            "cache_key": cache_key,
            "outputs": outputs,
            "params": params or {},
            "inputs": inputs or {},
            "upstream_keys": upstream_keys or {},
        }
        path = self._marker_path(cache_key)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(marker, fh, indent=2, ensure_ascii=True)

    def clear(self) -> int:
        """Remove **all** cached markers and return the count deleted."""
        count = 0
        for entry in self.cache_dir.iterdir():
            if entry.is_file():
                try:
                    entry.unlink()
                    count += 1
                except OSError:
                    pass
        return count


def _sorted_json(obj: Any) -> Any:
    """Recursively sort dicts so that JSON serialization is deterministic."""
    if isinstance(obj, dict):
        return {k: _sorted_json(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sorted_json(v) for v in obj]
    return obj
