"""Focused contracts for ESearch, EFetch, and GEO E-utilities nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin import ncbi as legacy
from bionodulo.nodes.builtin.ncbi_family import GEOQueryNode, NCBIEFetchNode, NCBIESearchNode
from bionodulo.nodes.builtin.ncbi_family import efetch, esearch, geo_query


def test_entrez_authority_ports_and_legacy_reexports() -> None:
    assert NCBIESearchNode.VERSION == "2026-03-04"
    assert NCBIESearchNode.SOURCE_SHA256 == ("69c3cbd73e1fe38484809221f46e2380cee7d5a354b7dffa2b5f612a52785ee1")
    assert NCBIEFetchNode.VERSION == "2026-03-04"
    assert GEOQueryNode.VERSION == "2026-03-04"
    assert NCBIESearchNode.RETURN_NAMES == ("id_list", "total_count", "query_translation")
    assert "return_uids" not in NCBIESearchNode.INPUT_TYPES()["optional"]
    assert set(NCBIEFetchNode.INPUT_TYPES()["required"]) == {"accessions", "database"}
    assert legacy.NCBIESearchNode is NCBIESearchNode
    assert legacy.NCBIEFetchNode is NCBIEFetchNode
    assert legacy.GEOQueryNode is GEOQueryNode


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
