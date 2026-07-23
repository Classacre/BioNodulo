from __future__ import annotations

import importlib
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


def _adapter_module() -> Any:
    return importlib.import_module(
        "bionodulo.nodes.builtin.protein_database_family.uniprot_adapter"
    )


def test_uniprot_retrieve_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["uniprot_retrieve"]["display_name"] == "UniProt Retrieve"
    assert info["uniprot_retrieve"]["category"] == "databases"
    assert info["uniprot_retrieve"]["output_name"] == ["protein_data", "sequence"]
    assert set(info["uniprot_retrieve"]["search_aliases"]).issuperset({"retrieve", "fetch", "sequence", "annotation"})
    assert info["uniprot_retrieve"]["input"]["required"]["uniprot_ids"] == (
        "STRING",
        {"default": "", "description": "UniProt accession(s), comma-separated"},
    )
    assert "format" not in info["uniprot_retrieve"]["input"]["optional"]
    assert info["uniprot_retrieve"]["input"]["hidden"]["format"] == (
        "STRING",
        {"description": ("Legacy compatibility only: when include_fasta is absent, fasta enables sequence output")},
    )
    assert info["uniprot_retrieve"]["input"]["optional"]["accession"] == (
        "STRING",
        {
            "default": "",
            "advanced": True,
            "description": "Backward-compatible UniProt accession(s), comma-separated",
        },
    )


def test_uniprot_search_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["uniprot_search"]["display_name"] == "UniProt Search"
    assert info["uniprot_search"]["category"] == "databases"
    assert info["uniprot_search"]["output_name"] == ["results_table", "results_data", "raw_results"]
    assert "query" in info["uniprot_search"]["search_aliases"]
    assert info["uniprot_search"]["input"]["optional"]["database"] == (
        "STRING",
        {"default": "uniprotkb", "options": ["uniprotkb", "uniref", "uniparc"]},
    )
    assert info["uniprot_search"]["input"]["optional"]["size"] == (
        "INT",
        {
            "default": None,
            "min": 1,
            "max": 500,
            "advanced": True,
            "description": "Legacy alias for max_results",
        },
    )


@pytest.mark.asyncio
async def test_uniprot_request_uses_shared_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _node_class("uniprot_retrieve")
    module = _adapter_module()
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
            request = httpx.Request(method, url, params=kwargs.get("params"), headers=kwargs.get("headers"))
            return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request(
        "uniprotkb/P04637.json",
        params={"fields": "accession"},
        retries=5,
        timeout=7.0,
    )

    assert response.json() == {"ok": True}
    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == f"{module.UNIPROT_BASE_URL}/uniprotkb/P04637.json"
    assert calls[0]["params"] == {"fields": "accession"}
    assert calls[0]["headers"] == {"User-Agent": module.UNIPROT_USER_AGENT}
    assert calls[0]["timeout"] == 7.0
    assert calls[0]["retries"] == 5
    assert calls[0]["retry_delay"] == module.RETRY_DELAY_S
    assert calls[0]["cache_ttl"] == module.UNIPROT_CACHE_TTL_S
    assert isinstance(calls[0]["cache"], module.APICache)
    assert isinstance(calls[0]["rate_limiter"], module.TokenBucketRateLimiter)

    await module._request(
        "uniprotkb/Q9Y6K9.json",
        params={"fields": "accession"},
        retries=5,
        timeout=7.0,
    )

    assert calls[1]["cache"] is calls[0]["cache"]
    assert calls[1]["rate_limiter"] is calls[0]["rate_limiter"]


@pytest.mark.asyncio
async def test_uniprot_retrieve_fetches_json_and_writes_fasta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_retrieve")
    module = _adapter_module()
    calls: list[tuple[str, str]] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        calls.append(("json", resource))
        return {
            "primaryAccession": "P04637",
            "uniProtkbId": "P53_HUMAN",
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}},
            },
            "organism": {"scientificName": "Homo sapiens"},
            "genes": [{"geneName": {"value": "TP53"}}],
            "sequence": {"length": 393, "value": "MEEPQSDPSV"},
        }

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(("text", resource))
        return ">sp|P04637|P53_HUMAN Cellular tumor antigen p53\nMEEPQSDPSV\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        accession="P04637",
        output_name="tp53",
        include_fasta=True,
        context=context,
    )

    protein_data = result["outputs"]["protein_data"]
    sequence_path = Path(result["outputs"]["sequence"])
    assert protein_data["primaryAccession"] == "P04637"
    assert protein_data["summary"] == {
        "accession": "P04637",
        "entry_name": "P53_HUMAN",
        "protein_name": "Cellular tumor antigen p53",
        "organism": "Homo sapiens",
        "gene_names": ["TP53"],
        "sequence_length": 393,
    }
    assert sequence_path.name == "tp53.fasta"
    assert sequence_path.read_text(encoding="utf-8") == ">sp|P04637|P53_HUMAN Cellular tumor antigen p53\nMEEPQSDPSV\n"
    assert calls == [
        ("json", "uniprotkb/P04637.json"),
        ("text", "uniprotkb/P04637.fasta"),
    ]


@pytest.mark.asyncio
async def test_uniprot_retrieve_accepts_planned_uniprot_ids_and_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_retrieve")
    module = _adapter_module()
    calls: list[tuple[str, str]] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        calls.append(("json", resource))
        return {
            "primaryAccession": "P04637",
            "uniProtkbId": "P53_HUMAN",
            "sequence": {"length": 393},
        }

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(("text", resource))
        return ">sp|P04637|P53_HUMAN\nMEEPQSDPSV\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        uniprot_ids="P04637",
        format="fasta",
        output_name="tp53_planned",
        context=context,
    )

    sequence_path = Path(result["outputs"]["sequence"])
    assert result["outputs"]["protein_data"]["primaryAccession"] == "P04637"
    assert sequence_path.name == "tp53_planned.fasta"
    assert sequence_path.read_text(encoding="utf-8") == ">sp|P04637|P53_HUMAN\nMEEPQSDPSV\n"
    assert calls == [
        ("json", "uniprotkb/P04637.json"),
        ("text", "uniprotkb/P04637.fasta"),
    ]


@pytest.mark.asyncio
async def test_uniprot_retrieve_supports_comma_separated_accessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_retrieve")
    module = _adapter_module()
    json_calls: list[str] = []
    fasta_calls: list[str] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        accession = resource.split("/")[1].split(".")[0]
        json_calls.append(resource)
        return {"primaryAccession": accession, "uniProtkbId": f"{accession}_ENTRY"}

    async def fake_text(resource: str, **_: Any) -> str:
        accession = resource.split("/")[1].split(".")[0]
        fasta_calls.append(resource)
        return f">sp|{accession}|{accession}_ENTRY\nMSEQ\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        accession="P04637, Q9Y6K9",
        include_fasta=True,
        context=context,
    )

    assert [entry["primaryAccession"] for entry in result["outputs"]["protein_data"]["entries"]] == [
        "P04637",
        "Q9Y6K9",
    ]
    assert Path(result["outputs"]["sequence"]).read_text(encoding="utf-8") == (
        ">sp|P04637|P04637_ENTRY\nMSEQ\n>sp|Q9Y6K9|Q9Y6K9_ENTRY\nMSEQ\n"
    )
    assert json_calls == ["uniprotkb/P04637.json", "uniprotkb/Q9Y6K9.json"]
    assert fasta_calls == ["uniprotkb/P04637.fasta", "uniprotkb/Q9Y6K9.fasta"]


@pytest.mark.asyncio
async def test_uniprot_search_database_option_selects_search_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()
    calls: list[str] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        calls.append(resource)
        return {"results": []}

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(node_dir=tmp_path)

    database_input = node_class.INPUT_TYPES()["optional"]["database"]
    assert database_input == (
        "STRING",
        {"default": "uniprotkb", "options": ["uniprotkb", "uniref", "uniparc"]},
    )

    await node_class().run(query="identity:0.9", database="uniref", context=context)

    assert calls == ["uniref/search"]


@pytest.mark.asyncio
async def test_uniprot_search_summarizes_uniref_json_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        assert resource == "uniref/search"
        return {
            "results": [
                {
                    "id": "UniRef90_P04637",
                    "name": "Cluster: Cellular tumor antigen p53",
                    "commonTaxon": {"scientificName": "Homo sapiens"},
                    "memberCount": 12,
                    "representativeMember": {
                        "memberId": "P53_HUMAN",
                        "proteinName": "Cellular tumor antigen p53",
                        "sequenceLength": 393,
                        "accessions": ["P04637"],
                    },
                }
            ]
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(
        query="identity:0.9",
        database="uniref",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    table_path = Path(result["outputs"]["results_table"])
    assert table_path.read_text(encoding="utf-8") == (
        "accession\tentry_name\tprotein_name\torganism\tgene_names\tsequence_length\n"
        "P04637\tUniRef90_P04637\tCellular tumor antigen p53\tHomo sapiens\t\t393\n"
    )
    summary = result["outputs"]["results_data"]["entries"][0]["summary"]
    assert summary["accession"] == "P04637"
    assert summary["entry_name"] == "UniRef90_P04637"
    assert summary["organism"] == "Homo sapiens"
    assert summary["member_count"] == 12


@pytest.mark.asyncio
async def test_uniprot_search_summarizes_uniparc_json_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        assert resource == "uniparc/search"
        return {
            "results": [
                {
                    "uniParcId": "UPI0000000001",
                    "crossReferenceCount": 57,
                    "commonTaxons": [
                        {"commonTaxon": "synthetic construct", "commonTaxonId": 32630},
                        {"commonTaxon": "Homo sapiens", "commonTaxonId": 9606},
                    ],
                    "uniProtKBAccessions": ["P07612.1", "P07612"],
                    "sequence": {"length": 250},
                }
            ]
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(
        query="upi:UPI0000000001",
        database="uniparc",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    table_path = Path(result["outputs"]["results_table"])
    assert table_path.read_text(encoding="utf-8") == (
        "accession\tentry_name\tprotein_name\torganism\tgene_names\tsequence_length\n"
        "P07612.1\tUPI0000000001\t\tHomo sapiens\t\t250\n"
    )
    summary = result["outputs"]["results_data"]["entries"][0]["summary"]
    assert summary["accession"] == "P07612.1"
    assert summary["entry_name"] == "UPI0000000001"
    assert summary["organism"] == "Homo sapiens"
    assert summary["cross_reference_count"] == 57


@pytest.mark.asyncio
async def test_uniprot_search_accepts_planned_size_alias(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()
    calls: list[dict[str, Any] | None] = []

    async def fake_json(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        calls.append(params)
        return {"results": []}

    monkeypatch.setattr(module, "_request_json", fake_json)

    await node_class().run(
        query="gene:TP53",
        size=7,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert calls == [
        {
            "query": "gene:TP53",
            "format": "json",
            "fields": "accession,id,gene_names,organism_name,protein_name,length",
            "size": 7,
        }
    ]


@pytest.mark.asyncio
async def test_uniprot_search_accepts_planned_tsv_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        calls.append((resource, params))
        return {
            "results": [
                {
                    "primaryAccession": "P04637",
                    "uniProtkbId": "P53_HUMAN",
                    "sequence": {"length": 393},
                }
            ]
        }

    async def fake_text(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> str:
        calls.append((resource, params))
        return "Entry\tEntry Name\nP04637\tP53_HUMAN\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)

    format_input = node_class.INPUT_TYPES()["optional"]["format"]
    assert format_input == (
        "STRING",
        {"default": "json", "options": ["json", "tsv", "xml", "fasta", "rdf", "gff"], "advanced": True},
    )

    result = await node_class().run(
        query="gene:TP53",
        format="tsv",
        output_name="tp53_search",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    table_path = Path(result["outputs"]["results_table"])
    raw_path = Path(result["outputs"]["raw_results"])
    assert table_path.name == "tp53_search.tsv"
    assert table_path.read_text(encoding="utf-8") == (
        "accession\tentry_name\tprotein_name\torganism\tgene_names\tsequence_length\nP04637\tP53_HUMAN\t\t\t\t393\n"
    )
    assert raw_path.name == "tp53_search.raw.tsv"
    assert raw_path.read_text(encoding="utf-8") == "Entry\tEntry Name\nP04637\tP53_HUMAN\n"
    assert result["outputs"]["results_data"]["record_count"] == 1
    assert result["outputs"]["results_data"]["raw_path"] == str(raw_path)
    assert calls == [
        (
            "uniprotkb/search",
            {
                "query": "gene:TP53",
                "format": "json",
                "fields": "accession,id,gene_names,organism_name,protein_name,length",
                "size": 25,
            },
        ),
        (
            "uniprotkb/search",
            {
                "query": "gene:TP53",
                "format": "tsv",
                "fields": "accession,id,gene_names,organism_name,protein_name,length",
                "size": 25,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_uniprot_search_accepts_planned_raw_text_formats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        calls.append((resource, params))
        return {
            "results": [
                {
                    "primaryAccession": "P04637",
                    "uniProtkbId": "P53_HUMAN",
                    "sequence": {"length": 393},
                }
            ]
        }

    async def fake_text(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> str:
        calls.append((resource, params))
        return '<uniprot><entry dataset="Swiss-Prot" /></uniprot>\n'

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        query="gene:TP53",
        format="xml",
        output_name="tp53_search",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    table_path = Path(result["outputs"]["results_table"])
    raw_path = Path(result["outputs"]["raw_results"])
    assert table_path.name == "tp53_search.tsv"
    assert table_path.read_text(encoding="utf-8") == (
        "accession\tentry_name\tprotein_name\torganism\tgene_names\tsequence_length\nP04637\tP53_HUMAN\t\t\t\t393\n"
    )
    assert raw_path.name == "tp53_search.raw.xml"
    assert raw_path.read_text(encoding="utf-8") == '<uniprot><entry dataset="Swiss-Prot" /></uniprot>\n'
    assert result["outputs"]["results_data"]["format"] == "xml"
    assert result["outputs"]["results_data"]["record_count"] == 1
    assert result["outputs"]["results_data"]["raw_path"] == str(raw_path)
    assert calls == [
        (
            "uniprotkb/search",
            {
                "query": "gene:TP53",
                "format": "json",
                "fields": "accession,id,gene_names,organism_name,protein_name,length",
                "size": 25,
            },
        ),
        (
            "uniprotkb/search",
            {
                "query": "gene:TP53",
                "format": "xml",
                "size": 25,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_uniprot_search_writes_summary_tsv_and_returns_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = _adapter_module()
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        calls.append((resource, params))
        return {
            "results": [
                {
                    "primaryAccession": "P04637",
                    "uniProtkbId": "P53_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}},
                    },
                    "organism": {"scientificName": "Homo sapiens"},
                    "genes": [{"geneName": {"value": "TP53"}}],
                    "sequence": {"length": 393},
                },
                {
                    "primaryAccession": "Q9Y6K9",
                    "uniProtkbId": "NEMO_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {"fullName": {"value": "NF-kappa-B essential modulator"}},
                    },
                    "organism": {"scientificName": "Homo sapiens"},
                    "genes": [{"geneName": {"value": "IKBKG"}, "synonyms": [{"value": "NEMO"}]}],
                    "sequence": {"length": 419},
                },
            ]
        }

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        query="gene:TP53 OR gene:IKBKG",
        max_results=2,
        reviewed_only=True,
        output_name="nfkb_tp53",
        context=context,
    )

    table_path = Path(result["outputs"]["results_table"])
    results_data = result["outputs"]["results_data"]
    assert table_path.name == "nfkb_tp53.tsv"
    assert table_path.read_text(encoding="utf-8") == (
        "accession\tentry_name\tprotein_name\torganism\tgene_names\tsequence_length\n"
        "P04637\tP53_HUMAN\tCellular tumor antigen p53\tHomo sapiens\tTP53\t393\n"
        "Q9Y6K9\tNEMO_HUMAN\tNF-kappa-B essential modulator\tHomo sapiens\tIKBKG;NEMO\t419\n"
    )
    assert results_data["query"] == "gene:TP53 OR gene:IKBKG"
    assert results_data["record_count"] == 2
    assert [entry["summary"]["accession"] for entry in results_data["entries"]] == ["P04637", "Q9Y6K9"]
    assert calls == [
        (
            "uniprotkb/search",
            {
                "query": "(gene:TP53 OR gene:IKBKG) AND reviewed:true",
                "format": "json",
                "fields": "accession,id,gene_names,organism_name,protein_name,length",
                "size": 2,
            },
        )
    ]


@pytest.mark.asyncio
async def test_uniprot_nodes_forward_include_isoform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    search_class = _node_class("uniprot_search")
    retrieve_class = _node_class("uniprot_retrieve")
    module = _adapter_module()
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        calls.append((resource, params))
        if params and params.get("query") == "accession:P04637":
            return {
                "results": [
                    {"primaryAccession": "P04637", "uniProtkbId": "P53_HUMAN"},
                    {"primaryAccession": "P04637-2", "uniProtkbId": "P53_HUMAN"},
                ]
            }
        if resource == "uniprotkb/search":
            return {"results": []}
        return {"primaryAccession": "P04637", "uniProtkbId": "P53_HUMAN"}

    async def fake_text(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> str:
        calls.append((resource, params))
        return ">sp|P04637|P53_HUMAN\nMSEQ\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    assert search_class.INPUT_TYPES()["optional"]["include_isoform"][0] == "BOOLEAN"
    assert retrieve_class.INPUT_TYPES()["optional"]["include_isoform"][0] == "BOOLEAN"

    await search_class().run(query="gene:TP53", include_isoform=True, context=context)
    await retrieve_class().run(accession="P04637", include_isoform=True, include_fasta=True, context=context)

    assert calls[0][1] == {
        "query": "gene:TP53",
        "format": "json",
        "fields": "accession,id,gene_names,organism_name,protein_name,length",
        "size": 25,
        "includeIsoform": "true",
    }
    assert calls[1] == (
        "uniprotkb/search",
        {
            "query": "accession:P04637",
            "format": "json",
            "size": 500,
            "includeIsoform": "true",
        },
    )
    assert calls[2] == (
        "uniprotkb/search",
        {
            "query": "accession:P04637",
            "format": "fasta",
            "size": 500,
            "includeIsoform": "true",
        },
    )
