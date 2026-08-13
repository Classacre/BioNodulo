"""The literature tool returns abstracts and flags paywalled papers.

Research mode grounds new workflow designs in current best practices, which
takes more than a title list: the assistant needs abstracts to extract the
consensus, and needs to know which papers it could NOT read so it can ask the
user for them instead of guessing.
"""

from __future__ import annotations

import pytest

from bionodulo.ai.tools import ToolContext, _search_literature


class _FakeResponse:
    def __init__(self, payload: dict | None = None, text: str = "") -> None:
        self._payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload or {}


_SUMMARY = {
    "result": {
        "111": {
            "title": "Moderated estimation of fold change",
            "authors": [{"name": "Love MI"}],
            "fulljournalname": "Genome Biology",
            "pubdate": "2014 Dec",
            "articleids": [
                {"idtype": "doi", "value": "10.1186/s13059-014-0550-8"},
                {"idtype": "pmc", "value": "PMC4302049"},
            ],
        },
        "222": {
            "title": "A paywalled methods paper",
            "authors": [{"name": "Doe J"}],
            "fulljournalname": "Closed Access Weekly",
            "pubdate": "2023",
            "articleids": [{"idtype": "doi", "value": "10.0000/closed.1"}],
        },
    }
}

_FETCH_XML = """<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>111</PMID>
      <Article>
        <Abstract>
          <AbstractText Label="BACKGROUND">Differential analysis needs shrinkage.</AbstractText>
          <AbstractText>We present a method.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class _FakeClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        if "esearch" in url:
            return _FakeResponse({"esearchresult": {"idlist": ["111", "222"]}})
        if "esummary" in url:
            return _FakeResponse(_SUMMARY)
        if "efetch" in url:
            return _FakeResponse(text=_FETCH_XML)
        raise AssertionError(f"unexpected URL {url}")


@pytest.mark.asyncio
async def test_search_literature_returns_abstracts_and_open_access_links(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    result = await _search_literature(ToolContext(), query="rna-seq", max_results=2)

    assert result["count"] == 2
    open_paper, closed_paper = result["results"]

    assert open_paper["pmid"] == "111"
    assert "BACKGROUND: Differential analysis needs shrinkage." in open_paper["abstract"]
    assert "We present a method." in open_paper["abstract"]
    assert open_paper["free_full_text_url"] == "https://pmc.ncbi.nlm.nih.gov/articles/PMC4302049/"
    assert open_paper["doi_url"] == "https://doi.org/10.1186/s13059-014-0550-8"
    assert "access_note" not in open_paper

    # Paywalled: no abstract, no PMC full text — the assistant must be told to
    # ask the user for the paper rather than guess at its methods.
    assert closed_paper["pmid"] == "222"
    assert closed_paper["abstract"] == ""
    assert "free_full_text_url" not in closed_paper
    assert "paywalled" in closed_paper["access_note"]


@pytest.mark.asyncio
async def test_search_literature_handles_empty_result_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class _EmptyClient(_FakeClient):
        async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
            return _FakeResponse({"esearchresult": {"idlist": []}})

    monkeypatch.setattr(httpx, "AsyncClient", _EmptyClient)

    result = await _search_literature(ToolContext(), query="nothing matches this")

    assert result == {"query": "nothing matches this", "results": [], "count": 0}
