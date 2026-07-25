"""Compact KEGG REST contract tests."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node() -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get("kegg_pathway")
    assert node is not None
    return node


def test_kegg_node_is_focused_rate_limited_and_has_no_hidden_image_mode() -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    assert node.__module__ == "bionodulo.nodes.builtin.kegg_family.pathway"
    assert node.VERSION == "KEGG REST 2026-07-20 contract snapshot"
    assert node.SOURCE_SHA256 == "702ac03a09ad800cbc3ec689ad6788ceffc336b441166876b7ffd6a5cc645d2f"
    assert node.POLICY_SOURCE_SHA256 == "789b45cf28fb2e6951fbfc6fec476ac9d1e2835d02c2efdc084967055f887872"
    assert node.LICENSE_SOURCE_SHA256 == "b87105e6251b08a2cd0f0208ee4615d021fe448f4ad46983eb7b576358ddd8e7"
    assert module.KEGG_RATE_LIMITER.rate_per_second == 3.0
    assert node.RETURN_NAMES == ("pathway_data", "gene_list_tsv")
    options = node.INPUT_TYPES()
    assert options["required"]["query_type"][1]["options"] == [
        "pathway_info",
        "pathway_genes",
        "list_pathways",
        "gene_info",
        "find_genes",
        "compound_info",
        "find_compounds",
        "link_kegg",
    ]
    assert "download_image" not in options["optional"]
    assert "three per second" in node.RATE_LIMIT_SEMANTICS
    assert "commercial" in node.LICENSE_SEMANTICS


@pytest.mark.parametrize(
    ("query", "query_type", "expected_resource", "expected_query"),
    [
        ("04110", "pathway_info", "get/hsa04110", "hsa04110"),
        ("path:hsa04110", "pathway_genes", "link/hsa/hsa04110", "hsa04110"),
        ("", "list_pathways", "list/pathway/hsa", "pathway:hsa"),
        ("1017", "gene_info", "get/hsa:1017", "hsa:1017"),
        ("cell cycle", "find_genes", "find/hsa/cell+cycle", "cell+cycle"),
        ("C00031", "compound_info", "get/cpd:C00031", "cpd:C00031"),
        (
            "glucose 6 phosphate",
            "find_compounds",
            "find/compound/glucose+6+phosphate",
            "glucose+6+phosphate",
        ),
        (
            "hsa:1017,cpd:C00031",
            "link_kegg",
            "link/pathway/hsa:1017+cpd:C00031",
            "hsa:1017+cpd:C00031",
        ),
    ],
)
def test_kegg_query_modes_use_documented_resources(
    query: str,
    query_type: str,
    expected_resource: str,
    expected_query: str,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    assert module._resource_for(query, query_type, "hsa") == (expected_resource, expected_query)


@pytest.mark.asyncio
async def test_kegg_transport_uses_bounded_cached_get(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, *, cache: Any, rate_limiter: Any) -> None:
            assert cache is module.KEGG_API_CACHE
            assert rate_limiter is module.KEGG_RATE_LIMITER

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append({"method": method, "url": url, **kwargs})
            return httpx.Response(200, text="path:hsa04110\thsa:1017\n", request=httpx.Request(method, url))

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    assert await module._request_text("link/hsa/hsa04110") == "path:hsa04110\thsa:1017\n"
    assert calls == [
        {
            "method": "GET",
            "url": "https://rest.kegg.jp/link/hsa/hsa04110",
            "headers": {"User-Agent": "BioNodulo/2.0 (KEGG REST node)"},
            "timeout": 30.0,
            "retries": 3,
            "retry_delay": 1.0,
            "cache_ttl": 300.0,
        }
    ]


@pytest.mark.asyncio
async def test_kegg_pathway_genes_uses_documented_link_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[str] = []

    async def fake_text(resource: str) -> str:
        calls.append(resource)
        return "path:hsa04110\thsa:1017\npath:hsa04110\thsa:1019\n"

    monkeypatch.setattr(module, "_request_text", fake_text)
    result = await node().run(
        query="04110",
        query_type="pathway_genes",
        organism="hsa",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["pathway_data"]).read_text(encoding="utf-8"))
    table = Path(result["outputs"]["gene_list_tsv"]).read_text(encoding="utf-8")
    assert calls == ["link/hsa/hsa04110"]
    assert payload["effective_query"] == "hsa04110"
    assert payload["entries"] == [
        {"id": "path:hsa04110", "value": "hsa:1017"},
        {"id": "path:hsa04110", "value": "hsa:1019"},
    ]
    assert table == "id\tvalue\npath:hsa04110\thsa:1017\npath:hsa04110\thsa:1019\n"


@pytest.mark.asyncio
async def test_kegg_flat_file_outputs_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    response = "ENTRY       hsa04110\nNAME        Cell cycle - Homo sapiens\nCLASS       Cellular Processes\n///\n"

    async def fake_text(resource: str) -> str:
        assert resource == "get/hsa04110"
        return response

    monkeypatch.setattr(module, "_request_text", fake_text)
    result = await node().run(
        query="04110",
        query_type="pathway_info",
        organism="hsa",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["pathway_data"]).read_text(encoding="utf-8"))
    table = Path(result["outputs"]["gene_list_tsv"]).read_text(encoding="utf-8")
    assert payload["entries"] == [
        {
            "CLASS": "Cellular Processes",
            "ENTRY": "hsa04110",
            "NAME": "Cell cycle - Homo sapiens",
        }
    ]
    assert table == "CLASS\tENTRY\tNAME\nCellular Processes\thsa04110\tCell cycle - Homo sapiens\n"


@pytest.mark.asyncio
async def test_kegg_rejects_empty_non_list_query() -> None:
    node = _node()
    with pytest.raises(ValueError, match="non-empty query"):
        await node().run(query="", query_type="pathway_info")
