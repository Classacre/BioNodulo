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


def test_string_db_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["string_db"]["display_name"] == "STRING DB"
    assert info["string_db"]["category"] == "databases"
    assert info["string_db"]["output_name"] == ["interaction_network", "network_metadata"]
    assert info["string_db"]["output"] == ["TSV", "JSON"]
    assert set(info["string_db"]["input"]["optional"]) == {
        "species",
        "query_type",
        "required_score",
        "network_flavor",
        "add_nodes",
        "protein_table",
        "id_column",
    }


@pytest.mark.asyncio
async def test_string_db_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.STRING_API_CACHE, module.APICache)
    assert isinstance(module.STRING_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            request = httpx.Request(method, url, params=kwargs.get("params"), headers=kwargs.get("headers"))
            return httpx.Response(200, text="preferredName_A\tpreferredName_B\nTP53\tMDM2\n", request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request(
        "tsv/network",
        params={"identifiers": "TP53\rMDM2", "species": 9606},
        retries=4,
        timeout=8.0,
    )

    assert response.text == "preferredName_A\tpreferredName_B\nTP53\tMDM2\n"
    assert calls == [
        {
            "method": "GET",
            "url": f"{module.STRING_BASE_URL}/tsv/network",
            "cache": module.STRING_API_CACHE,
            "rate_limiter": module.STRING_RATE_LIMITER,
            "params": {"identifiers": "TP53\rMDM2", "species": 9606},
            "headers": {"User-Agent": module.STRING_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": module.STRING_CACHE_TTL_S,
        }
    ]


@pytest.mark.asyncio
async def test_string_db_network_writes_tsv_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    network_tsv = (
        "stringId_A\tstringId_B\tpreferredName_A\tpreferredName_B\tscore\n"
        "9606.ENSP00000269305\t9606.ENSP00000258149\tTP53\tMDM2\t0.999\n"
    )

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return network_tsv

    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        protein_ids="TP53, MDM2",
        species=9606,
        query_type="network",
        required_score=700,
        network_flavor="confidence",
        add_nodes=2,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    tsv_path = Path(result["outputs"]["interaction_network"])
    metadata_path = Path(result["outputs"]["network_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert tsv_path.name == "interaction_network.tsv"
    assert tsv_path.read_text(encoding="utf-8") == network_tsv
    assert metadata_path.name == "network_metadata.json"
    assert metadata["query_type"] == "network"
    assert metadata["identifiers"] == ["TP53", "MDM2"]
    assert metadata["record_count"] == 1
    assert metadata["rows"][0]["preferredName_A"] == "TP53"
    assert calls == [
        {
            "endpoint": "tsv/network",
            "params": {
                "identifiers": "TP53\rMDM2",
                "species": 9606,
                "required_score": 700,
                "add_nodes": 2,
                "network_flavor": "confidence",
                "caller_identity": "BioNodulo",
            },
        }
    ]


@pytest.mark.asyncio
async def test_string_db_enrichment_writes_tsv_and_parsed_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    enrichment_tsv = (
        "category\tterm\tdescription\tp_value\tfdr\tinputGenes\n"
        "Process\tGO:0006915\tapoptotic process\t1.0e-05\t0.002\tTP53,MDM2\n"
    )

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return enrichment_tsv

    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        protein_ids=["TP53", "MDM2"],
        species=9606,
        query_type="enrichment",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    tsv_path = Path(result["outputs"]["interaction_network"])
    metadata = json.loads(Path(result["outputs"]["network_metadata"]).read_text(encoding="utf-8"))

    assert tsv_path.read_text(encoding="utf-8") == enrichment_tsv
    assert metadata["query_type"] == "enrichment"
    assert metadata["record_count"] == 1
    assert metadata["rows"] == [
        {
            "category": "Process",
            "term": "GO:0006915",
            "description": "apoptotic process",
            "p_value": "1.0e-05",
            "fdr": "0.002",
            "inputGenes": "TP53,MDM2",
        }
    ]
    assert calls == [
        {
            "endpoint": "tsv/enrichment",
            "params": {
                "identifiers": "TP53\rMDM2",
                "species": 9606,
                "caller_identity": "BioNodulo",
            },
        }
    ]


@pytest.mark.asyncio
async def test_string_db_image_downloads_network_png_and_records_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_response(endpoint: str, params: dict[str, Any], **_: Any) -> httpx.Response:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        request = httpx.Request(
            "GET",
            f"{module.STRING_BASE_URL}/{endpoint}",
            params=params,
            headers={"User-Agent": module.STRING_USER_AGENT},
        )
        return httpx.Response(200, content=b"\x89PNG\r\n\x1a\nstring-image", request=request)

    monkeypatch.setattr(module, "_request", fake_response)

    result = await node_class().run(
        protein_ids="TP53, MDM2",
        species=9606,
        query_type="image",
        required_score=700,
        network_flavor="confidence",
        add_nodes=2,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    tsv_path = Path(result["outputs"]["interaction_network"])
    metadata_path = Path(result["outputs"]["network_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    image_path = Path(metadata["image_path"])

    assert tsv_path.name == "interaction_network.tsv"
    assert tsv_path.read_text(encoding="utf-8") == "# STRING network image written to string_network.png\n"
    assert image_path == tmp_path / "string_db" / "string_network.png"
    assert image_path.read_bytes() == b"\x89PNG\r\n\x1a\nstring-image"
    assert metadata["query_type"] == "image"
    assert metadata["image_url"] == f"{module.STRING_BASE_URL}/image/network"
    assert metadata["image_params"] == {
        "identifiers": "TP53\rMDM2",
        "species": 9606,
        "caller_identity": "BioNodulo",
        "required_score": 700,
        "add_nodes": 2,
        "network_flavor": "confidence",
    }
    assert calls == [{"endpoint": "image/network", "params": metadata["image_params"]}]


@pytest.mark.asyncio
async def test_string_db_reads_identifiers_from_table_column(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    table = tmp_path / "significant_genes.csv"
    table.write_text("gene,padj\nTP53,0.001\nMDM2,0.02\nTP53,0.03\n,0.04\n", encoding="utf-8")

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return "category\tterm\tdescription\tfdr\nProcess\tGO:0006915\tapoptotic process\t0.002\n"

    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        protein_ids="",
        protein_table=str(table),
        id_column="gene",
        species=9606,
        query_type="enrichment",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    metadata = json.loads(Path(result["outputs"]["network_metadata"]).read_text(encoding="utf-8"))

    assert metadata["identifiers"] == ["TP53", "MDM2"]
    assert calls == [
        {
            "endpoint": "tsv/enrichment",
            "params": {
                "identifiers": "TP53\rMDM2",
                "species": 9606,
                "caller_identity": "BioNodulo",
            },
        }
    ]


@pytest.mark.asyncio
async def test_string_db_rejects_empty_ids_and_bad_query_type(tmp_path: Path) -> None:
    node_class = _node_class("string_db")

    with pytest.raises(ValueError, match="requires at least one protein ID"):
        await node_class().run(protein_ids="")

    with pytest.raises(ValueError, match="Column 'missing' not found in STRING identifier table"):
        table = tmp_path / "string_missing_column.tsv"
        table.write_text("gene\nTP53\n", encoding="utf-8")
        await node_class().run(protein_ids="", protein_table=str(table), id_column="missing")

    with pytest.raises(ValueError, match="Unsupported STRING query_type"):
        await node_class().run(protein_ids="TP53", query_type="orthologs")
