from fastapi.testclient import TestClient
from server import create_app


def test_loopback_and_cloud_allowed(monkeypatch):
    monkeypatch.setenv("BIONODULO_CORS_ORIGINS", "https://cloud.bionodulo.com")
    monkeypatch.setenv("BIONODULO_CORS_ALLOW_LOOPBACK", "1")
    app = create_app()
    client = TestClient(app)
    r = client.options("/api/config", headers={
        "Origin": "http://127.0.0.1:53211",
        "Access-Control-Request-Method": "GET",
    })
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:53211"
