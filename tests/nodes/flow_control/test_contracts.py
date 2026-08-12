from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.flow_control_family import (
    BreakContinueNode,
    CounterAccumulatorNode,
    DelayWaitNode,
    ForEachNode,
    GateNode,
    IfConditionNode,
    MergeNode,
    ParallelForNode,
    SleepNode,
    SwitchNode,
    TryCatchNode,
    WaitForNode,
    WhileLoopNode,
)
from bionodulo.nodes.builtin.flow_control_family import adapter


FOCUSED_OWNERS = {
    "break_continue": ("break_continue", BreakContinueNode),
    "counter_accumulator": ("counter_accumulator", CounterAccumulatorNode),
    "delay_wait": ("delay_wait", DelayWaitNode),
    "foreach": ("foreach", ForEachNode),
    "gate": ("gate", GateNode),
    "if_condition": ("if_condition", IfConditionNode),
    "merge": ("merge", MergeNode),
    "parallel_for": ("parallel_for", ParallelForNode),
    "sleep": ("sleep", SleepNode),
    "switch": ("switch", SwitchNode),
    "try_catch": ("try_catch", TryCatchNode),
    "wait_for": ("wait_for", WaitForNode),
    "while_loop": ("while_loop", WhileLoopNode),
}


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        candidate
        for _name, candidate in inspect.getmembers(module, inspect.isclass)
        if issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and candidate.__module__ == module.__name__
        and candidate.NODE_ID
    ]


def test_each_stable_id_has_one_focused_owner() -> None:
    assert _owned_node_classes(adapter) == []

    for node_id, (module_name, expected_class) in FOCUSED_OWNERS.items():
        module = importlib.import_module(f"bionodulo.nodes.builtin.flow_control_family.{module_name}")
        assert _owned_node_classes(module) == [expected_class]
        assert expected_class.NODE_ID == node_id


def test_flow_control_authorities_are_pinned() -> None:
    for _module_name, node_class in FOCUSED_OWNERS.values():
        assert node_class.GIT_COMMIT == "a32a426c03ce4c925bf7dcdbd2cf08fbdedd55e9"
        assert node_class.RUNTIME_VERSION == "3.12.3"
        assert node_class.RUNTIME_GIT_COMMIT == "f6650f9ad73359051f3e558c2431a109bc016664"
        assert node_class.GIT_COMMIT in node_class.SOURCE_URL
        assert all(node_class.RUNTIME_GIT_COMMIT in url for url in node_class.RUNTIME_SOURCE_URLS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node_class", "kwargs"),
    [
        (IfConditionNode, {"value": True, "condition_mode": "boolean", "compare_to": ""}),
        (SwitchNode, {"value": "case-a", "cases": "case-a"}),
        (ForEachNode, {"items": []}),
        (WhileLoopNode, {"condition_mode": "boolean_is_true", "value": False}),
        (MergeNode, {"num_inputs": 1, "input_0": "ready"}),
        (GateNode, {"value": "ready", "condition_mode": "always_pass"}),
        (ParallelForNode, {"items": []}),
        (TryCatchNode, {"try_input": "ready"}),
        (WaitForNode, {"condition": "elapsed_time", "seconds": 0}),
        (CounterAccumulatorNode, {"operation": "increment"}),
        (BreakContinueNode, {"action": "break"}),
        (DelayWaitNode, {"mode": "delay", "delay_seconds": 0}),
        (SleepNode, {"seconds": 0}),
    ],
)
async def test_runtime_output_shapes_match_declared_names(
    node_class: type[BaseNode],
    kwargs: dict[str, Any],
) -> None:
    result = await node_class().run(**kwargs)

    assert set(result["outputs"]) == set(node_class.RETURN_NAMES)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node_class", "kwargs"),
    [
        (IfConditionNode, {"value": True, "condition_mode": "unknown", "compare_to": ""}),
        (SwitchNode, {"value": "x", "cases": "", "num_branches": 0}),
        (ForEachNode, {"items": [], "batch_size": 0}),
        (WhileLoopNode, {"condition_mode": "boolean_is_true", "value": True, "max_iterations": 0}),
        (MergeNode, {"num_inputs": 11}),
        (GateNode, {"value": "x", "condition_mode": "unknown"}),
        (ParallelForNode, {"items": [], "max_concurrency": 101}),
        (TryCatchNode, {"try_input": "x", "max_retries": 11}),
        (WaitForNode, {"condition": "elapsed_time", "seconds": -1}),
        (CounterAccumulatorNode, {"operation": "unknown"}),
        (BreakContinueNode, {"action": "stop"}),
        (DelayWaitNode, {"mode": "delay", "delay_seconds": 86401}),
        (SleepNode, {"seconds": -1}),
    ],
)
async def test_public_modes_and_bounds_fail_closed(
    node_class: type[BaseNode],
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        await node_class().run(**kwargs)


@pytest.mark.asyncio
async def test_waiting_nodes_use_awaitable_sleep_without_real_delays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(adapter.asyncio, "sleep", fake_sleep)

    await SleepNode().run(seconds=1.25)
    await WaitForNode().run(condition="elapsed_time", seconds=2.5)
    await DelayWaitNode().run(mode="delay", delay_seconds=3.75)
    await TryCatchNode().run(
        try_input="sample.bam",
        max_retries=1,
        retry_delay=4.5,
        _phase="try_result",
        _try_error="runtime: retry",
    )

    assert sleeps == [1.25, 2.5, 3.75, 4.5]
