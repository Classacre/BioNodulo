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
