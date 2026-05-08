from pathlib import Path

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.run_metadata import RunRecord
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow
from bionodulo.workflow.validation import validate_workflow


def registry():
    reg = NodeRegistry()
    reg.load_builtin_nodes()
    return reg


@pytest.mark.asyncio
async def test_muted_node_blocks_downstream_without_running(tmp_path: Path):
    workflow = Workflow.model_validate(
        {
            "nodes": [
                {"id": "input", "type": "input_directory", "params": {"directory": "data"}},
                {"id": "collect", "type": "collect_files", "ui": {"muted": True}},
                {"id": "view", "type": "collect_files"},
            ],
            "edges": [
                {"id": "a", "from": {"node": "input", "output": "directory"}, "to": {"node": "collect", "input": "first"}},
                {"id": "b", "from": {"node": "collect", "output": "directory"}, "to": {"node": "view", "input": "first"}},
            ],
            "outputs": ["view"],
        }
    )
    events = []

    async def emit(event_type, data):
        events.append({"type": event_type, "data": data})

    executor = WorkflowExecutor(registry=registry(), runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache", emit=emit)
    record = RunRecord(run_id="run-muted", status="queued", workflow_name=workflow.name, mock_tools=True)

    await executor.execute(run_id=record.run_id, workflow=workflow, record=record, mock_tools=True)

    assert record.node_statuses["collect"] == "muted"
    assert record.node_statuses["view"] == "blocked"
    assert record.execution_plan["collect"]["reason"] == "muted"


@pytest.mark.asyncio
async def test_bypassed_node_passes_compatible_upstream_value(tmp_path: Path):
    workflow = Workflow.model_validate(
        {
            "nodes": [
                {"id": "input", "type": "input_file", "params": {"file": "a.txt"}},
                {"id": "pass", "type": "view_text_file", "ui": {"bypassed": True}},
                {"id": "view", "type": "view_text_file"},
            ],
            "edges": [
                {"id": "a", "from": {"node": "input", "output": "file"}, "to": {"node": "pass", "input": "file"}},
                {"id": "b", "from": {"node": "pass", "output": "file"}, "to": {"node": "view", "input": "file"}},
            ],
            "outputs": ["view"],
        }
    )
    events = []

    async def emit(event_type, data):
        events.append({"type": event_type, "data": data})

    executor = WorkflowExecutor(registry=registry(), runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache", emit=emit)
    record = RunRecord(run_id="run-bypass", status="queued", workflow_name=workflow.name, mock_tools=True)

    await executor.execute(run_id=record.run_id, workflow=workflow, record=record, mock_tools=True)

    assert record.node_statuses["pass"] == "bypassed"
    assert record.node_outputs["pass"]["file"] == "a.txt"


def test_bypass_validation_fails_without_compatible_input():
    workflow = Workflow.model_validate(
        {
            "nodes": [
                {"id": "pass", "type": "view_text_file", "ui": {"bypassed": True}},
                {"id": "view", "type": "view_text_file"},
            ],
            "edges": [{"id": "b", "from": {"node": "pass", "output": "file"}, "to": {"node": "view", "input": "file"}}],
            "outputs": ["view"],
        }
    )

    result = validate_workflow(workflow, registry(), mock_tools=True)

    assert not result.valid
    assert any(error.code == "bypass_without_input" for error in result.errors)
