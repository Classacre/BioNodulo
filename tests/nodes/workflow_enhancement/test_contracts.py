from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.workflow_enhancement_family import adapter
from bionodulo.nodes.builtin.workflow_enhancement_family.provenance import ProvenanceNode
from bionodulo.nodes.builtin.workflow_enhancement_family.resource_monitor import ResourceMonitorNode
from bionodulo.nodes.builtin.workflow_enhancement_family.timer import TimerNode
from bionodulo.nodes.registry import NodeRegistry


EXPECTED_MODULES = {
    node_id: f"bionodulo.nodes.builtin.workflow_enhancement_family.{module}"
    for node_id, module in {
        "batch_submitter": "batch_submitter",
        "cache_control": "cache_control",
        "checkpoint": "checkpoint",
        "compare_results": "compare_results",
        "data_validator": "data_validator",
        "memoize": "memoize",
        "notification": "notification",
        "pause_resume": "pause_resume",
        "provenance": "provenance",
        "resource_monitor": "resource_monitor",
        "retry": "retry",
        "sub_workflow": "sub_workflow",
        "timer": "timer",
        "workflow_trigger": "workflow_trigger",
    }.items()
}


def test_workflow_enhancement_ids_have_one_focused_owner() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert {node_id: registry.get(node_id).__module__ for node_id in EXPECTED_MODULES} == EXPECTED_MODULES
    adapter_classes = [
        value
        for value in vars(adapter).values()
        if isinstance(value, type) and value.__module__ == adapter.__name__
    ]
    assert all(not value.__dict__.get("NODE_ID") for value in adapter_classes)
    assert all(registry.get(node_id).GIT_COMMIT == adapter.BIONODULO_SOURCE_COMMIT for node_id in EXPECTED_MODULES)


def test_resource_monitor_requires_the_exact_measurement_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ResourceMonitorNode.CONDA_PACKAGE_CONSTRAINTS == {"psutil": "7.2.2"}
    assert PACKAGE_MIN_VERSIONS["psutil"] == "7.2.2"

    monkeypatch.setitem(sys.modules, "psutil", None)
    with pytest.raises(RuntimeError, match="requires psutil 7.2.2"):
        ResourceMonitorNode()._get_resource_stats()


@pytest.mark.asyncio
async def test_provenance_accepts_a_fixed_deterministic_timestamp() -> None:
    kwargs = {
        "input": "aligned.bam",
        "tool_name": "samtools",
        "tool_version": "1.23.1",
        "standard": "native",
        "include_system_info": False,
        "timestamp": "2026-07-19T03:04:05+08:00",
    }

    first = json.loads((await ProvenanceNode().run(**kwargs))[1])
    second = json.loads((await ProvenanceNode().run(**kwargs))[1])

    assert first == second
    assert first["bionodulo_provenance"]["timestamp"] == "2026-07-18T19:04:05Z"
    with pytest.raises(ValueError, match="ISO-8601"):
        await ProvenanceNode().run(**{**kwargs, "timestamp": "not-a-time"})


@pytest.mark.asyncio
async def test_timer_uses_monotonic_elapsed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    wall_times = iter((100.0, 90.0))
    monotonic_times = iter((10.0, 10.25))
    monkeypatch.setattr(
        adapter,
        "time",
        SimpleNamespace(
            time=lambda: next(wall_times),
            monotonic=lambda: next(monotonic_times),
            strftime=adapter.time.strftime,
            gmtime=adapter.time.gmtime,
        ),
    )

    _, elapsed, start_json, end_json = await TimerNode().run(input="value")

    assert elapsed == 0.25
    assert json.loads(start_json)["timestamp"] == 100.0
    assert json.loads(end_json)["timestamp"] == 90.0
