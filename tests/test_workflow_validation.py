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
    RETURN_NAMES = ("value",)

    async def run(self, **kwargs: Any) -> tuple[str]:
        return ("",)


class MigratableValidationNode(BaseNode):
    NODE_ID = "migratable_validation"
    VERSION = "2.0.0"
    RETURN_TYPES = ("STRING",)
    MIGRATIONS = [
        {
            "from_version": "1.x",
            "to_version": "2.0.0",
            "description": "Rename old_value to value.",
            "rename_params": {"old_value": "value"},
        }
    ]

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


def test_validation_warns_when_matching_node_migration_is_available() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(MigratableValidationNode)
    workflow = {
        "nodes": [
            {
                "id": "n1",
                "type": "migratable_validation",
                "params": {"old_value": "legacy"},
                "node_info": {"version": "1.0.0"},
            }
        ],
        "edges": [],
    }

    result = validate_workflow(workflow, registry)

    assert result.valid is True
    assert result.errors == []
    assert result.warnings == [
        "Node 'n1' (migratable_validation) was saved with version 1.0.0 but registry has 2.0.0",
        "Node 'n1' (migratable_validation) has a migration available from 1.x to 2.0.0: Rename old_value to value.",
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


def test_validation_accepts_declared_workflow_parameter_references() -> None:
    workflow = {
        "nodes": [
            {
                "id": "input",
                "type": "input_file",
                "params": {"path": "sample-{{sample_id}}.fastq.gz"},
                "inputs": {"threads": {"value": "{{threads}}"}},
            }
        ],
        "edges": [],
        "parameters": [
            {"name": "sample_id", "type": "STRING"},
            {"name": "threads", "type": "INTEGER", "default": 8},
        ],
    }

    result = validate_workflow(workflow, registry=None)

    assert result.valid is True
    assert result.errors == []


def test_validation_rejects_unknown_workflow_parameter_references() -> None:
    workflow = {
        "nodes": [
            {
                "id": "input",
                "type": "input_file",
                "params": {
                    "path": "sample-{{sample_typo}}.fastq.gz",
                    "metadata": {"sample": "{{sample_id}}"},
                },
            }
        ],
        "edges": [],
        "parameters": [
            {"name": "sample_id", "type": "STRING"},
        ],
    }

    result = validate_workflow(workflow, registry=None)

    assert result.valid is False
    assert "Node 'input' references unknown workflow parameter 'sample_typo' in params.path" in result.errors
    assert "Node 'input' references unknown workflow parameter 'sample_id' in params.metadata.sample" not in result.errors


def test_validation_allows_node_local_template_placeholders() -> None:
    workflow = {
        "nodes": [
            {
                "id": "template",
                "type": "text_template",
                "params": {
                    "template": "sample {{sample}}",
                    "workflow_template": '{"name": "qc-{{sample}}"}',
                    "prompt": "Summarize {{gene}}",
                    "custom_script": "output <- '{{sample}}'",
                },
            }
        ],
        "edges": [],
        "parameters": [],
    }

    result = validate_workflow(workflow, registry=None)

    assert result.valid is True
    assert result.errors == []


def test_validation_rejects_explicit_unknown_source_output_ports() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(VersionedValidationNode)
    workflow = {
        "nodes": [
            {"id": "source", "type": "versioned_validation", "params": {}},
            {"id": "target", "type": "versioned_validation", "params": {}},
        ],
        "edges": [
            {
                "from": {"node": "source", "output": "removed_output"},
                "to": {"node": "target", "input": "value"},
            }
        ],
    }

    result = validate_workflow(workflow, registry)

    assert result.valid is False
    assert result.errors == [
        "Edge from node 'source' (versioned_validation) references unknown output port 'removed_output'"
    ]
