"""Regression checks for destructive workspace file operations."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from fastapi import HTTPException

from bionodulo.api import routes
from bionodulo.api.routes import delete_files, file_operation
from bionodulo.api.schemas import DeleteFilesRequest, FileOperationRequest, WorkspaceRootRequest
from bionodulo.execution.subprocess_runner import run_subprocess


def _request(root: Path) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(project_root=root),
    )))


@pytest.mark.asyncio
async def test_delete_rejects_workspace_root_but_allows_child(tmp_path: Path) -> None:
    child = tmp_path / "discard.txt"
    child.write_text("data", encoding="utf-8")

    result = await delete_files(_request(tmp_path), DeleteFilesRequest(paths=[".", "discard.txt"]))

    assert tmp_path.exists()
    assert not child.exists()
    assert result["deleted"] == ["discard.txt"]
    assert result["failed"] == [{"path": ".", "reason": "cannot delete the workspace root"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["copy", "move"])
async def test_directory_cannot_be_placed_inside_itself(
    tmp_path: Path, operation: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_text("data", encoding="utf-8")

    with pytest.raises(HTTPException) as error:
        await file_operation(_request(tmp_path), FileOperationRequest(
            operation=operation, source="source", target="source/nested",
        ))

    assert error.value.status_code == 400
    assert not (source / "nested").exists()


@pytest.mark.asyncio
async def test_file_operation_rejects_workspace_root(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("data", encoding="utf-8")

    with pytest.raises(HTTPException) as error:
        await file_operation(_request(tmp_path), FileOperationRequest(
            operation="move", source=".", target="nested",
        ))

    assert error.value.status_code == 400
    assert (tmp_path / "data.txt").exists()


@pytest.mark.asyncio
async def test_workspace_switch_requires_restart_without_mutating_services(
    tmp_path: Path, monkeypatch,
) -> None:
    old_root = tmp_path / "old"
    old_root.mkdir()
    new_root = tmp_path / "new"
    new_root.mkdir()
    settings = SimpleNamespace(project_root=old_root, runs_dir=old_root / "runs")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))
    monkeypatch.setenv("BIONODULO_ROOT_BASE", str(tmp_path))

    with pytest.raises(HTTPException) as error:
        await routes.set_workspace_root(request, WorkspaceRootRequest(path=str(new_root)))

    assert error.value.status_code == 409
    assert "BIONODULO_ROOT" in error.value.detail
    assert settings.project_root == old_root
    assert settings.runs_dir == old_root / "runs"
    assert await routes.set_workspace_root(
        request, WorkspaceRootRequest(path=str(old_root)),
    ) == {"root": str(old_root), "status": "unchanged"}


def test_failed_cloud_download_preserves_existing_file(tmp_path: Path, monkeypatch) -> None:
    import httpx

    destination = tmp_path / "download.txt"
    destination.write_bytes(b"existing")

    class Response:
        status_code = 200
        headers = {"content-length": "10"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def iter_bytes(self, _chunk_size):
            yield b"partial"
            raise OSError("connection lost")

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args):
            return Response()

    monkeypatch.setattr(httpx, "Client", Client)
    routes._CLOUD_TRANSFERS["test-failed-download"] = {
        "status": "active", "loaded": 0, "total": 0, "error": None,
    }
    try:
        routes._sync_s3_get("test-failed-download", "https://example.invalid", destination)
        assert routes._CLOUD_TRANSFERS["test-failed-download"]["status"] == "error"
        assert destination.read_bytes() == b"existing"
        assert list(tmp_path.glob("*.part")) == []
    finally:
        routes._CLOUD_TRANSFERS.pop("test-failed-download", None)


def test_desktop_token_url_accepts_configured_default_host() -> None:
    routes._validate_clerk_url("https://clerk.bionodulo.com/oauth/token")
    with pytest.raises(HTTPException) as error:
        routes._validate_clerk_url("https://clerk.bionodulo.com.evil.example/oauth/token")
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_cloud_download_rejects_linked_download_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (workspace / "cloud-downloads").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlinks are unavailable: {exc}")

    request = _request(workspace)

    async def body():
        return {"url": "https://s3.us-east-1.amazonaws.com/bucket/key", "name": "data.txt"}

    request.json = body
    with pytest.raises(HTTPException) as error:
        await routes.cloud_download(request)

    assert error.value.status_code == 400
    assert not (outside / "data.txt").exists()


@pytest.mark.asyncio
async def test_task_cancellation_terminates_subprocess(tmp_path: Path) -> None:
    psutil = pytest.importorskip("psutil")
    marker = tmp_path / "process.pid"
    script = (
        "import os,time;"
        f"open({str(marker)!r},'w').write(str(os.getpid()));"
        "time.sleep(30)"
    )
    task = asyncio.create_task(run_subprocess([sys.executable, "-c", script]))
    try:
        for _ in range(100):
            if marker.exists():
                break
            await asyncio.sleep(0.05)
        assert marker.exists()
        pid = int(marker.read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(40):
            if not psutil.pid_exists(pid):
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail(f"Subprocess {pid} survived task cancellation")
    finally:
        if not task.done():
            task.cancel()


@pytest.mark.asyncio
async def test_task_cancellation_terminates_child_process_tree(tmp_path: Path) -> None:
    psutil = pytest.importorskip("psutil")
    marker = tmp_path / "child.pid"
    script = (
        "import subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
        f"open({str(marker)!r},'w').write(str(p.pid));"
        "time.sleep(30)"
    )
    task = asyncio.create_task(run_subprocess([sys.executable, "-c", script]))
    try:
        for _ in range(100):
            if marker.exists():
                break
            await asyncio.sleep(0.05)
        assert marker.exists()
        child_pid = int(marker.read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(40):
            if not psutil.pid_exists(child_pid):
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail(f"Child process {child_pid} survived task cancellation")
    finally:
        if not task.done():
            task.cancel()
