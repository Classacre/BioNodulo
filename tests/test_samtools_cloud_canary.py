from __future__ import annotations

import json
from pathlib import Path

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/samtools_first_wave/workflow.json"


@pytest.mark.asyncio
async def test_samtools_canary_uses_normal_registry_and_command_path(
    tmp_path: Path,
) -> None:
    workflow = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "catalog_canary" not in workflow

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    preview = await WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    ).dry_run("samtools-cloud-canary", workflow)

    assert preview["status"] == "dry_run"
    assert preview["execution_order"] == [
        "input_001",
        "view_001",
        "collate_001",
        "fixmate_001",
        "sort_001",
        "markdup_001",
        "index_001",
        "flagstat_001",
    ]

    plans = {plan["node_id"]: plan for plan in preview["nodes"]}
    for node_id in preview["execution_order"][1:]:
        assert plans[node_id]["command"][0] == "samtools"
        assert plans[node_id]["required_conda_packages"] == ["samtools"]
