"""The CLI must preserve the server's CORS policy and operator overrides."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("configured_origins", "cli_origins", "allowed_origin"),
    [
        (None, None, "http://localhost:8000"),
        ("https://configured.example", None, "https://configured.example"),
        ("https://configured.example", "https://override.example", "https://override.example"),
        (None, "*", "https://untrusted.example"),
    ],
)
def test_cli_cors_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    configured_origins: str | None,
    cli_origins: str | None,
    allowed_origin: str,
) -> None:
    import main

    # Record the original value even when the CLI adds the variable itself.
    monkeypatch.setenv("BIONODULO_CORS_ORIGINS", "")
    if configured_origins is None:
        monkeypatch.delenv("BIONODULO_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("BIONODULO_CORS_ORIGINS", configured_origins)
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_HOST", "127.0.0.1")
    monkeypatch.setenv("BIONODULO_PORT", "8000")
    monkeypatch.delenv("BIONODULO_CORS_ALLOW_LOOPBACK", raising=False)
    monkeypatch.setattr(main, "uvloop", None)
    arguments = ["main.py", "--project-root", str(tmp_path)]
    if cli_origins is not None:
        arguments.extend(["--cors-origins", cli_origins])
    monkeypatch.setattr(sys, "argv", arguments)

    def verify_server_policy(*args: object, **kwargs: object) -> None:
        from server import create_app

        with TestClient(create_app()) as client:
            allowed = client.options(
                "/api/config",
                headers={"Origin": allowed_origin, "Access-Control-Request-Method": "POST"},
            )
            assert allowed.status_code == 200
            if cli_origins == "*":
                assert allowed.headers["access-control-allow-origin"] == "*"
            else:
                blocked = client.options(
                    "/api/runs",
                    headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
                )
                assert blocked.status_code == 400
                assert "access-control-allow-origin" not in blocked.headers

    monkeypatch.setattr(main.uvicorn, "run", verify_server_policy)
    main.main()


def test_cli_refuses_unsupported_multi_user_isolation(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import main

    monkeypatch.setattr(sys, "argv", ["main.py", "--multi-user"])

    def fail_if_started(*args, **kwargs):
        raise AssertionError("Server must not start without the promised isolation")

    monkeypatch.setattr(main.uvicorn, "run", fail_if_started)
    monkeypatch.setattr(main, "ensure_workspace_root", fail_if_started)
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2
    assert "separate backend and workspace per user" in capsys.readouterr().err
