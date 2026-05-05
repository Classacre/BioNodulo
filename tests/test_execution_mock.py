from pathlib import Path

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.run_metadata import RunRecord
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow


def registry():
    reg = NodeRegistry()
    reg.load_builtin_nodes()
    return reg


@pytest.mark.asyncio
async def test_mock_execution_creates_outputs_and_cache(tmp_path: Path):
    workflow = Workflow.model_validate_json(open("examples/workflows/fastq_qc_pipeline.bionodulo.json", encoding="utf-8").read())
    events = []

    async def emit(event_type, data):
        events.append({"type": event_type, "data": data})

    executor = WorkflowExecutor(registry=registry(), runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache", emit=emit)
    record = RunRecord(run_id="run-test-001", status="queued", workflow_name=workflow.name, mock_tools=True)

    await executor.execute(run_id=record.run_id, workflow=workflow, record=record, mock_tools=True)

    assert record.status == "completed"
    assert record.node_statuses["multiqc-1"] == "completed"
    assert Path(record.node_outputs["multiqc-1"]["report"]).exists()
    assert any(event["type"] == "node_log" for event in events)

    second = RunRecord(run_id="run-test-002", status="queued", workflow_name=workflow.name, mock_tools=True)
    await executor.execute(run_id=second.run_id, workflow=workflow, record=second, mock_tools=True)

    assert second.node_statuses["multiqc-1"] == "cached"


@pytest.mark.asyncio
async def test_failed_node_blocks_downstream(tmp_path: Path):
    workflow = Workflow.model_validate(
        {
            "name": "failure test",
            "nodes": [
                {"id": "bad", "type": "generic_command", "params": {"command": "definitely_missing_bionodulo_executable"}},
                {"id": "collector", "type": "collect_files", "params": {}},
            ],
            "edges": [
                {"id": "edge", "from": {"node": "bad", "output": "output_dir"}, "to": {"node": "collector", "input": "first"}}
            ],
            "outputs": ["collector"],
        }
    )
    events = []

    async def emit(event_type, data):
        events.append({"type": event_type, "data": data})

    executor = WorkflowExecutor(registry=registry(), runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache", emit=emit)
    record = RunRecord(run_id="run-fail", status="queued", workflow_name=workflow.name, mock_tools=False)

    await executor.execute(run_id=record.run_id, workflow=workflow, record=record, mock_tools=False)

    assert record.status == "failed"
    assert record.node_statuses["bad"] == "failed"
    assert record.node_statuses["collector"] == "blocked"
