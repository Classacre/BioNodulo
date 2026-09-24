"""The packaged app serves its registry JSON instead of the SPA fallback."""
import json

from fastapi.testclient import TestClient


def test_registry_snapshot_is_json_and_missing_registry_assets_are_404(tmp_path, monkeypatch):
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path / "workspace"))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.setenv("BIONODULO_PROXY_SECRET", "static-asset-test-secret")
    monkeypatch.setenv("BIONODULO_SESSION_TOKEN", "")
    import server
    monkeypatch.setattr(server, "__file__", str(tmp_path / "server.py"))
    dist = tmp_path / "web" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "biotools-registry").mkdir()
    (dist / "index.html").write_text("<html>app shell</html>")
    snapshot = {"records": 1, "tools": [{"id": "registry_identity"}]}
    (dist / "biotools-registry" / "index.json").write_text(json.dumps(snapshot))
    with TestClient(server.create_app(), headers={"X-Bionodulo-Session": "static-asset-test-secret"}) as client:
        response = client.get("/biotools-registry/index.json")
        assert response.status_code == 200 and response.json() == snapshot
        assert response.headers["content-type"].startswith("application/json")
        assert client.get("/biotools-registry/missing.json").status_code == 404
        assert client.get("/").text == "<html>app shell</html>"
        assert client.post("/biotools-registry/index.json").status_code == 403
