from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.api.app_state import AppState
from bionodulo.api.routes import _extract_workflow_subgraph
from bionodulo.api.schemas import HPCSubmitRequest, RunCreateRequest, WorkflowExtractRequest
from bionodulo.execution.arq_executor import ArqWorkflowExecutor, maybe_wrap_with_arq
from bionodulo.execution.cache import CacheStore
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.queue import RunQueue
from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.manager.diagnostics import _check_r_packages_env_aware
from bionodulo.nodes.command_node import CommandNode, _shell_join
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.graph import (
    edge_source,
    edge_source_port,
    edge_target,
    edge_target_port,
    topological_sort,
)


def test_redact_tree_masks_nested_secret_values() -> None:
    from bionodulo.core.credentials import REDACTED, redact_tree

    payload = {
        "api_key": "secret-key",
        "nested": {
            "Authorization": "Bearer secret-token",
            "safe": "visible",
            "items": [{"password": "secret-password"}, "plain"],
        },
    }

    redacted = redact_tree(payload)

    assert redacted["api_key"] == REDACTED
    assert redacted["nested"]["Authorization"] == REDACTED
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["nested"]["items"][0]["password"] == REDACTED
    assert redacted["nested"]["items"][1] == "plain"


def test_resolve_secret_value_handles_credential_references() -> None:
    from bionodulo.core.credentials import resolve_secret_value

    context = SimpleNamespace(resolve_secret=lambda key: {"api_prod": "resolved-key"}.get(key))

    assert resolve_secret_value("credential://api_prod", context) == "resolved-key"
    assert resolve_secret_value("literal-key", context) == "literal-key"
    assert resolve_secret_value("", context, "api_prod") == "resolved-key"
    assert resolve_secret_value("credential://missing", context) == ""
    assert resolve_secret_value("credential://missing", context, default="fallback") == "fallback"


@pytest.mark.asyncio
async def test_run_subprocess_streams_to_log_files(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"

    result = await run_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('streamed-out'); print('streamed-err', file=sys.stderr)",
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        emit=lambda event, data: events.append((event, data)),
    )

    assert result["returncode"] == 0
    assert "streamed-out" in result["stdout"]
    assert "streamed-err" in result["stderr"]
    assert stdout_path.read_text(encoding="utf-8").strip() == "streamed-out"
    assert stderr_path.read_text(encoding="utf-8").strip() == "streamed-err"
    assert ("log", {"node_id": "subprocess", "level": "stdout", "message": "streamed-out"}) in events


@pytest.mark.asyncio
async def test_run_subprocess_cancel_kills_process_tree(tmp_path: Path) -> None:
    from bionodulo.execution.subprocess_runner import (
        CommandCancelledError,
        run_subprocess,
    )

    # Child writes its PID, then spawns a grandchild that sleeps for a long
    # time. Cancelling must kill the whole group, not just the immediate shell.
    marker = tmp_path / "grandchild.pid"
    script = (
        f"import os,sys,time,subprocess;"
        f"p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
        f"open(r'{marker}','w').write(str(p.pid));"
        f"sys.stdout.flush();"
        f"time.sleep(30)"
    )

    cancel_event = asyncio.Event()

    async def _cancel_soon() -> None:
        for _ in range(50):
            if marker.exists():
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.05)
        cancel_event.set()

    canceller = asyncio.create_task(_cancel_soon())
    with pytest.raises(CommandCancelledError):
        await run_subprocess(
            [sys.executable, "-c", script],
            stdout_path=tmp_path / "out.log",
            stderr_path=tmp_path / "err.log",
            cancel_event=cancel_event,
        )
    await canceller

    # Grandchild must be dead after cancellation.
    grandchild_pid = int(marker.read_text().strip())
    await asyncio.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(grandchild_pid, 0)


def test_cache_store_tracks_and_replaces_markers_atomically(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)

    store.write_marker("abc", outputs={"out": "one"})
    assert store.is_hit("abc")
    assert store.read_marker("abc")["outputs"] == {"out": "one"}

    store.write_marker("abc", outputs={"out": "two"})
    assert store.is_hit("abc")
    assert store.read_marker("abc")["outputs"] == {"out": "two"}


def test_cache_store_redacts_secret_like_marker_inputs_and_params(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)

    store.write_marker(
        "secret-cache",
        outputs={"out": "result"},
        params={"api_key": "secret-key", "sample": "S1"},
        inputs={"headers": {"Authorization": "Bearer secret-token"}},
    )

    marker = store.read_marker("secret-cache")
    assert marker["params"]["api_key"] == "***"
    assert marker["params"]["sample"] == "S1"
    assert marker["inputs"]["headers"]["Authorization"] == "***"
    assert "secret-key" not in json.dumps(marker)
    assert "secret-token" not in json.dumps(marker)


def test_executor_fans_in_multiple_edges_for_exact_typed_multiple_port(tmp_path: Path) -> None:
    class MultiFileNode:
        @classmethod
        def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
            return {"required": {"files": ("FILE", {"multiple": True})}}

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    node = {"id": "target", "type": "multi_file", "_node_class": MultiFileNode}
    edges = [
        {
            "from": {"node": "sample_a", "output": "file"},
            "to": {"node": "target", "input": "files"},
        },
        {
            "from": {"node": "sample_b", "output": "file"},
            "to": {"node": "target", "input": "files"},
        },
    ]

    resolved = executor._resolve_inputs(
        "target",
        node,
        {"target": edges},
        {"sample_a": {"file": "a.mzML"}, "sample_b": {"file": "b.mzML"}},
    )

    assert resolved == {"files": ["a.mzML", "b.mzML"]}


def test_cache_store_ttl_markers_expire_from_hits_and_reads(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)

    store.write_marker_with_ttl("fresh-cache", outputs={"out": "fresh"}, ttl_seconds=3600)
    assert store.is_hit("fresh-cache")
    assert store.read_marker("fresh-cache")["outputs"] == {"out": "fresh"}
    assert "expires_at" in store.read_marker("fresh-cache")

    store.write_marker_with_ttl("expired-cache", outputs={"out": "stale"}, ttl_seconds=-1)

    assert not store.is_hit("expired-cache")
    assert store.read_marker("expired-cache") is None


def test_shell_join_preserves_file_descriptor_redirects() -> None:
    command = _shell_join(["tool", "input file.txt", ">", "tool.log", "2>&1"])

    assert command == "tool 'input file.txt' > tool.log 2>&1"


@pytest.mark.asyncio
async def test_command_node_rejects_missing_planned_outputs(tmp_path: Path) -> None:
    class MissingOutputNode(CommandNode):
        NODE_ID = "missing_output"
        COMMAND = ["true"]
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("output",)

    with pytest.raises(RuntimeError, match="Command completed but did not create expected output"):
        await MissingOutputNode().run(output_dir=tmp_path)


def test_cache_clear_preserves_unrelated_files(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.write_marker("abc", outputs={"out": "cached"})
    legacy_marker = tmp_path / "legacy.marker.json"
    legacy_marker.write_text("{}", encoding="utf-8")
    unrelated = tmp_path / "do-not-delete.txt"
    unrelated.write_text("keep me", encoding="utf-8")

    count = store.clear()

    assert count >= 1
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert not legacy_marker.exists()
    assert not store.is_hit("abc")


@pytest.mark.asyncio
async def test_workflow_executor_passes_registry_to_node_context(tmp_path: Path) -> None:
    class RegistryAwareNode:
        RETURN_NAMES = ("registry_name",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            return {"outputs": {"registry_name": context.registry.name}}

    class Registry:
        name = "runtime-registry"

        def get(self, node_type: str) -> type[RegistryAwareNode] | None:
            return {"registry_aware": RegistryAwareNode}.get(node_type)

    workflow = {
        "nodes": [{"id": "reader", "type": "registry_aware", "outputs": {"registry_name": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("registry-context-run", workflow)

    assert result["status"] == "completed"
    assert result["outputs"]["reader"] == {"registry_name": "runtime-registry"}


@pytest.mark.asyncio
async def test_executor_applies_inline_output_validation_rules(tmp_path: Path) -> None:
    class FileProducerNode:
        RETURN_NAMES = ("file",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        async def run(self, context, **_: Any) -> dict[str, Any]:
            path = Path(context.node_dir) / "bad.fa"
            path.write_text("not-fasta\n", encoding="utf-8")
            return {"outputs": {"file": str(path)}}

    class Registry:
        def get(self, node_type: str) -> type[FileProducerNode] | None:
            return {"file_producer": FileProducerNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "producer",
                "type": "file_producer",
                "ui": {
                    "validation": {
                        "outputs": {
                            "file": {
                                "expected_format": "fasta",
                                "min_records": 1,
                                "fail_on_error": True,
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("inline-validation-run", workflow, force=True)

    assert result["status"] == "failed"
    assert "Data validation failed" in result["node_results"]["producer"]["error"]


def test_graph_helpers_support_frontend_and_legacy_edge_shapes() -> None:
    frontend_edge = {
        "from": {"node": "input", "output": "reads"},
        "to": {"node": "qc", "input": "reads"},
    }
    legacy_edge = {
        "source_node": "qc",
        "target_node": "multiqc",
        "source_output": "report",
        "target_input": "reports",
    }
    workflow = {
        "nodes": [{"id": "input"}, {"id": "qc"}, {"id": "multiqc"}],
        "edges": [frontend_edge, legacy_edge],
    }

    assert edge_source(frontend_edge) == "input"
    assert edge_source_port(frontend_edge) == "reads"
    assert edge_target(frontend_edge) == "qc"
    assert edge_target_port(frontend_edge) == "reads"
    assert edge_source(legacy_edge) == "qc"
    assert edge_target(legacy_edge) == "multiqc"
    assert topological_sort(workflow) == ["input", "qc", "multiqc"]


@pytest.mark.asyncio
async def test_run_store_persists_and_reconciles_orphans(tmp_path: Path) -> None:
    from bionodulo.execution.run_store import RunStore

    db = tmp_path / "runs.db"

    class HangingExecutor:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, **_: Any) -> dict[str, Any]:
            self.started.set()
            await self.release.wait()
            return {"status": "completed"}

    # First "process": one run finishes, a second is left running when we crash.
    store1 = RunStore(db)
    executor = HangingExecutor()
    queue1 = RunQueue(executor=executor, max_concurrent=1, store=store1)
    try:
        await queue1.submit({"nodes": [], "edges": []}, run_id="done")
        await asyncio.wait_for(executor.started.wait(), timeout=1.0)
        executor.release.set()
        for _ in range(40):
            if queue1.get_run("done") and queue1.get_run("done")["status"] == "completed":
                break
            await asyncio.sleep(0.02)

        executor.release.clear()
        executor.started.clear()
        await queue1.submit({"nodes": [], "edges": []}, run_id="orphan")
        await asyncio.wait_for(executor.started.wait(), timeout=1.0)
    finally:
        # Simulate a crash: drop in-memory state without graceful shutdown,
        # leaving "orphan" persisted as running.
        store1.close()

    # Second "process": fresh queue recovers from the same DB.
    store2 = RunStore(db)
    queue2 = RunQueue(executor=HangingExecutor(), max_concurrent=1, store=store2)
    try:
        summary = queue2.recover()
        assert "orphan" in summary["interrupted"]
        assert queue2.get_run("orphan")["status"] == "interrupted"
        assert queue2.get_run("done")["status"] == "completed"
    finally:
        await queue2.shutdown()


@pytest.mark.asyncio
async def test_run_queue_honors_max_concurrent() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self.started = 0
            self.both_started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, **_: Any) -> dict[str, Any]:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started += 1
            if self.started == 2:
                self.both_started.set()
            await self.release.wait()
            self.active -= 1
            return {"status": "completed"}

    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=2)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="one")
        await queue.submit({"nodes": [], "edges": []}, run_id="two")

        await asyncio.wait_for(executor.both_started.wait(), timeout=1.0)
        assert executor.max_active == 2

        executor.release.set()
        for _ in range(20):
            if len(queue.list_history()) == 2:
                break
            await asyncio.sleep(0.05)

        assert {entry["run_id"] for entry in queue.list_history()} == {"one", "two"}
    finally:
        executor.release.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_releases_pending_join_accounting() -> None:
    class Executor:
        async def execute(self, **_: Any) -> dict[str, Any]:
            return {"status": "completed"}

    queue = RunQueue(executor=Executor(), max_concurrent=1)
    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="joinable")
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)
        assert queue.get_run("joinable")["status"] == "completed"
    finally:
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_serializes_execution_plan_for_queue_and_history() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, **_: Any) -> dict[str, Any]:
            self.started.set()
            await self.release.wait()
            return {
                "status": "completed",
                "metadata": {
                    "nodes": {
                        "input": {"status": "completed"},
                        "qc": {"status": "completed"},
                    }
                },
            }

    workflow = {
        "name": "Queue Plan",
        "nodes": [
            {"id": "note", "type": "note"},
            {"id": "input", "type": "input_fastq"},
            {"id": "qc", "type": "fastqc"},
        ],
        "edges": [
            {"source_node": "input", "source_output": "reads", "target_node": "qc", "target_input": "reads"},
        ],
    }
    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit(workflow, run_id="running", metadata={"name": "Queue Plan"})
        await asyncio.wait_for(executor.started.wait(), timeout=1.0)
        await queue.submit(workflow, run_id="pending", metadata={"name": "Queue Plan"})

        state = queue.queue_state()
        assert state["running"][0]["execution_plan"] == ["input", "qc"]
        assert state["pending"][0]["execution_plan"] == ["input", "qc"]

        executor.release.set()
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        history_by_id = {entry["run_id"]: entry for entry in queue.list_history()}
        assert history_by_id["running"]["execution_plan"] == ["input", "qc"]
        assert history_by_id["running"]["node_statuses"] == [
            {"node_id": "input", "status": "completed"},
            {"node_id": "qc", "status": "completed"},
        ]
    finally:
        executor.release.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_reorders_pending_before_execution() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.started: list[str] = []
            self.first_started = asyncio.Event()
            self.release_first = asyncio.Event()

        async def execute(self, run_id: str, **_: Any) -> dict[str, Any]:
            self.started.append(run_id)
            if run_id == "one":
                self.first_started.set()
                await self.release_first.wait()
            return {"status": "completed"}

    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="one")
        await asyncio.wait_for(executor.first_started.wait(), timeout=1.0)
        await queue.submit({"nodes": [], "edges": []}, run_id="two")
        await queue.submit({"nodes": [], "edges": []}, run_id="three")

        pending = await queue.reorder_pending("three", index=0)

        assert [entry["run_id"] for entry in pending] == ["three", "two"]

        executor.release_first.set()
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        assert executor.started == ["one", "three", "two"]
    finally:
        executor.release_first.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_cancel_pending_moves_run_to_history() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, **_: Any) -> dict[str, Any]:
            self.started.set()
            await self.release.wait()
            return {"status": "completed"}

    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="running")
        await asyncio.wait_for(executor.started.wait(), timeout=1.0)
        await queue.submit({"nodes": [], "edges": []}, run_id="pending")

        assert await queue.cancel("pending") is True

        state = queue.queue_state()
        assert state["pending"] == []
        assert queue.get_run("pending")["status"] == "cancelled"
    finally:
        executor.release.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_cancel_running_not_overwritten_by_late_completion() -> None:
    """A cancel landing while the executor finalizes must stick."""

    class LateExecutor:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, *, cancel_event: asyncio.Event, **_: Any) -> dict[str, Any]:
            self.started.set()
            await self.release.wait()
            # Executor finished its work before noticing the cancel and reports
            # "completed" — the queue must not clobber the user's cancel.
            return {"status": "completed"}

    executor = LateExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="running")
        await asyncio.wait_for(executor.started.wait(), timeout=1.0)

        assert await queue.cancel("running") is True
        executor.release.set()

        for _ in range(40):
            if queue.get_run("running")["status"] in {"cancelled", "completed"}:
                if "running" not in queue._running:
                    break
            await asyncio.sleep(0.02)

        assert queue.get_run("running")["status"] == "cancelled"
    finally:
        executor.release.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_retry_uses_stored_workflow_options_and_force_nodes() -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def execute(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"status": "completed"}

    workflow = {"name": "Retry Me", "nodes": [{"id": "a", "type": "demo"}], "edges": []}
    executor = RecordingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit(
            workflow,
            run_id="original",
            options={"target_nodes": ["a"]},
            force_nodes={"a"},
            metadata={"name": "Retry Me"},
        )
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        await queue.retry("original", new_run_id="retry")
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        assert len(executor.calls) == 2
        assert executor.calls[1]["workflow"] == workflow
        assert executor.calls[1]["options"] == {"target_nodes": ["a"]}
        assert executor.calls[1]["force_nodes"] == {"a"}
    finally:
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_retry_resumes_from_latest_checkpoint_after_failure(tmp_path: Path) -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            self.workspace_dir = tmp_path

        async def execute(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return {"status": "failed", "error": "downstream failed"}
            return {"status": "completed"}

    checkpoint_file = tmp_path / "checkpoints" / "after_qc.json"
    checkpoint_file.parent.mkdir(parents=True)
    checkpoint_file.write_text('{"version":"1.0","data":"qc-passed"}', encoding="utf-8")
    checkpoint_entry = {
        "checkpoint_name": "after_qc",
        "checkpoint_path": str(checkpoint_file),
        "run_id": "original",
        "node_id": "checkpoint",
        "node_type": "checkpoint",
    }
    (checkpoint_file.parent / "checkpoint_manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "checkpoints": {str(checkpoint_file): checkpoint_entry},
                "latest_by_name": {"after_qc": checkpoint_entry},
                "latest_by_run_node": {"original:checkpoint": checkpoint_entry},
            }
        ),
        encoding="utf-8",
    )
    workflow = {
        "name": "Resume Retry",
        "nodes": [
            {"id": "checkpoint", "type": "checkpoint"},
            {"id": "downstream", "type": "demo"},
        ],
        "edges": [
            {"source_node": "checkpoint", "target_node": "downstream", "source_output": "passthrough", "target_input": "input"},
        ],
    }
    executor = RecordingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit(workflow, run_id="original", metadata={"name": "Resume Retry"})
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        await queue.retry("original", new_run_id="retry")
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        assert len(executor.calls) == 2
        assert executor.calls[1]["options"]["resume_checkpoint"] == checkpoint_entry
    finally:
        await queue.shutdown()


@pytest.mark.asyncio
async def test_executor_dry_run_preview_plans_command_outputs_and_cache(tmp_path: Path) -> None:
    class PreviewCommandNode(CommandNode):
        NODE_ID = "preview_command"
        COMMAND = ["echo", "{params.message}", ">", "{output}/result.out"]
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("result",)
        REQUIRED_EXECUTABLES = ["echo"]
        REQUIRED_CONDA_PACKAGES = ["coreutils"]
        SHELL = True

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"preview_command": PreviewCommandNode}.get(node_type)

    workflow = {
        "parameters": [{"name": "message", "default": "hello"}],
        "nodes": [
            {
                "id": "preview",
                "type": "preview_command",
                "inputs": {"message": {"value": "{{message}}"}},
                "outputs": {"result": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    preview = await executor.dry_run(
        "dry-run-1",
        workflow,
        options={"parameters": {"message": "from-runtime"}},
    )

    assert preview["status"] == "dry_run"
    assert preview["run_id"] == "dry-run-1"
    assert preview["execution_order"] == ["preview"]
    node_plan = preview["nodes"][0]
    assert node_plan["node_id"] == "preview"
    assert node_plan["node_type"] == "preview_command"
    assert node_plan["inputs"]["message"] == "from-runtime"
    assert node_plan["params"]["message"] == "from-runtime"
    assert node_plan["command"] == (
        "echo from-runtime > "
        f"{tmp_path / 'runs' / 'dry-run-1' / 'preview' / 'preview_command' / 'result.out'}"
    )
    assert node_plan["shell"] is True
    assert node_plan["required_executables"] == ["echo"]
    assert node_plan["required_conda_packages"] == ["coreutils"]
    assert node_plan["cache"]["key"]
    assert node_plan["cache"]["hit"] is False
    assert node_plan["planned_outputs"] == {
        "result": str(tmp_path / "runs" / "dry-run-1" / "preview" / "preview_command" / "result.out")
    }
    assert not (tmp_path / "runs" / "dry-run-1" / "run_metadata.json").exists()


@pytest.mark.asyncio
async def test_executor_dry_run_redacts_secret_like_inputs_params_and_commands(tmp_path: Path) -> None:
    class SecretCommandNode(CommandNode):
        NODE_ID = "secret_command"
        COMMAND = ["curl", "-H", "Authorization: Bearer {params.api_key}", "{params.url}"]
        RETURN_TYPES = ("STRING",)
        RETURN_NAMES = ("result",)

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"secret_command": SecretCommandNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "secret",
                "type": "secret_command",
                "params": {
                    "api_key": "secret-token",
                    "url": "https://example.test",
                },
                "outputs": {"result": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    preview = await executor.dry_run("secret-preview", workflow)

    node_plan = preview["nodes"][0]
    assert node_plan["params"]["api_key"] == "***"
    assert node_plan["params"]["url"] == "https://example.test"
    assert "secret-token" not in json.dumps(node_plan, sort_keys=True)
    assert "secret-token" not in json.dumps(preview, sort_keys=True)


@pytest.mark.asyncio
async def test_executor_context_merges_settings_api_secrets_with_option_overrides(tmp_path: Path) -> None:
    class SecretProbeNode:
        RETURN_NAMES = ("out",)
        observed: dict[str, str | None] = {}

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> tuple[str]:
            type(self).observed = {
                "configured": context.resolve_secret("configured"),
                "override": context.resolve_secret("override"),
                "option_only": context.resolve_secret("option_only"),
            }
            return ("ok",)

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"secret_probe": SecretProbeNode}.get(node_type)

    settings = SimpleNamespace(api_secrets={"configured": "from-settings", "override": "from-settings"})
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=settings,
    )

    result = await executor.execute(
        "secret-run",
        {"nodes": [{"id": "probe", "type": "secret_probe", "outputs": {"out": {}}}], "edges": []},
        options={"api_secrets": {"override": "from-options", "option_only": "from-options"}},
    )

    assert result["status"] == "completed"
    assert SecretProbeNode.observed == {
        "configured": "from-settings",
        "override": "from-options",
        "option_only": "from-options",
    }


@pytest.mark.asyncio
async def test_executor_resumes_downstream_from_checkpoint_artifact(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoints" / "saved.json"
    checkpoint_path.parent.mkdir()
    checkpoint_path.write_text(
        json.dumps({"version": "1.0", "checkpoint_name": "saved", "data": "restored"}),
        encoding="utf-8",
    )
    checkpoint_entry = {
        "checkpoint_name": "saved",
        "checkpoint_path": str(checkpoint_path),
        "compressed": False,
        "run_id": "previous",
        "node_id": "checkpoint",
        "node_type": "checkpoint",
    }

    class SourceNode:
        RETURN_NAMES = ("out",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> tuple[str]:
            self.calls.append(context.node_id)
            return ("fresh",)

    class CheckpointNodeForTest:
        RETURN_NAMES = ("passthrough", "checkpoint_file", "checkpoint_info")
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **kwargs: Any) -> tuple[Any, str, str]:
            self.calls.append(context.node_id)
            return (kwargs.get("input"), "", "{}")

    class DownstreamNode:
        RETURN_NAMES = ("out",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **kwargs: Any) -> tuple[str]:
            self.calls.append(kwargs["input"])
            return (f"downstream:{kwargs['input']}",)

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "source": SourceNode,
                "checkpoint": CheckpointNodeForTest,
                "downstream": DownstreamNode,
            }[node_type]

    workflow = {
        "nodes": [
            {"id": "source", "type": "source", "outputs": {"out": {}}},
            {"id": "checkpoint", "type": "checkpoint", "outputs": {"passthrough": {}, "checkpoint_file": {}, "checkpoint_info": {}}},
            {"id": "downstream", "type": "downstream", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "source", "target_node": "checkpoint", "source_output": "out", "target_input": "input"},
            {"source_node": "checkpoint", "target_node": "downstream", "source_output": "passthrough", "target_input": "input"},
        ],
    }
    SourceNode.calls = []
    CheckpointNodeForTest.calls = []
    DownstreamNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute(
        "resume-run",
        workflow,
        options={"resume_checkpoint": checkpoint_entry},
    )

    assert result["status"] == "completed"
    assert SourceNode.calls == []
    assert CheckpointNodeForTest.calls == []
    assert DownstreamNode.calls == ["restored"]
    assert result["node_results"]["checkpoint"]["status"] == "resumed"
    assert result["outputs"]["checkpoint"]["passthrough"] == "restored"
    assert result["outputs"]["downstream"] == {"out": "downstream:restored"}
    assert result["metadata"]["resume_checkpoint"]["node_id"] == "checkpoint"


@pytest.mark.asyncio
async def test_executor_dry_run_marks_checkpoint_resume_without_executing_upstream(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoints" / "saved.json"
    checkpoint_path.parent.mkdir()
    checkpoint_path.write_text(
        json.dumps({"version": "1.0", "checkpoint_name": "saved", "data": "restored"}),
        encoding="utf-8",
    )

    class AnyNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

    class CheckpointNodeForTest:
        RETURN_NAMES = ("passthrough", "checkpoint_file", "checkpoint_info")

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

    class Registry:
        def get(self, node_type: str) -> type:
            return CheckpointNodeForTest if node_type == "checkpoint" else AnyNode

    workflow = {
        "nodes": [
            {"id": "source", "type": "source", "outputs": {"out": {}}},
            {"id": "checkpoint", "type": "checkpoint", "outputs": {"passthrough": {}, "checkpoint_file": {}, "checkpoint_info": {}}},
            {"id": "downstream", "type": "downstream", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "source", "target_node": "checkpoint", "source_output": "out", "target_input": "input"},
            {"source_node": "checkpoint", "target_node": "downstream", "source_output": "passthrough", "target_input": "input"},
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    preview = await executor.dry_run(
        "resume-preview",
        workflow,
        options={
            "resume_checkpoint": {
                "checkpoint_name": "saved",
                "checkpoint_path": str(checkpoint_path),
                "compressed": False,
                "node_id": "checkpoint",
            }
        },
    )

    assert preview["status"] == "dry_run"
    assert preview["execution_order"] == ["checkpoint", "downstream"]
    assert preview["nodes"][0]["status"] == "resumed"
    assert preview["nodes"][0]["planned_outputs"]["passthrough"] == "restored"
    assert preview["resume_checkpoint"]["checkpoint_name"] == "saved"


@pytest.mark.asyncio
async def test_workflow_executor_blocks_downstream_until_pause_approval(tmp_path: Path) -> None:
    from bionodulo.nodes.builtin.workflow_enhancement import PauseResumeNode

    class SourceNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> tuple[str]:
            return ("review-me",)

    class DownstreamNode:
        RETURN_NAMES = ("out",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **kwargs: Any) -> tuple[str]:
            self.calls.append(kwargs["input"])
            return (f"approved:{kwargs['input']}",)

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "source": SourceNode,
                "pause_resume": PauseResumeNode,
                "downstream": DownstreamNode,
            }[node_type]

    workflow = {
        "nodes": [
            {"id": "source", "type": "source", "outputs": {"out": {}}},
            {
                "id": "pause",
                "type": "pause_resume",
                "params": {
                    "timeout_seconds": 0,
                    "default_action": "wait",
                    "message": "Review before downstream.",
                },
                "outputs": {"output": {}, "approved": {}, "pause_info": {}},
            },
            {"id": "downstream", "type": "downstream", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "source", "target_node": "pause", "source_output": "out", "target_input": "input"},
            {"source_node": "pause", "target_node": "downstream", "source_output": "output", "target_input": "input"},
        ],
    }
    DownstreamNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    task = asyncio.create_task(executor.execute("pause-run", workflow))
    await asyncio.sleep(0.05)

    pause_file = tmp_path / "pause_requests" / "pause-run__pause.json"
    assert pause_file.exists()
    assert DownstreamNode.calls == []
    assert not task.done()

    PauseResumeNode.resolve_pause_request(pause_file, action="approve", reviewer="ana")
    result = await asyncio.wait_for(task, timeout=1)

    assert result["status"] == "completed"
    assert DownstreamNode.calls == ["review-me"]
    assert result["outputs"]["downstream"] == {"out": "approved:review-me"}


@pytest.mark.asyncio
async def test_workflow_executor_fails_when_pause_request_is_rejected(tmp_path: Path) -> None:
    from bionodulo.nodes.builtin.workflow_enhancement import PauseResumeNode

    class SourceNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> tuple[str]:
            return ("review-me",)

    class DownstreamNode:
        RETURN_NAMES = ("out",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **kwargs: Any) -> tuple[str]:
            self.calls.append(kwargs["input"])
            return (f"approved:{kwargs['input']}",)

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "source": SourceNode,
                "pause_resume": PauseResumeNode,
                "downstream": DownstreamNode,
            }[node_type]

    workflow = {
        "nodes": [
            {"id": "source", "type": "source", "outputs": {"out": {}}},
            {
                "id": "pause",
                "type": "pause_resume",
                "params": {"timeout_seconds": 0, "default_action": "wait"},
                "outputs": {"output": {}, "approved": {}, "pause_info": {}},
            },
            {"id": "downstream", "type": "downstream", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "source", "target_node": "pause", "source_output": "out", "target_input": "input"},
            {"source_node": "pause", "target_node": "downstream", "source_output": "output", "target_input": "input"},
        ],
    }
    DownstreamNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    task = asyncio.create_task(executor.execute("pause-reject-run", workflow))
    await asyncio.sleep(0.05)

    pause_file = tmp_path / "pause_requests" / "pause-reject-run__pause.json"
    PauseResumeNode.resolve_pause_request(pause_file, action="reject", reviewer="ana")
    result = await asyncio.wait_for(task, timeout=1)

    assert result["status"] == "failed"
    assert "Pause request rejected" in result["node_results"]["pause"]["error"]
    assert DownstreamNode.calls == []


@pytest.mark.asyncio
async def test_workflow_executor_cancels_while_pause_request_is_waiting(tmp_path: Path) -> None:
    from bionodulo.nodes.builtin.workflow_enhancement import PauseResumeNode

    class SourceNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> tuple[str]:
            return ("review-me",)

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "source": SourceNode,
                "pause_resume": PauseResumeNode,
            }[node_type]

    workflow = {
        "nodes": [
            {"id": "source", "type": "source", "outputs": {"out": {}}},
            {
                "id": "pause",
                "type": "pause_resume",
                "params": {"timeout_seconds": 0, "default_action": "wait"},
                "outputs": {"output": {}, "approved": {}, "pause_info": {}},
            },
        ],
        "edges": [
            {"source_node": "source", "target_node": "pause", "source_output": "out", "target_input": "input"},
        ],
    }
    cancel_event = asyncio.Event()
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    task = asyncio.create_task(executor.execute("pause-cancel-run", workflow, cancel_event=cancel_event))
    await asyncio.sleep(0.05)

    assert (tmp_path / "pause_requests" / "pause-cancel-run__pause.json").exists()
    assert not task.done()
    cancel_event.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result["status"] == "cancelled"
    saved = json.loads((tmp_path / "pause_requests" / "pause-cancel-run__pause.json").read_text(encoding="utf-8"))
    assert saved["status"] == "cancelled"
    assert saved["approved"] is False


@pytest.mark.asyncio
async def test_run_queue_shutdown_closes_executor_cache() -> None:
    class Cache:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Executor:
        def __init__(self) -> None:
            self.cache = Cache()

    executor = Executor()
    queue = RunQueue(executor=executor)

    await queue.shutdown()

    assert executor.cache.closed


@pytest.mark.asyncio
async def test_workflow_executor_target_nodes_execute_upstream_dependencies_only(tmp_path: Path) -> None:
    class RecordingNode:
        RETURN_NAMES = ("out",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": context.node_id}}

    class Registry:
        def get(self, _node_type: str) -> type[RecordingNode]:
            return RecordingNode

    workflow = {
        "nodes": [
            {"id": "a", "type": "record", "outputs": {"out": {}}},
            {"id": "b", "type": "record", "outputs": {"out": {}}},
            {"id": "c", "type": "record", "outputs": {"out": {}}},
            {"id": "d", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "a", "target_node": "b", "source_output": "out", "target_input": "in"},
            {"source_node": "b", "target_node": "c", "source_output": "out", "target_input": "in"},
            {"source_node": "a", "target_node": "d", "source_output": "out", "target_input": "in"},
        ],
    }
    RecordingNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("targeted", workflow, options={"target_nodes": ["c"]})

    assert result["status"] == "completed"
    assert RecordingNode.calls == ["a", "b", "c"]
    assert set(result["outputs"]) == {"a", "b", "c"}
    assert result["metadata"]["target_nodes"] == ["c"]


@pytest.mark.asyncio
async def test_workflow_executor_context_exposes_executor_and_shared_run_metadata(tmp_path: Path) -> None:
    class ContextProbeNode:
        RETURN_NAMES = ("out",)
        observations: list[dict[str, Any]] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            context.run_metadata.setdefault("context_probe", []).append(context.node_id)
            self.observations.append({
                "node_id": context.node_id,
                "has_executor": context.executor is not None,
                "shared_metadata": context.run_metadata,
            })
            return {"outputs": {"out": context.node_id}}

    class Registry:
        def get(self, _node_type: str) -> type[ContextProbeNode]:
            return ContextProbeNode

    workflow = {
        "nodes": [{"id": "probe", "type": "context_probe", "outputs": {"out": {}}}],
        "edges": [],
    }
    ContextProbeNode.observations = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("context-run", workflow)

    assert result["status"] == "completed"
    assert result["metadata"]["context_probe"] == ["probe"]
    assert ContextProbeNode.observations == [{
        "node_id": "probe",
        "has_executor": True,
        "shared_metadata": result["metadata"],
    }]


@pytest.mark.asyncio
async def test_workflow_executor_persists_artifacts_in_run_metadata(tmp_path: Path) -> None:
    class FileWriterNode:
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            output_path = context.node_dir / "result.txt"
            output_path.write_text("persisted artifact\n", encoding="utf-8")
            return {"outputs": {"out": str(output_path)}}

    class Registry:
        def get(self, _node_type: str) -> type[FileWriterNode]:
            return FileWriterNode

    workflow = {
        "nodes": [{"id": "writer", "type": "file_writer", "outputs": {"out": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("artifact-run", workflow)

    metadata_path = tmp_path / "runs" / "artifact-run" / "run_metadata.json"
    persisted = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert result["artifacts"] == [
        {
            "node_id": "writer",
            "node_type": "file_writer",
            "port": "out",
            "path": str(tmp_path / "runs" / "artifact-run" / "writer" / "result.txt"),
            "size": len("persisted artifact\n"),
        }
    ]
    assert persisted["artifacts"] == result["artifacts"]


@pytest.mark.asyncio
async def test_workflow_executor_fails_nodes_that_return_none(tmp_path: Path) -> None:
    class NoneReturnNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> None:
            return None

    class Registry:
        def get(self, _node_type: str) -> type[NoneReturnNode]:
            return NoneReturnNode

    workflow = {
        "nodes": [{"id": "bad", "type": "none_return", "outputs": {"out": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("none-return-run", workflow)

    assert result["status"] == "failed"
    assert result["node_results"]["bad"]["status"] == "failed"
    assert "did not return outputs" in result["node_results"]["bad"]["error"]


@pytest.mark.asyncio
async def test_workflow_executor_fails_nodes_that_return_dict_without_outputs(tmp_path: Path) -> None:
    class InvalidDictNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            return {"out": "value"}

    class Registry:
        def get(self, _node_type: str) -> type[InvalidDictNode]:
            return InvalidDictNode

    workflow = {
        "nodes": [{"id": "bad", "type": "invalid_dict", "outputs": {"out": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("invalid-dict-run", workflow)

    assert result["status"] == "failed"
    assert result["node_results"]["bad"]["status"] == "failed"
    assert "must return an 'outputs' mapping" in result["node_results"]["bad"]["error"]


@pytest.mark.asyncio
async def test_workflow_executor_continue_on_fail_routes_error_outputs(tmp_path: Path) -> None:
    class FailingNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            raise RuntimeError("tool_error: alignment failed")

    class CaptureNode:
        calls: list[str] = []
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"message": ("STRING", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            type(self).calls.append(str(kwargs["message"]))
            return {"outputs": {"out": f"handled:{kwargs['message']}"}}

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "failing": FailingNode,
                "capture": CaptureNode,
            }[node_type]

    workflow = {
        "nodes": [
            {
                "id": "bad",
                "type": "failing",
                "continueOnFail": True,
                "outputs": {
                    "out": {},
                    "error": {},
                    "error_message": {},
                    "error_type": {},
                    "traceback": {},
                    "attempts": {},
                },
            },
            {"id": "handler", "type": "capture", "outputs": {"out": {}}},
        ],
        "edges": [
            {
                "source_node": "bad",
                "target_node": "handler",
                "source_output": "error",
                "target_input": "message",
            },
        ],
    }
    CaptureNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("continue-on-fail-run", workflow)

    assert result["status"] == "completed"
    assert result["node_results"]["bad"]["status"] == "failed"
    assert result["node_results"]["bad"]["continue_on_fail"] is True
    assert "tool_error: alignment failed" in result["node_results"]["bad"]["error"]
    assert result["outputs"]["bad"]["error"] == "Execution failed for bad: tool_error: alignment failed"
    assert result["outputs"]["bad"]["error_message"] == "tool_error: alignment failed"
    assert result["outputs"]["bad"]["error_type"] == "RuntimeError"
    assert result["outputs"]["bad"]["attempts"] == 1
    assert CaptureNode.calls == ["Execution failed for bad: tool_error: alignment failed"]
    assert result["outputs"]["handler"] == {"out": "handled:Execution failed for bad: tool_error: alignment failed"}
    assert result["metadata"]["failed_nodes"] == ["bad"]
    assert result["metadata"]["status"] == "completed"


@pytest.mark.asyncio
async def test_workflow_executor_continue_on_fail_accepts_meta_flag(tmp_path: Path) -> None:
    class FailingNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            raise ValueError("validation: missing sample")

    class Registry:
        def get(self, _node_type: str) -> type[FailingNode]:
            return FailingNode

    workflow = {
        "nodes": [
            {
                "id": "bad",
                "type": "failing",
                "meta": {"continue_on_fail": True},
                "outputs": {"error": {}, "error_message": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("continue-on-fail-meta-run", workflow)

    assert result["status"] == "completed"
    assert result["node_results"]["bad"]["status"] == "failed"
    assert result["outputs"]["bad"]["error_message"] == "validation: missing sample"


@pytest.mark.asyncio
async def test_workflow_executor_always_run_cache_policy_bypasses_generic_cache(tmp_path: Path) -> None:
    class AlwaysRunNode:
        RETURN_NAMES = ("out",)
        EXECUTOR_CACHE_POLICY = "always_run"
        calls = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            type(self).calls += 1
            return {"outputs": {"out": f"run-{type(self).calls}"}}

    class Registry:
        def get(self, _node_type: str) -> type[AlwaysRunNode]:
            return AlwaysRunNode

    workflow = {
        "nodes": [{"id": "control", "type": "always_run", "outputs": {"out": {}}}],
        "edges": [],
    }
    AlwaysRunNode.calls = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    first = await executor.execute("first", workflow)
    second = await executor.execute("second", workflow)

    assert first["outputs"]["control"]["out"] == "run-1"
    assert second["outputs"]["control"]["out"] == "run-2"
    assert second["node_results"]["control"]["status"] == "completed"
    assert second["node_results"]["control"]["cache_key"] is None


@pytest.mark.asyncio
async def test_workflow_executor_retries_downstream_node_after_retry_policy(tmp_path: Path) -> None:
    class RetryPolicyNode:
        RETURN_NAMES = ("passthrough", "retry_log")
        EXECUTOR_CACHE_POLICY = "always_run"

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {
                "required": {"input": ("ANY", {})},
                "optional": {
                    "max_retries": ("INT", {"default": 1}),
                    "delay_seconds": ("FLOAT", {"default": 0.0}),
                    "backoff_multiplier": ("FLOAT", {"default": 1.0}),
                    "max_delay": ("INT", {"default": 1}),
                    "retry_on": (["all"], {"default": "all"}),
                    "only_retry_specific_nodes": ("STRING", {"default": ""}),
                },
            }

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            policy = {
                "node_id": context.node_id,
                "max_retries": int(kwargs.get("max_retries", 1)),
                "delay_seconds": float(kwargs.get("delay_seconds", 0.0)),
                "backoff_multiplier": float(kwargs.get("backoff_multiplier", 1.0)),
                "max_delay": float(kwargs.get("max_delay", 1.0)),
                "retry_on": str(kwargs.get("retry_on", "all")),
                "target_nodes": [
                    value.strip()
                    for value in str(kwargs.get("only_retry_specific_nodes", "")).split(",")
                    if value.strip()
                ],
                "delays_seconds": [0.0],
            }
            context.run_metadata.setdefault("retry_policies", []).append(policy)
            return {"outputs": {"passthrough": kwargs["input"], "retry_log": "registered"}}

    class FlakyNode:
        NODE_ID = "flaky_registered"
        RETURN_NAMES = ("out",)
        attempts = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"input": ("ANY", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise RuntimeError("temporary failure")
            return {"outputs": {"out": f"{kwargs['input']}:attempt-{type(self).attempts}"}}

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "retry": RetryPolicyNode,
                "flaky": FlakyNode,
            }[node_type]

    workflow = {
        "nodes": [
            {
                "id": "retry",
                "type": "retry",
                "outputs": {"passthrough": {}, "retry_log": {}},
                "params": {"input": "reads", "max_retries": 1, "delay_seconds": 0.0},
            },
            {"id": "flaky", "type": "flaky", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "retry", "target_node": "flaky", "source_output": "passthrough", "target_input": "input"},
        ],
    }
    FlakyNode.attempts = 0
    events: list[tuple[str, dict[str, Any]]] = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("retry-run", workflow, emit=lambda event, payload: events.append((event, payload)))

    assert result["status"] == "completed"
    assert result["outputs"]["flaky"]["out"] == "reads:attempt-2"
    assert result["node_results"]["flaky"]["attempts"] == 2
    assert FlakyNode.attempts == 2
    assert ("node_retry", {"run_id": "retry-run", "node_id": "flaky", "attempt": 2, "max_attempts": 2}) in events


@pytest.mark.asyncio
async def test_workflow_executor_retry_policy_applies_to_branch_descendants(tmp_path: Path) -> None:
    class RetryPolicyNode:
        RETURN_NAMES = ("passthrough", "retry_log")
        EXECUTOR_CACHE_POLICY = "always_run"

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {
                "required": {"input": ("ANY", {})},
                "optional": {"max_retries": ("INT", {"default": 1}), "delay_seconds": ("FLOAT", {"default": 0.0})},
            }

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            context.run_metadata.setdefault("retry_policies", []).append({
                "node_id": context.node_id,
                "max_retries": int(kwargs.get("max_retries", 1)),
                "delay_seconds": float(kwargs.get("delay_seconds", 0.0)),
                "backoff_multiplier": 1.0,
                "max_delay": 1.0,
                "retry_on": "all",
                "target_nodes": [],
                "delays_seconds": [0.0],
            })
            return {"outputs": {"passthrough": kwargs["input"], "retry_log": "registered"}}

    class PrepNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"input": ("ANY", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            return {"outputs": {"out": f"{kwargs['input']}:prepared"}}

    class FlakyNode:
        RETURN_NAMES = ("out",)
        attempts = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"input": ("ANY", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise RuntimeError("descendant transient failure")
            return {"outputs": {"out": f"{kwargs['input']}:attempt-{type(self).attempts}"}}

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "retry": RetryPolicyNode,
                "prep": PrepNode,
                "flaky": FlakyNode,
            }[node_type]

    workflow = {
        "nodes": [
            {
                "id": "retry",
                "type": "retry",
                "outputs": {"passthrough": {}, "retry_log": {}},
                "params": {"input": "reads", "max_retries": 1, "delay_seconds": 0.0},
            },
            {"id": "prep", "type": "prep", "outputs": {"out": {}}},
            {"id": "flaky", "type": "flaky", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "retry", "target_node": "prep", "source_output": "passthrough", "target_input": "input"},
            {"source_node": "prep", "target_node": "flaky", "source_output": "out", "target_input": "input"},
        ],
    }
    FlakyNode.attempts = 0
    events: list[tuple[str, dict[str, Any]]] = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute(
        "retry-descendant-run",
        workflow,
        emit=lambda event, payload: events.append((event, payload)),
    )

    assert result["status"] == "completed"
    assert result["outputs"]["flaky"]["out"] == "reads:prepared:attempt-2"
    assert result["node_results"]["flaky"]["attempts"] == 2
    assert FlakyNode.attempts == 2
    assert (
        "node_retry",
        {"run_id": "retry-descendant-run", "node_id": "flaky", "attempt": 2, "max_attempts": 2},
    ) in events


@pytest.mark.asyncio
async def test_workflow_executor_retry_policy_respects_specific_target_nodes(tmp_path: Path) -> None:
    class RetryPolicyNode:
        RETURN_NAMES = ("passthrough", "retry_log")
        EXECUTOR_CACHE_POLICY = "always_run"

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {
                "required": {"input": ("ANY", {})},
                "optional": {
                    "max_retries": ("INT", {"default": 2}),
                    "delay_seconds": ("FLOAT", {"default": 0.0}),
                    "only_retry_specific_nodes": ("STRING", {"default": "flaky_allowed"}),
                },
            }

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            context.run_metadata.setdefault("retry_policies", []).append({
                "node_id": context.node_id,
                "max_retries": int(kwargs.get("max_retries", 2)),
                "delay_seconds": float(kwargs.get("delay_seconds", 0.0)),
                "backoff_multiplier": 1.0,
                "max_delay": 1.0,
                "retry_on": "all",
                "target_nodes": [
                    value.strip()
                    for value in str(kwargs.get("only_retry_specific_nodes", "")).split(",")
                    if value.strip()
                ],
                "delays_seconds": [0.0, 0.0],
            })
            return {"outputs": {"passthrough": kwargs["input"], "retry_log": "registered"}}

    class FlakyNode:
        RETURN_NAMES = ("out",)
        attempts_by_node: dict[str, int] = {}

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"input": ("ANY", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            attempts = type(self).attempts_by_node.get(context.node_id, 0) + 1
            type(self).attempts_by_node[context.node_id] = attempts
            raise RuntimeError(f"{context.node_id} fails on attempt {attempts}")

    class Registry:
        def get(self, node_type: str) -> type:
            return {
                "retry": RetryPolicyNode,
                "flaky": FlakyNode,
            }[node_type]

    workflow = {
        "nodes": [
            {
                "id": "retry",
                "type": "retry",
                "outputs": {"passthrough": {}, "retry_log": {}},
                "params": {
                    "input": "reads",
                    "max_retries": 2,
                    "delay_seconds": 0.0,
                    "only_retry_specific_nodes": "flaky_allowed",
                },
            },
            {"id": "flaky_blocked", "type": "flaky", "outputs": {"out": {}}},
        ],
        "edges": [
            {
                "source_node": "retry",
                "target_node": "flaky_blocked",
                "source_output": "passthrough",
                "target_input": "input",
            },
        ],
    }
    FlakyNode.attempts_by_node = {}
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("retry-target-run", workflow)

    assert result["status"] == "failed"
    assert FlakyNode.attempts_by_node == {"flaky_blocked": 1}
    assert result["node_results"]["flaky_blocked"]["attempts"] == 1


@pytest.mark.asyncio
async def test_workflow_executor_consumes_registered_retry_node_policy(tmp_path: Path) -> None:
    class FlakyNode:
        NODE_ID = "flaky_registered"
        RETURN_NAMES = ("out",)
        attempts = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"input": ("ANY", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise RuntimeError("transient CLI failure")
            return {"outputs": {"out": f"{kwargs['input']}:ok"}}

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    registry.register(FlakyNode)
    workflow = {
        "nodes": [
            {
                "id": "retry",
                "type": "retry",
                "outputs": {"passthrough": {}, "retry_log": {}},
                "params": {
                    "input": "sample.bam",
                    "max_retries": 1,
                    "delay_seconds": 0.0,
                    "backoff_multiplier": 1.0,
                    "max_delay": 1,
                    "retry_on": "all",
                },
            },
            {"id": "flaky", "type": "flaky_registered", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "retry", "target_node": "flaky", "source_output": "passthrough", "target_input": "input"},
        ],
    }
    FlakyNode.attempts = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)

    result = await executor.execute("registered-retry-run", workflow)

    assert result["status"] == "completed"
    assert result["outputs"]["flaky"]["out"] == "sample.bam:ok"
    assert result["metadata"]["retry_policies"][0]["executor_retry_supported"] is True
    assert result["node_results"]["flaky"]["attempts"] == 2


@pytest.mark.asyncio
async def test_workflow_executor_binds_workflow_parameters_into_node_inputs(tmp_path: Path) -> None:
    class CaptureNode:
        RETURN_NAMES = ("out", "threads")

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {
                "required": {
                    "sample": ("STRING", {}),
                    "threads": ("INT", {}),
                },
            }

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            return {"outputs": {"out": kwargs["sample"], "threads": kwargs["threads"]}}

    class Registry:
        def get(self, _node_type: str) -> type[CaptureNode]:
            return CaptureNode

    workflow = {
        "parameters": [
            {"name": "sample_id", "type": "STRING", "required": True, "value": "S2"},
            {"name": "threads", "type": "INT", "default": 8},
        ],
        "nodes": [
            {
                "id": "capture",
                "type": "capture",
                "inputs": {
                    "sample": {"value": "sample-{{sample_id}}"},
                    "threads": {"value": "{{threads}}"},
                },
                "outputs": {"out": {}, "threads": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("parameterized-run", workflow)

    assert result["status"] == "completed"
    assert result["outputs"]["capture"] == {"out": "sample-S2", "threads": 8}
    assert result["metadata"]["workflow_parameters"] == {
        "sample_id": "S2",
        "threads": 8,
    }


@pytest.mark.asyncio
async def test_workflow_executor_runtime_parameter_overrides_take_precedence(tmp_path: Path) -> None:
    class CaptureNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"sample": ("STRING", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            return {"outputs": {"out": kwargs["sample"]}}

    class Registry:
        def get(self, _node_type: str) -> type[CaptureNode]:
            return CaptureNode

    workflow = {
        "parameters": [
            {"name": "sample_id", "type": "STRING", "default": "default-sample", "value": "stored-sample"},
        ],
        "nodes": [
            {
                "id": "capture",
                "type": "capture",
                "params": {"sample": "{{sample_id}}"},
                "outputs": {"out": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute(
        "parameter-override-run",
        workflow,
        options={"parameters": {"sample_id": "runtime-sample"}},
    )

    assert result["status"] == "completed"
    assert result["outputs"]["capture"]["out"] == "runtime-sample"
    assert result["metadata"]["workflow_parameters"]["sample_id"] == "runtime-sample"


@pytest.mark.asyncio
async def test_workflow_executor_leaves_unknown_template_tokens_literal(tmp_path: Path) -> None:
    class CaptureNode:
        RETURN_NAMES = ("sample", "template")

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {
                "required": {
                    "sample": ("STRING", {}),
                    "template": ("STRING", {}),
                },
            }

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            return {"outputs": {"sample": kwargs["sample"], "template": kwargs["template"]}}

    class Registry:
        def get(self, _node_type: str) -> type[CaptureNode]:
            return CaptureNode

    workflow = {
        "parameters": [
            {"name": "sample_id", "type": "STRING", "value": "S1"},
        ],
        "nodes": [
            {
                "id": "capture",
                "type": "capture",
                "params": {
                    "sample": "{{sample_id}}",
                    "template": "internal {{tool_specific_token}}",
                },
                "outputs": {"sample": {}, "template": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("unknown-template-token-run", workflow)

    assert result["status"] == "completed"
    assert result["outputs"]["capture"] == {
        "sample": "S1",
        "template": "internal {{tool_specific_token}}",
    }


@pytest.mark.asyncio
async def test_workflow_executor_fails_when_required_workflow_parameter_is_missing(tmp_path: Path) -> None:
    class CaptureNode:
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"sample": ("STRING", {})}}

        def run(self, context, **kwargs: Any) -> dict[str, Any]:
            return {"outputs": {"out": kwargs["sample"]}}

    class Registry:
        def get(self, _node_type: str) -> type[CaptureNode]:
            return CaptureNode

    workflow = {
        "parameters": [
            {"name": "sample_id", "type": "STRING", "required": True},
        ],
        "nodes": [
            {
                "id": "capture",
                "type": "capture",
                "params": {"sample": "{{sample_id}}"},
                "outputs": {"out": {}},
            }
        ],
        "edges": [],
    }
    events: list[tuple[str, dict[str, Any]]] = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("missing-parameter-run", workflow, emit=lambda event, payload: events.append((event, payload)))

    assert result["status"] == "failed"
    assert result["error"] == "Missing required workflow parameter: sample_id"
    assert events == [
        ("error", {"run_id": "missing-parameter-run", "message": "Missing required workflow parameter: sample_id"})
    ]


def test_execution_request_schemas_accept_frontend_gap_fields() -> None:
    run_request = RunCreateRequest(
        workflow={"nodes": [], "edges": []},
        force_nodes=["qc"],
        target_nodes=["report"],
        parameters={"sample_id": "S1"},
    )
    hpc_request = HPCSubmitRequest(
        workflow={"nodes": [], "edges": []},
        name="QC job",
        parameters={"sample_id": "S1"},
    )
    extract_request = WorkflowExtractRequest(
        workflow={"nodes": [{"id": "qc"}], "edges": []},
        node_ids=["qc"],
        name="QC only",
    )

    assert run_request.force_nodes == ["qc"]
    assert run_request.target_nodes == ["report"]
    assert run_request.parameters == {"sample_id": "S1"}
    assert hpc_request.parameters == {"sample_id": "S1"}
    assert extract_request.node_ids == ["qc"]


def test_workflow_subgraph_extraction_keeps_only_internal_references() -> None:
    workflow = {
        "id": "wf",
        "name": "Full",
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"source_node": "a", "target_node": "b"},
            {"source_node": "b", "target_node": "c"},
            {"source_node": "a", "target_node": "c"},
        ],
        "groups": [{"id": "g", "node_ids": ["a", "c"]}],
        "outputs": [
            {"name": "keep", "node_id": "b", "output_name": "out"},
            {"name": "drop", "node_id": "c", "output_name": "out"},
        ],
    }

    extracted = _extract_workflow_subgraph(workflow, ["a", "b"], "Sub")

    assert extracted["name"] == "Sub"
    assert [node["id"] for node in extracted["nodes"]] == ["a", "b"]
    assert extracted["edges"] == [{"source_node": "a", "target_node": "b"}]
    assert extracted["groups"] == [{"id": "g", "node_ids": ["a"]}]
    assert extracted["outputs"] == [{"name": "keep", "node_id": "b", "output_name": "out"}]


@pytest.mark.asyncio
async def test_sync_r_diagnostics_do_not_block_running_event_loop() -> None:
    result = _check_r_packages_env_aware(["DefinitelyMissingPackage"], {})
    assert result["DefinitelyMissingPackage"]["available"] is False


def test_dependency_installer_is_app_scoped() -> None:
    state_one = AppState(SimpleNamespace())
    state_two = AppState(SimpleNamespace())

    assert state_one.dependency_installer is state_one.dependency_installer
    assert state_one.dependency_installer is not state_two.dependency_installer


def test_arq_execution_backend_is_opt_in(monkeypatch) -> None:
    executor = SimpleNamespace(workspace_dir="workspace", cache=SimpleNamespace(cache_dir="cache"))

    monkeypatch.delenv("BIONODULO_EXECUTION_BACKEND", raising=False)
    assert maybe_wrap_with_arq(executor) is executor

    monkeypatch.setenv("BIONODULO_EXECUTION_BACKEND", "arq")
    wrapped = maybe_wrap_with_arq(executor)

    assert isinstance(wrapped, ArqWorkflowExecutor)
    assert str(wrapped.workspace_dir) == "workspace"
    assert str(wrapped.cache_dir) == "cache"


@pytest.mark.asyncio
async def test_executor_runs_independent_nodes_concurrently(tmp_path: Path) -> None:
    """Independent DAG branches must overlap under the parallel scheduler.

    The old serial executor processed nodes one at a time, so the peak number
    of simultaneously-running nodes would always be 1. Three unconnected nodes
    should now run together.
    """
    state = {"active": 0, "peak": 0}

    class SleepNode:
        RETURN_NAMES = ("done",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {}, "optional": {}, "hidden": {}}

        async def run(self, context: Any = None, **_: Any) -> dict[str, Any]:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            await asyncio.sleep(0.15)
            state["active"] -= 1
            return {"outputs": {"done": "ok"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"sleep_node": SleepNode}.get(node_type)

    workflow = {
        "nodes": [
            {"id": "a", "type": "sleep_node"},
            {"id": "b", "type": "sleep_node"},
            {"id": "c", "type": "sleep_node"},
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("concurrent-run", workflow, force=True)

    assert result["status"] == "completed"
    assert state["peak"] >= 2


@pytest.mark.asyncio
async def test_executor_serializes_chained_nodes(tmp_path: Path) -> None:
    """A linear chain A->B->C must never overlap regardless of max_workers."""
    state = {"active": 0, "peak": 0}

    class ChainNode:
        RETURN_NAMES = ("value",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {}, "optional": {"value": ("STRING", {})}, "hidden": {}}

        async def run(self, context: Any = None, **_: Any) -> dict[str, Any]:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            await asyncio.sleep(0.05)
            state["active"] -= 1
            return {"outputs": {"value": "ok"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"chain_node": ChainNode}.get(node_type)

    workflow = {
        "nodes": [
            {"id": "a", "type": "chain_node"},
            {"id": "b", "type": "chain_node"},
            {"id": "c", "type": "chain_node"},
        ],
        "edges": [
            {"source": "a", "sourceHandle": "value", "target": "b", "targetHandle": "value"},
            {"source": "b", "sourceHandle": "value", "target": "c", "targetHandle": "value"},
        ],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("chain-run", workflow, force=True)

    assert result["status"] == "completed"
    assert state["peak"] == 1


@pytest.mark.asyncio
async def test_executor_cache_is_content_addressed(tmp_path: Path) -> None:
    """Editing an input file in place must invalidate the cache.

    Previously the key used only the input *path*, so a changed-but-same-path
    file produced a false cache hit and a stale (scientifically wrong) result.
    """
    data_file = tmp_path / "input.txt"
    data_file.write_text("v1")

    class ReaderNode:
        RETURN_NAMES = ("content",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"path": ("FILE", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, path: Any = None, **_: Any) -> dict[str, Any]:
            return {"outputs": {"content": "ok"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"reader": ReaderNode}.get(node_type)

    workflow = {
        "nodes": [
            {
                "id": "r",
                "type": "reader",
                "inputs": {"path": {"value": str(data_file)}},
                "outputs": {"content": {}},
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    first = await executor.execute("run1", workflow)
    assert first["node_results"]["r"]["status"] == "completed"

    # Unchanged file -> cache hit.
    second = await executor.execute("run2", workflow)
    assert second["node_results"]["r"]["status"] == "cached"

    # Changed contents at the same path -> cache miss, node re-runs.
    data_file.write_text("v2-different-contents")
    third = await executor.execute("run3", workflow)
    assert third["node_results"]["r"]["status"] == "completed"


@pytest.mark.asyncio
async def test_executor_cache_is_path_independent_across_runs(tmp_path: Path) -> None:
    """A rerun in a fresh run directory must reuse cache when contents match.

    Input-style nodes re-run every time and emit paths under the *new* run
    directory. Previously those fresh paths were baked into downstream cache
    keys, so an unchanged pipeline recomputed end to end. Keys now use content
    fingerprints instead of absolute paths.
    """
    import shutil

    source = tmp_path / "source.txt"
    source.write_text("stable-contents")

    class ProducerNode:
        RETURN_NAMES = ("out",)
        EXECUTOR_CACHE_POLICY = "always_run"

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"src": ("STRING", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, src: str = "", **_: Any) -> dict[str, Any]:
            out = Path(context.node_dir) / "out.txt"
            shutil.copyfile(src, out)
            return {"outputs": {"out": str(out)}}

    class ConsumerNode:
        RETURN_NAMES = ("done",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {"inp": ("FILE", {})}, "optional": {}, "hidden": {}}

        async def run(self, context: Any, inp: Any = None, **_: Any) -> dict[str, Any]:
            return {"outputs": {"done": "ran"}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"producer": ProducerNode, "consumer": ConsumerNode}.get(node_type)

    workflow = {
        "nodes": [
            {"id": "p", "type": "producer", "inputs": {"src": {"value": str(source)}}, "outputs": {"out": {}}},
            {"id": "c", "type": "consumer", "inputs": {}, "outputs": {"done": {}}},
        ],
        "edges": [
            {"id": "e1", "from": {"node": "p", "output": "out"}, "to": {"node": "c", "input": "inp"}}
        ],
    }

    class ExecSettings:
        class execution:  # noqa: N801 - mirrors settings schema
            content_hashing = "strong"

    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry(), settings=ExecSettings()
    )

    first = await executor.execute("run1", workflow)
    assert first["node_results"]["p"]["status"] == "completed"
    assert first["node_results"]["c"]["status"] == "completed"

    # Second run: producer re-runs (always_run) and emits a *new* run-dir path,
    # but the content is identical so the consumer must hit the cache.
    second = await executor.execute("run2", workflow)
    assert second["node_results"]["p"]["status"] == "completed"
    assert second["node_results"]["c"]["status"] == "cached"

    # Change the contents: the consumer must recompute.
    source.write_text("changed-contents")
    third = await executor.execute("run3", workflow)
    assert third["node_results"]["c"]["status"] == "completed"


def test_env_prefix_skips_unready_env(tmp_path: Path) -> None:
    """A manifest left behind by a failed install must NOT be used to run.

    Previously _env_prefix_for_node used the env as soon as a pixi.toml existed,
    so a half-installed (red) env wrapped every command in `pixi run` against an
    unsolvable env — which hangs the run. The env must be fully installed first.
    """
    from bionodulo.environments.manifest import get_env_dir, get_env_id, workflow_to_packages

    class ToolNode:
        REQUIRED_CONDA_PACKAGES = ["samtools"]

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {"required": {}, "optional": {}, "hidden": {}}

    class Registry:
        def get(self, node_type: str) -> type | None:
            return {"tool": ToolNode}.get(node_type)

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())
    workflow = {"nodes": [{"id": "n1", "type": "tool"}], "edges": []}
    node = {"id": "n1", "type": "tool", "_node_class": ToolNode}

    # No manifest at all -> system PATH.
    assert executor._env_prefix_for_node(node, workflow) == []

    # Manifest present but env never installed -> still system PATH (no pixi run).
    packages = workflow_to_packages(workflow, Registry())
    env_dir = get_env_dir(get_env_id(packages), tmp_path)
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    assert executor._env_prefix_for_node(node, workflow) == []


def test_named_env_prefix_uses_the_ready_workflow_manifest_and_locked_manta_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bionodulo.environments.manifest import (
        get_env_dir,
        get_environment_plan_id,
        workflow_to_environment_plan,
    )
    from bionodulo.manager import runtime_installer

    class DefaultNode:
        REQUIRED_CONDA_PACKAGES = ["samtools"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT: dict[str, str] = {}

    class MantaNode:
        REQUIRED_CONDA_PACKAGES = ["manta"]
        REQUIRED_EXECUTABLES: list[str] = []
        REQUIRED_R_PACKAGES: list[str] = []
        ENVIRONMENT = {"type": "pixi", "name": "manta"}

    class Registry:
        @staticmethod
        def get(node_type: str) -> type | None:
            return {"default": DefaultNode, "manta": MantaNode}.get(node_type)

    registry = Registry()
    workflow = {
        "nodes": [
            {"id": "sort", "type": "default"},
            {"id": "sv", "type": "manta"},
        ],
        "edges": [],
    }
    plan = workflow_to_environment_plan(workflow, registry)
    env_dir = get_env_dir(get_environment_plan_id(plan), tmp_path)
    (env_dir / ".pixi/envs/default/bin").mkdir(parents=True)
    (env_dir / ".pixi/envs/manta/bin").mkdir(parents=True)
    manifest_path = env_dir / "pixi.toml"
    manifest_path.write_text("[workspace]\n", encoding="utf-8")
    monkeypatch.setattr(runtime_installer, "get_pixi_path", lambda: Path("/opt/pixi"))

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)
    node = {"id": "sv", "type": "manta", "_node_class": MantaNode}

    assert executor._env_prefix_for_node(node, workflow) == [
        "/opt/pixi",
        "run",
        "--locked",
        "--manifest-path",
        str(manifest_path),
        "-e",
        "manta",
        "--",
    ]
