from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_kegg_pathway_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["kegg_pathway"]["display_name"] == "KEGG Pathway"
    assert info["kegg_pathway"]["category"] == "databases"
    assert info["kegg_pathway"]["output_name"] == ["pathway_data", "gene_list_tsv"]


@pytest.mark.asyncio
async def test_kegg_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.KEGG_API_CACHE, module.APICache)
    assert isinstance(module.KEGG_RATE_LIMITER, module.TokenBucketRateLimiter)

    class FakeClient:
        def __init__(self, *, cache: object | None = None, rate_limiter: object | None = None) -> None:
            self.cache = cache
            self.rate_limiter = rate_limiter

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "cache": self.cache,
                    "rate_limiter": self.rate_limiter,
                    **kwargs,
                }
            )
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            return httpx.Response(200, text="path:hsa04110\thsa:1029\n", request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request("link/genes/hsa04110", retries=4, timeout=8.0)

    assert response.text == "path:hsa04110\thsa:1029\n"
    assert calls == [
        {
            "method": "GET",
            "url": f"{module.KEGG_BASE_URL}/link/genes/hsa04110",
            "cache": module.KEGG_API_CACHE,
            "rate_limiter": module.KEGG_RATE_LIMITER,
            "headers": {"User-Agent": module.KEGG_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": module.KEGG_CACHE_TTL_S,
        }
    ]


@pytest.mark.asyncio
async def test_kegg_pathway_genes_writes_json_and_tsv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    calls: list[str] = []

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(resource)
        return (
            "path:hsa04110\thsa:1029\n"
            "path:hsa04110\thsa:51343\n"
        )

    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        query="04110",
        query_type="pathway_genes",
        organism="hsa",
        output_name="cell_cycle",
        context=context,
    )

    json_path = Path(result["outputs"]["pathway_data"])
    tsv_path = Path(result["outputs"]["gene_list_tsv"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_path.name == "cell_cycle.json"
    assert tsv_path.name == "cell_cycle.tsv"
    assert payload["query"] == "04110"
    assert payload["effective_query"] == "hsa04110"
    assert payload["query_type"] == "pathway_genes"
    assert payload["entries"] == [
        {"id": "path:hsa04110", "value": "hsa:1029"},
        {"id": "path:hsa04110", "value": "hsa:51343"},
    ]
    assert tsv_path.read_text(encoding="utf-8") == (
        "id\tvalue\n"
        "path:hsa04110\thsa:1029\n"
        "path:hsa04110\thsa:51343\n"
    )
    assert calls == ["link/genes/hsa04110"]
