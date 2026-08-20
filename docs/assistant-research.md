# AI Assistant Research Tools

The BioNodulo AI assistant can search and resolve the scholarly literature
directly from chat. All sources are free and keyless — no API keys are
required anywhere (PubMed optionally accepts an email parameter for
politeness).

## Tools

| Tool | Source | Returns |
| --- | --- | --- |
| `literature_search(query, max_results, year_from)` | OpenAlex | Title, first 3 authors, year, venue, DOI, citation count, open-access PDF, abstract |
| `pubmed_search(query, max_results, email)` | NCBI E-utilities | PMID, title, authors, journal, year, DOI |
| `arxiv_search(query, max_results)` | arXiv API | arXiv id, title, authors, published, summary, PDF URL |
| `get_paper(identifier)` | routed automatically | Metadata card + abstract for a DOI, arXiv id, or PMID |
| `citation_lookup(doi)` | OpenAlex | Cited-by count, references count, top 5 citing works |

`search_literature` (PubMed with abstracts and free full-text links) predates
this group and remains available; reach for `pubmed_search` when a lightweight
biomedical search is enough, and `literature_search`/`arxiv_search` for
cross-field or very recent work.

`get_paper` routes identifiers automatically: `10.xxxx/...` (or a
`https://doi.org/...` URL) goes to OpenAlex, `2401.12345`-style ids go to
arXiv, and bare numbers go to PubMed.

`citation_lookup` complements the workflow `CITATION_DOIS` export: DOIs
collected from a run's tool citations can be enriched with live citation
counts and the most influential citing works.

## Behavior

- Handlers are async and share one `httpx.AsyncClient` per call (30 s
  timeout).
- Requests are throttled per host (OpenAlex ~10 req/s, NCBI 3 req/s, arXiv one
  request per 3 s) in the spirit of the nim_family rate limiting.
- API failures return structured `{"error": ...}` results rather than raising,
  so the assistant can report the failure and continue.
- Parsing is stdlib-only: JSON plus `xml.etree` for the arXiv Atom feed and
  PubMed abstracts — no new runtime dependencies.

Implementation: `bionodulo/ai/research_tools.py`, registered in
`bionodulo/ai/tools.py`; tests in `tests/ai/test_research_tools.py`.
