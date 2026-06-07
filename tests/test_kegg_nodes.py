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
    assert info["kegg_pathway"]["category"] == "api"
    assert info["kegg_pathway"]["output_name"] == ["pathway_data", "gene_list_tsv"]
    assert info["kegg_pathway"]["input"]["required"]["query_type"] == (
        "STRING",
        {
            "default": "pathway_info",
            "options": [
                "pathway_info",
                "pathway_genes",
                "pathway_image",
                "list_pathways",
                "gene_info",
                "find_genes",
                "compound_info",
                "find_compounds",
                "link_kegg",
            ],
        },
    )
    assert info["kegg_pathway"]["input"]["optional"]["organism"] == (
        "STRING",
        {"default": "hsa", "options": ["hsa", "mmu", "rno", "dre", "cel", "dme", "sce", "ath", "eco"]},
    )


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


@pytest.mark.asyncio
async def test_kegg_pathway_uses_non_human_organism_option(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    calls: list[str] = []

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(resource)
        return "path:mmu04110\tmmu:12566\n"

    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        query="04110",
        query_type="pathway_genes",
        organism="mmu",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads(Path(result["outputs"]["pathway_data"]).read_text(encoding="utf-8"))
    assert payload["organism"] == "mmu"
    assert payload["effective_query"] == "mmu04110"
    assert calls == ["link/genes/mmu04110"]


@pytest.mark.asyncio
async def test_kegg_downloads_pathway_image_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    text_calls: list[str] = []
    download_calls: list[tuple[str, Path]] = []

    async def fake_text(resource: str, **_: Any) -> str:
        text_calls.append(resource)
        return "ENTRY       hsa04110                    Pathway\nNAME        Cell cycle - Homo sapiens\n///\n"

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_bytes(b"png-bytes")

    monkeypatch.setattr(module, "_request_text", fake_text)
    monkeypatch.setattr(module, "_download_file", fake_download)
    context = SimpleNamespace(node_dir=tmp_path)

    assert "pathway_image" in node_class.INPUT_TYPES()["required"]["query_type"][1]["options"]
    assert node_class.INPUT_TYPES()["optional"]["download_image"][0] == "BOOLEAN"

    result = await node_class().run(
        query="04110",
        query_type="pathway_image",
        organism="hsa",
        download_image=True,
        context=context,
    )

    json_path = Path(result["outputs"]["pathway_data"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    image_path = tmp_path / "kegg_pathway" / "hsa04110.png"

    assert payload["query_type"] == "pathway_image"
    assert payload["effective_query"] == "hsa04110"
    assert payload["pathway_image"] == str(image_path)
    assert image_path.read_bytes() == b"png-bytes"
    assert text_calls == ["get/hsa04110"]
    assert download_calls == [
        ("https://www.kegg.jp/kegg/pathway/hsa/hsa04110.png", image_path),
    ]


@pytest.mark.asyncio
async def test_kegg_compound_info_uses_compound_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    calls: list[str] = []

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(resource)
        return "ENTRY       C00031                      Compound\nNAME        D-Glucose\n///\n"

    monkeypatch.setattr(module, "_request_text", fake_text)

    assert "compound_info" in node_class.INPUT_TYPES()["required"]["query_type"][1]["options"]

    result = await node_class().run(
        query="C00031",
        query_type="compound_info",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads(Path(result["outputs"]["pathway_data"]).read_text(encoding="utf-8"))
    tsv_path = Path(result["outputs"]["gene_list_tsv"])

    assert payload["query_type"] == "compound_info"
    assert payload["effective_query"] == "cpd:C00031"
    assert payload["entries"][0]["ENTRY"] == "C00031                      Compound"
    assert "D-Glucose" in tsv_path.read_text(encoding="utf-8")
    assert calls == ["get/cpd:C00031"]


@pytest.mark.asyncio
async def test_kegg_find_compounds_uses_compound_find_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    calls: list[str] = []

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(resource)
        return "cpd:C00031\tD-Glucose; Grape sugar\n"

    monkeypatch.setattr(module, "_request_text", fake_text)

    assert "find_compounds" in node_class.INPUT_TYPES()["required"]["query_type"][1]["options"]

    result = await node_class().run(
        query="D Glucose",
        query_type="find_compounds",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = json.loads(Path(result["outputs"]["pathway_data"]).read_text(encoding="utf-8"))
    tsv_path = Path(result["outputs"]["gene_list_tsv"])

    assert payload["query_type"] == "find_compounds"
    assert payload["effective_query"] == "D+Glucose"
    assert payload["entries"] == [{"id": "cpd:C00031", "value": "D-Glucose; Grape sugar"}]
    assert tsv_path.read_text(encoding="utf-8") == "id\tvalue\ncpd:C00031\tD-Glucose; Grape sugar\n"
    assert calls == ["find/compound/D+Glucose"]
