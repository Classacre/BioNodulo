from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bionodulo.collab import doc_store
from bionodulo.hpc.base import HPCJob
from bionodulo.hpc.slurm import SLURMBackend


def test_event_websocket_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    import bionodulo.collab.auth as auth
    from server import create_app

    monkeypatch.setenv("BIONODULO_JWT_SECRET", "test-secret-for-event-websocket-32-bytes-min")
    monkeypatch.setattr(auth, "_JWT_SECRET_CACHE", None)
    monkeypatch.setattr(auth, "JWT_SECRET", "")
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()

        token = client.post("/api/auth/token", json={"name": "Socket User"}).json()["token"]
        with client.websocket_connect(f"/ws?token={token}") as ws:
            assert ws.receive_json()["type"] == "connected"

    assert exc_info.value.code == 4401


@pytest.mark.asyncio
async def test_slurm_backend_uses_exec_not_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = tmp_path / "job.sh"
    script.write_text("#!/bin/sh\necho hello\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    class Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"Submitted batch job 42\n", b""

    async def fake_exec(*args, **kwargs):
        del kwargs
        calls.append(tuple(str(arg) for arg in args))
        return Proc()

    async def fake_shell(*args, **kwargs):
        del args, kwargs
        raise AssertionError("create_subprocess_shell must not be used for SLURM commands")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", fake_shell)

    job = await SLURMBackend({"partition": "debug"}).submit_job(script)

    assert job.job_id == "42"
    assert calls[0] == ("sbatch", "--partition", "debug", str(script))


@pytest.mark.asyncio
async def test_slurm_rejects_shell_syntax_in_job_ids() -> None:
    backend = SLURMBackend()

    with pytest.raises(ValueError):
        await backend.cancel_job(HPCJob(job_id="123; rm -rf /"))


@pytest.mark.asyncio
async def test_doc_store_sync_bridge_rejects_running_event_loop() -> None:
    async def noop() -> None:
        return None

    with pytest.raises(RuntimeError, match="use the async doc_store API"):
        doc_store._run_ystore_sync(noop)


def test_assistant_graph_is_compiled_once() -> None:
    from bionodulo.ai.assistant import _compiled_assistant_graph

    assert _compiled_assistant_graph() is _compiled_assistant_graph()


def test_netguard_blocks_internal_addresses_and_allows_public():
    from bionodulo.core.netguard import assert_safe_url

    for blocked in (
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/secret",
        "http://[::1]/",
        "ftp://127.0.0.1/",
    ):
        with pytest.raises(ValueError):
            assert_safe_url(blocked)

    # A public IP literal is allowed (no DNS needed for the test).
    assert_safe_url("http://8.8.8.8/")
    # Private egress is permitted only when explicitly opted in.
    assert_safe_url("http://10.0.0.5/", allow_private=True)


@pytest.mark.asyncio
async def test_download_dataset_tool_blocks_ssrf(tmp_path):
    from types import SimpleNamespace

    from bionodulo.ai.tools import ToolContext, aexecute_tool

    ctx = ToolContext(workflow={}, settings=SimpleNamespace(project_root=tmp_path))
    result = await aexecute_tool(
        "download_dataset", {"source": "http://169.254.169.254/latest/meta-data/"}, ctx
    )
    assert result["status"] == "error"


def test_set_workspace_root_rejects_paths_outside_base(tmp_path, monkeypatch):
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT_BASE", str(tmp_path))
    allowed = tmp_path / "ws"
    allowed.mkdir()
    with TestClient(create_app()) as client:
        ok = client.post("/api/workspace/root", json={"path": str(allowed)})
        assert ok.status_code == 200
        bad = client.post("/api/workspace/root", json={"path": "/"})
        assert bad.status_code == 403
