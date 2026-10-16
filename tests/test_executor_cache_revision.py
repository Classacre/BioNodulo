"""Adapter render changes invalidate artifacts without misreporting tool versions."""

from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor


@pytest.mark.asyncio
async def test_adapter_revision_and_tool_version_both_invalidate_real_cache(tmp_path: Path) -> None:
    class Renderer:
        VERSION = "1.0.13"
        RETURN_NAMES = ("plot",)
        calls = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context: Any, **_: Any) -> dict[str, Any]:
            type(self).calls += 1
            return {"outputs": {"plot": type(self).calls}}

    class Registry:
        def get(self, node_type: str) -> type[Renderer] | None:
            return Renderer if node_type == "renderer" else None

    workflow = {"nodes": [{"id": "plot", "type": "renderer"}], "edges": []}
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    async def run_and_preview(name: str, expected_status: str) -> str:
        result = await executor.execute(name, workflow)
        assert result["status"] == "completed"
        node = result["node_results"]["plot"]
        assert node["status"] == expected_status
        preview = await executor.dry_run(f"preview-{name}", workflow)
        assert preview["nodes"][0]["cache"] == {"key": node["cache_key"], "hit": True, "forced": False}
        return node["cache_key"]

    legacy_key = await run_and_preview("legacy", "completed")
    assert await run_and_preview("unchanged", "cached") == legacy_key
    assert Renderer.calls == 1

    Renderer.CACHE_VERSION = "render2"
    revised_key = await run_and_preview("revised", "completed")
    assert revised_key != legacy_key
    assert Renderer.VERSION == "1.0.13"
    assert await run_and_preview("revised-again", "cached") == revised_key
    assert Renderer.calls == 2

    # An adapter revision must not mask a future upstream software update.
    Renderer.VERSION = "1.0.14"
    assert await run_and_preview("upstream-update", "completed") not in {legacy_key, revised_key}
    assert Renderer.calls == 3
