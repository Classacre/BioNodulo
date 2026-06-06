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


def test_ucsc_genome_browser_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["ucsc_genome_browser"]["display_name"] == "UCSC Genome Browser"
    assert info["ucsc_genome_browser"]["category"] == "databases"
    assert info["ucsc_genome_browser"]["output_name"] == ["sequence_fasta", "annotations_json"]
    assert info["ucsc_genome_browser"]["output"] == ["FASTA", "JSON"]


@pytest.mark.asyncio
async def test_ucsc_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ucsc_genome_browser")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.UCSC_API_CACHE, module.APICache)
    assert isinstance(module.UCSC_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            return httpx.Response(200, json={"dna": "ACGT"}, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request(
        "getData/sequence",
        {"genome": "hg38", "chrom": "chr1", "start": 1, "end": 5},
        retries=4,
        timeout=8.0,
    )

    assert response.json() == {"dna": "ACGT"}
    assert calls == [
        {
            "method": "GET",
            "url": f"{module.UCSC_BASE_URL}/getData/sequence",
            "cache": module.UCSC_API_CACHE,
            "rate_limiter": module.UCSC_RATE_LIMITER,
            "params": {"genome": "hg38", "chrom": "chr1", "start": 1, "end": 5},
            "headers": {"User-Agent": module.UCSC_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": module.UCSC_CACHE_TTL_S,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_ucsc_sequence_query_writes_fasta_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ucsc_genome_browser")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return {
            "genome": "hg38",
            "chrom": "chr17",
            "start": 43044295,
            "end": 43044305,
            "dna": "acgtacgtaa",
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(
        coordinates="chr17:43044295-43044305",
        genome="hg38",
        query_type="sequence",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    fasta_path = Path(result["outputs"]["sequence_fasta"])
    json_path = Path(result["outputs"]["annotations_json"])
    metadata = json.loads(json_path.read_text(encoding="utf-8"))

    assert fasta_path.name == "sequence.fasta"
    assert fasta_path.read_text(encoding="utf-8") == ">hg38:chr17:43044295-43044305\nACGTACGTAA\n"
    assert json_path.name == "sequence_info.json"
    assert metadata["query_type"] == "sequence"
    assert metadata["coordinates"] == "chr17:43044295-43044305"
    assert metadata["sequence_length"] == 10
    assert metadata["ucsc_response"]["dna"] == "acgtacgtaa"
    assert calls == [
        {
            "endpoint": "getData/sequence",
            "params": {
                "genome": "hg38",
                "chrom": "chr17",
                "start": 43044295,
                "end": 43044305,
            },
        }
    ]


@pytest.mark.asyncio
async def test_ucsc_genes_in_region_query_writes_annotation_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ucsc_genome_browser")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return {
            "genome": "hg38",
            "trackType": "genePred",
            "knownGene": {
                "chr17": [
                    {
                        "name": "uc002hqi.3",
                        "chrom": "chr17",
                        "txStart": 43044294,
                        "txEnd": 43125482,
                    }
                ]
            },
            "itemsReturned": 1,
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(
        coordinates="chr17:43044295-43125364",
        genome="hg38",
        query_type="genes_in_region",
        track="knownGene",
        max_items=25,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    fasta_path = Path(result["outputs"]["sequence_fasta"])
    json_path = Path(result["outputs"]["annotations_json"])
    annotations = json.loads(json_path.read_text(encoding="utf-8"))

    assert fasta_path.read_text(encoding="utf-8") == ">hg38:chr17:43044295-43125364\n\n"
    assert json_path.name == "annotations.json"
    assert annotations["query_type"] == "genes_in_region"
    assert annotations["track"] == "knownGene"
    assert annotations["ucsc_response"]["itemsReturned"] == 1
    assert calls == [
        {
            "endpoint": "getData/track",
            "params": {
                "genome": "hg38",
                "track": "knownGene",
                "chrom": "chr17",
                "start": 43044295,
                "end": 43125364,
                "maxItemsOutput": 25,
            },
        }
    ]


@pytest.mark.asyncio
async def test_ucsc_genome_browser_rejects_invalid_inputs() -> None:
    node_class = _node_class("ucsc_genome_browser")

    with pytest.raises(ValueError, match="Unsupported UCSC query_type"):
        await node_class().run(coordinates="chr1:1-10", genome="hg38", query_type="variants")

    with pytest.raises(ValueError, match="coordinates must look like"):
        await node_class().run(coordinates="not coordinates", genome="hg38", query_type="sequence")
