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


def test_alphafold_db_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["alphafold_db"]["display_name"] == "AlphaFold DB"
    assert info["alphafold_db"]["category"] == "databases"
    assert info["alphafold_db"]["output_name"] == ["structure_mmcif", "structure_metadata"]
    assert info["alphafold"]["display_name"] == "AlphaFold"
    assert info["alphafold"]["category"] == "databases"
    assert info["alphafold"]["output_name"] == ["structure_mmcif", "structure_metadata"]
    assert issubclass(registry.get("alphafold"), registry.get("alphafold_db"))


@pytest.mark.asyncio
async def test_alphafold_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.ALPHAFOLD_API_CACHE, module.APICache)
    assert isinstance(module.ALPHAFOLD_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            return httpx.Response(200, json=[{"entryId": "AF-P04637-F1"}], request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request("prediction/P04637", retries=4, timeout=8.0)

    assert response.json() == [{"entryId": "AF-P04637-F1"}]
    assert calls == [
        {
            "method": "GET",
            "url": f"{module.ALPHAFOLD_BASE_URL}/prediction/P04637",
            "cache": module.ALPHAFOLD_API_CACHE,
            "rate_limiter": module.ALPHAFOLD_RATE_LIMITER,
            "headers": {"User-Agent": module.ALPHAFOLD_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": module.ALPHAFOLD_CACHE_TTL_S,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_alphafold_downloads_use_shared_http_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

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
            return httpx.Response(200, content=b"data_p04637\n", request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    output_path = tmp_path / "P04637.cif"

    await module._download_file("https://alphafold.example/P04637.cif", output_path, retries=2, timeout=9.0)

    assert output_path.read_bytes() == b"data_p04637\n"
    assert calls == [
        {
            "method": "GET",
            "url": "https://alphafold.example/P04637.cif",
            "cache": module.ALPHAFOLD_API_CACHE,
            "rate_limiter": module.ALPHAFOLD_RATE_LIMITER,
            "headers": {"User-Agent": module.ALPHAFOLD_USER_AGENT},
            "timeout": 9.0,
            "retries": 2,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_alphafold_db_downloads_structure_and_writes_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[str] = []
    download_calls: list[tuple[str, Path]] = []

    async def fake_json(resource: str, **_: Any) -> Any:
        json_calls.append(resource)
        return [
            {
                "entryId": "AF-P04637-F1",
                "uniprotAccession": "P04637",
                "uniprotId": "P53_HUMAN",
                "cifUrl": "https://alphafold.example/P04637.cif",
                "pdbUrl": "https://alphafold.example/P04637.pdb",
                "paeDocUrl": "https://alphafold.example/P04637-pae.json",
                "latestVersion": 4,
            }
        ]

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_download_file", fake_download)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        uniprot_ids="P04637",
        structure_format="mmcif",
        download_pae=True,
        context=context,
    )

    structure_path = Path(result["outputs"]["structure_mmcif"])
    metadata_path = Path(result["outputs"]["structure_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert structure_path.name == "P04637.cif"
    assert structure_path.read_text(encoding="utf-8") == "downloaded from https://alphafold.example/P04637.cif\n"
    assert metadata_path.name == "structure_metadata.json"
    assert metadata == {
        "record_count": 1,
        "structures": [
            {
                "uniprot_id": "P04637",
                "entry_id": "AF-P04637-F1",
                "uniprot_accession": "P04637",
                "uniprot_name": "P53_HUMAN",
                "latest_version": 4,
                "structure_file": str(structure_path),
                "pae_file": str(tmp_path / "alphafold_db" / "P04637_pae.json"),
            }
        ],
        "raw": {"P04637": [{"entryId": "AF-P04637-F1", "uniprotAccession": "P04637", "uniprotId": "P53_HUMAN", "cifUrl": "https://alphafold.example/P04637.cif", "pdbUrl": "https://alphafold.example/P04637.pdb", "paeDocUrl": "https://alphafold.example/P04637-pae.json", "latestVersion": 4}]},
    }
    assert (tmp_path / "alphafold_db" / "P04637_pae.json").read_text(encoding="utf-8") == (
        "downloaded from https://alphafold.example/P04637-pae.json\n"
    )
    assert json_calls == ["prediction/P04637"]
    assert download_calls == [
        ("https://alphafold.example/P04637.cif", tmp_path / "alphafold_db" / "P04637.cif"),
        ("https://alphafold.example/P04637-pae.json", tmp_path / "alphafold_db" / "P04637_pae.json"),
    ]
