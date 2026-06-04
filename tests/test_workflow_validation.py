from __future__ import annotations

from typing import Any

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow
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


def test_workflow_schema_preserves_parameter_definitions() -> None:
    workflow = Workflow.from_dict({
        "version": "2.0",
        "app": "bionodulo",
        "name": "Parameterized",
        "description": "",
        "nodes": [],
        "edges": [],
        "groups": [],
        "parameters": [
            {
                "name": "sample_id",
                "type": "STRING",
                "required": True,
                "default": "S1",
                "value": "S2",
                "description": "Sample identifier",
            }
        ],
    })

    assert workflow.to_dict()["parameters"] == [
        {
            "name": "sample_id",
            "type": "STRING",
            "required": True,
            "default": "S1",
            "value": "S2",
            "description": "Sample identifier",
        }
    ]


def test_validation_rejects_duplicate_workflow_parameter_names() -> None:
    workflow = {
        "nodes": [],
        "edges": [],
        "parameters": [
            {"name": "sample_id", "type": "STRING"},
            {"name": "sample_id", "type": "STRING"},
        ],
    }

    result = validate_workflow(workflow, registry=None)

    assert result.valid is False
    assert "Workflow parameter 'sample_id' is defined more than once" in result.errors


def test_validation_rejects_malformed_workflow_parameter_definitions() -> None:
    workflow = {
        "nodes": [],
        "edges": [],
        "parameters": [
            {"name": "", "type": "STRING"},
            {"name": "threshold", "type": ""},
            "sample_id",
        ],
    }

    result = validate_workflow(workflow, registry=None)

    assert result.valid is False
    assert "Workflow parameter at index 0 must have a non-empty name" in result.errors
    assert "Workflow parameter 'threshold' must have a non-empty type" in result.errors
    assert "Workflow parameter at index 2 must be an object" in result.errors
