"""Focused contracts for ESearch, EFetch, and GEO E-utilities nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from bionodulo.nodes.builtin import ncbi as legacy
from bionodulo.nodes.builtin.api import http as api_http
from bionodulo.nodes.builtin.api.http import APIHttpClient as SharedAPIHttpClient
from bionodulo.nodes.builtin.ncbi_family import GEOQueryNode, NCBIEFetchNode, NCBIESearchNode
from bionodulo.nodes.builtin.ncbi_family import adapter, efetch, esearch, geo_query


def test_entrez_authority_ports_and_legacy_reexports() -> None:
    assert NCBIESearchNode.VERSION == "2026-03-04"
    assert NCBIESearchNode.SOURCE_SHA256 == ("69c3cbd73e1fe38484809221f46e2380cee7d5a354b7dffa2b5f612a52785ee1")
    assert NCBIEFetchNode.VERSION == "2026-03-04"
    assert NCBIEFetchNode.RESPONSE_SOURCE_REVISION == "26.0.20260717"
    assert NCBIEFetchNode.RESPONSE_SOURCE_SHA256 == (
        "c674a022027fc3451883f6dbebb99caa5b58f54bc842ca1ece12f73159cbac33"
    )
    assert GEOQueryNode.VERSION == "2026-03-04"
    assert NCBIESearchNode.RETURN_NAMES == ("id_list", "total_count", "query_translation")
    assert "return_uids" not in NCBIESearchNode.INPUT_TYPES()["optional"]
    assert set(NCBIEFetchNode.INPUT_TYPES()["required"]) == {"accessions", "database"}
    assert legacy.NCBIESearchNode is NCBIESearchNode
    assert legacy.NCBIEFetchNode is NCBIEFetchNode
    assert legacy.GEOQueryNode is GEOQueryNode
    assert efetch.default_extension("fasta", "text") == ".fasta"
    assert efetch.default_extension("gbwithparts", "text") == ".gb"
    assert efetch.default_extension("abstract", "text") == ".txt"
    assert efetch.default_extension("fasta", "xml") == ".xml"
    assert efetch.default_extension("json", "json") == ".json"


@pytest.mark.asyncio
async def test_eutils_selects_documented_rate_tier_and_bounded_request_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, *, cache: Any, rate_limiter: Any) -> None:
            clients.append({"cache": cache, "rate_limiter": rate_limiter, "requests": []})

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            clients[-1]["requests"].append({"method": method, "url": url, "kwargs": kwargs})
            return httpx.Response(200, text="ok", request=httpx.Request(method, url))

    monkeypatch.setattr(adapter, "APIHttpClient", FakeClient)

    await adapter.request_eutils("efetch.fcgi", {"db": "nuccore", "id": "A1"})
    await adapter.request_eutils(
        "efetch.fcgi",
        {"db": "nuccore", "id": "A1", "api_key": "test-api-key"},
    )

    assert clients[0]["rate_limiter"] is adapter._EUTILS_RATE_LIMITER
    assert clients[1]["rate_limiter"] is adapter._EUTILS_API_KEY_RATE_LIMITER
    assert clients[0]["rate_limiter"].rate_per_second == 3.0
    assert clients[1]["rate_limiter"].rate_per_second == 10.0
    for client in clients:
        request = client["requests"][0]
        assert request["method"] == "GET"
        assert request["url"] == f"{adapter.NCBI_EUTILS_BASE_URL}/efetch.fcgi"
        assert request["kwargs"]["timeout"] == 30.0
        assert request["kwargs"]["retries"] == 3
        assert request["kwargs"]["retry_delay"] == 1.0
        assert request["kwargs"]["cache_ttl"] == 300.0


@pytest.mark.parametrize("failure_kind", ("http", "transport"))
@pytest.mark.asyncio
async def test_eutils_bounds_retries_and_redacts_api_key(
    failure_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = f"private-{failure_kind}-key"
    attempts = 0
    sleeps: list[float] = []

    async def fake_send(**kwargs: Any) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        request = httpx.Request(kwargs["method"], kwargs["url"], params=kwargs["params"])
        message = f"failure for api_key={api_key}"
        if failure_kind == "http":
            return httpx.Response(503, text=message, request=request)
        raise httpx.ConnectError(message, request=request)

    def client_factory(*, cache: Any, rate_limiter: Any) -> SharedAPIHttpClient:
        return SharedAPIHttpClient(send=fake_send, cache=None, rate_limiter=None)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(adapter, "APIHttpClient", client_factory)
    monkeypatch.setattr(api_http.asyncio, "sleep", fake_sleep)

    expected_message = "HTTP 503" if failure_kind == "http" else "request failed"
    with pytest.raises(RuntimeError, match=expected_message) as error:
        await adapter.request_eutils("efetch.fcgi", {"db": "nuccore", "api_key": api_key})

    assert attempts == 3
    assert sleeps == [1.0, 2.0]
    assert api_key not in str(error.value)
    assert "api_key=***" in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.asyncio
async def test_esearch_returns_uids_and_omits_unsupplied_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((endpoint, params))
        return {
            "esearchresult": {
                "idlist": ["101", "202"],
                "count": "42",
                "querytranslation": "kinase[All Fields]",
            }
        }

    monkeypatch.delenv("BIONODULO_EMAIL", raising=False)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    monkeypatch.setattr(esearch, "request_json", fake_request)
    result = await NCBIESearchNode().run(
        query="kinase",
        database="gene",
        max_results=2,
        retstart=5,
        sort="name",
    )

    assert calls == [
        (
            "esearch.fcgi",
            {
                "db": "gene",
                "term": "kinase",
                "retmode": "json",
                "retmax": 2,
                "retstart": 5,
                "tool": "bionodulo",
                "sort": "name",
            },
        )
    ]
    assert result["outputs"] == {
        "id_list": ["101", "202"],
        "total_count": 42,
        "query_translation": "kinase[All Fields]",
    }


def test_esearch_enforces_documented_retmax_and_email_shape() -> None:
    base = {"query": "cancer", "database": "pubmed"}
    assert NCBIESearchNode.VALIDATE_INPUTS({**base, "max_results": 10001}) == (
        "Input 'max_results' must be between 1 and 10000"
    )
    assert NCBIESearchNode.VALIDATE_INPUTS({**base, "email": "not an email"}) == (
        "Input 'email' must be a valid email address without whitespace"
    )


@pytest.mark.asyncio
async def test_efetch_batches_text_without_corrupting_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_request(endpoint: str, params: dict[str, Any]) -> str:
        calls.append((endpoint, params))
        return "".join(f">{record_id}\nACGT\n" for record_id in str(params["id"]).split(","))

    class Context:
        node_dir = tmp_path

    monkeypatch.setattr(efetch, "request_text", fake_request)
    result = await NCBIEFetchNode().run(
        context=Context(),
        accessions="A1,A2,A3",
        database="nuccore",
        rettype="fasta",
        retmode="text",
        batch_size=2,
        email="owner@example.org",
        output_name="records.fasta",
    )

    output_path = Path(result["outputs"]["records"])
    assert output_path.read_text(encoding="utf-8") == ">A1\nACGT\n>A2\nACGT\n>A3\nACGT\n"
    assert [call[1]["id"] for call in calls] == ["A1,A2", "A3"]
    assert all(call[1]["tool"] == "bionodulo" for call in calls)
    assert all(call[1]["email"] == "owner@example.org" for call in calls)
    assert result["outputs"]["metadata"]["batch_count"] == 2


def test_efetch_rejects_documented_error_and_invalid_response_bodies() -> None:
    cases = (
        (" \n\t", "text", "empty response"),
        ('{"error":"API rate limit exceeded","count":"11"}', "text", "error response"),
        ("<eFetchResult><ERROR>Cannot process ID list</ERROR></eFetchResult>", "xml", "error response"),
        ('{"records":', "json", "invalid JSON"),
    )

    for body, retmode, message in cases:
        with pytest.raises(RuntimeError, match=message):
            efetch.validate_efetch_response(body, retmode=retmode)


@pytest.mark.asyncio
async def test_efetch_error_body_is_not_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request(endpoint: str, params: dict[str, Any]) -> str:
        assert endpoint == "efetch.fcgi"
        assert params["id"] == "A1"
        return '{"error":"API rate limit exceeded","count":"11"}'

    class Context:
        node_dir = tmp_path

    monkeypatch.setattr(efetch, "request_text", fake_request)

    with pytest.raises(RuntimeError, match="error response"):
        await NCBIEFetchNode().run(
            context=Context(),
            accessions="A1",
            database="nuccore",
            rettype="fasta",
            retmode="text",
        )

    assert not (tmp_path / NCBIEFetchNode.NODE_ID).exists()


@pytest.mark.asyncio
async def test_efetch_json_output_has_deterministic_extension_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request(endpoint: str, params: dict[str, Any]) -> str:
        assert endpoint == "efetch.fcgi"
        assert params["retmode"] == "json"
        return '{"records":[{"uid":"101"}]}'

    class Context:
        node_dir = tmp_path

    monkeypatch.setattr(efetch, "request_text", fake_request)
    result = await NCBIEFetchNode().run(
        context=Context(),
        accessions="101",
        database="snp",
        rettype="json",
        retmode="json",
    )

    output_path = Path(result["outputs"]["records"])
    assert output_path.name == "snp_json_1_records.json"
    assert output_path.read_text(encoding="utf-8") == '{"records":[{"uid":"101"}]}\n'
    assert result["outputs"]["metadata"] == {
        "database": "snp",
        "ids": ["101"],
        "rettype": "json",
        "retmode": "json",
        "record_count": 1,
        "batch_size": 100,
        "batch_count": 1,
        "records_path": str(output_path),
    }


@pytest.mark.asyncio
async def test_efetch_rejects_structured_multi_batch_before_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_request(endpoint: str, params: dict[str, Any]) -> str:
        raise AssertionError((endpoint, params))

    monkeypatch.setattr(efetch, "request_text", unexpected_request)
    with pytest.raises(ValueError, match="Structured EFetch output cannot be split"):
        await NCBIEFetchNode().run(
            accessions="1,2",
            database="gene",
            rettype="docsum",
            retmode="xml",
            batch_size=1,
        )


@pytest.mark.asyncio
async def test_geo_uses_gds_esearch_then_esummary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((endpoint, params))
        if endpoint == "esearch.fcgi":
            return {"esearchresult": {"idlist": ["200001"], "count": "1"}}
        return {
            "result": {
                "uids": ["200001"],
                "200001": {
                    "uid": "200001",
                    "accession": "GSE123",
                    "title": "Synthetic GEO series",
                    "entryType": "GSE",
                    "n_samples": 4,
                    "taxon": "Homo sapiens",
                },
            }
        }

    class Context:
        node_dir = tmp_path

    monkeypatch.delenv("BIONODULO_EMAIL", raising=False)
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    monkeypatch.setattr(geo_query, "request_json", fake_request)
    result = await GEOQueryNode().run(
        context=Context(),
        query="GSE123",
        query_type="series",
        max_results=5,
    )

    assert [call[0] for call in calls] == ["esearch.fcgi", "esummary.fcgi"]
    assert calls[0][1] == {
        "db": "gds",
        "term": "GSE123[ACCN] AND gse[ETYP]",
        "retmode": "json",
        "retmax": 5,
        "tool": "bionodulo",
    }
    assert calls[1][1]["id"] == "200001"
    metadata = json.loads(Path(result["outputs"]["geo_metadata"]).read_text(encoding="utf-8"))
    table = Path(result["outputs"]["sample_table"]).read_text(encoding="utf-8")
    assert metadata["record_count"] == 1
    assert "GSE123\tSynthetic GEO series" in table
