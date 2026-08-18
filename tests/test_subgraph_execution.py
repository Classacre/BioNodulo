"""Execution of generic ``subgraph`` nodes (embedded inner workflows).

A subgraph node carries its inner Workflow JSON in ``params.workflow`` plus
explicit ``input_ports``/``output_ports`` mappings between the parent graph's
ports and inner node slots. These tests cover the executor's in-run recursion
(artifact rooting, port mapping, seeds, events, resume) plus validation and
dry-run behaviour.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import ExecutionContext, WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow

# candidate_generator rejects base sequences containing stop codons.
BASE_CDS = "ATGGCTAAATTTGGCTTTGTT"


def _loaded_registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    return registry


class _HybridRegistry:
    """Registry that serves test stubs first and defers to a real registry."""

    def __init__(self, extra: dict[str, type], base: Any = None) -> None:
        self._extra = dict(extra)
        self._base = base

    def get(self, node_type: str) -> type | None:
        if node_type in self._extra:
            return self._extra[node_type]
        return self._base.get(node_type) if self._base is not None else None


class ConstantNode:
    NODE_ID = "constant"
    RETURN_NAMES = ("value",)
    RETURN_TYPES = ("ANY",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, value: Any) -> dict[str, Any]:
        return {"outputs": {"value": value}}


class RecorderNode:
    NODE_ID = "recorder"
    RETURN_NAMES = ("value",)
    RETURN_TYPES = ("ANY",)
    received: dict[str, Any] = {}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, value: Any) -> dict[str, Any]:
        type(self).received[f"{context.run_id}:{context.node_id}"] = value
        return {"outputs": {"value": value}}


class SentinelNode:
    NODE_ID = "sentinel"
    RETURN_NAMES = ("out",)
    RETURN_TYPES = ("ANY",)
    executions: list[str] = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {"payload": ("ANY", {"default": ""})}, "hidden": {}}

    async def run(self, context: Any, payload: Any = "") -> dict[str, Any]:
        type(self).executions.append(f"{context.run_id}/{context.node_id}")
        marker = context.node_dir / "sentinel.txt"
        marker.write_text(
            json.dumps({"node_id": context.node_id, "payload": str(payload), "run_id": context.run_id}),
            encoding="utf-8",
        )
        return {"outputs": {"out": str(marker)}}


class HeavyNode:
    NODE_ID = "heavy"
    RETURN_NAMES = ("out",)
    RETURN_TYPES = ("ANY",)
    REQUIRED_EXECUTABLES = ("fakebin",)
    REQUIRES_GPU = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any) -> dict[str, Any]:
        return {"outputs": {"out": "heavy"}}


class IncrementNode:
    NODE_ID = "increment"
    RETURN_NAMES = ("value",)
    RETURN_TYPES = ("ANY",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, value: Any) -> dict[str, Any]:
        return {"outputs": {"value": int(value) + 1}}


class BoolFlipNode:
    NODE_ID = "bool_flip"
    RETURN_NAMES = ("value",)
    RETURN_TYPES = ("ANY",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"value": ("ANY", {})}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, value: Any) -> dict[str, Any]:
        return {"outputs": {"value": not bool(value)}}


STUB_CLASSES = {
    "constant": ConstantNode,
    "recorder": RecorderNode,
    "sentinel": SentinelNode,
    "heavy": HeavyNode,
    "increment": IncrementNode,
    "bool_flip": BoolFlipNode,
}


def _subgraph_node(
    node_id: str,
    inner_workflow: dict[str, Any],
    input_ports: list[dict[str, str]],
    output_ports: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "subgraph",
        "params": {
            "workflow": inner_workflow,
            "input_ports": input_ports,
            "output_ports": output_ports,
        },
        "outputs": {port["name"]: {} for port in output_ports},
    }


def _inner_candidates_workflow(seed_value: Any = "{{subgraph_seed}}") -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "gen",
                "type": "candidate_generator",
                "params": {"n_candidates": 8, "seed": seed_value, "strategy": "synonymous_uniform"},
                "outputs": {"candidates": {}, "fasta": {}},
            },
            {"id": "metrics", "type": "codon_metrics", "outputs": {"metrics": {}, "metrics_table": {}}},
        ],
        "edges": [
            {
                "source_node": "gen",
                "target_node": "metrics",
                "source_output": "fasta",
                "target_input": "cds",
            }
        ],
    }


async def _reference_candidates(tmp_path: Path, seed: int) -> str:
    """Run candidate_generator directly with *seed* and return its JSON text."""
    gen_class = _loaded_registry().get("candidate_generator")
    assert gen_class is not None
    node_dir = tmp_path / "reference" / f"seed-{seed}"
    node_dir.mkdir(parents=True, exist_ok=True)
    ctx = ExecutionContext(
        run_id="reference",
        node_id="gen",
        node_type="candidate_generator",
        node_dir=node_dir,
        workspace_dir=tmp_path,
        params={},
        api_secrets={},
        emit=lambda *_: None,
        cancel_event=asyncio.Event(),
    )
    produced = await gen_class().run(context=ctx, base_cds=BASE_CDS, n_candidates=8, seed=seed)
    return Path(produced[0]).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) input/output port mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subgraph_maps_parent_inputs_to_inner_slots_and_outputs_back(tmp_path: Path) -> None:
    registry = _HybridRegistry(STUB_CLASSES, base=_loaded_registry())
    subgraph = _subgraph_node(
        "sub",
        _inner_candidates_workflow(seed_value=11),
        input_ports=[{"name": "in__gen__base_cds", "type": "STRING", "innerNodeId": "gen", "innerSlot": "base_cds"}],
        output_ports=[
            {"name": "out__metrics__metrics", "type": "JSON", "innerNodeId": "metrics", "innerSlot": "metrics"}
        ],
    )
    workflow = {
        "nodes": [
            {"id": "src", "type": "constant", "params": {"value": BASE_CDS}, "outputs": {"value": {}}},
            subgraph,
            {"id": "sink", "type": "recorder", "outputs": {"value": {}}},
        ],
        "edges": [
            {
                "source_node": "src",
                "target_node": "sub",
                "source_output": "value",
                "target_input": "in__gen__base_cds",
            },
            {
                "source_node": "sub",
                "target_node": "sink",
                "source_output": "out__metrics__metrics",
                "target_input": "value",
            },
        ],
    }
    RecorderNode.received = {}
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute("map-run", workflow, force=True)

    assert result["status"] == "completed", result["node_results"]
    # Inner artifacts are rooted under the subgraph node's run directory.
    assert (tmp_path / "runs" / "map-run" / "sub" / "gen" / "candidate_generator" / "candidates.json").is_file()
    assert (tmp_path / "runs" / "map-run" / "sub" / "run_metadata.json").is_file()
    # The mapped output port carries the inner node's metrics file.
    metrics_path = result["outputs"]["sub"]["out__metrics__metrics"]
    assert Path(metrics_path).is_file()
    metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
    assert metrics["length_nt"] == 8 * len(BASE_CDS)
    # The extra subgraph_dir output always exists.
    assert result["outputs"]["sub"]["subgraph_dir"] == str((tmp_path / "runs" / "map-run" / "sub").resolve())
    # The parent's downstream node consumed the mapped output.
    assert RecorderNode.received["map-run:sink"] == metrics_path
    # Inner metadata records both inner nodes.
    inner_meta = json.loads(
        (tmp_path / "runs" / "map-run" / "sub" / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert set(inner_meta["nodes"]) == {"gen", "metrics"}
    assert inner_meta["nodes"]["gen"]["status"] == "completed"


@pytest.mark.asyncio
async def test_subgraph_input_port_named_seed_defaults_to_derived_seed(tmp_path: Path) -> None:
    registry = _HybridRegistry(STUB_CLASSES, base=_loaded_registry())
    inner = {
        "nodes": [
            {
                "id": "gen",
                "type": "candidate_generator",
                "params": {"n_candidates": 8},
                "outputs": {"candidates": {}, "fasta": {}},
            },
        ],
        "edges": [],
    }
    subgraph = _subgraph_node(
        "sg",
        inner,
        input_ports=[
            {"name": "in__gen__base_cds", "type": "STRING", "innerNodeId": "gen", "innerSlot": "base_cds"},
            {"name": "seed", "type": "INT", "innerNodeId": "gen", "innerSlot": "seed"},
        ],
        output_ports=[{"name": "out__gen__candidates", "type": "JSON", "innerNodeId": "gen", "innerSlot": "candidates"}],
    )
    workflow = {
        "nodes": [
            {"id": "src", "type": "constant", "params": {"value": BASE_CDS}, "outputs": {"value": {}}},
            subgraph,
        ],
        "edges": [
            {"source_node": "src", "target_node": "sg", "source_output": "value", "target_input": "in__gen__base_cds"},
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute(
        "seed-port-run", workflow, options={"parameters": {"seed": 5}, "embed_provenance": False}, force=True
    )

    assert result["status"] == "completed", result["node_results"]
    # Derived seeds are masked to 31 bits so node INT validation accepts them.
    expected_seed = int(hashlib.sha256(b"5:sg").hexdigest()[:8], 16) & 0x7FFFFFFF
    inner_meta = json.loads(
        (tmp_path / "runs" / "seed-port-run" / "sg" / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert inner_meta["workflow_parameters"]["subgraph_seed"] == expected_seed
    # The inner generator actually ran with the derived seed, not its default 0.
    produced = tmp_path / "runs" / "seed-port-run" / "sg" / "gen" / "candidate_generator" / "candidates.json"
    assert produced.read_text(encoding="utf-8") == await _reference_candidates(tmp_path, expected_seed)
    assert produced.read_text(encoding="utf-8") != await _reference_candidates(tmp_path, 0)


# ---------------------------------------------------------------------------
# (b) two-level nesting: artifacts + tagged events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nested_subgraphs_root_artifacts_and_tag_events(tmp_path: Path) -> None:
    leaf_workflow = {
        "nodes": [{"id": "leaf", "type": "sentinel", "outputs": {"out": {}}}],
        "edges": [],
    }
    l2 = _subgraph_node(
        "l2",
        leaf_workflow,
        input_ports=[],
        output_ports=[{"name": "out__leaf__out", "type": "ANY", "innerNodeId": "leaf", "innerSlot": "out"}],
    )
    l1 = _subgraph_node(
        "l1",
        {"nodes": [l2], "edges": []},
        input_ports=[],
        output_ports=[{"name": "out__l2__out", "type": "ANY", "innerNodeId": "l2", "innerSlot": "out__leaf__out"}],
    )
    workflow = {
        "nodes": [l1, {"id": "sink", "type": "recorder", "outputs": {"value": {}}}],
        "edges": [
            {"source_node": "l1", "target_node": "sink", "source_output": "out__l2__out", "target_input": "value"},
        ],
    }
    events: list[tuple[str, dict[str, Any]]] = []
    RecorderNode.received = {}
    SentinelNode.executions = []
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=_HybridRegistry(STUB_CLASSES),
    )

    result = await executor.execute("nested-run", workflow, emit=lambda e, d: events.append((e, d)))

    assert result["status"] == "completed", result["node_results"]
    # Artifacts land at runs/<run>/l1/l2/<inner>/.
    sentinel = tmp_path / "runs" / "nested-run" / "l1" / "l2" / "leaf" / "sentinel.txt"
    assert sentinel.is_file()
    assert (tmp_path / "runs" / "nested-run" / "l1" / "run_metadata.json").is_file()
    assert (tmp_path / "runs" / "nested-run" / "l1" / "l2" / "run_metadata.json").is_file()
    # The mapped output flowed through both levels to the parent sink.
    assert RecorderNode.received["nested-run:sink"] == str(sentinel)
    # Inner events reached the same stream tagged with the nesting path.
    starts = [payload for event, payload in events if event == "node_start"]
    by_node = {payload["node_id"]: payload for payload in starts}
    assert by_node["l2"]["subgraph_path"] == "l1"
    assert by_node["leaf"]["subgraph_path"] == "l1.l2"
    # Exactly one run-level start/complete pair (inner ones stay internal).
    assert [event for event, _ in events].count("start") == 1
    assert [event for event, _ in events].count("complete") == 1


# ---------------------------------------------------------------------------
# (c) seed determinism
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_master_seed_derives_deterministic_inner_seeds(tmp_path: Path) -> None:
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_loaded_registry())

    def build(subgraph_id: str) -> dict[str, Any]:
        subgraph = _subgraph_node(
            subgraph_id,
            _inner_candidates_workflow(),
            input_ports=[{"name": "in__gen__base_cds", "type": "STRING", "innerNodeId": "gen", "innerSlot": "base_cds"}],
            output_ports=[{"name": "out__gen__candidates", "type": "JSON", "innerNodeId": "gen", "innerSlot": "candidates"}],
        )
        # Feed the port from the subgraph node's own params (unwired port).
        subgraph["params"]["in__gen__base_cds"] = BASE_CDS
        return {"nodes": [subgraph], "edges": []}

    first = await executor.execute("seed-a", build("sg"), options={"parameters": {"seed": 42}, "embed_provenance": False}, force=True)
    second = await executor.execute("seed-b", build("sg"), options={"parameters": {"seed": 42}, "embed_provenance": False}, force=True)
    other_node = await executor.execute(
        "seed-c", build("sg_other"), options={"parameters": {"seed": 42}, "embed_provenance": False}, force=True
    )

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert other_node["status"] == "completed"

    expected_sg = int(hashlib.sha256(b"42:sg").hexdigest()[:8], 16) & 0x7FFFFFFF
    expected_other = int(hashlib.sha256(b"42:sg_other").hexdigest()[:8], 16) & 0x7FFFFFFF
    assert expected_sg != expected_other

    for run_id, subgraph_id, expected_seed in (
        ("seed-a", "sg", expected_sg),
        ("seed-b", "sg", expected_sg),
        ("seed-c", "sg_other", expected_other),
    ):
        inner_meta = json.loads(
            (tmp_path / "runs" / run_id / subgraph_id / "run_metadata.json").read_text(encoding="utf-8")
        )
        assert inner_meta["workflow_parameters"]["subgraph_seed"] == expected_seed

    def candidates(run_id: str, subgraph_id: str) -> str:
        return (
            tmp_path / "runs" / run_id / subgraph_id / "gen" / "candidate_generator" / "candidates.json"
        ).read_text(encoding="utf-8")

    assert candidates("seed-a", "sg") == candidates("seed-b", "sg") == await _reference_candidates(
        tmp_path, expected_sg
    )
    assert candidates("seed-a", "sg") != candidates("seed-c", "sg_other")


# ---------------------------------------------------------------------------
# (d) checkpoint/resume does not re-execute the subgraph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_skips_subgraph_and_downstream_consumes_mapped_output(tmp_path: Path) -> None:
    registry = _HybridRegistry(STUB_CLASSES, base=_loaded_registry())
    inner = {
        "nodes": [{"id": "maker", "type": "sentinel", "params": {"payload": "built"}, "outputs": {"out": {}}}],
        "edges": [],
    }
    subgraph = _subgraph_node(
        "sub",
        inner,
        input_ports=[],
        output_ports=[{"name": "out__maker__out", "type": "ANY", "innerNodeId": "maker", "innerSlot": "out"}],
    )
    workflow = {
        "nodes": [
            subgraph,
            {
                "id": "ckpt",
                "type": "checkpoint",
                "params": {"checkpoint_name": "after_sub"},
                "outputs": {"passthrough": {}, "checkpoint_file": {}, "checkpoint_info": {}},
            },
            {"id": "sink", "type": "recorder", "outputs": {"value": {}}},
        ],
        "edges": [
            {"source_node": "sub", "target_node": "ckpt", "source_output": "out__maker__out", "target_input": "input"},
            {"source_node": "ckpt", "target_node": "sink", "source_output": "passthrough", "target_input": "value"},
        ],
    }
    RecorderNode.received = {}
    SentinelNode.executions = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    # Provenance embedding rewrites artifact files, which would blur the
    # "subgraph not re-executed" mtime assertion below.
    first = await executor.execute("master-run", workflow, options={"embed_provenance": False})
    assert first["status"] == "completed", first["node_results"]
    sentinel = tmp_path / "runs" / "master-run" / "sub" / "maker" / "sentinel.txt"
    assert sentinel.is_file()
    first_mtime = sentinel.stat().st_mtime_ns
    assert SentinelNode.executions == ["master-run/maker"]
    assert RecorderNode.received["master-run:sink"] == str(sentinel)

    # Mirror queue.retry: pull the run's latest checkpoint from the manifest.
    manifest = json.loads(
        (tmp_path / "checkpoints" / "checkpoint_manifest.json").read_text(encoding="utf-8")
    )
    checkpoint_entry = manifest["latest_by_run_node"]["master-run:ckpt"]
    assert Path(str(checkpoint_entry["checkpoint_path"])).is_file()

    SentinelNode.executions = []
    second = await executor.execute(
        "master-resume", workflow, options={"resume_checkpoint": checkpoint_entry, "embed_provenance": False}
    )

    assert second["status"] == "completed", second["node_results"]
    # The subgraph was not part of the resumed graph at all.
    assert "sub" not in second["node_results"]
    assert SentinelNode.executions == []
    assert sentinel.stat().st_mtime_ns == first_mtime
    # The checkpointed passthrough (the subgraph's mapped output) fed the sink
    # (a cache hit here still resolves from the checkpointed mapped output).
    assert second["node_results"]["ckpt"]["status"] == "resumed"
    assert second["node_results"]["sink"]["outputs"]["value"] == str(sentinel)


# ---------------------------------------------------------------------------
# (e) validation
# ---------------------------------------------------------------------------


def _valid_inner() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "gen",
                "type": "candidate_generator",
                "params": {"base_cds": BASE_CDS},
                "outputs": {"candidates": {}, "fasta": {}},
            },
            {"id": "metrics", "type": "codon_metrics", "outputs": {"metrics": {}, "metrics_table": {}}},
        ],
        "edges": [
            {"source_node": "gen", "target_node": "metrics", "source_output": "fasta", "target_input": "cds"}
        ],
    }


def _subgraph_workflow(inner: dict[str, Any], edges: list[dict[str, str]] | None = None) -> dict[str, Any]:
    subgraph = _subgraph_node(
        "sub",
        inner,
        input_ports=[{"name": "in__gen__base_cds", "type": "STRING", "innerNodeId": "gen", "innerSlot": "base_cds"}],
        output_ports=[{"name": "out__metrics__metrics", "type": "JSON", "innerNodeId": "metrics", "innerSlot": "metrics"}],
    )
    return {
        "nodes": [
            {
                "id": "src",
                "type": "candidate_generator",
                "params": {"base_cds": BASE_CDS},
                "outputs": {"candidates": {}, "fasta": {}},
            },
            subgraph,
        ],
        "edges": edges
        if edges is not None
        else [
            {"source_node": "src", "target_node": "sub", "source_output": "fasta", "target_input": "in__gen__base_cds"},
        ],
    }


def test_validation_accepts_subgraph_and_validates_inner_recursively() -> None:
    result = validate_workflow(_subgraph_workflow(_valid_inner()), _loaded_registry())

    assert result.valid is True, result.errors
    assert "sub/gen" in result.sorted_node_order
    assert "sub/metrics" in result.sorted_node_order


def test_validation_rejects_unknown_subgraph_port_on_edge() -> None:
    bad_target = _subgraph_workflow(
        _valid_inner(),
        edges=[
            {"source_node": "src", "target_node": "sub", "source_output": "fasta", "target_input": "not_a_port"},
        ],
    )
    bad_source = {
        "nodes": [
            _subgraph_node(
                "sub",
                _valid_inner(),
                input_ports=[],
                output_ports=[{"name": "out__metrics__metrics", "type": "JSON", "innerNodeId": "metrics", "innerSlot": "metrics"}],
            ),
            {"id": "sink", "type": "codon_metrics", "outputs": {"metrics": {}, "metrics_table": {}}},
        ],
        "edges": [
            {"source_node": "sub", "target_node": "sink", "source_output": "nope", "target_input": "cds"},
        ],
    }
    registry = _loaded_registry()

    target_result = validate_workflow(bad_target, registry)
    source_result = validate_workflow(bad_source, registry)

    assert target_result.valid is False
    assert any("unknown input port 'not_a_port'" in error for error in target_result.errors)
    assert source_result.valid is False
    assert any("unknown output port 'nope'" in error for error in source_result.errors)


def test_validation_rejects_cycle_inside_subgraph() -> None:
    cyclic_inner = {
        "nodes": [
            {
                "id": "gen",
                "type": "candidate_generator",
                "params": {"base_cds": BASE_CDS},
                "outputs": {"candidates": {}, "fasta": {}},
            },
            {"id": "metrics", "type": "codon_metrics", "outputs": {"metrics": {}, "metrics_table": {}}},
        ],
        "edges": [
            {"source_node": "gen", "target_node": "metrics", "source_output": "fasta", "target_input": "cds"},
            {"source_node": "metrics", "target_node": "gen", "source_output": "metrics", "target_input": "base_cds"},
        ],
    }
    result = validate_workflow(_subgraph_workflow(cyclic_inner), _loaded_registry())

    assert result.valid is False
    assert any("Subgraph 'sub'" in error and "Cycle" in error for error in result.errors)


def test_validation_accepts_nested_subgraphs() -> None:
    leaf = {
        "nodes": [
            {
                "id": "gen",
                "type": "candidate_generator",
                "params": {"base_cds": BASE_CDS},
                "outputs": {"candidates": {}, "fasta": {}},
            },
        ],
        "edges": [],
    }
    # Ports only ever reference DIRECT inner nodes: the outer subgraph's port
    # maps onto the inner subgraph node's own declared port, which in turn maps
    # onto the leaf node's slot.
    nested_inner = {
        "nodes": [
            _subgraph_node(
                "inner_sub",
                leaf,
                input_ports=[
                    {
                        "name": "in__gen__base_cds",
                        "type": "STRING",
                        "innerNodeId": "gen",
                        "innerSlot": "base_cds",
                    }
                ],
                output_ports=[{"name": "out__gen__fasta", "type": "FASTA", "innerNodeId": "gen", "innerSlot": "fasta"}],
            ),
            {"id": "metrics", "type": "codon_metrics", "outputs": {"metrics": {}, "metrics_table": {}}},
        ],
        "edges": [
            {"source_node": "inner_sub", "target_node": "metrics", "source_output": "out__gen__fasta", "target_input": "cds"},
        ],
    }
    workflow = _subgraph_workflow(nested_inner)
    workflow["nodes"][1]["params"]["input_ports"] = [
        {
            "name": "in__gen__base_cds",
            "type": "STRING",
            "innerNodeId": "inner_sub",
            "innerSlot": "in__gen__base_cds",
        }
    ]
    result = validate_workflow(workflow, _loaded_registry())

    assert result.valid is True, result.errors
    assert "sub/inner_sub/gen" in result.sorted_node_order


# ---------------------------------------------------------------------------
# (f) dry_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_plans_inner_nodes_and_aggregates_requirements(tmp_path: Path) -> None:
    inner = {
        "nodes": [
            {"id": "gpu_node", "type": "heavy", "params": {}, "outputs": {"out": {}}},
        ],
        "edges": [],
    }
    subgraph = _subgraph_node(
        "sub",
        inner,
        input_ports=[],
        output_ports=[{"name": "out__gpu__out", "type": "ANY", "innerNodeId": "gpu_node", "innerSlot": "out"}],
    )
    workflow = {
        "nodes": [subgraph, {"id": "sink", "type": "recorder", "outputs": {"value": {}}}],
        "edges": [
            {"source_node": "sub", "target_node": "sink", "source_output": "out__gpu__out", "target_input": "value"},
        ],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=_HybridRegistry(STUB_CLASSES),
    )

    preview = await executor.dry_run("plan-run", workflow)

    assert preview["status"] == "dry_run"
    entries = {entry["node_id"]: entry for entry in preview["nodes"]}
    assert entries["sub"]["inner_node_count"] == 1
    assert entries["sub"]["cache"]["forced"] is True
    inner_entry = entries["sub/gpu_node"]
    assert inner_entry["node_type"] == "heavy"
    assert inner_entry["requires_gpu"] is True
    assert inner_entry["required_executables"] == ["fakebin"]
    assert preview["requirements"]["gpu"] is True
    assert "sub/gpu_node" in preview["requirements"]["gpu_nodes"]
    assert "fakebin" in preview["requirements"]["executables"]


@pytest.mark.asyncio
async def test_dry_run_recurses_into_real_inner_workflow(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=_loaded_registry(),
    )

    preview = await executor.dry_run("plan-real", _subgraph_workflow(_valid_inner()))

    assert preview["status"] == "dry_run"
    entries = {entry["node_id"]: entry for entry in preview["nodes"]}
    assert entries["sub"]["inner_node_count"] == 2
    assert entries["sub/gen"]["node_type"] == "candidate_generator"
    assert entries["sub/metrics"]["node_type"] == "codon_metrics"
    # Planned inner paths are rooted under the subgraph's run directory.
    sub_root = str(tmp_path / "runs" / "plan-real" / "sub")
    assert entries["sub/gen"]["planned_outputs"]
    assert all(
        str(path).startswith(sub_root)
        for path in entries["sub/gen"]["planned_outputs"].values()
    )


# ---------------------------------------------------------------------------
# (g) loop x subgraph composition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subgraph_inside_while_loop_body_runs_each_iteration(tmp_path: Path) -> None:
    """A subgraph node inside a while_loop body executes once per iteration."""
    registry = _HybridRegistry(STUB_CLASSES, base=_loaded_registry())
    inner = {
        "nodes": [
            {"id": "inc", "type": "increment", "outputs": {"value": {}}},
            {"id": "marker", "type": "sentinel", "params": {"payload": "inner"}, "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "inc", "target_node": "marker", "source_output": "value", "target_input": "payload"},
        ],
    }
    subgraph = _subgraph_node(
        "sub",
        inner,
        input_ports=[{"name": "in__inc__value", "type": "ANY", "innerNodeId": "inc", "innerSlot": "value"}],
        output_ports=[{"name": "out__inc__value", "type": "ANY", "innerNodeId": "inc", "innerSlot": "value"}],
    )
    workflow = {
        "nodes": [
            {"id": "init", "type": "constant", "params": {"value": 1}, "outputs": {"value": {}}},
            {
                "id": "wl",
                "type": "while_loop",
                "params": {"condition_mode": "numeric_less", "compare_to": "3", "max_iterations": 10},
                "outputs": {"iteration": {}, "results": {}, "iterations": {}, "converged": {}},
            },
            subgraph,
        ],
        "edges": [
            {"source_node": "init", "target_node": "wl", "source_output": "value", "target_input": "value"},
            {"source_node": "wl", "target_node": "sub", "source_output": "iteration", "target_input": "in__inc__value"},
            {"source_node": "sub", "target_node": "wl", "source_output": "out__inc__value", "target_input": "value"},
        ],
    }
    SentinelNode.executions = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute("while-sub-run", workflow, emit=lambda *_: None)

    assert result["status"] == "completed", result["node_results"]
    wl_result = result["node_results"]["wl"]
    assert wl_result["outputs"]["iterations"] == 2
    assert wl_result["outputs"]["converged"] is True
    assert len(wl_result["outputs"]["results"]) == 2
    # The inner sentinel ran once per while iteration, nested under the loop's
    # iteration directory, and the subgraph mapped the loop-carried value out.
    for iteration in (1, 2):
        marker = (
            tmp_path / "runs" / "while-sub-run" / "wl" / "iterations" / f"{iteration:04d}"
            / "sub" / "marker" / "sentinel.txt"
        )
        assert marker.is_file(), marker
    assert SentinelNode.executions == [
        "while-sub-run/marker",
        "while-sub-run/marker",
    ]


@pytest.mark.asyncio
async def test_while_loop_inside_foreach_body_executes_nested(tmp_path: Path) -> None:
    """A while_loop node inside a foreach body iterates per foreach item."""
    registry = _HybridRegistry(STUB_CLASSES, base=_loaded_registry())
    workflow = {
        "nodes": [
            {
                "id": "fe",
                "type": "foreach",
                "params": {"items": [True, False]},
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            {
                "id": "wl",
                "type": "while_loop",
                "params": {"condition_mode": "boolean_is_true", "max_iterations": 5},
                "outputs": {"iteration": {}, "results": {}, "iterations": {}, "converged": {}},
            },
            {"id": "flip", "type": "bool_flip", "outputs": {"value": {}}},
        ],
        "edges": [
            {"source_node": "fe", "target_node": "wl", "source_output": "iteration", "target_input": "value"},
            {"source_node": "wl", "target_node": "flip", "source_output": "iteration", "target_input": "value"},
            {"source_node": "flip", "target_node": "wl", "source_output": "value", "target_input": "value"},
        ],
    }
    validation = validate_workflow(workflow, registry)
    assert validation.valid is True, validation.errors
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute("fe-while-run", workflow, emit=lambda *_: None)

    assert result["status"] == "completed", result["node_results"]
    fe_result = result["node_results"]["fe"]
    assert fe_result["outputs"]["count"] == 2
    assert len(fe_result["outputs"]["results"]) == 2
    # Item True: the nested while ran its body exactly once before the flip
    # completed it; the body node lives under the foreach iteration directory.
    first_flip = (
        tmp_path / "runs" / "fe-while-run" / "fe" / "iterations" / "0001" / "wl"
        / "iterations" / "0001" / "flip"
    )
    assert first_flip.is_dir(), first_flip
    # Item False: the nested while completed immediately with zero iterations.
    assert not (tmp_path / "runs" / "fe-while-run" / "fe" / "iterations" / "0002" / "wl" / "iterations").exists()


@pytest.mark.asyncio
async def test_subgraph_inside_foreach_body_runs_per_item(tmp_path: Path) -> None:
    """A subgraph node inside a foreach body executes once per item."""
    registry = _HybridRegistry(STUB_CLASSES, base=_loaded_registry())
    inner = {
        "nodes": [
            {"id": "maker", "type": "sentinel", "outputs": {"out": {}},
             "params": {"payload": "built"}},
        ],
        "edges": [],
    }
    subgraph = _subgraph_node(
        "sub",
        inner,
        input_ports=[{"name": "in__maker__payload", "type": "ANY", "innerNodeId": "maker", "innerSlot": "payload"}],
        output_ports=[{"name": "out__maker__out", "type": "ANY", "innerNodeId": "maker", "innerSlot": "out"}],
    )
    workflow = {
        "nodes": [
            {
                "id": "fe",
                "type": "foreach",
                "params": {"items": ["a", "b", "c"]},
                "outputs": {"iteration": {}, "results": {}, "count": {}, "all_succeeded": {}},
            },
            subgraph,
        ],
        "edges": [
            {"source_node": "fe", "target_node": "sub", "source_output": "iteration",
             "target_input": "in__maker__payload"},
        ],
    }
    SentinelNode.executions = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute("fe-sub-run", workflow, emit=lambda *_: None)

    assert result["status"] == "completed", result["node_results"]
    assert result["node_results"]["fe"]["outputs"]["count"] == 3
    assert len(result["node_results"]["fe"]["outputs"]["results"]) == 3
    for index, item in enumerate(("a", "b", "c"), start=1):
        marker = (
            tmp_path / "runs" / "fe-sub-run" / "fe" / "iterations" / f"{index:04d}"
            / "sub" / "maker" / "sentinel.txt"
        )
        assert marker.is_file(), marker
        payload = json.loads(marker.read_text(encoding="utf-8").splitlines()[0])["payload"]
        assert payload == item
    assert len(SentinelNode.executions) == 3
