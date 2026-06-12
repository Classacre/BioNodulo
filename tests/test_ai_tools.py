from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from bionodulo.ai.assistant import chat_with_tools
from bionodulo.ai.tools import ToolContext, execute_tool


class DummyRegistry:
    def object_info(self, node_type: str | None = None):
        data = {
            "input_fastq": {
                "display_name": "Input FASTQ",
                "category": "Input",
                "description": "FASTQ input",
                "input_types": {"required": {}, "optional": {"path": {"type": "STRING", "default": ""}}},
                "return_types": ["FASTQ"],
                "return_names": ["fastq"],
            },
            "fastqc": {
                "display_name": "FastQC",
                "category": "QC",
                "description": "Quality control",
                "input_types": {"required": {"fastq": {"type": "FASTQ"}}},
                "return_types": ["HTML"],
                "return_names": ["report"],
                "requires_external_tools": ["fastqc"],
            },
        }
        return data if node_type is None else data.get(node_type)


def test_ai_graph_tools_preserve_workflow_id_and_validate_edges():
    ctx = ToolContext(
        workflow={"id": "wf-local", "nodes": [], "edges": []},
        workflow_id="wf-local",
        registry=DummyRegistry(),
    )

    first = execute_tool("add_node", {"node_type": "input_fastq"}, ctx)
    second = execute_tool("add_node", {"node_type": "fastqc"}, ctx)
    nodes = ctx.workflow["nodes"]
    edge = execute_tool(
        "add_edge",
        {
            "from_node": nodes[0]["id"],
            "from_output": "fastq",
            "to_node": nodes[1]["id"],
            "to_input": "fastq",
        },
        ctx,
    )

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert edge["status"] == "ok"
    assert ctx.workflow["id"] == "wf-local"
    assert len(ctx.workflow["edges"]) == 1


def test_ai_graph_tools_reject_unknown_slots():
    ctx = ToolContext(
        workflow={"id": "wf-local", "nodes": [], "edges": []},
        workflow_id="wf-local",
        registry=DummyRegistry(),
    )
    execute_tool("add_node", {"node_type": "input_fastq"}, ctx)
    execute_tool("add_node", {"node_type": "fastqc"}, ctx)
    nodes = ctx.workflow["nodes"]

    result = execute_tool(
        "add_edge",
        {
            "from_node": nodes[0]["id"],
            "from_output": "not_a_real_output",
            "to_node": nodes[1]["id"],
            "to_input": "fastq",
        },
        ctx,
    )

    assert result["status"] == "error"
    assert "not_a_real_output" in result["error"]


@pytest.mark.asyncio
async def test_ai_chat_uses_litellm_native_tool_calls(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="",
                            tool_calls=[
                                SimpleNamespace(
                                    id="call_1",
                                    type="function",
                                    function=SimpleNamespace(
                                        name="get_current_workflow",
                                        arguments="{}",
                                    ),
                                )
                            ],
                        )
                    )
                ]
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="The workflow is empty.", tool_calls=[]))]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))

    response = await chat_with_tools(
        "What is on the canvas?",
        workflow={"id": "wf-local", "nodes": [], "edges": []},
        history=[],
        workflow_id="wf-local",
        registry=DummyRegistry(),
        api_key="sk-test",
    )

    assert calls[0]["tools"]
    assert "tool_choice" in calls[0]
    assert any(step.type == "tool_call" and step.name == "get_current_workflow" for step in response.steps)
    assert response.reply == "The workflow is empty."


# --- Autonomous-agent tool tests (no live LLM required) ---------------------

from pathlib import Path  # noqa: E402

from bionodulo.ai.tools import aexecute_tool  # noqa: E402
from bionodulo.execution.executor import WorkflowExecutor  # noqa: E402


class _SleeperNode:
    RETURN_NAMES = ("done",)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context=None, **_):
        return {"outputs": {"done": "ok"}}


class _RunRegistry:
    def get(self, node_type: str):
        return {"sleeper": _SleeperNode}.get(node_type)

    def object_info(self, node_type=None):
        data = {"sleeper": {"display_name": "Sleeper", "category": "Test", "return_names": ["done"]}}
        return data if node_type is None else data.get(node_type)


@pytest.mark.asyncio
async def test_run_workflow_tool_executes_and_reports_status(tmp_path):
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_RunRegistry())
    workflow = {"id": "wf", "nodes": [{"id": "n1", "type": "sleeper"}], "edges": []}
    ctx = ToolContext(
        workflow=workflow,
        workflow_id="wf",
        registry=_RunRegistry(),
        run_queue=SimpleNamespace(executor=executor),
    )

    result = await aexecute_tool("run_workflow", {}, ctx)

    assert result["status"] == "ok"
    assert result["result"]["status"] == "completed"
    assert result["result"]["node_statuses"]["n1"] == "completed"


@pytest.mark.asyncio
async def test_run_workflow_tool_rejects_invalid_graph(tmp_path):
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_RunRegistry())
    workflow = {"id": "wf", "nodes": [{"id": "n1", "type": "does_not_exist"}], "edges": []}
    ctx = ToolContext(
        workflow=workflow,
        workflow_id="wf",
        registry=_RunRegistry(),
        run_queue=SimpleNamespace(executor=executor),
    )

    result = await aexecute_tool("run_workflow", {}, ctx)

    assert result["status"] == "error"
    assert "validation_errors" in result.get("result", {})


def test_read_run_logs_tool_returns_tail(tmp_path):
    node_dir = tmp_path / "runs" / "r1" / "nodeA"
    node_dir.mkdir(parents=True)
    (node_dir / "stdout.log").write_text("line one\nline two\n")
    (node_dir / "stderr.log").write_text("boom: something failed\n")
    ctx = ToolContext(workflow={}, settings=SimpleNamespace(project_root=tmp_path))

    result = execute_tool("read_run_logs", {"run_id": "r1"}, ctx)

    assert result["status"] == "ok"
    tail = result["result"]["log_tail"]
    assert any("line two" in line for line in tail)
    assert any("boom" in line for line in tail)


def test_get_run_history_tool_reads_queue():
    queue = SimpleNamespace(
        list_history=lambda: [
            {"run_id": "r2", "name": "Second", "status": "failed"},
            {"run_id": "r1", "name": "First", "status": "completed"},
        ]
    )
    ctx = ToolContext(workflow={}, run_queue=queue)

    result = execute_tool("get_run_history", {"limit": 5}, ctx)

    assert result["status"] == "ok"
    assert result["result"]["runs"][0]["run_id"] == "r2"
    assert result["result"]["count"] == 2


def test_write_custom_node_tool_writes_module(tmp_path):
    ctx = ToolContext(
        workflow={},
        settings=SimpleNamespace(project_root=tmp_path, custom_nodes_dir="custom_nodes"),
    )

    result = execute_tool(
        "write_custom_node",
        {"name": "my_tool", "code": "# a custom node\n", "requirements": ["samtools"]},
        ctx,
    )

    assert result["status"] == "ok"
    assert (tmp_path / "custom_nodes" / "my_tool.py").is_file()
    assert (tmp_path / "custom_nodes" / "my_tool.requirements.txt").read_text().strip() == "samtools"


def test_read_workspace_file_tool_is_traversal_safe(tmp_path):
    (tmp_path / "data.txt").write_text("payload-here")
    ctx = ToolContext(workflow={}, settings=SimpleNamespace(project_root=tmp_path))

    ok = execute_tool("read_workspace_file", {"path": "data.txt"}, ctx)
    assert ok["status"] == "ok"
    assert "payload-here" in ok["result"]["content"]

    escape = execute_tool("read_workspace_file", {"path": "../../../etc/passwd"}, ctx)
    assert escape["status"] == "error"


@pytest.mark.asyncio
async def test_ai_autonomously_runs_fixes_and_reruns_workflow(tmp_path, monkeypatch):
    """End-to-end proof of the autonomous debug loop with a scripted LLM.

    The model runs the workflow (which fails), edits the failing node's param,
    re-runs (which now succeeds), then replies — all inside one chat turn.
    """
    import json as _json

    class FlakyNode:
        RETURN_NAMES = ("done",)

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {}, "optional": {"fixed": ("BOOLEAN", {"default": False})}, "hidden": {}}

        async def run(self, context=None, fixed=False, **_):
            if not fixed:
                raise RuntimeError("node needs the 'fixed' flag")
            return {"outputs": {"done": "ok"}}

    class Registry:
        def get(self, node_type):
            return {"flaky": FlakyNode}.get(node_type)

        def object_info(self, node_type=None):
            data = {"flaky": {"display_name": "Flaky", "category": "Test", "return_names": ["done"]}}
            return data if node_type is None else data.get(node_type)

    calls: list[dict] = []

    def _tool_call(call_index: int, name: str, args: dict):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id=f"c{call_index}",
                                type="function",
                                function=SimpleNamespace(name=name, arguments=_json.dumps(args)),
                            )
                        ],
                    )
                )
            ]
        )

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        n = len(calls)
        if n == 1:
            return _tool_call(n, "run_workflow", {})
        if n == 2:
            return _tool_call(n, "update_node", {"node_id": "n1", "params": {"fixed": True}})
        if n == 3:
            return _tool_call(n, "run_workflow", {})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Fixed the node and re-ran successfully.", tool_calls=[]))]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())
    workflow = {"id": "wf", "nodes": [{"id": "n1", "type": "flaky", "params": {}}], "edges": []}

    response = await chat_with_tools(
        "Make this workflow run successfully.",
        workflow=workflow,
        history=[],
        workflow_id="wf",
        registry=Registry(),
        run_queue=SimpleNamespace(executor=executor),
        api_key="sk-test",
    )

    run_results = [
        step.result["result"]
        for step in response.steps
        if step.type == "tool_result" and step.name == "run_workflow" and isinstance(step.result, dict)
    ]
    assert len(run_results) == 2
    assert run_results[0]["status"] == "failed"  # first run fails
    assert run_results[1]["status"] == "completed"  # after the autonomous fix
    assert "successfully" in response.reply.lower()
