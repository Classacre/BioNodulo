from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.execution.capabilities import explicit_dorado_cpu_mode
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.builtin.long_read_family.dorado_basecaller import DoradoBasecallerNode


def _node(device="cpu") -> dict:
    return {"id": "call", "type": "dorado_basecaller", "params": {
        "device": device, "pod5_dir": "signals", "model": "models/simplex", "reference": "reference.fa",
    }}


@pytest.mark.parametrize("device", ["auto", "cuda:0", "cuda:all", "", "CPU", " cpu ", None, 0, {}, [], "{{device}}"])
def test_only_exact_cpu_literal_gets_the_capability_exception(device) -> None:
    assert explicit_dorado_cpu_mode(_node(device), []) is False
    assert explicit_dorado_cpu_mode(_node(), []) is True


@pytest.mark.parametrize("field", ["inputs", "widgets"])
@pytest.mark.parametrize("value", [{"device": "cuda:0"}, {"device": "cpu"}, None, [], "cpu"])
def test_input_and_widget_bindings_or_malformed_shapes_keep_gpu(field, value) -> None:
    node = _node()
    node[field] = value
    assert not explicit_dorado_cpu_mode(node, [])


@pytest.mark.parametrize("edge", [
    {"from": {"node": "source"}, "to": {"node": "call", "input": "device"}},
    {"source_node": "source", "target_node": "call", "target_input": "device"},
    {"from_node": "source", "to_node": "call", "to_input": "device"},
    {"from": "source", "to": "call", "input": "device"},
])
def test_connected_device_never_uses_cpu_exception(edge) -> None:
    assert not explicit_dorado_cpu_mode(_node(), [edge])


def test_conservative_metadata_other_types_nested_and_malformed_inputs() -> None:
    assert DoradoBasecallerNode.REQUIRES_GPU is True
    assert not explicit_dorado_cpu_mode(_node(), [], nested=True)
    assert not explicit_dorado_cpu_mode(_node(), None)
    assert not explicit_dorado_cpu_mode(_node(), [None])
    for params in ({}, None, [], "cpu"):
        assert not explicit_dorado_cpu_mode({**_node(), "params": params}, [])
    for node_type in ("dorado_correct", "dorado_duplex", "dorado_basecaller_unknown", "esmfold_predict"):
        assert not explicit_dorado_cpu_mode({**_node(), "type": node_type}, [])
    assert explicit_dorado_cpu_mode(_node(), [{"to": {"node": "call", "input": "reference"}}])


def _executor(tmp_path: Path) -> WorkflowExecutor:
    registry = SimpleNamespace(get=lambda name: {
        "dorado_basecaller": DoradoBasecallerNode,
    }.get(name))
    settings = SimpleNamespace(execution=SimpleNamespace(max_workers=1, env_isolation="off", content_hashing="off"), api_secrets={})
    return WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry, settings=settings)


@pytest.mark.asyncio
@pytest.mark.parametrize(("device", "requires_gpu"), [("cpu", False), ("auto", True), ("cuda:0", True), ("{{device}}", True)])
async def test_real_dorado_plan_agrees_with_native_argv(tmp_path: Path, device: str, requires_gpu: bool) -> None:
    workflow = {"nodes": [_node(device)], "edges": []}
    plan = await _executor(tmp_path).dry_run("cpu-plan", workflow, options={"parameters": {"device": "cpu"}})
    assert plan["status"] == "dry_run", plan
    assert plan["requirements"]["gpu"] is requires_gpu
    entry = plan["nodes"][0]
    assert entry["requires_gpu"] is requires_gpu
    command = entry["command"]
    assert command[command.index("--device") + 1] == ("cpu" if device == "{{device}}" else device)


@pytest.mark.asyncio
async def test_nested_port_binding_keeps_dorado_gpu_requirement(tmp_path: Path) -> None:
    workflow = {"nodes": [{"id": "sub", "type": "subgraph", "params": {
        "workflow": {"nodes": [_node()], "edges": []},
        "input_ports": [{"name": "selected_device", "type": "STRING", "innerNodeId": "call", "innerSlot": "device"}],
        "output_ports": [], "selected_device": "cuda:0",
    }}], "edges": []}
    plan = await _executor(tmp_path).dry_run("nested-plan", workflow)
    assert plan["status"] == "dry_run", plan
    assert plan["requirements"]["gpu"] is True
    assert plan["requirements"]["gpu_nodes"] == ["sub/call"]


def test_ont_template_uses_supported_explicit_cpu_command() -> None:
    workflow = json.loads((Path(__file__).parents[1] / "templates/long_read_ont_pipeline.json").read_text())
    node = next(node for node in workflow["nodes"] if node["type"] == "dorado_basecaller")
    assert explicit_dorado_cpu_mode(node, workflow["edges"])
    command = DoradoBasecallerNode.render_command({**_node()["params"], **node["params"]})
    assert command[command.index("--device") + 1] == "cpu"
    note = next(node["params"]["text"] for node in workflow["nodes"] if node["type"] == "note")
    assert "slower than GPU" in note and "100" in note and "does not validate methylation accuracy" in note
