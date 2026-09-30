"""Lifecycle contracts for the observable, cancellable assistant driver."""
from __future__ import annotations

import asyncio

import pytest

from bionodulo.ai.runtime import ChatStep, ModelTurn, run_turn


def call(name: str = "inspect", *, call_id: str = "call-1") -> dict:
    return {"id": call_id, "name": name, "arguments": {"target": "current"}}


async def drive(model, execute, *, on_step=None, **options):
    return await run_turn(
        messages=[{"role": "user", "content": "inspect"}], model=model, execute=execute,
        allowed_tools={"inspect"}, truncate=lambda value: value, on_step=on_step, **options,
    )


@pytest.mark.asyncio
async def test_running_tool_event_arrives_before_blocked_tool_completes() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    events: list[ChatStep] = []
    rounds = 0

    async def model(_messages, _on_text):
        nonlocal rounds
        rounds += 1
        return ModelTurn("Checking", [call()]) if rounds == 1 else ModelTurn("Done")

    async def execute(_name, _arguments):
        entered.set()
        await release.wait()
        return {"status": "ok"}

    task = asyncio.create_task(drive(model, execute, on_step=events.append))
    await asyncio.wait_for(entered.wait(), 1)
    assert [event.type for event in events][-1] == "tool_call"
    assert events[-1].status == "running"
    assert not any(event.type == "tool_result" for event in events)
    release.set()
    response = await task
    assert response.reply == "Done"
    result = next(event for event in events if event.type == "tool_result")
    assert result.id == next(event.id for event in events if event.type == "tool_call")
    assert result.status == "completed"
    assert result.duration_ms is not None


@pytest.mark.asyncio
async def test_cancellation_stops_later_tools_and_model_rounds() -> None:
    entered = asyncio.Event()
    calls: list[str] = []
    model_calls = 0

    async def model(_messages, _on_text):
        nonlocal model_calls
        model_calls += 1
        return ModelTurn("", [call(call_id="one"), call(call_id="two")])

    async def execute(name, _arguments):
        calls.append(name)
        entered.set()
        await asyncio.Event().wait()
        return {"status": "ok"}

    task = asyncio.create_task(drive(model, execute))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["inspect"]
    assert model_calls == 1


@pytest.mark.asyncio
async def test_model_and_tool_timeouts_are_bounded() -> None:
    async def never_model(_messages, _on_text):
        await asyncio.Event().wait()
        return ModelTurn("unreachable")

    async def unused(_name, _arguments):
        return {}

    with pytest.raises(TimeoutError):
        await drive(never_model, unused, model_timeout=0.01, request_timeout=1)

    rounds = 0

    async def model(_messages, _on_text):
        nonlocal rounds
        rounds += 1
        return ModelTurn("", [call()]) if rounds == 1 else ModelTurn("Tool timed out")

    async def never_tool(_name, _arguments):
        await asyncio.Event().wait()
        return {}

    response = await drive(model, never_tool, tool_timeout=0.01)
    result = next(step for step in response.steps if step.type == "tool_result")
    assert result.status == "error"
    assert "timed out" in str(result.result).lower()


@pytest.mark.asyncio
async def test_repeated_identical_errors_stop_after_three_calls() -> None:
    executions = 0

    async def model(_messages, _on_text):
        return ModelTurn("", [call()])

    async def execute(_name, _arguments):
        nonlocal executions
        executions += 1
        return {"status": "error", "error": "bad input"}

    response = await drive(model, execute)
    assert executions == 3
    assert [step.type for step in response.steps].count("tool_result") == 3
    assert response.steps[-1].type == "error"
    assert "three times" in response.steps[-1].content


@pytest.mark.asyncio
async def test_unknown_tool_and_nested_domain_error_are_reported_as_failures() -> None:
    executions = 0
    rounds = 0

    async def model(_messages, _on_text):
        nonlocal rounds
        rounds += 1
        return ModelTurn("", [call("unknown")]) if rounds == 1 else ModelTurn("Done")

    async def execute(_name, _arguments):
        nonlocal executions
        executions += 1
        return {"result": {"status": "error", "error": "domain failure"}}

    unknown = await drive(model, execute)
    assert executions == 0
    assert next(step for step in unknown.steps if step.type == "tool_result").status == "error"

    rounds = 0

    async def known_model(_messages, _on_text):
        nonlocal rounds
        rounds += 1
        return ModelTurn("", [call()]) if rounds == 1 else ModelTurn("Done")

    nested = await drive(known_model, execute)
    assert next(step for step in nested.steps if step.type == "tool_result").status == "error"


@pytest.mark.asyncio
async def test_round_limit_and_empty_reply_are_visible_failures() -> None:
    async def looping_model(_messages, _on_text):
        return ModelTurn("", [call()])

    async def execute(_name, _arguments):
        return {"status": "ok"}

    limited = await drive(looping_model, execute, max_rounds=1)
    assert [step.type for step in limited.steps].count("tool_call") == 1
    assert limited.steps[-1].type == "error"
    assert "limit" in limited.steps[-1].content

    async def empty_model(_messages, _on_text):
        return ModelTurn(" ")

    with pytest.raises(RuntimeError, match="empty response"):
        await drive(empty_model, execute)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutates", [False, True])
async def test_only_mutating_tool_results_propose_workflow_changes(mutates: bool) -> None:
    rounds = 0
    workflow = {"nodes": [], "edges": []}

    async def model(_messages, _on_text):
        nonlocal rounds
        rounds += 1
        return ModelTurn("", [call()]) if rounds == 1 else ModelTurn("Done")

    async def execute(_name, _arguments):
        return {"status": "ok", "result": {"workflow": workflow}, "mutates": mutates}

    response = await drive(model, execute)
    assert response.reply == "Done"
    assert response.proposed_workflow == (workflow if mutates else None)
    assert any(step.type == "propose_changes" for step in response.steps) is mutates
