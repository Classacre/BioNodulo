from __future__ import annotations

from typing import Any

import pytest

from bionodulo.manager.resolver import build_node_manifest
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.registry import NodeRegistry


class VersionedLegacyNode(BaseNode):
    NODE_ID = "versioned_legacy"
    DISPLAY_NAME = "Versioned Legacy"
    CATEGORY = "tests"
    DESCRIPTION = "Node used to exercise version lifecycle metadata."
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)
    VERSION = "2.1.0"
    PREVIOUS_VERSIONS = ["1.0.0", "2.0.0"]
    DEPRECATED = True
    DEPRECATION_MESSAGE = "Use versioned_modern for new workflows."
    REPLACED_BY = "versioned_modern"
    MIGRATIONS = [
        {
            "from_version": "1.x",
            "to_version": "2.0.0",
            "description": "Rename the old_value parameter to value.",
        }
    ]

    async def run(self, **kwargs: Any) -> tuple[str]:
        return (str(kwargs.get("value", "")),)


def test_base_node_metadata_exposes_version_lifecycle_contract() -> None:
    meta = VersionedLegacyNode.metadata()

    assert meta["version"] == "2.1.0"
    assert meta["deprecated"] is True
    assert meta["deprecation_message"] == "Use versioned_modern for new workflows."
    assert meta["replaced_by"] == "versioned_modern"
    assert meta["lifecycle"] == {
        "status": "deprecated",
        "deprecated": True,
        "deprecation_message": "Use versioned_modern for new workflows.",
        "replaced_by": "versioned_modern",
    }
    assert meta["versioning"] == {
        "current": "2.1.0",
        "previous": ["1.0.0", "2.0.0"],
        "migrations": [
            {
                "from_version": "1.x",
                "to_version": "2.0.0",
                "description": "Rename the old_value parameter to value.",
            }
        ],
    }


def test_registry_object_info_exposes_version_lifecycle_contract() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(VersionedLegacyNode)

    node_info = registry.object_info("versioned_legacy")

    assert node_info["version"] == "2.1.0"
    assert node_info["deprecated"] is True
    assert node_info["lifecycle"]["status"] == "deprecated"
    assert node_info["lifecycle"]["replaced_by"] == "versioned_modern"
    assert node_info["versioning"]["previous"] == ["1.0.0", "2.0.0"]
    assert node_info["versioning"]["migrations"][0]["from_version"] == "1.x"


def test_registry_rejects_malformed_migration_metadata() -> None:
    class BadMigrationNode(BaseNode):
        NODE_ID = "bad_migration"
        RETURN_TYPES = ("STRING",)
        MIGRATIONS = [{"from_version": "1.0.0", "description": "Missing target"}]

        async def run(self, **kwargs: Any) -> tuple[str]:
            return ("",)

    with pytest.raises(ValueError, match="MIGRATIONS"):
        NodeRegistry.create_isolated().register(BadMigrationNode)


def test_node_manifest_preserves_version_lifecycle_contract() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(VersionedLegacyNode)
    workflow = {
        "nodes": [
            {
                "id": "legacy-1",
                "type": "versioned_legacy",
                "params": {"value": "sample"},
            }
        ]
    }

    manifest = build_node_manifest(workflow, registry)

    entry = manifest["versioned_legacy"]
    assert entry["version"] == "2.1.0"
    assert entry["lifecycle"]["status"] == "deprecated"
    assert entry["lifecycle"]["deprecation_message"] == "Use versioned_modern for new workflows."
    assert entry["versioning"]["current"] == "2.1.0"
    assert entry["versioning"]["migrations"][0]["description"] == "Rename the old_value parameter to value."
