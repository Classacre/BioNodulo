# tests/api/test_collab_tunnel.py
import os
from bionodulo.api.collab_runtime_routes import _resolve_cloudflared

def test_prefers_env_binary(tmp_path, monkeypatch):
    fake = tmp_path / "cloudflared"
    fake.write_text("#!/bin/sh\n")
    os.chmod(fake, 0o755)
    monkeypatch.setenv("BIONODULO_CLOUDFLARED", str(fake))
    assert _resolve_cloudflared() == str(fake)

def test_falls_back_to_path(monkeypatch):
    monkeypatch.delenv("BIONODULO_CLOUDFLARED", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/cloudflared" if name == "cloudflared" else None)
    assert _resolve_cloudflared() == "/usr/bin/cloudflared"
