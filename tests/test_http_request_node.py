from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_http_request_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["http_request"]["display_name"] == "HTTP Request"
    assert info["http_request"]["category"] == "api"
    assert info["http_request"]["output_name"] == ["response_body", "metadata"]
    assert "cache_ttl" in info["http_request"]["input"]["optional"]
    assert "rate_limit_per_second" in info["http_request"]["input"]["optional"]


@pytest.mark.asyncio
async def test_http_request_posts_json_and_writes_response_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("http_request")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        status_code = 201
        headers = {"content-type": "application/json", "x-request-id": "req-1"}
        text = '{"ok": true, "id": "TP53"}'
        url = "https://api.example.test/genes?species=human"

    async def fake_request(**kwargs: Any) -> FakeResponse:
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr(module, "_request", fake_request)
    context = SimpleNamespace(
        node_dir=tmp_path,
        resolve_secret=lambda key: "secret-token" if key == "http_bearer_token" else None,
    )

    result = await node_class().run(
        url="https://api.example.test/genes",
        method="POST",
        query_params='{"species": "human"}',
        headers='{"X-Trace": "abc"}',
        body_format="json",
        body='{"gene": "TP53"}',
        auth_mode="bearer",
        bearer_token="",
        output_name="gene-response",
        context=context,
    )

    body_path = Path(result["outputs"]["response_body"])
    metadata = result["outputs"]["metadata"]

    assert body_path.name == "gene-response.json"
    assert body_path.read_text(encoding="utf-8") == '{"ok": true, "id": "TP53"}'
    assert metadata == {
        "status_code": 201,
        "url": "https://api.example.test/genes?species=human",
        "content_type": "application/json",
        "headers": {"content-type": "application/json", "x-request-id": "req-1"},
        "response_body": str(body_path),
        "json": {"ok": True, "id": "TP53"},
    }
    assert calls == [
        {
            "method": "POST",
            "url": "https://api.example.test/genes",
            "params": {"species": "human"},
            "headers": {
                "User-Agent": "BioNodulo/2.0 (workflow node; generic HTTP)",
                "X-Trace": "abc",
                "Authorization": "Bearer secret-token",
            },
            "json_body": {"gene": "TP53"},
            "data": None,
            "timeout": 30.0,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_http_request_resolves_bearer_token_credential_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("http_request")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/plain"}
        text = "ok"
        url = "https://api.example.test/resource"

    async def fake_request(**kwargs: Any) -> FakeResponse:
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr(module, "_request", fake_request)
    context = SimpleNamespace(
        node_dir=tmp_path,
        resolve_secret=lambda key: "resolved-token" if key == "http_prod_token" else None,
    )

    result = await node_class().run(
        url="https://api.example.test/resource",
        method="GET",
        auth_mode="bearer",
        bearer_token="credential://http_prod_token",
        context=context,
    )

    assert Path(result["outputs"]["response_body"]).read_text(encoding="utf-8") == "ok"
    assert calls[0]["headers"]["Authorization"] == "Bearer resolved-token"
    assert "credential://http_prod_token" not in json.dumps(calls, sort_keys=True)


@pytest.mark.asyncio
async def test_http_request_passes_cache_and_rate_limit_options_to_shared_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("http_request")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            calls.append({"init": kwargs})

        async def request(self, *args: Any, **kwargs: Any) -> Any:
            calls.append({"request": {"args": args, "kwargs": kwargs}})
            return SimpleNamespace(
                status_code=200,
                headers={"content-type": "text/plain"},
                text="ok",
                url="https://api.example.test/resource",
                raise_for_status=lambda: None,
            )

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request(
        method="GET",
        url="https://api.example.test/resource",
        params={"gene": "TP53"},
        headers={"User-Agent": "test"},
        json_body=None,
        data=None,
        timeout=10,
        follow_redirects=False,
        retries=4,
        cache_ttl=60,
        rate_limit_per_second=2,
    )

    assert response.text == "ok"
    assert calls[0]["init"]["cache"] is not None
    assert calls[0]["init"]["rate_limiter"] is not None
    assert calls[1] == {
        "request": {
            "args": ("GET", "https://api.example.test/resource"),
            "kwargs": {
                "params": {"gene": "TP53"},
                "headers": {"User-Agent": "test"},
                "json": None,
                "data": None,
                "timeout": 10,
                "follow_redirects": False,
                "retries": 4,
                "retry_delay": 1.0,
                "cache_ttl": 60,
            },
        }
    }
