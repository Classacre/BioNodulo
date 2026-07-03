from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bionodulo.collab import doc_store
from bionodulo.hpc.base import HPCJob
from bionodulo.hpc.slurm import SLURMBackend


def test_event_websocket_requires_token_in_collab_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import bionodulo.collab.auth as auth
    from server import create_app

    # Isolate the workspace root: enabling collab below writes to the settings
    # file, and without this it pollutes the shared ~/.bionodulo workspace and
    # breaks the local-mode test that expects collab off by default.
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_JWT_SECRET", "test-secret-for-event-websocket-32-bytes-min")
    monkeypatch.setattr(auth, "_JWT_SECRET_CACHE", None)
    monkeypatch.setattr(auth, "JWT_SECRET", "")
    with TestClient(create_app()) as client:
        # Enable collaboration so the event socket enforces auth.
        client.post("/api/settings", json={"settings": {"bionodulo.collab.enabled": True}})

        with client.websocket_connect("/ws") as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()

        token = client.post("/api/auth/token", json={"name": "Socket User"}).json()["token"]
        with client.websocket_connect(f"/ws?token={token}") as ws:
            assert ws.receive_json()["type"] == "connected"

    assert exc_info.value.code == 4401


def test_event_websocket_allows_anonymous_in_local_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """In local (single-user) mode the event stream is reachable without a JWT —
    run logs / install progress must work for the default, collab-disabled app."""
    from server import create_app

    # Isolate the workspace so this test sees collab disabled by default rather
    # than whatever a previous collab test may have written globally.
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "connected"


def test_queue_mutations_require_auth_in_collab_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Queue/history mutations must reject anonymous callers once collab is on."""
    import bionodulo.collab.auth as auth
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_JWT_SECRET", "test-secret-for-queue-auth-32-bytes-minimum")
    monkeypatch.setattr(auth, "_JWT_SECRET_CACHE", None)
    monkeypatch.setattr(auth, "JWT_SECRET", "")

    with TestClient(create_app()) as client:
        client.post("/api/settings", json={"settings": {"bionodulo.collab.enabled": True}})

        # Anonymous mutations are rejected.
        assert client.post("/api/queue/clear").status_code == 401
        assert client.post("/api/history/clear").status_code == 401
        assert client.post("/api/queue/run-x/cancel").status_code == 401
        assert client.post("/api/runs/run-x/retry").status_code == 401

        # With a valid token the gate is satisfied (cancel of an unknown run is
        # then a normal 404, not an auth failure).
        token = client.post("/api/auth/token", json={"name": "Op"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/api/queue/clear", headers=headers).status_code == 200
        assert client.post("/api/queue/run-x/cancel", headers=headers).status_code == 404


def test_queue_mutations_open_in_local_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Local (collab-disabled) mode keeps queue endpoints unauthenticated by design."""
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    with TestClient(create_app()) as client:
        assert client.post("/api/queue/clear").status_code == 200
        assert client.post("/api/history/clear").status_code == 200


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
async def test_sge_and_pbs_backends_use_exec_not_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SGE/PBS must submit via exec (argument list), never a shell string —
    otherwise a malicious dependency/extra_args element is command injection."""
    from bionodulo.hpc.pbs import PBSBackend
    from bionodulo.hpc.sge import SGEBackend

    script = tmp_path / "job.sh"
    script.write_text("#!/bin/sh\necho hello\n", encoding="utf-8")

    class Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"Your job 42 (\"job\") has been submitted\n", b""

    calls: list[tuple[str, ...]] = []

    async def fake_exec(*args, **kwargs):
        del kwargs
        calls.append(tuple(str(arg) for arg in args))
        return Proc()

    async def fake_shell(*args, **kwargs):
        del args, kwargs
        raise AssertionError("HPC backends must not use create_subprocess_shell")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", fake_shell)

    sge_job = await SGEBackend().submit_job(script)
    assert sge_job.job_id == "42"
    pbs_job = await PBSBackend().submit_job(script)
    assert pbs_job.job_id == "42"


@pytest.mark.asyncio
async def test_sge_and_pbs_reject_shell_syntax_in_job_ids_and_args() -> None:
    from bionodulo.hpc.pbs import PBSBackend
    from bionodulo.hpc.sge import SGEBackend

    for backend in (SGEBackend(), PBSBackend()):
        with pytest.raises(ValueError):
            await backend.cancel_job(HPCJob(job_id="123; rm -rf /"))
        with pytest.raises(ValueError):
            await backend.check_status(HPCJob(job_id="$(whoami)"))

    # Malicious submit-time args (dependency / extra_args) are rejected too.
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write("#!/bin/sh\n")
        script = fh.name
    for backend in (SGEBackend(), PBSBackend()):
        with pytest.raises(ValueError):
            await backend.submit_job(script, dependency="1; rm -rf /")
        with pytest.raises(ValueError):
            await backend.submit_job(script, extra_args=["--evil=$(id)"])


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
async def test_safe_request_event_hook_blocks_redirect_to_metadata() -> None:
    """The httpx event hook must re-validate redirect hops: an allowed first
    host that 30x-bounces to a blocked internal/metadata address is rejected."""
    import httpx

    from bionodulo.core.netguard import safe_request_event_hook

    hook = safe_request_event_hook()
    # First-hop public host: allowed.
    await hook(httpx.Request("GET", "http://8.8.8.8/start"))
    # Redirect target to cloud metadata: blocked (httpx fires the hook per hop).
    with pytest.raises(ValueError):
        await hook(httpx.Request("GET", "http://169.254.169.254/latest/meta-data/"))


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


def test_editor_mode_fails_closed_without_proxy_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A shared editor backend must refuse to boot ungated: editor mode with no
    proxy secret (and no explicit insecure opt-out) raises rather than serving
    the multi-tenant editing API without its request gate."""
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.delenv("BIONODULO_PROXY_SECRET", raising=False)
    monkeypatch.delenv("BIONODULO_ALLOW_INSECURE_EDITOR", raising=False)

    with pytest.raises(RuntimeError, match="refuses to run ungated"):
        create_app()


def test_editor_mode_boots_with_proxy_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Editor mode WITH a proxy secret boots and gates unexempt paths (401 for
    requests missing the shared secret; /api/config stays open)."""
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.setenv("BIONODULO_PROXY_SECRET", "test-proxy-secret-value")

    with TestClient(create_app()) as client:
        # No secret header -> 401 on a gated path.
        assert client.get("/api/object_info").status_code == 401
        # Exempt config path stays open.
        assert client.get("/api/config").status_code == 200
        # Correct secret is accepted.
        ok = client.get(
            "/api/object_info",
            headers={"X-Bionodulo-Session": "test-proxy-secret-value"},
        )
        assert ok.status_code == 200


def test_editor_mode_insecure_optout_boots_ungated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The explicit local-dev opt-out lets editor mode run without a secret."""
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.delenv("BIONODULO_PROXY_SECRET", raising=False)
    monkeypatch.setenv("BIONODULO_ALLOW_INSECURE_EDITOR", "1")

    # Should not raise; app boots (ungated) for local development.
    with TestClient(create_app()) as client:
        assert client.get("/api/config").status_code == 200
