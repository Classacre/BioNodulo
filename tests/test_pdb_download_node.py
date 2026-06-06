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


def test_pdb_download_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["pdb_download"]["display_name"] == "PDB Download"
    assert info["pdb_download"]["category"] == "api"
    assert info["pdb_download"]["output_name"] == ["structure_file", "pdb_metadata"]
    assert info["pdb_retrieve"]["display_name"] == "PDB Retrieve"
    assert info["pdb_retrieve"]["category"] == "api"
    assert info["pdb_retrieve"]["output_name"] == ["structure_file", "pdb_metadata"]
    assert issubclass(registry.get("pdb_retrieve"), registry.get("pdb_download"))


@pytest.mark.asyncio
async def test_rcsb_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("pdb_download")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.RCSB_API_CACHE, module.APICache)
    assert isinstance(module.RCSB_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            return httpx.Response(200, json={"rcsb_id": "4HHB"}, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request("entry/4HHB", retries=4, timeout=8.0)

    assert response.json() == {"rcsb_id": "4HHB"}
    assert calls == [
        {
            "method": "GET",
            "url": f"{module.RCSB_DATA_BASE_URL}/entry/4HHB",
            "cache": module.RCSB_API_CACHE,
            "rate_limiter": module.RCSB_RATE_LIMITER,
            "headers": {"User-Agent": module.RCSB_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": module.RCSB_CACHE_TTL_S,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_rcsb_downloads_use_shared_http_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("pdb_download")
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
            return httpx.Response(200, content=b"data_4hhb\n", request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    output_path = tmp_path / "4HHB.cif"

    await module._download_file("https://files.rcsb.org/download/4HHB.cif", output_path, retries=2, timeout=9.0)

    assert output_path.read_bytes() == b"data_4hhb\n"
    assert calls == [
        {
            "method": "GET",
            "url": "https://files.rcsb.org/download/4HHB.cif",
            "cache": module.RCSB_API_CACHE,
            "rate_limiter": module.RCSB_RATE_LIMITER,
            "headers": {"User-Agent": module.RCSB_USER_AGENT},
            "timeout": 9.0,
            "retries": 2,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_pdb_download_writes_structure_density_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("pdb_download")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[str] = []
    download_calls: list[tuple[str, Path]] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        json_calls.append(resource)
        pdb_id = resource.rsplit("/", 1)[-1]
        return {
            "rcsb_id": pdb_id,
            "struct": {"title": f"{pdb_id} test structure"},
            "rcsb_entry_info": {"experimental_method": ["X-ray"]},
        }

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_download_file", fake_download)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        pdb_ids="4hhb, 1mbn",
        format="cif",
        fetch_metadata=True,
        download_density=True,
        context=context,
    )

    structure_path = Path(result["outputs"]["structure_file"])
    metadata_path = Path(result["outputs"]["pdb_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert structure_path.name == "4HHB.cif"
    assert structure_path.read_text(encoding="utf-8") == (
        "downloaded from https://files.rcsb.org/download/4HHB.cif\n"
    )
    assert metadata_path.name == "pdb_metadata.json"
    assert metadata == {
        "record_count": 2,
        "structures": [
            {
                "pdb_id": "4HHB",
                "format": "cif",
                "structure_file": str(tmp_path / "pdb_download" / "4HHB.cif"),
                "density_file": str(tmp_path / "pdb_download" / "4HHB_density.bcif"),
                "metadata": {
                    "rcsb_id": "4HHB",
                    "struct": {"title": "4HHB test structure"},
                    "rcsb_entry_info": {"experimental_method": ["X-ray"]},
                },
            },
            {
                "pdb_id": "1MBN",
                "format": "cif",
                "structure_file": str(tmp_path / "pdb_download" / "1MBN.cif"),
                "density_file": str(tmp_path / "pdb_download" / "1MBN_density.bcif"),
                "metadata": {
                    "rcsb_id": "1MBN",
                    "struct": {"title": "1MBN test structure"},
                    "rcsb_entry_info": {"experimental_method": ["X-ray"]},
                },
            },
        ],
    }
    assert json_calls == ["entry/4HHB", "entry/1MBN"]
    assert download_calls == [
        ("https://files.rcsb.org/download/4HHB.cif", tmp_path / "pdb_download" / "4HHB.cif"),
        ("https://maps.rcsb.org/x-ray/4hhb/cell/", tmp_path / "pdb_download" / "4HHB_density.bcif"),
        ("https://files.rcsb.org/download/1MBN.cif", tmp_path / "pdb_download" / "1MBN.cif"),
        ("https://maps.rcsb.org/x-ray/1mbn/cell/", tmp_path / "pdb_download" / "1MBN_density.bcif"),
    ]


@pytest.mark.asyncio
async def test_pdb_download_rejects_invalid_format() -> None:
    node_class = _node_class("pdb_download")

    with pytest.raises(ValueError, match="Unsupported PDB format"):
        await node_class().run(pdb_ids="4HHB", format="mtz")
