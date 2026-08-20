"""Research tools resolve papers across OpenAlex, PubMed, and arXiv.

The assistant grounds workflow designs in the literature without any API keys,
so these tools must parse three different response shapes (OpenAlex JSON,
NCBI JSON + XML, arXiv Atom XML) and route identifiers to the right backend.
Network access is replaced with ``httpx.MockTransport`` and the per-host
throttle sleep is stubbed out, keeping the suite hermetic and fast.
"""

from __future__ import annotations

import json

import httpx
import pytest

from bionodulo.ai import research_tools
from bionodulo.ai.tools import ToolContext, aexecute_tool, get_tool


async def _no_sleep(seconds: float) -> None:
    return None


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(research_tools, "_TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(research_tools, "_SLEEP", _no_sleep)
    monkeypatch.setattr(research_tools, "_last_request_at", {})


def _json_response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(payload), headers={"Content-Type": "application/json"})


_OPENALEX_WORK = {
    "id": "https://openalex.org/W2741809807",
    "title": "Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2",
    "display_name": "Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2",
    "authorships": [
        {"author": {"display_name": "Michael I Love"}},
        {"author": {"display_name": "Wolfgang Huber"}},
        {"author": {"display_name": "Simon Anders"}},
        {"author": {"display_name": "Fourth Author"}},
    ],
    "publication_year": 2014,
    "primary_location": {"source": {"display_name": "Genome Biology"}},
    "doi": "https://doi.org/10.1186/s13059-014-0550-8",
    "cited_by_count": 42000,
    "open_access": {"is_oa": True, "oa_url": "https://genomebiology.biomedcentral.com/track/pdf/10.1186/s13059-014-0550-8.pdf"},
    "abstract_inverted_index": {"Shrinkage": [0], "of": [1], "fold": [2], "change.": [3]},
    "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W2"],
    "cited_by_api_url": "https://api.openalex.org/works?filter=cites:W2741809807",
}


@pytest.mark.asyncio
async def test_literature_search_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.openalex.org"
        assert "from_publication_date" in str(request.url) and "2020-01-01" in str(request.url)
        return _json_response({"results": [_OPENALEX_WORK]})

    _install_transport(monkeypatch, handler)

    result = await research_tools._literature_search(ToolContext(), query="deseq2", max_results=5, year_from=2020)

    assert result["count"] == 1
    paper = result["results"][0]
    assert paper["title"].startswith("Moderated estimation")
    assert paper["authors"] == ["Michael I Love", "Wolfgang Huber", "Simon Anders"]  # first 3 only
    assert paper["year"] == 2014
    assert paper["venue"] == "Genome Biology"
    assert paper["doi"] == "10.1186/s13059-014-0550-8"
    assert paper["citation_count"] == 42000
    assert paper["open_access_pdf"].endswith(".pdf")
    assert paper["abstract"] == "Shrinkage of fold change."  # rebuilt from the inverted index


@pytest.mark.asyncio
async def test_literature_search_empty_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: _json_response({"results": []}))
    result = await research_tools._literature_search(ToolContext(), query="nothing")
    assert result == {"query": "nothing", "year_from": None, "results": [], "count": 0}

    _install_transport(monkeypatch, lambda request: httpx.Response(500, text="boom"))
    result = await research_tools._literature_search(ToolContext(), query="deseq2")
    assert "error" in result
    assert "OpenAlex search failed" in result["error"]


_PUBMED_ESUMMARY = {
    "result": {
        "uids": ["111", "222"],
        "111": {
            "title": "A methods paper",
            "authors": [{"name": "Love MI"}, {"name": "Huber W"}],
            "fulljournalname": "Genome Biology",
            "pubdate": "2014 Dec",
            "articleids": [{"idtype": "doi", "value": "10.1186/s13059-014-0550-8"}],
        },
        "222": {
            "title": "A second paper",
            "authors": [{"name": "Doe J"}],
            "source": "J Testing",
            "pubdate": "2023",
            "articleids": [],
        },
    }
}


@pytest.mark.asyncio
async def test_pubmed_search_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "esearch" in request.url.path:
            return _json_response({"esearchresult": {"idlist": ["111", "222"]}})
        if "esummary" in request.url.path:
            return _json_response(_PUBMED_ESUMMARY)
        raise AssertionError(f"unexpected path {request.url.path}")

    _install_transport(monkeypatch, handler)

    result = await research_tools._pubmed_search(ToolContext(), query="rna-seq", max_results=2)

    assert result["count"] == 2
    first, second = result["results"]
    assert first["pmid"] == "111"
    assert first["title"] == "A methods paper"
    assert first["authors"] == ["Love MI", "Huber W"]
    assert first["journal"] == "Genome Biology"
    assert first["year"] == "2014"
    assert first["doi"] == "10.1186/s13059-014-0550-8"
    assert second["pmid"] == "222"
    assert second["doi"] == ""


@pytest.mark.asyncio
async def test_pubmed_search_empty_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: _json_response({"esearchresult": {"idlist": []}}))
    result = await research_tools._pubmed_search(ToolContext(), query="nothing")
    assert result == {"query": "nothing", "results": [], "count": 0}

    _install_transport(monkeypatch, lambda request: httpx.Response(429, text="slow down"))
    result = await research_tools._pubmed_search(ToolContext(), query="rna-seq")
    assert "error" in result
    assert "PubMed search failed" in result["error"]


_ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <title>  A   Very Recent Method </title>
    <summary> We propose a thing.
With details.</summary>
    <published>2024-01-22T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Grace Hopper</name></author>
    <link href="http://arxiv.org/abs/2401.12345v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.12345v2" type="application/pdf"/>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_arxiv_search_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "export.arxiv.org"
        return httpx.Response(200, text=_ARXIV_FEED)

    _install_transport(monkeypatch, handler)

    result = await research_tools._arxiv_search(ToolContext(), query="protein folding", max_results=3)

    assert result["count"] == 1
    paper = result["results"][0]
    assert paper["arxiv_id"] == "2401.12345v2"
    assert paper["title"] == "A Very Recent Method"  # whitespace collapsed
    assert paper["authors"] == ["Ada Lovelace", "Grace Hopper"]
    assert paper["published"].startswith("2024-01-22")
    assert "We propose a thing." in paper["summary"]
    assert paper["pdf_url"] == "http://arxiv.org/pdf/2401.12345v2"


@pytest.mark.asyncio
async def test_arxiv_search_empty_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_feed = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    _install_transport(monkeypatch, lambda request: httpx.Response(200, text=empty_feed))
    result = await research_tools._arxiv_search(ToolContext(), query="nothing")
    assert result == {"query": "nothing", "results": [], "count": 0}

    _install_transport(monkeypatch, lambda request: httpx.Response(502, text="bad gateway"))
    result = await research_tools._arxiv_search(ToolContext(), query="protein")
    assert "error" in result
    assert "arXiv search failed" in result["error"]


_EFETCH_XML = """<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>111</PMID>
      <Article>
        <Abstract>
          <AbstractText Label="BACKGROUND">Context matters.</AbstractText>
          <AbstractText>We did a study.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


@pytest.mark.asyncio
async def test_get_paper_routes_by_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.url.host}{request.url.path}")
        host = request.url.host
        if host == "api.openalex.org":
            return _json_response(_OPENALEX_WORK)
        if "esummary" in request.url.path:
            return _json_response(_PUBMED_ESUMMARY)
        if "efetch" in request.url.path:
            return httpx.Response(200, text=_EFETCH_XML)
        if host == "export.arxiv.org":
            return httpx.Response(200, text=_ARXIV_FEED)
        raise AssertionError(f"unexpected request {request.url}")

    _install_transport(monkeypatch, handler)

    doi_card = await research_tools._get_paper(ToolContext(), identifier="10.1186/s13059-014-0550-8")
    assert doi_card["identifier_type"] == "doi"
    assert doi_card["title"].startswith("Moderated estimation")
    assert doi_card["abstract"] == "Shrinkage of fold change."

    # DOI URL / doi: prefixes normalize to the bare DOI.
    prefixed = await research_tools._get_paper(ToolContext(), identifier="https://doi.org/10.1186/s13059-014-0550-8")
    assert prefixed["identifier_type"] == "doi"

    arxiv_card = await research_tools._get_paper(ToolContext(), identifier="arXiv:2401.12345")
    assert arxiv_card["identifier_type"] == "arxiv"
    assert arxiv_card["title"] == "A Very Recent Method"
    assert "We propose a thing." in arxiv_card["abstract"]

    pmid_card = await research_tools._get_paper(ToolContext(), identifier="111")
    assert pmid_card["identifier_type"] == "pmid"
    assert pmid_card["pmid"] == "111"
    assert "BACKGROUND: Context matters." in pmid_card["abstract"]

    assert any("api.openalex.org" in c for c in calls)
    assert any("export.arxiv.org" in c for c in calls)
    assert any("esummary" in c for c in calls)


@pytest.mark.asyncio
async def test_get_paper_unknown_identifier_and_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: _json_response({}))

    result = await research_tools._get_paper(ToolContext(), identifier="not a paper id")
    assert "error" in result
    assert "DOI" in result["error"]

    _install_transport(monkeypatch, lambda request: httpx.Response(404, text="not found"))
    result = await research_tools._get_paper(ToolContext(), identifier="10.0000/missing")
    assert "error" in result
    assert "Paper lookup failed" in result["error"]


@pytest.mark.asyncio
async def test_citation_lookup_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "cites" in url:
            return _json_response({"results": [_OPENALEX_WORK]})
        return _json_response(_OPENALEX_WORK)

    _install_transport(monkeypatch, handler)

    result = await research_tools._citation_lookup(ToolContext(), doi="10.1186/s13059-014-0550-8")

    assert result["doi"] == "10.1186/s13059-014-0550-8"
    assert result["cited_by_count"] == 42000
    assert result["references_count"] == 2
    assert len(result["top_citing_works"]) == 1
    assert result["top_citing_works"][0]["title"].startswith("Moderated estimation")
    assert "abstract" not in result["top_citing_works"][0]


@pytest.mark.asyncio
async def test_citation_lookup_rejects_non_doi_and_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_transport(monkeypatch, lambda request: _json_response({}))

    result = await research_tools._citation_lookup(ToolContext(), doi="2401.12345")
    assert "error" in result
    assert "expects a DOI" in result["error"]

    _install_transport(monkeypatch, lambda request: httpx.Response(500, text="boom"))
    result = await research_tools._citation_lookup(ToolContext(), doi="10.1186/s13059-014-0550-8")
    assert "error" in result
    assert "Citation lookup failed" in result["error"]


@pytest.mark.asyncio
async def test_research_tools_registered_and_async_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("literature_search", "pubmed_search", "arxiv_search", "get_paper", "citation_lookup"):
        assert get_tool(name) is not None, name

    _install_transport(monkeypatch, lambda request: _json_response({"results": []}))
    result = await aexecute_tool("literature_search", {"query": "deseq2"}, ToolContext())
    assert result["status"] == "ok"
    assert result["result"]["count"] == 0
