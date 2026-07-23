from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bionodulo.execution.arq_executor import ArqWorkflowExecutor
from bionodulo.execution.catalog_canary import (
    CANARY_OPTION,
    CatalogCanaryError,
    CatalogCanaryRunner,
    SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
    SAMTOOLS_FIRST_WAVE_INPUT_SHA256,
    SAMTOOLS_FIRST_WAVE_INPUT_URL,
    SAMTOOLS_FIRST_WAVE_PROFILE,
)
from bionodulo.execution.executor import ExecutionContext, WorkflowExecutor
from bionodulo.nodes.builtin.input_family.file import InputFileNode


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "samtools_first_wave"
GENERATED_DIR = Path(__file__).resolve().parents[2] / "bionodulo" / "nodes" / "generated"
CANARY_SELECTOR = {
    "profile": SAMTOOLS_FIRST_WAVE_PROFILE,
    "catalog_digest": SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
}


class RejectingLegacyRegistry:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, node_type: str) -> Any:
        self.calls.append(node_type)
        raise AssertionError(f"legacy registry lookup is forbidden for catalog canary: {node_type}")


def _workflow() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "workflow.json").read_text(encoding="utf-8"))


def _stub_pinned_input(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FIXTURE_DIR / "tiny.sam"

    def _resolve_source(
        cls: type[InputFileNode],
        value: Any,
        context: Any,
        mode: str = "auto",
        *,
        ncbi_email: Any = "",
    ) -> Path:
        del cls, context, ncbi_email
        assert value == SAMTOOLS_FIRST_WAVE_INPUT_URL
        assert mode == "url"
        return source

    monkeypatch.setattr(InputFileNode, "_resolve_source", classmethod(_resolve_source))


def _fake_samtools_runner(commands: list[list[str]]):
    async def _run_command(
        context: ExecutionContext,
        cmd: str | list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        del kwargs
        assert isinstance(cmd, list)
        assert cmd[:1] == ["samtools"]
        commands.append(cmd)
        operation = cmd[1]
        stdout = ""

        if operation in {"view", "collate", "sort", "index"}:
            output = Path(cmd[cmd.index("-o") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(f"{operation} synthetic output\n".encode())
        elif operation == "fixmate":
            Path(cmd[-1]).write_bytes(b"fixmate synthetic output\n")
        elif operation == "markdup":
            Path(cmd[cmd.index("-f") + 1]).write_text("duplicates: 0\n", encoding="utf-8")
            Path(cmd[-1]).write_bytes(b"markdup synthetic output\n")
        elif operation == "flagstat":
            stdout = "4 + 0 in total (QC-passed reads + QC-failed reads)\n"
        else:  # pragma: no cover - the exact profile is closed above
            raise AssertionError(operation)

        return {
            "returncode": 0,
            "stdout": stdout,
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    return _run_command


@pytest.mark.asyncio
async def test_flag_absent_preserves_legacy_execution(tmp_path: Path) -> None:
    class LegacyNode:
        RETURN_NAMES = ("value",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {}, "optional": {}, "hidden": {}}

        def run(self, context: Any, **kwargs: Any) -> dict[str, Any]:
            del context, kwargs
            return {"outputs": {"value": "legacy-ok"}}

    class Registry:
        def get(self, node_type: str) -> type[LegacyNode] | None:
            return LegacyNode if node_type == "legacy_test" else None

    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
    )
    result = await executor.execute(
        "legacy-run",
        {"nodes": [{"id": "legacy", "type": "legacy_test"}], "edges": []},
        options={"embed_provenance": False},
    )

    assert result["status"] == "completed"
    assert result["outputs"]["legacy"] == {"value": "legacy-ok"}
    assert CANARY_OPTION not in result["metadata"]


@pytest.mark.asyncio
async def test_explicit_canary_executes_typed_plans_without_legacy_lookup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _stub_pinned_input(monkeypatch)
    commands: list[list[str]] = []
    monkeypatch.setattr(ExecutionContext, "run_command", _fake_samtools_runner(commands))
    registry = RejectingLegacyRegistry()
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )
    workflow = _workflow()

    result = await executor.execute(
        "catalog-canary-run",
        workflow,
        options={CANARY_OPTION: CANARY_SELECTOR},
    )

    assert result["status"] == "completed"
    json.dumps(workflow)
    assert registry.calls == []
    assert [command[1] for command in commands] == [
        "view",
        "collate",
        "fixmate",
        "sort",
        "markdup",
        "index",
        "flagstat",
    ]
    assert all(node_result["cache_key"] is None for node_result in result["node_results"].values())

    metadata = result["metadata"][CANARY_OPTION]
    assert metadata["catalog_digest"] == SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST
    assert metadata["provenance_embedding"] is False
    assert len(metadata["nodes"]) == 8
    assert metadata["nodes"]["input_001"] == {
        "kind": "pinned_https_input",
        "source_url": SAMTOOLS_FIRST_WAVE_INPUT_URL,
        "content_digest": SAMTOOLS_FIRST_WAVE_INPUT_SHA256,
    }
    for node_id in (
        "view_001",
        "collate_001",
        "fixmate_001",
        "sort_001",
        "markdup_001",
        "index_001",
        "flagstat_001",
    ):
        attestation = metadata["nodes"][node_id]
        assert attestation["contract_digest"].startswith("sha256:")
        assert attestation["plan_digest"].startswith("sha256:")
        assert attestation["status"] == "promotion_candidate"

    index_outputs = result["outputs"]["index_001"]
    assert Path(index_outputs["indexed_bam"]).read_bytes() == b"markdup synthetic output\n"
    assert Path(index_outputs["bai"]).read_bytes() == b"index synthetic output\n"
    stats = Path(result["outputs"]["flagstat_001"]["stats"])
    assert stats.read_text(encoding="utf-8") == (
        "4 + 0 in total (QC-passed reads + QC-failed reads)\n"
    )


@pytest.mark.asyncio
async def test_wrong_catalog_digest_fails_before_any_node_or_process(tmp_path: Path) -> None:
    registry = RejectingLegacyRegistry()
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )

    result = await executor.execute(
        "wrong-digest",
        _workflow(),
        options={
            CANARY_OPTION: {
                **CANARY_SELECTOR,
                "catalog_digest": "sha256:" + "0" * 64,
            }
        },
    )

    assert result["status"] == "failed"
    assert "committed Samtools first-wave digest" in result["error"]
    assert registry.calls == []


@pytest.mark.asyncio
async def test_unknown_or_extra_node_fails_closed_without_legacy_fallback(tmp_path: Path) -> None:
    workflow = _workflow()
    workflow["nodes"].append({"id": "unknown", "type": "generic_command"})
    registry = RejectingLegacyRegistry()
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )

    result = await executor.execute(
        "unknown-node",
        workflow,
        options={CANARY_OPTION: CANARY_SELECTOR},
    )

    assert result["status"] == "failed"
    assert "exactly 8 executable nodes" in result["error"]
    assert registry.calls == []


def test_quarantined_status_in_generated_documents_fails_closed(tmp_path: Path) -> None:
    for filename in (
        "node-index.json",
        "catalog.runtime.json",
        "catalog.lock.json",
        "catalog.promotion.json",
    ):
        shutil.copy2(GENERATED_DIR / filename, tmp_path / filename)

    for filename in ("node-index.json", "catalog.runtime.json"):
        path = tmp_path / filename
        document = json.loads(path.read_text(encoding="utf-8"))
        entry = next(
            value
            for value in document["nodes"].values()
            if value["machine_id"] == "samtools_view"
        )
        entry["status"] = "quarantined"
        path.write_text(json.dumps(document), encoding="utf-8")
    promotion_path = tmp_path / "catalog.promotion.json"
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    next(
        entry for entry in promotion["nodes"] if entry["machine_id"] == "samtools_view"
    )["status"] = "quarantined"
    promotion_path.write_text(json.dumps(promotion), encoding="utf-8")

    with pytest.raises(CatalogCanaryError, match="disallowed promotion status"):
        CatalogCanaryRunner(
            profile=SAMTOOLS_FIRST_WAVE_PROFILE,
            catalog_digest=SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST,
            generated_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_non_argv_factory_result_is_rejected_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from bionodulo.nodes.catalog.tools.samtools import view

    _stub_pinned_input(monkeypatch)
    monkeypatch.setattr(view, "build_plan", lambda *args, **kwargs: object())
    commands: list[list[str]] = []
    monkeypatch.setattr(ExecutionContext, "run_command", _fake_samtools_runner(commands))
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=RejectingLegacyRegistry(),
    )

    result = await executor.execute(
        "bad-plan",
        _workflow(),
        options={CANARY_OPTION: CANARY_SELECTOR},
    )

    assert result["status"] == "failed"
    assert "did not return ArgvPlan" in result["node_results"]["view_001"]["error"]
    assert commands == []


def test_run_api_carries_typed_canary_selector_into_normal_queue_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    class Queue:
        def __init__(self) -> None:
            self.submit_calls: list[dict[str, Any]] = []

        async def submit(self, **kwargs: Any) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs["run_id"])

        async def shutdown(self) -> None:
            return None

    with TestClient(create_app()) as client:
        queue = Queue()
        client.app.state.run_queue = queue
        response = client.post(
            "/api/runs",
            json={
                "name": "Samtools Catalog Canary",
                "workflow": _workflow(),
                CANARY_OPTION: CANARY_SELECTOR,
            },
        )

    assert response.status_code == 200
    assert queue.submit_calls[0]["options"] == {CANARY_OPTION: CANARY_SELECTOR}
    assert queue.submit_calls[0]["metadata"][CANARY_OPTION] == CANARY_SELECTOR


@pytest.mark.asyncio
async def test_arq_payload_preserves_catalog_canary_selector(tmp_path: Path) -> None:
    class Job:
        async def result(self, timeout: float) -> dict[str, Any]:
            del timeout
            return {"status": "completed"}

    class Pool:
        def __init__(self) -> None:
            self.payload: dict[str, Any] | None = None

        async def enqueue_job(self, function: str, payload: dict[str, Any], **kwargs: Any) -> Job:
            del function, kwargs
            self.payload = payload
            return Job()

    pool = Pool()
    executor = ArqWorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    executor._pool = pool

    result = await executor.execute(
        "arq-canary",
        _workflow(),
        options={CANARY_OPTION: CANARY_SELECTOR},
    )

    assert result == {"status": "completed"}
    assert pool.payload is not None
    assert pool.payload["options"] == {CANARY_OPTION: CANARY_SELECTOR}
