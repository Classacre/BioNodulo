"""Version management for collaborative workflow snapshots.

Provides manual save points, auto-save with cooldown, restore, and
diff capabilities between versions. All public methods are ``async``
and wrap blocking SQLite / CRDT calls with :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pycrdt

from bionodulo.collab.doc_store import (
    auto_save_version_sync,
    delete_version_sync,
    list_versions_sync,
    load_version_snapshot_sync,
    save_version_snapshot_sync,
)
from bionodulo.collab.models import WorkflowVersion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synchronous diff helpers
# ---------------------------------------------------------------------------


def _extract_nodes(doc: pycrdt.Doc) -> dict[str, dict[str, Any]]:
    """Extract node data from a pycrdt Doc as a flat dict keyed by node ID.

    ``Map.get()`` returns a plain Python dict for nested CRDT maps.
    Returns an empty dict if the document structure is unexpected.
    """
    nodes: dict[str, dict[str, Any]] = {}
    try:
        workflow_map = doc.get("workflow", type=pycrdt.Map)
        nodes_data = workflow_map.get("nodes", {})
        if isinstance(nodes_data, dict):
            for key, node_data in nodes_data.items():
                if isinstance(node_data, dict):
                    nodes[key] = node_data
                else:
                    nodes[key] = {"id": key}
    except Exception:
        pass
    return nodes


def _diff_nodes_sync(
    version_id_a: str,
    version_id_b: str,
) -> dict[str, Any]:
    """Compare two versions and return changed/added/deleted nodes.

    Loads both versions into temporary :class:`pycrdt.Doc` instances and
    compares their ``workflow.nodes`` maps.

    Returns::

        {
            "added":   [node_dict, ...],
            "removed": [node_dict, ...],
            "modified": [{"id": str, "before": node_dict, "after": node_dict}, ...],
        }
    """
    doc_a = load_version_snapshot_sync(version_id_a)
    doc_b = load_version_snapshot_sync(version_id_b)

    if doc_a is None:
        return {"error": f"Version {version_id_a} not found"}
    if doc_b is None:
        return {"error": f"Version {version_id_b} not found"}

    nodes_a = _extract_nodes(doc_a)
    nodes_b = _extract_nodes(doc_b)

    keys_a = set(nodes_a.keys())
    keys_b = set(nodes_b.keys())

    added_ids = keys_b - keys_a
    removed_ids = keys_a - keys_b
    common_ids = keys_a & keys_b

    added = [nodes_b[nid] for nid in sorted(added_ids)]
    removed = [nodes_a[nid] for nid in sorted(removed_ids)]

    modified = []
    for nid in sorted(common_ids):
        node_a = nodes_a[nid]
        node_b = nodes_b[nid]
        if node_a != node_b:
            modified.append({"id": nid, "before": node_a, "after": node_b})

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
    }


# ---------------------------------------------------------------------------
# Async VersionManager
# ---------------------------------------------------------------------------


class VersionManager:
    """Async manager for workflow version snapshots.

    Provides manual save points, auto-save with a 5-minute cooldown,
    restore, listing, deletion, and node-level diffing.

    Args:
        doc_store: A :class:`DocStore` instance (or module) providing
            the underlying snapshot operations.
    """

    def __init__(self, doc_store: Any = None) -> None:
        self.doc_store = doc_store

    async def create_manual(
        self,
        workflow_id: str,
        user_id: str,
        user_name: str,
        doc: pycrdt.Doc,
        name: str,
    ) -> str:
        """Create a named manual save point.

        Args:
            workflow_id: The workflow to snapshot.
            user_id: ID of the user creating the version.
            user_name: Display name of the user.
            doc: The current :class:`pycrdt.Doc` to snapshot.
            name: Human-readable name for this save point.

        Returns:
            The generated version ID.
        """
        return await asyncio.to_thread(
            save_version_snapshot_sync,
            workflow_id,
            user_id,
            user_name,
            doc,
            name=name,
            auto_save=False,
        )

    async def create_auto(
        self,
        workflow_id: str,
        user_id: str,
        user_name: str,
        doc: pycrdt.Doc,
    ) -> str | None:
        """Auto-save if 5 minutes since last auto-save.

        Args:
            workflow_id: The workflow to snapshot.
            user_id: ID of the user triggering the auto-save.
            user_name: Display name of the user.
            doc: The current :class:`pycrdt.Doc` to snapshot.

        Returns:
            The version ID if a new snapshot was created, or ``None``
            if the 5-minute cooldown has not elapsed.
        """
        return await asyncio.to_thread(
            auto_save_version_sync,
            workflow_id,
            user_id,
            user_name,
            doc,
        )

    async def restore(self, version_id: str) -> pycrdt.Doc | None:
        """Restore a version into a new Doc.

        Creates a fresh :class:`pycrdt.Doc` and applies the version
        snapshot. The current document is **not** overwritten — this
        returns a new Doc that can be used to create a branch or
        compare states.

        Args:
            version_id: The version to restore.

        Returns:
            A new :class:`pycrdt.Doc` with the version's state, or
            ``None`` if the version was not found.
        """
        return await asyncio.to_thread(load_version_snapshot_sync, version_id)

    async def list(
        self,
        workflow_id: str,
        limit: int = 50,
    ) -> list[WorkflowVersion]:
        """List versions newest first.

        Args:
            workflow_id: The workflow to list versions for.
            limit: Maximum number of versions to return.

        Returns:
            A list of :class:`WorkflowVersion` objects without the
            binary snapshot payload.
        """
        return await asyncio.to_thread(list_versions_sync, workflow_id, limit)

    async def delete(self, version_id: str) -> bool:
        """Delete a version.

        Args:
            version_id: The version to delete.

        Returns:
            ``True`` if the version was found and deleted.
        """
        return await asyncio.to_thread(delete_version_sync, version_id)

    async def diff_nodes(
        self,
        version_id_a: str,
        version_id_b: str,
    ) -> dict[str, Any]:
        """Compare two versions and return changed/added/deleted nodes.

        Both versions are loaded into temporary :class:`pycrdt.Doc`
        instances and their ``workflow.nodes`` maps are compared.

        Args:
            version_id_a: First version ID.
            version_id_b: Second version ID.

        Returns::

            {
                "added":    [{node}, ...],
                "removed":  [{node}, ...],
                "modified": [{"id": str, "before": {}, "after": {}}, ...],
            }

        If a version is not found, the dict contains an ``"error"`` key.
        """
        return await asyncio.to_thread(
            _diff_nodes_sync, version_id_a, version_id_b
        )
