"""Unit tests for the AI assistant's compositional tools.

Covers add_group, add_note, save_as_template, extract_subgraph,
add_subgraph_instance, get_run_events, and list_flow_control_nodes using the
same ToolContext + execute_tool pattern as tests/test_ai_tools.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bionodulo.ai.tools as tools_module
from bionodulo.ai.tools import ToolContext, execute_tool, get_tool
from bionodulo.workflow.validation import validate_workflow


class _SrcNode:
    NODE_ID = "src"
    RETURN_NAMES = ("out",)
    RETURN_TYPES = ("ANY",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}


class _StepNode:
    NODE_ID = "step"
    RETURN_NAMES = ("out",)
    RETURN_TYPES = ("ANY",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        # The default keeps inner subgraph workflows valid even when a required
        # input arrives through a parent-mapped port rather than an inner edge.
        return {"required": {"data": ("ANY", {"default": None})}, "optional": {}, "hidden": {}}


class _Registry:
    """Registry usable by both the tools (object_info) and the validator (get)."""

    def get(self, node_type: str) -> Any:
        return {"src": _SrcNode, "step": _StepNode}.get(node_type)

    def object_info(self, node_type: str | None = None) -> Any:
        data = {
            "src": {
                "display_name": "Source",
                "category": "Test",
                "description": "Emits a value",
                "input_types": {"required": {}, "optional": {}},
                "return_types": ["ANY"],
                "return_names": ["out"],
            },
            "step": {
                "display_name": "Step",
                "category": "Test",
                "description": "Processes a value",
                "input_types": {"required": {"data": {"type": "ANY"}}, "optional": {}},
                "return_types": ["ANY"],
                "return_names": ["out"],
            },
        }
        return data if node_type is None else data.get(node_type)


def _fresh_ctx() -> ToolContext:
    return ToolContext(
        workflow={"id": "wf-compose", "nodes": [], "edges": []},
        workflow_id="wf-compose",
        registry=_Registry(),
    )


def _pipeline_ctx() -> ToolContext:
    """src -> a -> b -> sink built through the add_node/add_edge tools."""
    ctx = _fresh_ctx()
    execute_tool("add_node", {"node_type": "src", "position": [0, 0]}, ctx)
    execute_tool("add_node", {"node_type": "step", "position": [200, 0]}, ctx)
    execute_tool("add_node", {"node_type": "step", "position": [400, 0]}, ctx)
    execute_tool("add_node", {"node_type": "step", "position": [600, 0]}, ctx)
    ids = [node["id"] for node in ctx.workflow["nodes"]]
    src, a, b, sink = ids
    for from_node, to_node in ((src, a), (a, b), (b, sink)):
        result = execute_tool(
            "add_edge",
            {"from_node": from_node, "from_output": "out", "to_node": to_node, "to_input": "data"},
            ctx,
        )
        assert result["status"] == "ok", result
    return ctx


# --- add_group ---------------------------------------------------------------


def test_add_group_computes_bounding_box_from_nodes() -> None:
    ctx = _fresh_ctx()
    execute_tool("add_node", {"node_type": "src", "position": [100, 100]}, ctx)
    execute_tool("add_node", {"node_type": "step", "position": [300, 260]}, ctx)
    ids = [node["id"] for node in ctx.workflow["nodes"]]

    result = execute_tool("add_group", {"name": "QC", "node_ids": ids}, ctx)

    assert result["status"] == "ok", result
    group = result["result"]["added_group"]
    assert group["name"] == "QC"
    assert group["node_ids"] == ids
    assert group["color"] == "#6366f1"
    # 60px padding around the [100,100]-[300,260] bounding box.
    assert group["position"] == [40, 40]
    assert group["width"] == pytest.approx(320)
    assert group["height"] == pytest.approx(280)
    assert ctx.workflow["groups"] == [group]


def test_add_group_honors_position_and_color_overrides() -> None:
    ctx = _fresh_ctx()
    execute_tool("add_node", {"node_type": "src", "position": [0, 0]}, ctx)
    ids = [ctx.workflow["nodes"][0]["id"]]

    result = execute_tool(
        "add_group",
        {"name": "Custom", "node_ids": ids, "position": [10, 20], "color": "#ff0000"},
        ctx,
    )

    assert result["status"] == "ok"
    group = result["result"]["added_group"]
    assert group["position"] == [10, 20]
    assert group["color"] == "#ff0000"


def test_add_group_rejects_unknown_node_ids() -> None:
    ctx = _fresh_ctx()

    result = execute_tool("add_group", {"name": "Bad", "node_ids": ["ghost"]}, ctx)

    assert result["status"] == "error"
    assert "ghost" in result["error"]
    assert ctx.workflow["groups"] == []


# --- add_note ----------------------------------------------------------------


def test_add_note_creates_visual_note_node() -> None:
    ctx = _fresh_ctx()

    result = execute_tool("add_note", {"text": "Line one\nLine two"}, ctx)

    assert result["status"] == "ok", result
    node = result["result"]["added_node"]
    assert node["type"] == "note"
    assert node["id"].startswith("note_")
    assert node["params"]["text"] == "Line one\nLine two"
    assert len(node["position"]) == 2
    assert ctx.workflow["nodes"] == [node]


def test_add_note_rejects_empty_text_and_honors_position() -> None:
    ctx = _fresh_ctx()

    empty = execute_tool("add_note", {"text": "   "}, ctx)
    assert empty["status"] == "error"

    placed = execute_tool("add_note", {"text": "hi", "position": [5, 6]}, ctx)
    assert placed["status"] == "ok"
    assert placed["result"]["added_node"]["position"] == [5, 6]


# --- save_as_template ----------------------------------------------------------


def test_save_as_template_writes_loadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools_module, "TEMPLATES_DIR", tmp_path)
    ctx = _pipeline_ctx()
    execute_tool("add_note", {"text": "pipeline notes"}, ctx)

    result = execute_tool(
        "save_as_template",
        {"name": "My Pipeline", "description": "demo", "tags": ["qc", "demo"]},
        ctx,
    )

    assert result["status"] == "ok", result
    path = tmp_path / "my_pipeline.json"
    assert path.is_file()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == "2.0"
    assert saved["app"] == "bionodulo"
    assert saved["name"] == "My Pipeline"
    assert saved["description"] == "demo"
    assert saved["category"] == "Custom"
    assert saved["tags"] == ["qc", "demo"]
    assert "id" not in saved  # every load gets a fresh workflow id
    assert len(saved["nodes"]) == 5  # 4 pipeline nodes + the note
    assert isinstance(saved["groups"], list)
    assert isinstance(saved["outputs"], dict)

    # The saved template round-trips through load_template.
    loaded = execute_tool("load_template", {"template_name": "my_pipeline"}, ctx)
    assert loaded["status"] == "ok"
    assert loaded["result"]["template"] == "my_pipeline"


def test_save_as_template_rejects_empty_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools_module, "TEMPLATES_DIR", tmp_path)
    ctx = _fresh_ctx()

    result = execute_tool("save_as_template", {"name": "  ", "description": "x"}, ctx)

    assert result["status"] == "error"
    assert list(tmp_path.glob("*.json")) == []


# --- extract_subgraph ----------------------------------------------------------


def test_extract_subgraph_from_pipeline_produces_valid_subgraph_node() -> None:
    ctx = _pipeline_ctx()
    src, a, b, sink = [node["id"] for node in ctx.workflow["nodes"]]

    result = execute_tool("extract_subgraph", {"node_ids": [a, b], "name": "Middle"}, ctx)

    assert result["status"] == "ok", result
    subgraph = result["result"]["subgraph_node"]
    assert subgraph["type"] == "subgraph"
    assert subgraph["ui"]["title"] == "Middle"

    # Crossing edges became ports named in__<node>__<slot> / out__<node>__<slot>.
    in_ports = result["result"]["input_ports"]
    out_ports = result["result"]["output_ports"]
    assert [p["name"] for p in in_ports] == [f"in__{a}__data"]
    assert in_ports[0]["innerNodeId"] == a
    assert in_ports[0]["innerSlot"] == "data"
    assert [p["name"] for p in out_ports] == [f"out__{b}__out"]
    assert subgraph["params"]["input_ports"] == in_ports
    assert subgraph["params"]["output_ports"] == out_ports

    # The embedded workflow carries the selected nodes and the inner edge only.
    inner = subgraph["params"]["workflow"]
    assert [n["id"] for n in inner["nodes"]] == [a, b]
    assert len(inner["edges"]) == 1
    assert inner["name"] == "Middle"
    assert inner["version"] == "2.0"

    # Parent: selection replaced by the subgraph node, external edges rewired.
    parent_ids = {n["id"] for n in ctx.workflow["nodes"]}
    assert parent_ids == {src, sink, subgraph["id"]}
    assert len(ctx.workflow["edges"]) == 2
    into_sub = next(e for e in ctx.workflow["edges"] if e["to"]["node"] == subgraph["id"])
    out_of_sub = next(e for e in ctx.workflow["edges"] if e["from"]["node"] == subgraph["id"])
    assert into_sub["from"]["node"] == src
    assert into_sub["to"]["input"] == f"in__{a}__data"
    assert out_of_sub["to"]["node"] == sink
    assert out_of_sub["from"]["output"] == f"out__{b}__out"

    # The rewritten parent graph still validates (ports declared, inner too).
    validation = validate_workflow(ctx.workflow, _Registry())
    assert validation.valid, validation.errors


def test_extract_subgraph_moves_fully_inner_group() -> None:
    ctx = _pipeline_ctx()
    src, a, b, sink = [node["id"] for node in ctx.workflow["nodes"]]
    execute_tool("add_group", {"name": "Middle", "node_ids": [a, b]}, ctx)
    outer_group_added = execute_tool("add_group", {"name": "All", "node_ids": [src, a, b, sink]}, ctx)
    assert outer_group_added["status"] == "ok"

    result = execute_tool("extract_subgraph", {"node_ids": [a, b], "name": "Middle"}, ctx)

    assert result["status"] == "ok"
    inner_groups = result["result"]["subgraph_node"]["params"]["workflow"]["groups"]
    assert [g["name"] for g in inner_groups] == ["Middle"]
    assert [g["name"] for g in ctx.workflow["groups"]] == ["All"]


def test_extract_subgraph_rejects_unknown_nodes() -> None:
    ctx = _fresh_ctx()

    result = execute_tool("extract_subgraph", {"node_ids": ["ghost"], "name": "X"}, ctx)

    assert result["status"] == "error"
    assert "ghost" in result["error"]


# --- add_subgraph_instance ------------------------------------------------------


def test_add_subgraph_instance_loads_and_wraps_saved_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tools_module, "TEMPLATES_DIR", tmp_path)

    step_meta = _Registry().object_info("step")
    template_wf = {
        "version": "2.0",
        "app": "bionodulo",
        "name": "Mini Template",
        "description": "one step",
        "nodes": [
            {
                "id": "n2",
                "type": "step",
                "position": [0, 0],
                "params": {},
                "node_info": step_meta,
            }
        ],
        "edges": [],
        "groups": [],
        "outputs": {"o": "n2"},
    }
    (tmp_path / "mini_template.json").write_text(json.dumps(template_wf), encoding="utf-8")

    ctx = _fresh_ctx()
    result = execute_tool("add_subgraph_instance", {"template_name": "mini_template", "position": [7, 8]}, ctx)

    assert result["status"] == "ok", result
    node = result["result"]["added_node"]
    assert node["type"] == "subgraph"
    assert node["position"] == [7, 8]
    assert node["params"]["workflow"]["name"] == "Mini Template"
    assert node["params"]["workflow"]["nodes"][0]["id"] == "n2"

    params = node["params"]
    # Output ports from the template's exposed outputs map.
    assert [p["name"] for p in params["output_ports"]] == ["out__n2__o"]
    assert params["output_ports"][0]["innerNodeId"] == "n2"
    assert params["output_ports"][0]["innerSlot"] == "default"
    # Input ports from the template's unconnected required inputs.
    assert [p["name"] for p in params["input_ports"]] == ["in__n2__data"]
    assert node["node_info"]["return_names"] == ["out__n2__o"]
    assert ctx.workflow["nodes"] == [node]


def test_add_subgraph_instance_falls_back_to_sink_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tools_module, "TEMPLATES_DIR", tmp_path)
    meta = _Registry().object_info
    template_wf = {
        "version": "2.0",
        "app": "bionodulo",
        "name": "Chain",
        "nodes": [
            {"id": "c1", "type": "src", "position": [0, 0], "params": {}, "node_info": meta("src")},
            {"id": "c2", "type": "step", "position": [1, 0], "params": {}, "node_info": meta("step")},
        ],
        "edges": [{"id": "e1", "from": {"node": "c1", "output": "out"}, "to": {"node": "c2", "input": "data"}}],
        "groups": [],
        "outputs": {},
    }
    (tmp_path / "chain_template.json").write_text(json.dumps(template_wf), encoding="utf-8")

    ctx = _fresh_ctx()
    result = execute_tool("add_subgraph_instance", {"template_name": "chain_template"}, ctx)

    assert result["status"] == "ok", result
    node = result["result"]["added_node"]
    # No declared outputs: the sink node's outputs are exposed instead.
    assert [p["name"] for p in node["params"]["output_ports"]] == ["out__c2__out"]
    # c2's required input is connected inside the template, so no input ports.
    assert node["params"]["input_ports"] == []


def test_add_subgraph_instance_reports_missing_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tools_module, "TEMPLATES_DIR", tmp_path)
    ctx = _fresh_ctx()

    result = execute_tool("add_subgraph_instance", {"template_name": "nope"}, ctx)

    assert result["status"] == "error"
    assert "nope" in result["error"]


# --- get_run_events ------------------------------------------------------------


def test_get_run_events_formats_timeline_and_honors_limit() -> None:
    calls: dict[str, Any] = {}
    events = [
        {"run_id": "r1", "seq": 1, "ts": 1.0, "type": "queue_submit", "payload": {"status": "pending"}},
        {"run_id": "r1", "seq": 2, "ts": 2.0, "type": "node_complete", "payload": {"node": "n1"}},
    ]

    def fake_get_events(run_id: str, limit: int = 50) -> list[dict[str, Any]]:
        calls["run_id"] = run_id
        calls["limit"] = limit
        return events

    ctx = ToolContext(workflow={}, run_queue=SimpleNamespace(get_run_events=fake_get_events))

    result = execute_tool("get_run_events", {"run_id": "r1", "limit": 10}, ctx)

    assert result["status"] == "ok", result
    assert calls == {"run_id": "r1", "limit": 10}
    payload = result["result"]
    assert payload["count"] == 2
    assert payload["events"] == events
    assert payload["timeline"][0] == "#1 [queue_submit] {\"status\": \"pending\"}"
    assert payload["timeline"][1].startswith("#2 [node_complete]")


def test_get_run_events_handles_missing_store_and_queue() -> None:
    no_attr = ToolContext(workflow={}, run_queue=SimpleNamespace())
    assert execute_tool("get_run_events", {"run_id": "r1"}, no_attr)["status"] == "error"

    def returns_none(run_id: str, limit: int = 50) -> None:
        return None

    no_store = ToolContext(workflow={}, run_queue=SimpleNamespace(get_run_events=returns_none))
    result = execute_tool("get_run_events", {"run_id": "r1"}, no_store)
    assert result["status"] == "error"
    assert "store" in result["error"]


# --- list_flow_control_nodes -----------------------------------------------------


def test_list_flow_control_nodes_returns_wiring_patterns() -> None:
    ctx = _fresh_ctx()

    result = execute_tool("list_flow_control_nodes", {}, ctx)

    assert result["status"] == "ok", result
    payload = result["result"]
    names = {entry["node"] for entry in payload["nodes"]}
    assert {"while_loop", "foreach", "parallel_for", "try_catch", "counter_accumulator"} <= names
    assert payload["count"] == len(payload["nodes"])
    while_loop = next(entry for entry in payload["nodes"] if entry["node"] == "while_loop")
    assert "_body_result" in while_loop["wiring"]
    assert "iteration" in while_loop["outputs"]
    assert "_body_result" in payload["summary"] or "body_result" in payload["summary"]


# --- registration -----------------------------------------------------------------


def test_compositional_tools_are_registered_with_expected_flags() -> None:
    mutating = {"add_group", "add_note", "extract_subgraph", "add_subgraph_instance"}
    for name in mutating | {"save_as_template", "get_run_events", "list_flow_control_nodes"}:
        tool = get_tool(name)
        assert tool is not None, name
        assert tool.name == name
        if name in mutating:
            assert tool.mutates is True, name
    save_tool = get_tool("save_as_template")
    assert save_tool is not None
    assert save_tool.action is True
    assert save_tool.mutates is False
