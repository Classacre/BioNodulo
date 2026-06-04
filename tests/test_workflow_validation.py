from __future__ import annotations

from typing import Any

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


class VersionedValidationNode(BaseNode):
    NODE_ID = "versioned_validation"
    VERSION = "1.1.0"
    RETURN_TYPES = ("STRING",)

    async def run(self, **kwargs: Any) -> tuple[str]:
        return ("",)


def test_validation_warns_when_saved_node_version_differs_from_registry() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(VersionedValidationNode)
    workflow = {
        "nodes": [
            {
                "id": "n1",
                "type": "versioned_validation",
                "params": {},
                "node_info": {
                    "version": "1.0.0",
                },
            }
        ],
        "edges": [],
    }

    result = validate_workflow(workflow, registry)

    assert result.valid is True
    assert result.errors == []
    assert result.warnings == [
        "Node 'n1' (versioned_validation) was saved with version 1.0.0 but registry has 1.1.0"
    ]
