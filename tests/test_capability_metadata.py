from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.registry import NodeRegistry

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import export_capabilities  # noqa: E402


class GpuToolNode(BaseNode):
    NODE_ID = "gpu_tool"
    REQUIRES_GPU = True
    REQUIRED_EXECUTABLES = ["esmfold"]

    async def run(self, **_: Any) -> dict[str, Any]:
        return {"outputs": {}}


class CpuToolNode(BaseNode):
    NODE_ID = "cpu_tool"
    REQUIRED_EXECUTABLES = ["samtools", "bcftools"]

    async def run(self, **_: Any) -> dict[str, Any]:
        return {"outputs": {}}


class Registry:
    def get(self, node_type: str) -> Any:
        return {"gpu_tool": GpuToolNode, "cpu_tool": CpuToolNode}.get(node_type)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        execution=SimpleNamespace(max_workers=1, env_isolation="off", content_hashing="off"),
        api_secrets={},
    )


@pytest.mark.asyncio
async def test_dry_run_aggregates_gpu_and_executable_requirements(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    workflow = {
        "name": "capabilities",
        "nodes": [
            {"id": "cpu_node", "type": "cpu_tool"},
            {"id": "gpu_node", "type": "gpu_tool"},
        ],
        "edges": [
            {
                "from": {"node": "cpu_node", "output": "default"},
                "to": {"node": "gpu_node", "input": "input"},
            },
        ],
    }

    plan = await executor.dry_run("run-dry", workflow)

    assert plan["requirements"] == {
        "gpu": True,
        "gpu_nodes": ["gpu_node"],
        "executables": ["bcftools", "esmfold", "samtools"],
    }
    per_node = {entry["node_id"]: entry["requires_gpu"] for entry in plan["nodes"]}
    assert per_node == {"cpu_node": False, "gpu_node": True}


@pytest.mark.asyncio
async def test_dry_run_requirements_report_gpu_false_without_gpu_nodes(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    workflow = {
        "name": "cpu-only",
        "nodes": [{"id": "cpu_node", "type": "cpu_tool"}],
        "edges": [],
    }

    plan = await executor.dry_run("run-cpu", workflow)

    assert plan["requirements"] == {
        "gpu": False,
        "gpu_nodes": [],
        "executables": ["bcftools", "samtools"],
    }


def test_base_node_metadata_exposes_requires_gpu_default_false() -> None:
    class PlainNode(BaseNode):
        NODE_ID = "plain"
        VERSION = "1.0.0"

        async def run(self, **_: Any) -> dict[str, Any]:
            return {"outputs": {}}

    class AcceleratedNode(PlainNode):
        NODE_ID = "accelerated"
        REQUIRES_GPU = True

    assert PlainNode.metadata()["requires_gpu"] is False
    assert AcceleratedNode.metadata()["requires_gpu"] is True


def test_registry_object_info_serves_requires_gpu() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(GpuToolNode)
    registry.register(CpuToolNode)

    info = registry.object_info()
    assert info["gpu_tool"]["requires_gpu"] is True
    assert info["cpu_tool"]["requires_gpu"] is False
    assert info["gpu_tool"]["required_executables"] == ["esmfold"]


def test_committed_capabilities_artifact_flags_gpu_families() -> None:
    artifact_path = _REPO_ROOT / "bionodulo" / "nodes" / "node_capabilities.json"
    if not artifact_path.exists():
        pytest.skip("capabilities artifact not generated in this checkout")

    import json

    capabilities = json.loads(artifact_path.read_text(encoding="utf-8"))
    gpu_nodes = {node_id for node_id, cap in capabilities.items() if cap["requires_gpu"]}
    assert {
        "dorado_basecaller",
        "dorado_duplex",
        "dorado_correct",
        "esmfold_predict",
        "biapy",
        "cell2location",
    } <= gpu_nodes
    assert capabilities["bwa_index"]["requires_gpu"] is False


def test_build_capabilities_maps_registry_classes() -> None:
    registry = SimpleNamespace(
        all=lambda: {"gpu_tool": GpuToolNode, "cpu_tool": CpuToolNode}
    )

    capabilities = export_capabilities.build_capabilities(registry)

    assert capabilities == {
        "cpu_tool": {"requires_gpu": False, "required_executables": ["bcftools", "samtools"]},
        "gpu_tool": {"requires_gpu": True, "required_executables": ["esmfold"]},
    }
