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


def test_interpro_scan_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["interpro_scan"]["display_name"] == "InterProScan"
    assert info["interpro_scan"]["category"] == "api"
    assert info["interpro_scan"]["output_name"] == ["domain_annotations", "domains_tsv"]
    assert info["interpro_scan"]["output"] == ["JSON", "TSV"]
    assert info["interpro"]["display_name"] == "InterPro"
    assert info["interpro"]["category"] == "api"
    assert info["interpro"]["output_name"] == ["domain_annotations", "domains_tsv"]
    assert info["interpro"]["output"] == ["JSON", "TSV"]
    assert issubclass(registry.get("interpro"), registry.get("interpro_scan"))


@pytest.mark.asyncio
async def test_interproscan_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("interpro_scan")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.INTERPROSCAN_API_CACHE, module.APICache)
    assert isinstance(module.INTERPROSCAN_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            text = "IPRSCAN-JOB-1\n" if method == "POST" else "FINISHED"
            return httpx.Response(200, text=text, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    post_response = await module._request(
        "POST",
        "run",
        data={"email": "analyst@example.org", "sequence": "MEEPQSDPSV"},
        retries=4,
        timeout=8.0,
    )
    get_response = await module._request("GET", "status/IPRSCAN-JOB-1", retries=2, timeout=9.0)

    assert post_response.text == "IPRSCAN-JOB-1\n"
    assert get_response.text == "FINISHED"
    assert calls == [
        {
            "method": "POST",
            "url": f"{module.INTERPROSCAN_BASE_URL}/run",
            "cache": module.INTERPROSCAN_API_CACHE,
            "rate_limiter": module.INTERPROSCAN_RATE_LIMITER,
            "data": {"email": "analyst@example.org", "sequence": "MEEPQSDPSV"},
            "headers": {"User-Agent": module.INTERPROSCAN_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        },
        {
            "method": "GET",
            "url": f"{module.INTERPROSCAN_BASE_URL}/status/IPRSCAN-JOB-1",
            "cache": module.INTERPROSCAN_API_CACHE,
            "rate_limiter": module.INTERPROSCAN_RATE_LIMITER,
            "headers": {"User-Agent": module.INTERPROSCAN_USER_AGENT},
            "timeout": 9.0,
            "retries": 2,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        },
    ]


@pytest.mark.asyncio
async def test_interpro_scan_submits_polls_and_writes_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("interpro_scan")
    module = importlib.import_module(node_class.__module__)
    posts: list[dict[str, Any]] = []
    status_calls: list[str] = []
    result_calls: list[str] = []
    sleeps: list[float] = []
    statuses = ["RUNNING", "FINISHED"]

    async def fake_post_text(endpoint: str, data: dict[str, Any], **_: Any) -> str:
        posts.append({"endpoint": endpoint, "data": dict(data)})
        return "IPRSCAN-JOB-1\n"

    async def fake_get_text(endpoint: str, **_: Any) -> str:
        status_calls.append(endpoint)
        return statuses.pop(0)

    async def fake_get_json(endpoint: str, **_: Any) -> dict[str, Any]:
        result_calls.append(endpoint)
        return {
            "matches": [
                {
                    "signature": {
                        "accession": "PF00069",
                        "name": "Protein kinase domain",
                        "entry": {
                            "accession": "IPR000719",
                            "type": "DOMAIN",
                            "description": "Protein kinase-like domain",
                        },
                    },
                    "locations": [
                        {"start": 12, "end": 274, "evalue": "1.2e-45"},
                    ],
                }
            ]
        }

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(module, "_post_text", fake_post_text)
    monkeypatch.setattr(module, "_get_text", fake_get_text)
    monkeypatch.setattr(module, "_get_json", fake_get_json)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    result = await node_class().run(
        sequence=">TP53 fragment\nMEEPQSDPSVEPPLSQETFSDLWKLLPEN",
        applications="pfam,smart",
        goterms=True,
        pathways=False,
        email="analyst@example.org",
        timeout_minutes=2,
        poll_interval_seconds=0.25,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    json_path = Path(result["outputs"]["domain_annotations"])
    tsv_path = Path(result["outputs"]["domains_tsv"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert json_path.name == "domain_annotations.json"
    assert tsv_path.name == "domains.tsv"
    assert payload["job_id"] == "IPRSCAN-JOB-1"
    assert payload["applications"] == "pfam,smart"
    assert payload["goterms"] is True
    assert payload["pathways"] is False
    assert payload["interproscan_result"]["matches"][0]["signature"]["accession"] == "PF00069"
    assert tsv_path.read_text(encoding="utf-8") == (
        "accession\tname\tdatabase\tstart\tend\tevalue\tdescription\n"
        "PF00069\tProtein kinase domain\tDOMAIN\t12\t274\t1.2e-45\tProtein kinase-like domain\n"
    )
    assert posts == [
        {
            "endpoint": "run",
            "data": {
                "email": "analyst@example.org",
                "title": "bionodulo_interpro",
                "sequence": "MEEPQSDPSVEPPLSQETFSDLWKLLPEN",
                "appl": "pfam,smart",
                "goterms": "true",
                "pathways": "false",
            },
        }
    ]
    assert status_calls == ["status/IPRSCAN-JOB-1", "status/IPRSCAN-JOB-1"]
    assert result_calls == ["result/IPRSCAN-JOB-1/json"]
    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_interpro_scan_rejects_empty_sequence() -> None:
    node_class = _node_class("interpro_scan")

    with pytest.raises(ValueError, match="requires a protein sequence"):
        await node_class().run(sequence=">empty\n")


@pytest.mark.asyncio
async def test_interpro_scan_reports_failed_job(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("interpro_scan")
    module = importlib.import_module(node_class.__module__)

    async def fake_post_text(endpoint: str, data: dict[str, Any], **_: Any) -> str:
        return "IPRSCAN-FAILED"

    async def fake_get_text(endpoint: str, **_: Any) -> str:
        return "FAILURE"

    monkeypatch.setattr(module, "_post_text", fake_post_text)
    monkeypatch.setattr(module, "_get_text", fake_get_text)

    with pytest.raises(RuntimeError, match="InterProScan job IPRSCAN-FAILED failed"):
        await node_class().run(
            sequence="MEEPQSDPSV",
            email="analyst@example.org",
            poll_interval_seconds=0.01,
        )
