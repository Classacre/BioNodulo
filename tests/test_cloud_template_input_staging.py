from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


_PROXY_SECRET = "test-proxy-secret-value"
_HEADERS = {"X-Bionodulo-Session": _PROXY_SECRET}
_R2_HOST = "c8c417e5b639695becad5bbf2c1c2dfd.r2.cloudflarestorage.com"


def _editor_env(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("BIONODULO_ROOT", str(root))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.setenv("BIONODULO_PROXY_SECRET", _PROXY_SECRET)


def test_editor_serves_only_packaged_template_data_for_cloud_staging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from server import create_app

    _editor_env(monkeypatch, tmp_path)
    # Deliberately a packaged local file. This route exists to serve bundled
    # data and to reject traversal; template *inputs* moved to public URLs, but
    # that is a separate concern from what this endpoint may serve.
    path = "templates/data/smoke/paired_R1.fastq"
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/workspace/download", params={"path": path}, headers=_HEADERS
        )
        head = client.head(
            "/api/workspace/download", params={"path": path}, headers=_HEADERS
        )
        traversal = client.get(
            "/api/workspace/download",
            params={"path": "templates/data/../../pyproject.toml"},
            headers=_HEADERS,
        )

    assert response.status_code == 200
    assert response.content.startswith(b"@")
    assert head.status_code == 200
    assert int(head.headers["content-length"]) == len(response.content)
    assert int(head.headers["x-bionodulo-file-size"]) == len(response.content)
    assert traversal.status_code == 400


def test_cloud_relay_accepts_production_r2_without_widening_ssrf_allowlist() -> None:
    from bionodulo.api.routes import _validate_s3_url

    _validate_s3_url(f"https://{_R2_HOST}/uploads/example")
    with pytest.raises(HTTPException):
        _validate_s3_url(f"https://{_R2_HOST}.example.com/uploads/example")


def test_cloud_upload_blocked_in_editor_mode_and_relays_in_full_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import bionodulo.api.routes as routes
    from server import create_app

    source = tmp_path / "tiny.fastq"
    source.write_bytes(b"@read\nACGT\n+\n!!!!\n")
    completed: list[Path] = []

    def fake_put(
        tid: str,
        local_path: Path,
        _url: str,
        _content_type: str,
        *,
        remove_after: bool = False,
    ) -> None:
        completed.append(local_path)
        transfer = routes._CLOUD_TRANSFERS[tid]
        transfer["loaded"] = local_path.stat().st_size
        transfer["status"] = "done"
        if remove_after:
            local_path.unlink(missing_ok=True)

    monkeypatch.setattr(routes, "_sync_s3_put", fake_put)
    routes._CLOUD_TRANSFERS.clear()

    # Editor mode (audit C2): the workspace->S3 relay is hard-blocked; the
    # hosted editor stages inputs browser-direct via presigned PUTs instead.
    _editor_env(monkeypatch, tmp_path)
    with TestClient(create_app()) as client:
        editor_response = client.post(
            "/api/workspace/cloud-upload",
            headers=_HEADERS,
            json={
                "path": "tiny.fastq",
                "url": f"https://{_R2_HOST}/uploads/tiny.fastq",
                "content_type": "application/octet-stream",
                "expected_size": source.stat().st_size,
            },
        )

    assert editor_response.status_code == 403

    # Full mode (desktop / Colab / self-host) keeps the relay, transferring
    # in a tracked background task.
    monkeypatch.delenv("BIONODULO_EDITOR_MODE")
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/workspace/cloud-upload",
            headers=_HEADERS,
            json={
                "path": "tiny.fastq",
                "url": f"https://{_R2_HOST}/uploads/tiny.fastq",
                "content_type": "application/octet-stream",
                "expected_size": source.stat().st_size,
            },
        )

    assert response.status_code == 200
    transfer_id = response.json()["transfer_id"]
    deadline = time.monotonic() + 5.0
    while not completed and time.monotonic() < deadline:
        if routes._CLOUD_TRANSFERS[transfer_id]["status"] == "error":
            break
        time.sleep(0.01)
    assert completed == [source]
