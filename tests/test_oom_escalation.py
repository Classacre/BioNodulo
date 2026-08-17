from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.errors import NodeMemoryError
from bionodulo.execution.executor import ExecutionContext, WorkflowExecutor


class OomOnceNode:
    RETURN_NAMES = ("default",)
    calls = 0

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        OomOnceNode.calls += 1
        if OomOnceNode.calls == 1:
            raise NodeMemoryError("std::bad_alloc")
        return {
            "outputs": {"default": str(context.node_dir / "out.txt")},
            "memory_directive": str(context.params.get("memory", "")),
        }


def _policy(escalate: dict[str, Any] | None) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "node_id": "policy",
        "max_retries": 2,
        "retry_on": "memory",
        "delay_seconds": 0.0,
    }
    if escalate is not None:
        policy["escalate"] = escalate
    return policy


def _context(tmp_path: Path, params: dict[str, Any]) -> ExecutionContext:
    return ExecutionContext(
        run_id="run-escalate",
        node_id="hpc",
        node_type="hpc_submit_job",
        node_dir=tmp_path / "hpc",
        workspace_dir=tmp_path,
        params=params,
        api_secrets={},
        emit=lambda *_: None,
        cancel_event=asyncio.Event(),
        run_metadata={"retry_policies": [_policy({"memory_multiplier": 2.0})]},
    )


@pytest.mark.asyncio
async def test_oom_retry_with_escalation_emits_event_and_bumps_memory(tmp_path: Path) -> None:
    OomOnceNode.calls = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    events: list[tuple[str, dict[str, Any]]] = []
    ctx = _context(tmp_path, {"memory": "32G"})
    node = {"id": "hpc", "type": "hpc_submit_job", "_node_class": OomOnceNode}

    result = await executor._execute_node_with_retry(
        ctx=ctx,
        node=node,
        inputs={},
        upstream_nodes={"policy"},
        emit=lambda evt, data: events.append((evt, data)),
    )

    assert result["attempts"] == 2
    assert ctx.params["memory"] == "64G"

    escalate_events = [data for evt, data in events if evt == "node_escalate"]
    assert len(escalate_events) == 1
    assert escalate_events[0]["memory_multiplier"] == 2.0
    assert escalate_events[0]["attempt"] == 2
    assert escalate_events[0]["applied"] is True
    assert escalate_events[0]["memory"] == "64G"
    assert escalate_events[0]["node_id"] == "hpc"

    escalations = ctx.run_metadata["escalations"]
    assert escalations == [
        {
            "node_id": "hpc",
            "attempt": 2,
            "memory_multiplier": 2.0,
            "applied": True,
            "memory": "64G",
        }
    ]


@pytest.mark.asyncio
async def test_oom_retry_without_memory_param_records_intent_only(tmp_path: Path) -> None:
    OomOnceNode.calls = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    events: list[tuple[str, dict[str, Any]]] = []
    ctx = _context(tmp_path, {"threads": 8})
    node = {"id": "hpc", "type": "hpc_submit_job", "_node_class": OomOnceNode}

    result = await executor._execute_node_with_retry(
        ctx=ctx,
        node=node,
        inputs={},
        upstream_nodes={"policy"},
        emit=lambda evt, data: events.append((evt, data)),
    )

    assert result["attempts"] == 2
    assert ctx.params == {"threads": 8}
    escalate_events = [data for evt, data in events if evt == "node_escalate"]
    assert escalate_events[0]["applied"] is False
    assert "memory" not in escalate_events[0]


@pytest.mark.asyncio
async def test_oom_retry_without_escalate_policy_emits_nothing(tmp_path: Path) -> None:
    OomOnceNode.calls = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    events: list[tuple[str, dict[str, Any]]] = []
    ctx = _context(tmp_path, {"memory": "32G"})
    ctx.run_metadata = {"retry_policies": [_policy(None)]}
    node = {"id": "hpc", "type": "hpc_submit_job", "_node_class": OomOnceNode}

    await executor._execute_node_with_retry(
        ctx=ctx,
        node=node,
        inputs={},
        upstream_nodes={"policy"},
        emit=lambda evt, data: events.append((evt, data)),
    )

    assert not [evt for evt, _ in events if evt == "node_escalate"]
    assert ctx.params["memory"] == "32G"
    assert "escalations" not in ctx.run_metadata


@pytest.mark.asyncio
async def test_escalation_attempt_persisted_to_run_event_log(tmp_path: Path) -> None:
    from bionodulo.execution.run_store import RunStore

    OomOnceNode.calls = 0
    store = RunStore(tmp_path / "runs.db")
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        run_store=store,
    )
    ctx = _context(tmp_path, {"memory": "8G"})
    node = {"id": "hpc", "type": "hpc_submit_job", "_node_class": OomOnceNode}

    await executor._execute_node_with_retry(
        ctx=ctx,
        node=node,
        inputs={},
        upstream_nodes={"policy"},
        emit=lambda *_: None,
    )

    persisted = [event for event in store.get_events("run-escalate") if event["type"] == "node_escalate"]
    assert len(persisted) == 1
    assert persisted[0]["payload"]["memory_multiplier"] == 2.0
    assert persisted[0]["payload"]["applied"] is True
    store.close()


def test_bump_memory_directive_scales_common_units() -> None:
    bump = WorkflowExecutor._bump_memory_directive
    assert bump("32G", 1.5) == "48G"
    assert bump("512M", 2.0) == "1024M"
    assert bump("16000", 2.0) == "32000"
    assert bump("1.5T", 2.0) == "3T"
    assert bump("16GiB", 2.0) == "32G"
    # Unparseable directives pass through unchanged (no fake bumps).
    assert bump("auto", 2.0) == "auto"
    assert bump("", 2.0) == ""
    assert bump("32G", 1.0) == "32G"


def test_escalate_policy_parsing_tolerates_bad_values(tmp_path: Path) -> None:
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    ctx = _context(tmp_path, {"memory": "32G"})
    ctx.run_metadata = {
        "retry_policies": [
            {
                "node_id": "policy",
                "max_retries": 1,
                "retry_on": "memory",
                "delay_seconds": 0.0,
                "escalate": {"memory_multiplier": "not-a-number"},
            }
        ]
    }

    executor._apply_memory_escalation(
        ctx, ctx.run_metadata["retry_policies"][0], 2, lambda *_: None
    )

    record = ctx.run_metadata["escalations"][0]
    assert record["memory_multiplier"] == 1.0
    assert record["applied"] is False
