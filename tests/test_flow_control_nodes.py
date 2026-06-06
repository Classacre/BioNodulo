from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry


def _loaded_registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    return registry


def _node_class(node_id: str) -> type:
    node_class = _loaded_registry().get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_flow_control_nodes_are_registered_for_frontend_discovery() -> None:
    info = _loaded_registry().object_info()

    assert info["if_condition"]["display_name"] == "If Condition"
    assert info["if_condition"]["category"] == "flow_control"
    assert info["if_condition"]["output_name"] == ["true", "false", "condition_result"]
    assert info["switch"]["display_name"] == "Switch"
    assert info["switch"]["category"] == "flow_control"
    assert info["switch"]["output_name"] == ["output_1", "output_2", "output_3", "output_4", "default"]
    assert info["foreach"]["display_name"] == "For Each"
    assert info["foreach"]["category"] == "flow_control"
    assert info["foreach"]["output_name"] == ["iteration", "results", "count", "all_succeeded"]
    assert info["try_catch"]["display_name"] == "Try / Catch"
    assert info["try_catch"]["category"] == "flow_control"
    assert info["try_catch"]["output_name"] == ["try", "catch", "output", "succeeded", "error_info", "retry_count"]
    assert info["try_catch"]["output"] == ["ANY", "ANY", "ANY", "BOOLEAN", "STRING", "INT"]
    assert info["gate"]["display_name"] == "Gate"
    assert info["gate"]["category"] == "flow_control"
    assert info["gate"]["output_name"] == ["output", "passed"]
    assert info["gate"]["output"] == ["ANY", "BOOLEAN"]
    assert info["merge"]["display_name"] == "Merge"
    assert info["merge"]["category"] == "flow_control"
    assert info["merge"]["output_name"] == ["merged", "received_count"]
    assert info["merge"]["output"] == ["ANY", "INT"]
    assert info["delay_wait"]["display_name"] == "Delay / Wait"
    assert info["delay_wait"]["category"] == "flow_control"
    assert info["delay_wait"]["output_name"] == ["value", "condition_met", "actual_wait_seconds"]
    assert info["delay_wait"]["output"] == ["ANY", "BOOLEAN", "FLOAT"]
    assert info["sleep"]["display_name"] == "Sleep"
    assert info["sleep"]["category"] == "flow_control"
    assert info["sleep"]["output_name"] == ["done", "actual_wait_seconds", "value"]
    assert info["sleep"]["output"] == ["BOOLEAN", "FLOAT", "ANY"]
    assert info["wait_for"]["display_name"] == "Wait For"
    assert info["wait_for"]["category"] == "flow_control"
    assert info["wait_for"]["output_name"] == ["triggered", "actual_wait_seconds", "value"]
    assert info["wait_for"]["output"] == ["BOOLEAN", "FLOAT", "ANY"]
    assert info["break_continue"]["display_name"] == "Break / Continue"
    assert info["break_continue"]["category"] == "flow_control"
    assert info["break_continue"]["output_name"] == ["signal", "value", "triggered", "reason"]
    assert info["break_continue"]["output"] == ["STRING", "ANY", "BOOLEAN", "STRING"]
    assert "break" in info["break_continue"]["search_aliases"]
    assert "continue" in info["break_continue"]["search_aliases"]
    assert info["counter_accumulator"]["display_name"] == "Counter / Accumulator"
    assert info["counter_accumulator"]["category"] == "flow_control"
    assert info["counter_accumulator"]["output_name"] == ["value", "count", "accumulator"]
    assert info["counter_accumulator"]["output"] == ["ANY", "INT", "ANY"]
    assert info["parallel_for"]["display_name"] == "Parallel For"
    assert info["parallel_for"]["category"] == "flow_control"
    assert info["parallel_for"]["output_name"] == ["results", "completed_count", "all_succeeded"]
    assert info["parallel_for"]["output"] == ["ANY", "INT", "BOOLEAN"]
    assert info["while_loop"]["display_name"] == "While Loop"
    assert info["while_loop"]["category"] == "flow_control"
    assert info["while_loop"]["output_name"] == ["results", "iterations", "converged"]
    assert info["while_loop"]["output"] == ["ANY", "INT", "BOOLEAN"]

    sleep_inputs = info["sleep"]["input"]
    assert set(sleep_inputs["required"]) == {"seconds"}
    assert set(sleep_inputs["optional"]) == {"value"}

    wait_for_inputs = info["wait_for"]["input"]
    assert set(wait_for_inputs["required"]) == {"condition"}
    assert set(wait_for_inputs["optional"]) == {
        "path",
        "seconds",
        "poll_interval",
        "timeout",
        "on_timeout",
        "value",
    }

    break_continue_inputs = info["break_continue"]["input"]
    assert set(break_continue_inputs["required"]) == {"action"}
    assert set(break_continue_inputs["optional"]) == {"condition", "value", "reason"}

    if_condition_inputs = info["if_condition"]["input"]
    assert {
        "combinator",
        "condition_mode_2",
        "compare_to_2",
        "output_mode",
    }.issubset(if_condition_inputs["optional"])
    assert if_condition_inputs["optional"]["combinator"][1]["options"] == ["and", "or"]
    assert if_condition_inputs["optional"]["output_mode"][1]["options"] == ["route", "signal"]


def test_switch_frontend_metadata_exposes_dynamic_branch_contract() -> None:
    switch_info = _loaded_registry().object_info("switch")

    num_branches_type, num_branches_config = switch_info["input"]["optional"]["num_branches"]

    assert num_branches_type == "INT"
    assert num_branches_config["default"] == 4
    assert num_branches_config["min"] == 1
    assert num_branches_config["max"] >= 6
    assert num_branches_config["dynamic_outputs"] == {
        "prefix": "output_",
        "count_input": "num_branches",
        "default_output": "default",
        "type": "ANY",
    }


@pytest.mark.asyncio
async def test_if_condition_routes_value_to_selected_branch() -> None:
    node = _node_class("if_condition")()

    result = await node.run(
        value="PASS",
        condition_mode="string_equal",
        compare_to="PASS",
    )

    assert result["outputs"] == {
        "true": "PASS",
        "false": None,
        "condition_result": True,
    }
    assert result["inactive_outputs"] == ["false"]


@pytest.mark.asyncio
async def test_if_condition_supports_additional_comparison_modes() -> None:
    node = _node_class("if_condition")()

    numeric = await node.run(value="12", condition_mode="numeric_not_equal", compare_to="10")
    string = await node.run(value="tumor_RNA.fastq.gz", condition_mode="string_startswith", compare_to="tumor")
    suffix = await node.run(value="tumor_RNA.fastq.gz", condition_mode="string_endswith", compare_to=".fastq.gz")
    not_equal = await node.run(value="mouse", condition_mode="string_not_equal", compare_to="human")
    empty = await node.run(value="", condition_mode="is_empty", compare_to="")

    assert numeric["outputs"]["condition_result"] is True
    assert string["outputs"]["condition_result"] is True
    assert suffix["outputs"]["condition_result"] is True
    assert not_equal["outputs"]["condition_result"] is True
    assert empty["outputs"]["condition_result"] is True


@pytest.mark.asyncio
async def test_if_condition_combines_second_condition_with_and() -> None:
    node = _node_class("if_condition")()

    result = await node.run(
        value="tumor_RNA.fastq.gz",
        condition_mode="string_contains",
        compare_to="tumor",
        combinator="and",
        condition_mode_2="string_endswith",
        compare_to_2=".bam",
    )

    assert result["outputs"] == {
        "true": None,
        "false": "tumor_RNA.fastq.gz",
        "condition_result": False,
    }
    assert result["inactive_outputs"] == ["true"]


@pytest.mark.asyncio
async def test_if_condition_combines_second_condition_with_or() -> None:
    node = _node_class("if_condition")()

    result = await node.run(
        value="tumor_RNA.fastq.gz",
        condition_mode="string_contains",
        compare_to="control",
        combinator="or",
        condition_mode_2="string_endswith",
        compare_to_2=".fastq.gz",
    )

    assert result["outputs"] == {
        "true": "tumor_RNA.fastq.gz",
        "false": None,
        "condition_result": True,
    }
    assert result["inactive_outputs"] == ["false"]


@pytest.mark.asyncio
async def test_if_condition_signal_output_mode_emits_booleans() -> None:
    node = _node_class("if_condition")()

    result = await node.run(
        value="PASS",
        condition_mode="string_equal",
        compare_to="PASS",
        output_mode="signal",
    )

    assert result["outputs"] == {
        "true": True,
        "false": False,
        "condition_result": True,
    }
    assert result["inactive_outputs"] == ["false"]


@pytest.mark.asyncio
async def test_switch_routes_passthrough_to_matching_case() -> None:
    node = _node_class("switch")()

    result = await node.run(
        value="human",
        cases="mouse,human,yeast",
        passthrough_data="hg38",
    )

    assert result["outputs"] == {
        "output_1": None,
        "output_2": "hg38",
        "output_3": None,
        "output_4": None,
        "default": None,
    }
    assert result["inactive_outputs"] == ["output_1", "output_3", "output_4", "default"]


@pytest.mark.asyncio
async def test_switch_num_branches_routes_to_dynamic_case_output() -> None:
    node = _node_class("switch")()

    result = await node.run(
        value="zebrafish",
        cases="mouse,human,yeast,rat,fly,zebrafish",
        passthrough_data="danRer11",
        num_branches=6,
    )

    assert result["outputs"] == {
        "output_1": None,
        "output_2": None,
        "output_3": None,
        "output_4": None,
        "output_5": None,
        "output_6": "danRer11",
        "default": None,
    }
    assert result["inactive_outputs"] == ["output_1", "output_2", "output_3", "output_4", "output_5", "default"]


@pytest.mark.asyncio
async def test_switch_json_rules_route_regex_match() -> None:
    node = _node_class("switch")()

    result = await node.run(
        value="sample_RNA_001.fastq.gz",
        passthrough_data="reads.fastq.gz",
        rules=json.dumps([
            {"branch_index": 1, "match_type": "regex", "pattern": "RNA_\\d+"},
        ]),
        fallback="drop",
    )

    assert result["outputs"] == {
        "output_1": None,
        "output_2": "reads.fastq.gz",
        "output_3": None,
        "output_4": None,
        "default": None,
    }
    assert result["inactive_outputs"] == ["output_1", "output_3", "output_4", "default"]


@pytest.mark.asyncio
async def test_switch_numeric_range_and_fallback_error() -> None:
    node = _node_class("switch")()

    result = await node.run(
        value="42",
        passthrough_data={"sample": "S1"},
        rules=json.dumps([
            {"branch_index": 0, "match_type": "numeric_range", "min": 0, "max": 20},
            {"branch_index": 2, "match_type": "numeric_range", "min": 21, "max": 50},
        ]),
        fallback="error",
    )

    assert result["outputs"]["output_3"] == {"sample": "S1"}
    assert set(result["inactive_outputs"]) == {"output_1", "output_2", "output_4", "default"}

    with pytest.raises(ValueError, match="Switch value did not match any rule"):
        await node.run(
            value="unmatched",
            rules=json.dumps([{"branch_index": 0, "match_type": "exact", "pattern": "matched"}]),
            fallback="error",
        )


@pytest.mark.asyncio
async def test_switch_all_match_marks_multiple_outputs_active() -> None:
    node = _node_class("switch")()

    result = await node.run(
        value="tumor_RNA",
        passthrough_data="sample.tsv",
        rules=json.dumps([
            {"branch_index": 0, "match_type": "contains", "pattern": "tumor"},
            {"branch_index": 2, "match_type": "regex", "pattern": "RNA$"},
        ]),
        match_mode="all",
        fallback="drop",
    )

    assert result["outputs"]["output_1"] == "sample.tsv"
    assert result["outputs"]["output_3"] == "sample.tsv"
    assert result["inactive_outputs"] == ["output_2", "output_4", "default"]


@pytest.mark.asyncio
async def test_foreach_rejects_items_beyond_max_iterations_without_body() -> None:
    node = _node_class("foreach")()

    with pytest.raises(RuntimeError, match="Loop foreach would exceed max_iterations=2"):
        await node.run(items=["S1", "S2", "S3"], max_iterations=2)


@pytest.mark.asyncio
async def test_sleep_waits_for_requested_seconds_and_passes_value(monkeypatch: pytest.MonkeyPatch) -> None:
    import bionodulo.nodes.builtin.flow_control as module

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    result = await _node_class("sleep")().run(seconds=2.5, value="sample.bam")

    assert sleeps == [2.5]
    assert result["outputs"]["done"] is True
    assert result["outputs"]["value"] == "sample.bam"
    assert result["outputs"]["actual_wait_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_wait_for_file_exists_triggers_without_sleep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import bionodulo.nodes.builtin.flow_control as module

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    marker = tmp_path / "finished.flag"
    marker.write_text("done\n", encoding="utf-8")

    result = await _node_class("wait_for")().run(
        condition="file_exists",
        path=str(marker),
        timeout=1.0,
        value="next-step",
    )

    assert sleeps == []
    assert result["outputs"]["triggered"] is True
    assert result["outputs"]["value"] == "next-step"


@pytest.mark.asyncio
async def test_wait_for_timeout_can_pass_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import bionodulo.nodes.builtin.flow_control as module

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    result = await _node_class("wait_for")().run(
        condition="file_exists",
        path=str(tmp_path / "missing.flag"),
        poll_interval=0.25,
        timeout=0.25,
        on_timeout="pass_through",
        value="fallback",
    )

    assert sleeps == [0.25]
    assert result["outputs"]["triggered"] is False
    assert result["outputs"]["value"] == "fallback"


@pytest.mark.asyncio
async def test_break_continue_emits_triggered_loop_control_signal() -> None:
    node = _node_class("break_continue")()

    result = await node.run(action="break", condition=True, value="sample-3", reason="QC failed")

    assert result["outputs"] == {
        "signal": "break",
        "value": "sample-3",
        "triggered": True,
        "reason": "QC failed",
    }
    assert result["flow_control"] == {
        "type": "break_continue",
        "action": "break",
        "triggered": True,
        "reason": "QC failed",
    }


@pytest.mark.asyncio
async def test_break_continue_condition_false_emits_noop_signal() -> None:
    node = _node_class("break_continue")()

    result = await node.run(action="continue", condition=False, value="sample-3")

    assert result["outputs"] == {
        "signal": "none",
        "value": "sample-3",
        "triggered": False,
        "reason": "",
    }
    assert result["flow_control"] == {
        "type": "break_continue",
        "action": "none",
        "triggered": False,
        "reason": "",
    }


@pytest.mark.asyncio
async def test_try_catch_initial_phase_routes_input_to_try_branch() -> None:
    node = _node_class("try_catch")()

    result = await node.run(try_input="sample.bam", max_retries=2)

    assert result["outputs"] == {
        "try": "sample.bam",
        "catch": None,
        "output": None,
        "succeeded": False,
        "error_info": "",
        "retry_count": 0,
    }
    assert result["inactive_outputs"] == ["catch", "output", "succeeded", "error_info", "retry_count"]
    assert result["flow_control"]["phase"] == "trying"
    assert result["flow_control"]["retry_count"] == 0


@pytest.mark.asyncio
async def test_try_catch_success_phase_returns_try_result() -> None:
    node = _node_class("try_catch")()

    result = await node.run(
        try_input="sample.bam",
        _phase="try_result",
        _try_result="calls.vcf",
        _try_error="",
        _retry_count=1,
    )

    assert result["outputs"] == {
        "try": None,
        "catch": None,
        "output": "calls.vcf",
        "succeeded": True,
        "error_info": "",
        "retry_count": 1,
    }
    assert result["inactive_outputs"] == ["try", "catch", "error_info"]
    assert result["flow_control"]["phase"] == "completed"


@pytest.mark.asyncio
async def test_try_catch_failure_retries_before_catch_branch() -> None:
    node = _node_class("try_catch")()

    result = await node.run(
        try_input="sample.bam",
        _phase="try_result",
        _try_error="tool_error: temporary failure",
        _retry_count=0,
        max_retries=1,
        retry_delay=0,
    )

    assert result["outputs"]["try"] == "sample.bam"
    assert result["outputs"]["catch"] is None
    assert result["outputs"]["succeeded"] is False
    assert result["outputs"]["retry_count"] == 1
    assert result["inactive_outputs"] == ["catch", "output", "succeeded"]
    assert result["flow_control"]["phase"] == "retrying"
    assert result["flow_control"]["retry_count"] == 1


@pytest.mark.asyncio
async def test_try_catch_failure_routes_to_catch_after_retries() -> None:
    node = _node_class("try_catch")()

    result = await node.run(
        try_input="sample.bam",
        _phase="try_result",
        _try_error="tool_error: GATK failed",
        _retry_count=2,
        max_retries=2,
        pass_input_to_catch=True,
        pass_error_to_catch=True,
    )

    assert result["outputs"] == {
        "try": None,
        "catch": {"input": "sample.bam", "error": "tool_error: GATK failed"},
        "output": None,
        "succeeded": False,
        "error_info": "tool_error: GATK failed",
        "retry_count": 2,
    }
    assert result["inactive_outputs"] == ["try", "output", "succeeded", "retry_count"]
    assert result["flow_control"]["phase"] == "catching"


@pytest.mark.asyncio
async def test_try_catch_ignores_uncaught_error_types() -> None:
    node = _node_class("try_catch")()

    result = await node.run(
        try_input="sample.bam",
        _phase="try_result",
        _try_error="validation: missing reference",
        catch_errors="tool_error,timeout",
    )

    assert result["outputs"]["catch"] is None
    assert result["outputs"]["succeeded"] is False
    assert result["outputs"]["error_info"] == "validation: missing reference"
    assert result["inactive_outputs"] == ["try", "catch", "output", "succeeded", "retry_count"]
    assert result["flow_control"]["phase"] == "uncaught_error"


@pytest.mark.asyncio
async def test_try_catch_catch_phase_returns_catch_result() -> None:
    node = _node_class("try_catch")()

    result = await node.run(
        try_input="sample.bam",
        _phase="catch_result",
        _try_error="tool_error: GATK failed",
        _catch_result="freebayes.vcf",
        _retry_count=1,
    )

    assert result["outputs"] == {
        "try": None,
        "catch": None,
        "output": "freebayes.vcf",
        "succeeded": False,
        "error_info": "tool_error: GATK failed",
        "retry_count": 1,
    }
    assert result["inactive_outputs"] == ["try", "catch", "succeeded"]
    assert result["flow_control"]["phase"] == "completed_with_catch"


@pytest.mark.asyncio
async def test_executor_try_catch_continues_with_try_branch_result(tmp_path: Path) -> None:
    try_catch_node = _node_class("try_catch")

    class RiskyNode:
        NODE_ID = "risky"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": f"try:{value}"}}

    class RecoveryNode:
        NODE_ID = "recovery"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": f"catch:{value}"}}

    class DownstreamNode:
        NODE_ID = "downstream"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "try_catch": try_catch_node,
                "risky": RiskyNode,
                "recovery": RecoveryNode,
                "downstream": DownstreamNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "guard",
                "type": "try_catch",
                "inputs": {
                    "try_input": {"value": "sample.bam"},
                    "max_retries": {"value": 0},
                    "retry_delay": {"value": 0},
                },
                "outputs": {"try": {}, "catch": {}, "output": {}, "succeeded": {}, "error_info": {}, "retry_count": {}},
            },
            {"id": "risky", "type": "risky", "outputs": {"out": {}}},
            {"id": "recovery", "type": "recovery", "outputs": {"out": {}}},
            {"id": "downstream", "type": "downstream", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "guard", "target_node": "risky", "source_output": "try", "target_input": "value"},
            {"source_node": "risky", "target_node": "guard", "source_output": "out", "target_input": "_try_result"},
            {"source_node": "guard", "target_node": "recovery", "source_output": "catch", "target_input": "value"},
            {"source_node": "recovery", "target_node": "guard", "source_output": "out", "target_input": "_catch_result"},
            {"source_node": "guard", "target_node": "downstream", "source_output": "output", "target_input": "value"},
        ],
    }
    RiskyNode.calls = []
    RecoveryNode.calls = []
    DownstreamNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("try-catch-success", workflow, force=True)

    assert result["status"] == "completed"
    assert RiskyNode.calls == ["sample.bam"]
    assert RecoveryNode.calls == []
    assert DownstreamNode.calls == ["try:sample.bam"]
    assert result["outputs"]["guard"]["output"] == "try:sample.bam"
    assert result["outputs"]["guard"]["succeeded"] is True


@pytest.mark.asyncio
async def test_executor_try_catch_runs_catch_branch_after_try_failure(tmp_path: Path) -> None:
    try_catch_node = _node_class("try_catch")

    class RiskyNode:
        NODE_ID = "risky"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            raise RuntimeError("tool_error: GATK failed")

    class RecoveryNode:
        NODE_ID = "recovery"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": f"recovered:{value['input']}:{value['error']}"}}

    class DownstreamNode:
        NODE_ID = "downstream"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "try_catch": try_catch_node,
                "risky": RiskyNode,
                "recovery": RecoveryNode,
                "downstream": DownstreamNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "guard",
                "type": "try_catch",
                "inputs": {
                    "try_input": {"value": "sample.bam"},
                    "max_retries": {"value": 0},
                    "retry_delay": {"value": 0},
                    "catch_errors": {"value": "tool_error"},
                },
                "outputs": {"try": {}, "catch": {}, "output": {}, "succeeded": {}, "error_info": {}, "retry_count": {}},
            },
            {"id": "risky", "type": "risky", "outputs": {"out": {}}},
            {"id": "recovery", "type": "recovery", "outputs": {"out": {}}},
            {"id": "downstream", "type": "downstream", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "guard", "target_node": "risky", "source_output": "try", "target_input": "value"},
            {"source_node": "risky", "target_node": "guard", "source_output": "out", "target_input": "_try_result"},
            {"source_node": "guard", "target_node": "recovery", "source_output": "catch", "target_input": "value"},
            {"source_node": "recovery", "target_node": "guard", "source_output": "out", "target_input": "_catch_result"},
            {"source_node": "guard", "target_node": "downstream", "source_output": "output", "target_input": "value"},
        ],
    }
    RiskyNode.calls = []
    RecoveryNode.calls = []
    DownstreamNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("try-catch-failure", workflow, force=True)

    assert result["status"] == "completed"
    assert RiskyNode.calls == ["sample.bam"]
    assert RecoveryNode.calls == [{"input": "sample.bam", "error": "tool_error: GATK failed"}]
    assert DownstreamNode.calls == ["recovered:sample.bam:tool_error: GATK failed"]
    assert result["outputs"]["guard"]["output"] == "recovered:sample.bam:tool_error: GATK failed"
    assert result["outputs"]["guard"]["succeeded"] is False
    assert result["outputs"]["guard"]["error_info"] == "tool_error: GATK failed"


@pytest.mark.asyncio
async def test_executor_try_catch_retries_try_branch_before_catch(tmp_path: Path) -> None:
    try_catch_node = _node_class("try_catch")

    class FlakyNode:
        NODE_ID = "flaky"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            if len(self.calls) == 1:
                raise RuntimeError("tool_error: transient failure")
            return {"outputs": {"out": f"try:{value}:attempt-{len(self.calls)}"}}

    class RecoveryNode:
        NODE_ID = "recovery"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": f"catch:{value}"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "try_catch": try_catch_node,
                "flaky": FlakyNode,
                "recovery": RecoveryNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "guard",
                "type": "try_catch",
                "inputs": {
                    "try_input": {"value": "sample.bam"},
                    "max_retries": {"value": 1},
                    "retry_delay": {"value": 0},
                    "catch_errors": {"value": "tool_error"},
                },
                "outputs": {"try": {}, "catch": {}, "output": {}, "succeeded": {}, "error_info": {}, "retry_count": {}},
            },
            {"id": "flaky", "type": "flaky", "outputs": {"out": {}}},
            {"id": "recovery", "type": "recovery", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "guard", "target_node": "flaky", "source_output": "try", "target_input": "value"},
            {"source_node": "flaky", "target_node": "guard", "source_output": "out", "target_input": "_try_result"},
            {"source_node": "guard", "target_node": "recovery", "source_output": "catch", "target_input": "value"},
            {"source_node": "recovery", "target_node": "guard", "source_output": "out", "target_input": "_catch_result"},
        ],
    }
    FlakyNode.calls = []
    RecoveryNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("try-catch-retry", workflow, force=True)

    assert result["status"] == "completed"
    assert FlakyNode.calls == ["sample.bam", "sample.bam"]
    assert RecoveryNode.calls == []
    assert result["outputs"]["guard"]["output"] == "try:sample.bam:attempt-2"
    assert result["outputs"]["guard"]["succeeded"] is True
    assert result["outputs"]["guard"]["retry_count"] == 1


@pytest.mark.asyncio
async def test_executor_try_catch_branch_can_use_outer_upstream_outputs(tmp_path: Path) -> None:
    try_catch_node = _node_class("try_catch")

    class ConstantNode:
        NODE_ID = "constant"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            return {"outputs": {"out": value}}

    class CombineNode:
        NODE_ID = "combine"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[tuple[Any, Any]] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {
                "required": {"value": ("ANY", {}), "reference": ("ANY", {})},
                "optional": {},
                "hidden": {},
            }

        async def run(self, context: Any, value: Any, reference: Any) -> dict[str, Any]:
            self.calls.append((value, reference))
            return {"outputs": {"out": f"{value}:{reference}"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "constant": ConstantNode,
                "try_catch": try_catch_node,
                "combine": CombineNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {"id": "reference", "type": "constant", "inputs": {"value": {"value": "hg38"}}, "outputs": {"out": {}}},
            {
                "id": "guard",
                "type": "try_catch",
                "inputs": {
                    "try_input": {"value": "sample.bam"},
                    "retry_delay": {"value": 0},
                },
                "outputs": {"try": {}, "catch": {}, "output": {}, "succeeded": {}, "error_info": {}, "retry_count": {}},
            },
            {"id": "combine", "type": "combine", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "guard", "target_node": "combine", "source_output": "try", "target_input": "value"},
            {"source_node": "reference", "target_node": "combine", "source_output": "out", "target_input": "reference"},
            {"source_node": "combine", "target_node": "guard", "source_output": "out", "target_input": "_try_result"},
        ],
    }
    CombineNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("try-catch-outer-upstream", workflow, force=True)

    assert result["status"] == "completed"
    assert CombineNode.calls == [("sample.bam", "hg38")]
    assert result["outputs"]["guard"]["output"] == "sample.bam:hg38"


@pytest.mark.asyncio
async def test_gate_passes_value_when_condition_succeeds(tmp_path: Path) -> None:
    node = _node_class("gate")()
    marker = tmp_path / "reads.fastq.gz"
    marker.write_text("reads", encoding="utf-8")

    result = await node.run(value=str(marker), condition_mode="file_exists", on_fail="halt")

    assert result["outputs"] == {"output": str(marker), "passed": True}
    assert result["inactive_outputs"] == []
    assert result["flow_control"]["phase"] == "passed"


@pytest.mark.asyncio
async def test_gate_skip_failure_marks_output_inactive() -> None:
    node = _node_class("gate")()

    result = await node.run(value=10, condition_mode="numeric_greater", compare_to="20", on_fail="skip")

    assert result["outputs"] == {"output": None, "passed": False}
    assert result["inactive_outputs"] == ["output"]
    assert result["flow_control"]["phase"] == "skipped"


@pytest.mark.asyncio
async def test_gate_default_failure_outputs_default_value() -> None:
    node = _node_class("gate")()

    result = await node.run(
        value="sample-a",
        condition_mode="string_contains",
        compare_to="tumor",
        on_fail="default",
        default_value="control",
    )

    assert result["outputs"] == {"output": "control", "passed": False}
    assert result["inactive_outputs"] == []
    assert result["flow_control"]["phase"] == "defaulted"


@pytest.mark.asyncio
async def test_gate_halt_failure_raises_custom_error() -> None:
    node = _node_class("gate")()

    with pytest.raises(RuntimeError, match="Reference genome not indexed"):
        await node.run(
            value="missing.fasta.bwt",
            condition_mode="file_exists",
            on_fail="halt",
            error_message="Reference genome not indexed",
        )


@pytest.mark.asyncio
async def test_executor_skips_downstream_of_gate_skip_output(tmp_path: Path) -> None:
    gate_node = _node_class("gate")

    class RecordingNode:
        NODE_ID = "record"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"gate": gate_node, "record": RecordingNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "validate",
                "type": "gate",
                "inputs": {
                    "value": {"value": ""},
                    "condition_mode": {"value": "is_not_empty"},
                    "on_fail": {"value": "skip"},
                },
                "outputs": {"output": {}, "passed": {}},
            },
            {"id": "downstream", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "validate", "target_node": "downstream", "source_output": "output", "target_input": "value"},
        ],
    }
    RecordingNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("gate-skip", workflow, force=True)

    assert result["status"] == "completed"
    assert result["outputs"]["validate"] == {"output": None, "passed": False}
    assert result["node_results"]["downstream"]["status"] == "skipped"
    assert result["node_results"]["downstream"]["reason"] == "inactive_branch"
    assert RecordingNode.calls == []


@pytest.mark.asyncio
async def test_merge_append_strategy_flattens_inputs() -> None:
    node = _node_class("merge")()

    result = await node.run(
        num_inputs=4,
        strategy="append",
        input_0=["fastqc", "flagstat"],
        input_1="qualimap",
        input_2=None,
        input_3=("multiqc",),
    )

    assert result["outputs"] == {
        "merged": ["fastqc", "flagstat", "qualimap", "multiqc"],
        "received_count": 3,
    }


@pytest.mark.asyncio
async def test_merge_dict_merge_and_last_valid_strategies() -> None:
    node = _node_class("merge")()

    dict_result = await node.run(
        num_inputs=3,
        strategy="dict_merge",
        input_0={"sample": "S1", "reads": 100},
        input_1={"reads": 120},
        input_2=None,
    )
    last_result = await node.run(
        num_inputs=4,
        strategy="last_valid",
        input_0=None,
        input_1="first.vcf",
        input_2=None,
        input_3="fallback.vcf",
    )

    assert dict_result["outputs"] == {"merged": {"sample": "S1", "reads": 120}, "received_count": 2}
    assert last_result["outputs"] == {"merged": "fallback.vcf", "received_count": 2}


@pytest.mark.asyncio
async def test_merge_wait_modes_filter_received_inputs() -> None:
    node = _node_class("merge")()

    any_result = await node.run(
        num_inputs=3,
        strategy="append",
        wait_mode="any",
        input_0=None,
        input_1=["ready"],
        input_2=["late"],
    )
    first_n_result = await node.run(
        num_inputs=4,
        strategy="append",
        wait_mode="first_n",
        wait_n=2,
        input_0=["a"],
        input_1=None,
        input_2=["b"],
        input_3=["c"],
    )

    assert any_result["outputs"] == {"merged": ["ready"], "received_count": 1}
    assert first_n_result["outputs"] == {"merged": ["a", "b"], "received_count": 2}


@pytest.mark.asyncio
async def test_merge_zip_and_interleave_strategies() -> None:
    node = _node_class("merge")()

    zip_result = await node.run(num_inputs=2, strategy="zip", input_0=["S1", "S2"], input_1=[10, 20])
    interleave_result = await node.run(
        num_inputs=3,
        strategy="interleave",
        input_0=["chr1", "chr2"],
        input_1=["chrX"],
        input_2="single",
    )

    assert zip_result["outputs"] == {"merged": [("S1", 10), ("S2", 20)], "received_count": 2}
    assert interleave_result["outputs"] == {
        "merged": ["chr1", "chrX", "single", "chr2", "single"],
        "received_count": 3,
    }


@pytest.mark.asyncio
async def test_executor_fans_in_two_branches_with_merge_node(tmp_path: Path) -> None:
    merge_node = _node_class("merge")

    class ConstantNode:
        NODE_ID = "constant"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"constant": ConstantNode, "merge": merge_node}.get(node_type)

    workflow = {
        "nodes": [
            {"id": "fastqc", "type": "constant", "inputs": {"value": {"value": "fastqc.zip"}}, "outputs": {"out": {}}},
            {"id": "flagstat", "type": "constant", "inputs": {"value": {"value": "flagstat.txt"}}, "outputs": {"out": {}}},
            {
                "id": "merge_reports",
                "type": "merge",
                "inputs": {
                    "num_inputs": {"value": 2},
                    "strategy": {"value": "append"},
                },
                "outputs": {"merged": {}, "received_count": {}},
            },
        ],
        "edges": [
            {"source_node": "fastqc", "target_node": "merge_reports", "source_output": "out", "target_input": "input_0"},
            {"source_node": "flagstat", "target_node": "merge_reports", "source_output": "out", "target_input": "input_1"},
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("merge-fanin", workflow, force=True)

    assert result["status"] == "completed"
    assert result["outputs"]["merge_reports"] == {
        "merged": ["fastqc.zip", "flagstat.txt"],
        "received_count": 2,
    }


@pytest.mark.asyncio
async def test_executor_runs_merge_fanin_after_inactive_conditional_branch(tmp_path: Path) -> None:
    if_node = _node_class("if_condition")
    merge_node = _node_class("merge")

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"if_condition": if_node, "merge": merge_node}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "route",
                "type": "if_condition",
                "inputs": {
                    "value": {"value": "selected-result"},
                    "condition_mode": {"value": "not_empty"},
                    "compare_to": {"value": ""},
                },
                "outputs": {"true": {}, "false": {}, "condition_result": {}},
            },
            {
                "id": "merge_selected",
                "type": "merge",
                "inputs": {
                    "num_inputs": {"value": 2},
                    "strategy": {"value": "append"},
                    "wait_mode": {"value": "any"},
                },
                "outputs": {"merged": {}, "received_count": {}},
            },
        ],
        "edges": [
            {"source_node": "route", "target_node": "merge_selected", "source_output": "true", "target_input": "input_0"},
            {"source_node": "route", "target_node": "merge_selected", "source_output": "false", "target_input": "input_1"},
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("merge-inactive-branch", workflow, force=True)

    assert result["status"] == "completed"
    assert result["node_results"]["merge_selected"]["status"] == "completed"
    assert result["outputs"]["merge_selected"] == {
        "merged": ["selected-result"],
        "received_count": 1,
    }


@pytest.mark.asyncio
async def test_delay_wait_zero_delay_passes_value_through() -> None:
    node = _node_class("delay_wait")()

    result = await node.run(mode="delay", delay_seconds=0, value="sample-ready")

    assert result["outputs"]["value"] == "sample-ready"
    assert result["outputs"]["condition_met"] is True
    assert result["outputs"]["actual_wait_seconds"] >= 0


@pytest.mark.asyncio
async def test_delay_wait_file_exists_succeeds_when_file_present(tmp_path: Path) -> None:
    node = _node_class("delay_wait")()
    marker = tmp_path / "done.txt"
    marker.write_text("ok", encoding="utf-8")

    result = await node.run(
        mode="file_exists",
        watch_path=str(marker),
        poll_interval=0.01,
        max_wait=0.1,
        value=str(marker),
    )

    assert result["outputs"]["value"] == str(marker)
    assert result["outputs"]["condition_met"] is True


@pytest.mark.asyncio
async def test_delay_wait_timeout_can_pass_through(tmp_path: Path) -> None:
    node = _node_class("delay_wait")()

    result = await node.run(
        mode="file_exists",
        watch_path=str(tmp_path / "missing.done"),
        poll_interval=0.01,
        max_wait=0.02,
        on_timeout="pass_through",
        value="continue",
    )

    assert result["outputs"]["value"] == "continue"
    assert result["outputs"]["condition_met"] is False
    assert result["outputs"]["actual_wait_seconds"] >= 0


@pytest.mark.asyncio
async def test_delay_wait_timeout_raises_by_default(tmp_path: Path) -> None:
    node = _node_class("delay_wait")()

    with pytest.raises(RuntimeError, match="Delay / Wait timed out"):
        await node.run(
            mode="file_exists",
            watch_path=str(tmp_path / "missing.done"),
            poll_interval=0.01,
            max_wait=0.02,
            on_timeout="error",
        )


@pytest.mark.asyncio
async def test_delay_wait_poll_url_uses_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node_class("delay_wait")()
    module = __import__(node.__class__.__module__, fromlist=["APIHttpClient"])
    calls: list[dict[str, Any]] = []

    class FakeClient:
        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append({"method": method, "url": url, **kwargs})
            request = httpx.Request(method, url)
            return httpx.Response(204, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    result = await node.run(
        mode="poll_url",
        poll_url="https://example.org/ready",
        poll_interval=0,
        max_wait=0.1,
        value="ready",
    )

    assert result["outputs"]["value"] == "ready"
    assert result["outputs"]["condition_met"] is True
    assert calls == [
        {
            "method": "GET",
            "url": "https://example.org/ready",
            "timeout": 2.0,
            "retries": 1,
            "cache_ttl": None,
        }
    ]


@pytest.mark.asyncio
async def test_counter_accumulator_increments_shared_loop_state() -> None:
    node = _node_class("counter_accumulator")()
    loop_state: dict[str, Any] = {}

    first = await node.run(operation="increment", accumulator_key="samples", _loop_state=loop_state, _iteration=0)
    second = await node.run(operation="increment", accumulator_key="samples", _loop_state=loop_state, _iteration=1)

    assert first["outputs"] == {"value": 1, "count": 0, "accumulator": {"samples": 1}}
    assert second["outputs"] == {"value": 2, "count": 1, "accumulator": {"samples": 2}}
    assert loop_state == {"samples": 2}


@pytest.mark.asyncio
async def test_counter_accumulator_add_and_reset_operations() -> None:
    node = _node_class("counter_accumulator")()
    loop_state: dict[str, Any] = {}

    added = await node.run(
        operation="add",
        operand=25,
        initial_value=100,
        accumulator_key="reads",
        _loop_state=loop_state,
        _iteration=3,
    )
    reset = await node.run(
        operation="reset",
        initial_value=10,
        accumulator_key="reads",
        _loop_state=loop_state,
        _iteration=4,
    )

    assert added["outputs"] == {"value": 125, "count": 3, "accumulator": {"reads": 125}}
    assert reset["outputs"] == {"value": 10, "count": 4, "accumulator": {"reads": 10}}


@pytest.mark.asyncio
async def test_counter_accumulator_appends_and_reports_length() -> None:
    node = _node_class("counter_accumulator")()
    loop_state: dict[str, Any] = {}

    await node.run(operation="append", operand="S1", accumulator_key="samples", _loop_state=loop_state)
    appended = await node.run(operation="append", operand="S2", accumulator_key="samples", _loop_state=loop_state)
    length = await node.run(operation="length", accumulator_key="samples", _loop_state=loop_state, _iteration=2)

    assert appended["outputs"]["value"] == ["S1", "S2"]
    assert length["outputs"] == {"value": 2, "count": 2, "accumulator": {"samples": 2}}
    assert loop_state == {"samples": 2}


@pytest.mark.asyncio
async def test_counter_accumulator_read_only_does_not_mutate_state() -> None:
    node = _node_class("counter_accumulator")()
    loop_state: dict[str, Any] = {"reads": 42}

    result = await node.run(
        operation="add",
        operand=10,
        accumulator_key="reads",
        access_mode="read_only",
        _loop_state=loop_state,
        _iteration=7,
    )

    assert result["outputs"] == {"value": 42, "count": 7, "accumulator": {"reads": 42}}
    assert loop_state == {"reads": 42}


@pytest.mark.asyncio
async def test_parallel_for_scatter_chunks_items() -> None:
    node = _node_class("parallel_for")()

    result = await node.run(
        items=["chr1", "chr2", "chr3", "chr4", "chr5"],
        chunk_size=2,
        max_concurrency=3,
        gather="all",
    )

    assert result["outputs"] == {"results": [], "completed_count": 0, "all_succeeded": False}
    assert result["inactive_outputs"] == ["results", "completed_count", "all_succeeded"]
    assert result["flow_control"] == {
        "type": "parallel_for",
        "phase": "scatter",
        "chunks": [["chr1", "chr2"], ["chr3", "chr4"], ["chr5"]],
        "max_concurrency": 3,
        "gather": "all",
        "first_n": 1,
        "sort_key": "",
    }


@pytest.mark.asyncio
async def test_parallel_for_gathers_first_non_null_results() -> None:
    node = _node_class("parallel_for")()

    any_result = await node.run(items=["a", "b"], gather="any", _parallel_results=[None, "ready", "late"])
    first_result = await node.run(
        items=["a", "b", "c"],
        gather="first",
        first_n=2,
        _parallel_results=["one", None, "two", "three"],
    )

    assert any_result["outputs"] == {"results": "ready", "completed_count": 2, "all_succeeded": False}
    assert any_result["inactive_outputs"] == []
    assert first_result["outputs"] == {"results": ["one", "two"], "completed_count": 3, "all_succeeded": False}


@pytest.mark.asyncio
async def test_parallel_for_sorts_dict_results_by_key() -> None:
    node = _node_class("parallel_for")()

    result = await node.run(
        items=["S2", "S1", "S3"],
        gather="sorted",
        sort_key="sample",
        _parallel_results=[
            {"sample": "S2", "vcf": "s2.vcf"},
            None,
            {"sample": "S1", "vcf": "s1.vcf"},
        ],
    )

    assert result["outputs"] == {
        "results": [
            {"sample": "S1", "vcf": "s1.vcf"},
            {"sample": "S2", "vcf": "s2.vcf"},
        ],
        "completed_count": 2,
        "all_succeeded": False,
    }
    assert result["flow_control"]["phase"] == "gather"


@pytest.mark.asyncio
async def test_while_loop_initial_condition_false_converges_without_iteration(tmp_path: Path) -> None:
    node = _node_class("while_loop")()
    marker = tmp_path / "done.txt"
    marker.write_text("ok", encoding="utf-8")

    result = await node.run(condition_mode="file_not_exists", value=str(marker), max_iterations=5)

    assert result["outputs"] == {"results": [], "iterations": 0, "converged": True}
    assert result["inactive_outputs"] == []
    assert result["flow_control"]["phase"] == "completed"
    assert result["flow_control"]["is_complete"] is True


@pytest.mark.asyncio
async def test_while_loop_initial_condition_true_requests_iteration() -> None:
    node = _node_class("while_loop")()

    result = await node.run(condition_mode="numeric_less", value=1, compare_to="3", max_iterations=5)

    assert result["outputs"] == {"results": [], "iterations": 0, "converged": False}
    assert result["inactive_outputs"] == ["results", "iterations", "converged"]
    assert result["flow_control"]["phase"] == "iterating"
    assert result["flow_control"]["is_complete"] is False
    assert result["flow_control"]["loop_state"]["iteration"] == 0
    assert result["flow_control"]["loop_state"]["max_iterations"] == 5


@pytest.mark.asyncio
async def test_while_loop_iteration_accumulates_result_and_converges() -> None:
    node = _node_class("while_loop")()
    initial = await node.run(condition_mode="numeric_less", value=1, compare_to="3", max_iterations=5)
    loop_state = initial["flow_control"]["loop_state"]

    result = await node.run(
        condition_mode="numeric_less",
        value=4,
        compare_to="3",
        _is_loop_iteration=True,
        _loop_state=loop_state,
        _body_result={"iteration": 1, "score": 4},
    )

    assert result["outputs"] == {
        "results": [{"iteration": 1, "score": 4}],
        "iterations": 1,
        "converged": True,
    }
    assert result["inactive_outputs"] == []
    assert result["flow_control"]["phase"] == "completed"
    assert result["flow_control"]["is_complete"] is True


@pytest.mark.asyncio
async def test_while_loop_honors_check_frequency_between_condition_checks() -> None:
    node = _node_class("while_loop")()
    initial = await node.run(
        condition_mode="numeric_less",
        value=1,
        compare_to="3",
        max_iterations=5,
        check_frequency=2,
    )
    loop_state = initial["flow_control"]["loop_state"]

    first_iteration = await node.run(
        condition_mode="numeric_less",
        value=4,
        compare_to="3",
        _is_loop_iteration=True,
        _loop_state=loop_state,
        _body_result={"iteration": 1, "score": 4},
    )

    assert first_iteration["outputs"] == {
        "results": [{"iteration": 1, "score": 4}],
        "iterations": 1,
        "converged": False,
    }
    assert first_iteration["inactive_outputs"] == ["results", "iterations", "converged"]
    assert first_iteration["flow_control"]["phase"] == "iterating"
    assert first_iteration["flow_control"]["is_complete"] is False

    second_iteration = await node.run(
        condition_mode="numeric_less",
        value=4,
        compare_to="3",
        _is_loop_iteration=True,
        _loop_state=first_iteration["flow_control"]["loop_state"],
        _body_result={"iteration": 2, "score": 4},
    )

    assert second_iteration["outputs"] == {
        "results": [
            {"iteration": 1, "score": 4},
            {"iteration": 2, "score": 4},
        ],
        "iterations": 2,
        "converged": True,
    }
    assert second_iteration["flow_control"]["phase"] == "completed"
    assert second_iteration["flow_control"]["is_complete"] is True


@pytest.mark.asyncio
async def test_while_loop_stops_at_max_iterations_without_convergence() -> None:
    node = _node_class("while_loop")()
    initial = await node.run(condition_mode="boolean_is_true", value=True, max_iterations=1)
    loop_state = initial["flow_control"]["loop_state"]

    result = await node.run(
        condition_mode="boolean_is_true",
        value=True,
        _is_loop_iteration=True,
        _loop_state=loop_state,
        _body_result="round-1",
    )

    assert result["outputs"] == {"results": ["round-1"], "iterations": 1, "converged": False}
    assert result["inactive_outputs"] == []
    assert result["flow_control"]["phase"] == "max_iterations"
    assert result["flow_control"]["is_complete"] is True


@pytest.mark.asyncio
async def test_executor_runs_while_loop_body_until_condition_is_false(tmp_path: Path) -> None:
    while_node = _node_class("while_loop")

    class IncrementNode:
        NODE_ID = "increment"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            type(self).calls += 1
            return {"outputs": {"out": type(self).calls}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"while_loop": while_node, "increment": IncrementNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "loop",
                "type": "while_loop",
                "inputs": {
                    "condition_mode": {"value": "numeric_less"},
                    "value": {"value": 0},
                    "compare_to": {"value": "3"},
                    "max_iterations": {"value": 5},
                },
                "outputs": {"iteration": {}, "results": {}, "iterations": {}, "converged": {}},
            },
            {"id": "step", "type": "increment", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "loop", "target_node": "step", "source_output": "iteration", "target_input": "value"},
            {"source_node": "step", "target_node": "loop", "source_output": "out", "target_input": "value"},
            {"source_node": "step", "target_node": "loop", "source_output": "out", "target_input": "_body_result"},
        ],
    }
    IncrementNode.calls = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("while-loop-body", workflow, force=True)

    assert result["status"] == "completed"
    assert IncrementNode.calls == 3
    assert result["outputs"]["loop"]["results"] == [1, 2, 3]
    assert result["outputs"]["loop"]["iterations"] == 3
    assert result["outputs"]["loop"]["converged"] is True


@pytest.mark.asyncio
async def test_executor_skips_inactive_if_branch_and_descendants(tmp_path: Path) -> None:
    if_node = _node_class("if_condition")

    class RecordingNode:
        NODE_ID = "record"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"if_condition": if_node, "record": RecordingNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "gate",
                "type": "if_condition",
                "inputs": {
                    "value": {"value": 10},
                    "condition_mode": {"value": "numeric_greater"},
                    "compare_to": {"value": "5"},
                },
                "outputs": {"true": {}, "false": {}, "condition_result": {}},
            },
            {"id": "true_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "false_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "false_descendant", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "gate", "target_node": "true_branch", "source_output": "true", "target_input": "value"},
            {"source_node": "gate", "target_node": "false_branch", "source_output": "false", "target_input": "value"},
            {"source_node": "false_branch", "target_node": "false_descendant", "source_output": "out", "target_input": "value"},
        ],
    }
    RecordingNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("if-branches", workflow, force=True)

    assert result["status"] == "completed"
    assert RecordingNode.calls == ["true_branch"]
    assert result["node_results"]["false_branch"]["status"] == "skipped"
    assert result["node_results"]["false_branch"]["reason"] == "inactive_branch"
    assert result["node_results"]["false_descendant"]["status"] == "skipped"
    assert set(result["outputs"]) == {"gate", "true_branch"}


@pytest.mark.asyncio
async def test_executor_skips_inactive_switch_outputs(tmp_path: Path) -> None:
    switch_node = _node_class("switch")

    class RecordingNode:
        NODE_ID = "record"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"switch": switch_node, "record": RecordingNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "route",
                "type": "switch",
                "inputs": {
                    "value": {"value": "rna"},
                    "cases": {"value": "dna,rna,protein"},
                    "passthrough_data": {"value": "sample-42"},
                },
                "outputs": {"output_1": {}, "output_2": {}, "output_3": {}, "output_4": {}, "default": {}},
            },
            {"id": "dna_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "rna_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "default_branch", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "route", "target_node": "dna_branch", "source_output": "output_1", "target_input": "value"},
            {"source_node": "route", "target_node": "rna_branch", "source_output": "output_2", "target_input": "value"},
            {"source_node": "route", "target_node": "default_branch", "source_output": "default", "target_input": "value"},
        ],
    }
    RecordingNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("switch-branches", workflow, force=True)

    assert result["status"] == "completed"
    assert RecordingNode.calls == ["rna_branch"]
    assert result["node_results"]["dna_branch"]["status"] == "skipped"
    assert result["node_results"]["default_branch"]["status"] == "skipped"
    assert result["outputs"]["rna_branch"] == {"out": "sample-42"}


@pytest.mark.asyncio
async def test_executor_skips_inactive_switch_rule_outputs(tmp_path: Path) -> None:
    switch_node = _node_class("switch")

    class RecordingNode:
        NODE_ID = "record"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"switch": switch_node, "record": RecordingNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "route",
                "type": "switch",
                "inputs": {
                    "value": {"value": "tumor_RNA"},
                    "rules": {
                        "value": json.dumps([
                            {"branch_index": 0, "match_type": "contains", "pattern": "tumor"},
                            {"branch_index": 2, "match_type": "regex", "pattern": "RNA$"},
                        ])
                    },
                    "match_mode": {"value": "all"},
                    "fallback": {"value": "drop"},
                    "passthrough_data": {"value": "sample.tsv"},
                },
                "outputs": {"output_1": {}, "output_2": {}, "output_3": {}, "output_4": {}, "default": {}},
            },
            {"id": "tumor_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "normal_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "rna_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "default_branch", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "route", "target_node": "tumor_branch", "source_output": "output_1", "target_input": "value"},
            {"source_node": "route", "target_node": "normal_branch", "source_output": "output_2", "target_input": "value"},
            {"source_node": "route", "target_node": "rna_branch", "source_output": "output_3", "target_input": "value"},
            {"source_node": "route", "target_node": "default_branch", "source_output": "default", "target_input": "value"},
        ],
    }
    RecordingNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("switch-rule-branches", workflow, force=True)

    assert result["status"] == "completed"
    assert RecordingNode.calls == ["tumor_branch", "rna_branch"]
    assert result["node_results"]["normal_branch"]["status"] == "skipped"
    assert result["node_results"]["default_branch"]["status"] == "skipped"
    assert result["outputs"]["tumor_branch"] == {"out": "sample.tsv"}
    assert result["outputs"]["rna_branch"] == {"out": "sample.tsv"}


@pytest.mark.asyncio
async def test_cached_flow_control_preserves_inactive_outputs(tmp_path: Path) -> None:
    if_node = _node_class("if_condition")

    class RecordingNode:
        NODE_ID = "record"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"if_condition": if_node, "record": RecordingNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "gate",
                "type": "if_condition",
                "inputs": {
                    "value": {"value": "ready"},
                    "condition_mode": {"value": "not_empty"},
                    "compare_to": {"value": ""},
                },
                "outputs": {"true": {}, "false": {}, "condition_result": {}},
            },
            {"id": "true_branch", "type": "record", "outputs": {"out": {}}},
            {"id": "false_branch", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "gate", "target_node": "true_branch", "source_output": "true", "target_input": "value"},
            {"source_node": "gate", "target_node": "false_branch", "source_output": "false", "target_input": "value"},
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    RecordingNode.calls = []
    first = await executor.execute("first", workflow)
    assert first["status"] == "completed"
    assert RecordingNode.calls == ["true_branch"]

    RecordingNode.calls = []
    second = await executor.execute("second", workflow)

    assert second["status"] == "completed"
    assert second["node_results"]["gate"]["status"] == "cached"
    assert second["node_results"]["true_branch"]["status"] == "cached"
    assert second["node_results"]["false_branch"]["status"] == "skipped"
    assert second["outputs"]["true_branch"] == {"out": "ready"}
    assert RecordingNode.calls == []


@pytest.mark.asyncio
async def test_executor_runs_foreach_body_subgraph_for_each_item(tmp_path: Path) -> None:
    foreach_node = _node_class("foreach")

    class BodyNode:
        NODE_ID = "body"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[tuple[str, Any]] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append((context.node_id, value))
            return {"outputs": {"out": f"{context.node_id}:{value}"}}

    class CollectorNode:
        NODE_ID = "collector"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": value}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "foreach": foreach_node,
                "body": BodyNode,
                "collector": CollectorNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "loop",
                "type": "foreach",
                "inputs": {
                    "items": {"value": ["S1", "S2", "S3"]},
                    "iteration_mode": {"value": "single"},
                    "collect_mode": {"value": "list"},
                    "max_iterations": {"value": 10},
                },
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            {"id": "step_a", "type": "body", "outputs": {"out": {}}},
            {"id": "step_b", "type": "body", "outputs": {"out": {}}},
            {"id": "after_loop", "type": "collector", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "loop", "target_node": "step_a", "source_output": "iteration", "target_input": "value"},
            {"source_node": "step_a", "target_node": "step_b", "source_output": "out", "target_input": "value"},
            {"source_node": "step_b", "target_node": "loop", "source_output": "out", "target_input": "body_result"},
            {"source_node": "loop", "target_node": "after_loop", "source_output": "results", "target_input": "value"},
        ],
    }
    BodyNode.calls = []
    CollectorNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("foreach-body", workflow, force=True)

    expected_results = [
        "step_b:step_a:S1",
        "step_b:step_a:S2",
        "step_b:step_a:S3",
    ]
    assert result["status"] == "completed"
    assert BodyNode.calls == [
        ("step_a", "S1"),
        ("step_b", "step_a:S1"),
        ("step_a", "S2"),
        ("step_b", "step_a:S2"),
        ("step_a", "S3"),
        ("step_b", "step_a:S3"),
    ]
    assert result["outputs"]["loop"]["iteration"] is None
    assert result["outputs"]["loop"]["results"] == expected_results
    assert result["outputs"]["loop"]["count"] == 3
    assert result["outputs"]["loop"]["all_succeeded"] is True
    assert CollectorNode.calls == [expected_results]
    assert result["outputs"]["after_loop"] == {"out": expected_results}


@pytest.mark.asyncio
async def test_executor_foreach_injects_shared_loop_state_and_iteration_for_counter_accumulator(
    tmp_path: Path,
) -> None:
    registry = _loaded_registry()
    workflow = {
        "nodes": [
            {
                "id": "loop",
                "type": "foreach",
                "inputs": {
                    "items": {"value": ["S1", "S2", "S3"]},
                    "iteration_mode": {"value": "single"},
                    "collect_mode": {"value": "list"},
                    "max_iterations": {"value": 10},
                },
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            {
                "id": "accumulate",
                "type": "counter_accumulator",
                "inputs": {
                    "operation": {"value": "append"},
                    "accumulator_key": {"value": "samples"},
                },
                "outputs": {"value": {}, "count": {}, "accumulator": {}},
            },
        ],
        "edges": [
            {
                "source_node": "loop",
                "target_node": "accumulate",
                "source_output": "iteration",
                "target_input": "operand",
            },
            {
                "source_node": "accumulate",
                "target_node": "loop",
                "source_output": "value",
                "target_input": "body_result",
            },
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute("foreach-counter", workflow, force=True)

    assert result["status"] == "completed"
    assert result["outputs"]["loop"]["results"] == [
        ["S1"],
        ["S1", "S2"],
        ["S1", "S2", "S3"],
    ]
    assert result["outputs"]["loop"]["count"] == 3


@pytest.mark.asyncio
async def test_executor_foreach_continue_skips_remaining_body_for_iteration(tmp_path: Path) -> None:
    foreach_node = _node_class("foreach")
    break_continue_node = _node_class("break_continue")

    class ContinueOnS2Node:
        NODE_ID = "continue_on_s2"
        RETURN_NAMES = ("signal", "value", "triggered", "reason")
        RETURN_TYPES = ("STRING", "ANY", "BOOLEAN", "STRING")
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return await break_continue_node().run(
                action="continue",
                condition=value == "S2",
                value=value,
                reason="skip S2",
            )

    class BodyNode:
        NODE_ID = "body"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": f"processed:{value}"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "foreach": foreach_node,
                "continue_on_s2": ContinueOnS2Node,
                "body": BodyNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "loop",
                "type": "foreach",
                "inputs": {
                    "items": {"value": ["S1", "S2", "S3"]},
                    "iteration_mode": {"value": "single"},
                    "collect_mode": {"value": "list"},
                },
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            {"id": "control", "type": "continue_on_s2", "outputs": {"signal": {}, "value": {}, "triggered": {}, "reason": {}}},
            {"id": "body", "type": "body", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "loop", "target_node": "control", "source_output": "iteration", "target_input": "value"},
            {"source_node": "control", "target_node": "body", "source_output": "value", "target_input": "value"},
            {"source_node": "body", "target_node": "loop", "source_output": "out", "target_input": "body_result"},
        ],
    }
    ContinueOnS2Node.calls = []
    BodyNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("foreach-continue", workflow, force=True)

    assert result["status"] == "completed"
    assert ContinueOnS2Node.calls == ["S1", "S2", "S3"]
    assert BodyNode.calls == ["S1", "S3"]
    assert result["outputs"]["loop"]["results"] == ["processed:S1", "processed:S3"]
    assert result["outputs"]["loop"]["count"] == 3
    assert result["outputs"]["loop"]["all_succeeded"] is True


@pytest.mark.asyncio
async def test_executor_foreach_break_stops_remaining_iterations(tmp_path: Path) -> None:
    foreach_node = _node_class("foreach")
    break_continue_node = _node_class("break_continue")

    class BreakOnS2Node:
        NODE_ID = "break_on_s2"
        RETURN_NAMES = ("signal", "value", "triggered", "reason")
        RETURN_TYPES = ("STRING", "ANY", "BOOLEAN", "STRING")
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return await break_continue_node().run(
                action="break",
                condition=value == "S2",
                value=value,
                reason="stop at S2",
            )

    class BodyNode:
        NODE_ID = "body"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[Any] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append(value)
            return {"outputs": {"out": f"processed:{value}"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "foreach": foreach_node,
                "break_on_s2": BreakOnS2Node,
                "body": BodyNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "loop",
                "type": "foreach",
                "inputs": {
                    "items": {"value": ["S1", "S2", "S3"]},
                    "iteration_mode": {"value": "single"},
                    "collect_mode": {"value": "list"},
                },
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            {"id": "control", "type": "break_on_s2", "outputs": {"signal": {}, "value": {}, "triggered": {}, "reason": {}}},
            {"id": "body", "type": "body", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "loop", "target_node": "control", "source_output": "iteration", "target_input": "value"},
            {"source_node": "control", "target_node": "body", "source_output": "value", "target_input": "value"},
            {"source_node": "body", "target_node": "loop", "source_output": "out", "target_input": "body_result"},
        ],
    }
    BreakOnS2Node.calls = []
    BodyNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("foreach-break", workflow, force=True)

    assert result["status"] == "completed"
    assert BreakOnS2Node.calls == ["S1", "S2"]
    assert BodyNode.calls == ["S1"]
    assert result["outputs"]["loop"]["results"] == ["processed:S1"]
    assert result["outputs"]["loop"]["count"] == 2
    assert result["outputs"]["loop"]["all_succeeded"] is True


@pytest.mark.asyncio
async def test_executor_foreach_body_honors_inactive_branch_outputs(tmp_path: Path) -> None:
    foreach_node = _node_class("foreach")
    if_node = _node_class("if_condition")

    class BranchRecorderNode:
        NODE_ID = "branch_recorder"
        RETURN_NAMES = ("out",)
        RETURN_TYPES = ("ANY",)
        calls: list[tuple[str, Any]] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, value: Any) -> dict[str, Any]:
            self.calls.append((context.node_id, value))
            return {"outputs": {"out": f"{context.node_id}:{value}"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {
                "foreach": foreach_node,
                "if_condition": if_node,
                "branch_recorder": BranchRecorderNode,
            }.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "loop",
                "type": "foreach",
                "inputs": {
                    "items": {"value": ["S1", "S2", "S3"]},
                    "iteration_mode": {"value": "single"},
                    "collect_mode": {"value": "list"},
                },
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            {
                "id": "route",
                "type": "if_condition",
                "inputs": {
                    "condition_mode": {"value": "string_equal"},
                    "compare_to": {"value": "S2"},
                },
                "outputs": {"true": {}, "false": {}, "condition_result": {}},
            },
            {"id": "true_body", "type": "branch_recorder", "outputs": {"out": {}}},
            {"id": "false_body", "type": "branch_recorder", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "loop", "target_node": "route", "source_output": "iteration", "target_input": "value"},
            {"source_node": "route", "target_node": "true_body", "source_output": "true", "target_input": "value"},
            {"source_node": "route", "target_node": "false_body", "source_output": "false", "target_input": "value"},
            {"source_node": "true_body", "target_node": "loop", "source_output": "out", "target_input": "body_result"},
            {"source_node": "false_body", "target_node": "loop", "source_output": "out", "target_input": "body_result"},
        ],
    }
    BranchRecorderNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("foreach-branch-routing", workflow, force=True)

    assert result["status"] == "completed"
    assert BranchRecorderNode.calls == [
        ("false_body", "S1"),
        ("true_body", "S2"),
        ("false_body", "S3"),
    ]
    assert result["outputs"]["loop"]["results"] == [
        "false_body:S1",
        "true_body:S2",
        "false_body:S3",
    ]
