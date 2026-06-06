"""Workflow node migration helpers."""

from __future__ import annotations

import copy
import fnmatch
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowMigrationResult:
    """Result returned when applying registered node migrations."""

    workflow: dict[str, Any]
    applied: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def apply_workflow_migrations(workflow: dict[str, Any], registry: Any) -> WorkflowMigrationResult:
    """Return a migrated workflow copy using node-class migration metadata."""
    migrated = copy.deepcopy(workflow)
    applied: list[dict[str, Any]] = []
    warnings: list[str] = []
    nodes = _workflow_nodes(migrated)

    for node_id, node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", "") or "")
        node_class = _registry_lookup(registry, node_type)
        if node_class is None:
            continue
        saved_version = _saved_node_version(node)
        current_version = _registry_node_version(node_class)
        if not saved_version or not current_version or saved_version == current_version:
            continue

        for migration in getattr(node_class, "MIGRATIONS", []) or []:
            if not isinstance(migration, dict):
                continue
            from_version = str(migration.get("from_version", "") or "")
            if from_version and not _version_matches(saved_version, from_version):
                continue
            actions = _apply_node_migration(node, migration)
            if not actions:
                continue
            applied.append(
                {
                    "node_id": str(node.get("id", node_id)),
                    "node_type": node_type,
                    "from_version": saved_version,
                    "to_version": str(migration.get("to_version", current_version) or current_version),
                    "description": str(migration.get("description", "") or ""),
                    "actions": actions,
                }
            )

        if applied and applied[-1].get("node_id") == str(node.get("id", node_id)):
            node_info = node.get("node_info")
            if not isinstance(node_info, dict):
                node_info = {}
                node["node_info"] = node_info
            node_info["version"] = current_version
        elif saved_version != current_version:
            warnings.append(
                f"Node '{node.get('id', node_id)}' ({node_type}) was saved with version "
                f"{saved_version} but no matching migration was applied for registry version {current_version}"
            )

    return WorkflowMigrationResult(workflow=migrated, applied=applied, warnings=warnings)


def _workflow_nodes(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    raw_nodes = workflow.get("nodes", [])
    if isinstance(raw_nodes, dict):
        items = []
        for node_id, node in raw_nodes.items():
            if isinstance(node, dict):
                node.setdefault("id", str(node_id))
                items.append((str(node_id), node))
        return items
    if isinstance(raw_nodes, list):
        return [
            (str(node.get("id", index)), node)
            for index, node in enumerate(raw_nodes)
            if isinstance(node, dict)
        ]
    return []


def _registry_lookup(registry: Any, node_type: str) -> Any:
    if registry is None:
        return None
    if hasattr(registry, "get_node"):
        return registry.get_node(node_type)
    if hasattr(registry, "get"):
        return registry.get(node_type)
    return None


def _saved_node_version(node: dict[str, Any]) -> str:
    node_info = node.get("node_info", {})
    if not isinstance(node_info, dict):
        return ""
    version = node_info.get("version", "")
    return str(version) if version else ""


def _registry_node_version(node_class: Any) -> str:
    if isinstance(node_class, dict):
        version = node_class.get("version", "")
    else:
        version = getattr(node_class, "VERSION", "")
    return str(version) if version else ""


def _version_matches(saved_version: str, pattern: str) -> bool:
    if pattern.endswith(".x"):
        return saved_version.startswith(pattern[:-1])
    return saved_version == pattern or fnmatch.fnmatch(saved_version, pattern)


def _apply_node_migration(node: dict[str, Any], migration: dict[str, Any]) -> list[dict[str, Any]]:
    params = node.get("params")
    if not isinstance(params, dict):
        params = {}
        node["params"] = params
    actions: list[dict[str, Any]] = []

    for old_name, new_name in (migration.get("rename_params") or {}).items():
        old_key = str(old_name)
        new_key = str(new_name)
        if old_key not in params or new_key in params:
            continue
        params[new_key] = params.pop(old_key)
        actions.append({"op": "rename_param", "from": old_key, "to": new_key})

    for name, value in (migration.get("set_defaults") or {}).items():
        key = str(name)
        if key in params:
            continue
        params[key] = copy.deepcopy(value)
        actions.append({"op": "set_default", "name": key})

    for name in migration.get("remove_params") or []:
        key = str(name)
        if key not in params:
            continue
        params.pop(key)
        actions.append({"op": "remove_param", "name": key})

    return actions
