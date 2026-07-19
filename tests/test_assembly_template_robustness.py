from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_assembly_template_retries_spades_branch_after_assembler_switch() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["switch_assembler_001"] == "switch"
    assert node_types["spades_retry_001"] == "retry"
    assert node_types["spades_001"] == "spades"

    retry = _node_by_id(workflow, "spades_retry_001")
    assert retry["params"]["max_retries"] == 2
    assert retry["params"]["delay_seconds"] == 5.0
    assert retry["params"]["backoff_multiplier"] == 2.0
    assert retry["params"]["retry_on"] == "all"
    assert retry["params"]["only_retry_specific_nodes"] == "spades_001"

    assert _has_edge(workflow, "switch_assembler_001", "output_1", "spades_retry_001", "input")
    assert _has_edge(workflow, "spades_retry_001", "passthrough", "spades_001", "reads")
    assert not _has_edge(workflow, "switch_assembler_001", "output_1", "spades_001", "reads")
    assert workflow["outputs"]["spades_retry_policy"] == "spades_retry_001"


def test_assembly_template_selects_one_assembler_before_validation() -> None:
    workflow = _load_template("assembly_pipeline.json")
    selector = _node_by_id(workflow, "select_assembly_001")
    incoming = [
        edge
        for edge in workflow["edges"]
        if edge.get("to") == {"node": "validate_assembly_001", "input": "input"}
    ]

    assert selector["type"] == "merge"
    assert selector["params"] == {
        "num_inputs": 2,
        "strategy": "first_valid",
        "wait_mode": "any",
        "ignore_none": True,
    }
    assert incoming == [
        {
            "id": "e3_selected",
            "from": {"node": "select_assembly_001", "output": "merged"},
            "to": {"node": "validate_assembly_001", "input": "input"},
        }
    ]
    assert _has_edge(workflow, "spades_001", "assembly", "select_assembly_001", "input_0")
    assert _has_edge(workflow, "megahit_001", "contigs", "select_assembly_001", "input_1")
    assert workflow["outputs"]["assembly"] == "select_assembly_001"
    assert workflow["outputs"]["selected_assembly"] == "select_assembly_001"

    result = validate_workflow(workflow, NodeRegistry.create_isolated())
    assert result.valid, result.errors


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selection", "expected_node", "inactive_node", "expected_name"),
    [
        ("spades", "spades_001", "megahit_001", "spades.fasta"),
        ("megahit", "megahit_001", "spades_001", "megahit.fasta"),
    ],
)
async def test_assembly_selector_runtime_uses_only_the_active_branch(
    tmp_path: Path,
    selection: str,
    expected_node: str,
    inactive_node: str,
    expected_name: str,
) -> None:
    template = _load_template("assembly_pipeline.json")
    template_nodes = {node["id"]: node for node in template["nodes"]}
    branch_ids = {
        "switch_assembler_001",
        "spades_retry_001",
        "spades_001",
        "megahit_001",
        "select_assembly_001",
        "validate_assembly_001",
    }
    nodes = [deepcopy(template_nodes[node_id]) for node_id in branch_ids]
    switch = next(node for node in nodes if node["id"] == "switch_assembler_001")
    switch["params"]["value"] = selection
    nodes.append({"id": "reads_source", "type": "test_reads", "params": {}})

    wanted_edges = {"e2", "e2a", "e2a_retry", "e2b", "e3", "e3a", "e3_selected"}
    edges = [deepcopy(edge) for edge in template["edges"] if edge.get("id") in wanted_edges]
    edge_to_switch = next(edge for edge in edges if edge["id"] == "e2")
    edge_to_switch["from"] = {"node": "reads_source", "output": "reads"}

    spades_path = tmp_path / "spades.fasta"
    megahit_path = tmp_path / "megahit.fasta"
    spades_path.write_text(">spades\nACGT\n", encoding="utf-8")
    megahit_path.write_text(">megahit\nTGCA\n", encoding="utf-8")

    class ReadsNode:
        NODE_ID = "test_reads"
        RETURN_NAMES = ("reads",)
        RETURN_TYPES = ("FASTQ_LIST",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {}, "optional": {}, "hidden": {}}

        async def run(self, **kwargs: Any) -> dict[str, Any]:
            return {"outputs": {"reads": ["reads_R1.fastq", "reads_R2.fastq"]}}

    class SpadesNode:
        NODE_ID = "spades"
        RETURN_NAMES = ("assembly",)
        RETURN_TYPES = ("ASSEMBLY",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"reads": ("FASTQ_LIST", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"assembly": str(spades_path)}}

    class MegahitNode:
        NODE_ID = "megahit"
        RETURN_NAMES = ("contigs",)
        RETURN_TYPES = ("CONTIGS",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"reads": ("FASTQ_LIST", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"contigs": str(megahit_path)}}

    live_registry = NodeRegistry.create_isolated()
    node_classes = {
        "test_reads": ReadsNode,
        "spades": SpadesNode,
        "megahit": MegahitNode,
        "switch": live_registry.get("switch"),
        "retry": live_registry.get("retry"),
        "merge": live_registry.get("merge"),
        "data_validator": live_registry.get("data_validator"),
    }

    class Registry:
        def get(self, node_type: str) -> type | None:
            return node_classes.get(node_type)

    executor = WorkflowExecutor(
        workspace_dir=tmp_path / "workspace",
        cache_dir=tmp_path / "cache",
        registry=Registry(),
    )
    result = await executor.execute(
        f"assembly-{selection}",
        {"nodes": nodes, "edges": edges},
        force=True,
    )

    selected_path = str(tmp_path / expected_name)
    assert result["status"] == "completed"
    assert result["node_results"][expected_node]["status"] == "completed"
    assert result["node_results"][inactive_node]["status"] == "skipped"
    assert result["node_results"][inactive_node]["reason"] == "inactive_branch"
    assert SpadesNode.calls == (["spades_001"] if selection == "spades" else [])
    assert MegahitNode.calls == (["megahit_001"] if selection == "megahit" else [])
    assert result["outputs"]["select_assembly_001"] == {
        "merged": selected_path,
        "received_count": 1,
    }
    assert result["outputs"]["validate_assembly_001"]["passthrough"] == selected_path
