"""Literature/research tools for the BioNodulo AI assistant.

Free, keyless scholarly APIs — no credentials required anywhere:

- OpenAlex (https://api.openalex.org): broad citation-index search, single-work
  lookup by DOI, and citation graphs (citing works, references).
- NCBI E-utilities (PubMed): biomedical literature search and metadata.
- arXiv (export.arxiv.org/api/query): preprint search and lookup.
- Europe PMC (www.ebi.ac.uk/europepmc): biomedical literature including
  bioRxiv/medRxiv preprints (per-result ``source`` field).
- ClinicalTrials.gov v2: clinical study search (NCT id, status, phase, sponsor).

All handlers are async, share one ``httpx.AsyncClient`` per call with a 30 s
timeout, throttle per host (a simple minimum-interval delay in the spirit of
the nim_family token bucket), and return structured ``{"error": ...}`` dicts
instead of raising on API failures. Parsing is stdlib-only: JSON plus
``xml.etree`` for the arXiv Atom feed and PubMed abstracts.

``_TRANSPORT`` and ``_SLEEP`` are module-level seams for tests: a
``httpx.MockTransport`` swaps out the network, and a no-op sleep removes the
throttle delay.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

from bionodulo.ai.tools import ToolContext, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 30.0
USER_AGENT = "BioNodulo/2.0 (AI assistant research tools; mailto:bionodulo@users.noreply.github.com)"

OPENALEX_BASE = "https://api.openalex.org"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ARXIV_BASE = "https://export.arxiv.org/api/query"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
CLINICALTRIALS_BASE = "https://clinicaltrials.gov/api/v2"

#: Minimum seconds between requests to the same host. OpenAlex's polite pool
#: allows ~10 req/s, NCBI 3 req/s without a key, and arXiv asks for ~3 s.
_HOST_MIN_INTERVAL_S = {
    "api.openalex.org": 0.1,
    "eutils.ncbi.nlm.nih.gov": 0.34,
    "export.arxiv.org": 3.0,
    "www.ebi.ac.uk": 0.34,
    "clinicaltrials.gov": 0.34,
}
_DEFAULT_MIN_INTERVAL_S = 0.5

# Test seams: a MockTransport replaces the network; a no-op replaces the sleep.
_TRANSPORT: httpx.BaseTransport | None = None
_SLEEP = asyncio.sleep

_last_request_at: dict[str, float] = {}


async def _throttle(url: str) -> None:
    """Enforce the per-host minimum interval before a request."""
    host = httpx.URL(url).host
    interval = _HOST_MIN_INTERVAL_S.get(host, _DEFAULT_MIN_INTERVAL_S)
    last = _last_request_at.get(host)
    now = time.monotonic()
    if last is not None:
        wait = interval - (now - last)
        if wait > 0:
            await _SLEEP(wait)
    _last_request_at[host] = time.monotonic()


def _new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_S,
        transport=_TRANSPORT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET JSON with throttling; raises httpx.HTTPError on failure."""
    await _throttle(url)
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


async def _get_text(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> str:
    await _throttle(url)
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.text


def _clamp_count(value: Any, default: int, maximum: int) -> int:
    try:
        count = int(value) if value is not None else default
    except (TypeError, ValueError):
        count = default
    return max(1, min(count, maximum))


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------


def _openalex_abstract(work: dict[str, Any]) -> str:
    """Rebuild plain-text abstract from OpenAlex's abstract_inverted_index."""
    index = work.get("abstract_inverted_index")
    if not isinstance(index, dict) or not index:
        return ""
    positions: dict[int, str] = {}
    for word, offsets in index.items():
        for offset in offsets or []:
            try:
                positions[int(offset)] = str(word)
            except (TypeError, ValueError):
                continue
    return " ".join(positions[i] for i in sorted(positions))


def _openalex_card(work: dict[str, Any], *, abstract: bool = True) -> dict[str, Any]:
    authors = [
        str((a.get("author") or {}).get("display_name") or "")
        for a in (work.get("authorships") or [])[:3]
        if isinstance(a, dict)
    ]
    authors = [a for a in authors if a]
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    open_access = work.get("open_access") or {}
    doi = str(work.get("doi") or "")
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    card: dict[str, Any] = {
        "openalex_id": work.get("id", ""),
        "title": work.get("title") or work.get("display_name") or "",
        "authors": authors,
        "year": work.get("publication_year"),
        "venue": source.get("display_name") or "",
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else "",
        "citation_count": work.get("cited_by_count", 0),
        "open_access_pdf": open_access.get("oa_url") or "",
    }
    if abstract:
        card["abstract"] = _openalex_abstract(work)
    return card


async def _literature_search(
    ctx: ToolContext,
    query: str,
    max_results: int | None = 10,
    year_from: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search OpenAlex for works matching a free-text query."""
    count = _clamp_count(max_results, 10, 50)
    filters: list[str] = []
    if year_from is not None:
        try:
            filters.append(f"from_publication_date:{int(year_from)}-01-01")
        except (TypeError, ValueError):
            return {"error": f"year_from must be an integer year, got {year_from!r}", "query": query}
    params: dict[str, Any] = {"search": query, "per-page": count}
    if filters:
        params["filter"] = ",".join(filters)
    try:
        async with _new_client() as client:
            payload = await _get_json(client, f"{OPENALEX_BASE}/works", params=params)
    except Exception as exc:
        return {"error": f"OpenAlex search failed: {exc}", "query": query}
    works = payload.get("results") or []
    results = [_openalex_card(w) for w in works if isinstance(w, dict)]
    return {"query": query, "year_from": year_from, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# PubMed (NCBI E-utilities)
# ---------------------------------------------------------------------------


def _pubmed_entry_card(pmid: str, entry: dict[str, Any]) -> dict[str, Any]:
    doi = ""
    for article_id in entry.get("articleids", []) or []:
        if article_id.get("idtype") == "doi" and not doi:
            doi = article_id.get("value", "")
    return {
        "pmid": pmid,
        "title": entry.get("title", ""),
        "authors": [a.get("name", "") for a in (entry.get("authors") or [])][:6],
        "journal": entry.get("fulljournalname") or entry.get("source", ""),
        "year": (entry.get("pubdate", "") or "")[:4],
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _pubmed_abstracts_from_xml(xml_text: str) -> dict[str, str]:
    """PMID -> abstract text parsed from an efetch PubmedArticleSet."""
    abstracts: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return abstracts
    for article in root.iter("PubmedArticle"):
        pmid_el = article.find("./MedlineCitation/PMID")
        if pmid_el is None or not (pmid_el.text or "").strip():
            continue
        parts = []
        for abstext in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
            text = "".join(abstext.itertext()).strip()
            if not text:
                continue
            label = abstext.get("Label")
            parts.append(f"{label}: {text}" if label else text)
        abstract = "\n".join(parts).strip()
        if abstract:
            abstracts[pmid_el.text.strip()] = abstract[:4000]
    return abstracts


async def _pubmed_search(
    ctx: ToolContext,
    query: str,
    max_results: int | None = 10,
    email: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search PubMed via NCBI E-utilities (esearch + esummary)."""
    count = _clamp_count(max_results, 10, 50)
    extra = {"email": email} if email else {}
    try:
        async with _new_client() as client:
            search = await _get_json(
                client,
                f"{NCBI_BASE}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": count, "retmode": "json", **extra},
            )
            ids = (search.get("esearchresult", {}) or {}).get("idlist", []) or []
            if not ids:
                return {"query": query, "results": [], "count": 0}
            summary = await _get_json(
                client,
                f"{NCBI_BASE}/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json", **extra},
            )
    except Exception as exc:
        return {"error": f"PubMed search failed: {exc}", "query": query}
    payload = summary.get("result", {}) or {}
    results = [_pubmed_entry_card(pmid, payload.get(pmid) or {}) for pmid in ids]
    return {"query": query, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _arxiv_cards_from_xml(xml_text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    cards: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", _ARXIV_NS):
        raw_id = (entry.findtext("atom:id", default="", namespaces=_ARXIV_NS) or "").strip()
        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
        title = " ".join((entry.findtext("atom:title", default="", namespaces=_ARXIV_NS) or "").split())
        summary = " ".join((entry.findtext("atom:summary", default="", namespaces=_ARXIV_NS) or "").split())
        published = (entry.findtext("atom:published", default="", namespaces=_ARXIV_NS) or "").strip()
        authors = [
            (a.findtext("atom:name", default="", namespaces=_ARXIV_NS) or "").strip()
            for a in entry.findall("atom:author", _ARXIV_NS)
        ]
        pdf_url = ""
        for link in entry.findall("atom:link", _ARXIV_NS):
            if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
                break
        cards.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": [a for a in authors if a],
                "published": published,
                "summary": summary[:4000],
                "pdf_url": pdf_url,
                "url": raw_id,
            }
        )
    return cards


async def _arxiv_search(
    ctx: ToolContext,
    query: str,
    max_results: int | None = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search the arXiv API (Atom feed parsed with stdlib xml.etree)."""
    count = _clamp_count(max_results, 10, 50)
    try:
        async with _new_client() as client:
            text = await _get_text(
                client,
                ARXIV_BASE,
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": count,
                    "sortBy": "relevance",
                },
            )
    except Exception as exc:
        return {"error": f"arXiv search failed: {exc}", "query": query}
    results = _arxiv_cards_from_xml(text)
    return {"query": query, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Europe PMC (covers PubMed + bioRxiv/medRxiv preprints)
# ---------------------------------------------------------------------------


def _europepmc_card(entry: dict[str, Any]) -> dict[str, Any]:
    source = str(entry.get("source") or "")
    entry_id = str(entry.get("id") or "")
    return {
        "id": entry_id,
        "source": source,  # MED = PubMed, PMC, PPR = preprint (bioRxiv/medRxiv), ...
        "pmid": entry.get("pmid") or "",
        "doi": entry.get("doi") or "",
        "title": entry.get("title") or "",
        "authors": str(entry.get("authorString") or "").split(", ")[:6] if entry.get("authorString") else [],
        "journal": entry.get("journalTitle") or "",
        "year": entry.get("pubYear") or "",
        "abstract": (entry.get("abstractText") or "")[:4000],
        "is_open_access": entry.get("isOpenAccess") == "Y",
        "url": f"https://europepmc.org/article/{source}/{entry_id}" if source and entry_id else "",
    }


async def _europepmc_search(
    ctx: ToolContext,
    query: str,
    max_results: int | None = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search Europe PMC (keyless), which also indexes bioRxiv/medRxiv preprints."""
    count = _clamp_count(max_results, 10, 50)
    try:
        async with _new_client() as client:
            payload = await _get_json(
                client,
                f"{EUROPEPMC_BASE}/search",
                params={"query": query, "format": "json", "pageSize": count},
            )
    except Exception as exc:
        return {"error": f"Europe PMC search failed: {exc}", "query": query}
    entries = (payload.get("resultList") or {}).get("result") or []
    results = [_europepmc_card(e) for e in entries if isinstance(e, dict)]
    return {"query": query, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# ClinicalTrials.gov (API v2)
# ---------------------------------------------------------------------------


def _clinicaltrials_card(study: dict[str, Any]) -> dict[str, Any]:
    protocol = study.get("protocolSection") or {}
    identification = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    sponsor = protocol.get("sponsorCollaboratorsModule") or {}
    nct_id = identification.get("nctId") or ""
    phases = design.get("phases") or []
    return {
        "nct_id": nct_id,
        "title": identification.get("briefTitle") or identification.get("officialTitle") or "",
        "status": status.get("overallStatus") or "",
        "phase": ", ".join(str(p) for p in phases),
        "sponsor": (sponsor.get("leadSponsor") or {}).get("name") or "",
        "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
    }


async def _clinicaltrials_search(
    ctx: ToolContext,
    query: str,
    max_results: int | None = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search ClinicalTrials.gov (API v2, keyless) for clinical studies."""
    count = _clamp_count(max_results, 10, 50)
    try:
        async with _new_client() as client:
            payload = await _get_json(
                client,
                f"{CLINICALTRIALS_BASE}/studies",
                params={"query.term": query, "pageSize": count},
            )
    except Exception as exc:
        return {"error": f"ClinicalTrials.gov search failed: {exc}", "query": query}
    studies = payload.get("studies") or []
    results = [_clinicaltrials_card(s) for s in studies if isinstance(s, dict)]
    return {"query": query, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Identifier routing: get_paper / citation_lookup
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})(v\d+)?$", re.IGNORECASE)
_PMID_RE = re.compile(r"^\d{1,9}$")


def _classify_identifier(identifier: str) -> tuple[str, str]:
    """Return (kind, normalized) for a DOI, arXiv id, or PMID."""
    value = str(identifier or "").strip()
    lowered = value.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            return "doi", value[len(prefix):].strip()
    if lowered.startswith("arxiv:"):
        return "arxiv", value.split(":", 1)[1].strip()
    if _DOI_RE.match(value):
        return "doi", value
    if _ARXIV_ID_RE.match(value):
        return "arxiv", value
    if _PMID_RE.match(value):
        return "pmid", value
    return "unknown", value


async def _paper_by_doi(client: httpx.AsyncClient, doi: str) -> dict[str, Any]:
    encoded = quote(f"https://doi.org/{doi}", safe="")
    work = await _get_json(client, f"{OPENALEX_BASE}/works/{encoded}")
    card = _openalex_card(work)
    card["identifier_type"] = "doi"
    return card


async def _paper_by_arxiv(client: httpx.AsyncClient, arxiv_id: str) -> dict[str, Any]:
    text = await _get_text(client, ARXIV_BASE, params={"id_list": arxiv_id, "max_results": 1})
    cards = _arxiv_cards_from_xml(text)
    if not cards:
        return {"error": f"No arXiv paper found for id '{arxiv_id}'."}
    card = cards[0]
    card["abstract"] = card.pop("summary")
    card["identifier_type"] = "arxiv"
    return card


async def _paper_by_pmid(client: httpx.AsyncClient, pmid: str) -> dict[str, Any]:
    summary = await _get_json(
        client,
        f"{NCBI_BASE}/esummary.fcgi",
        params={"db": "pubmed", "id": pmid, "retmode": "json"},
    )
    entry = (summary.get("result", {}) or {}).get(pmid)
    if not isinstance(entry, dict) or not entry.get("title"):
        return {"error": f"No PubMed record found for PMID '{pmid}'."}
    card = _pubmed_entry_card(pmid, entry)
    xml_text = await _get_text(
        client,
        f"{NCBI_BASE}/efetch.fcgi",
        params={"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml"},
    )
    card["abstract"] = _pubmed_abstracts_from_xml(xml_text).get(pmid, "")
    card["identifier_type"] = "pmid"
    return card


async def _get_paper(ctx: ToolContext, identifier: str, **kwargs: Any) -> dict[str, Any]:
    """Resolve a DOI, arXiv id, or PMID to a metadata card plus abstract."""
    kind, value = _classify_identifier(identifier)
    if kind == "unknown":
        return {
            "error": (
                f"Could not interpret '{identifier}' as a DOI, arXiv id, or PMID. "
                "DOIs look like 10.xxxx/..., arXiv ids like 2401.12345, PMIDs are numeric."
            ),
            "identifier": identifier,
        }
    try:
        async with _new_client() as client:
            if kind == "doi":
                card = await _paper_by_doi(client, value)
            elif kind == "arxiv":
                card = await _paper_by_arxiv(client, value)
            else:
                card = await _paper_by_pmid(client, value)
    except Exception as exc:
        return {"error": f"Paper lookup failed for '{identifier}': {exc}", "identifier": identifier}
    card["identifier"] = identifier
    return card


async def _citation_lookup(ctx: ToolContext, doi: str, **kwargs: Any) -> dict[str, Any]:
    """OpenAlex citation profile for a DOI: counts and top citing works.

    Complements the workflow CITATION_DOIS export: DOIs collected from a run's
    tool citations can be enriched with live citation counts here.
    """
    kind, value = _classify_identifier(doi)
    if kind != "doi":
        return {"error": f"citation_lookup expects a DOI, got '{doi}'.", "doi": doi}
    encoded = quote(f"https://doi.org/{value}", safe="")
    try:
        async with _new_client() as client:
            work = await _get_json(client, f"{OPENALEX_BASE}/works/{encoded}")
            citing: list[dict[str, Any]] = []
            cited_by_url = work.get("cited_by_api_url") or ""
            if cited_by_url and work.get("cited_by_count"):
                # httpx replaces a URL's existing query string when ``params``
                # is given, so merge into the URL first (the cites: filter
                # embedded in cited_by_api_url must survive).
                citing_url = str(
                    httpx.URL(cited_by_url).copy_merge_params({"per-page": 5, "sort": "cited_by_count:desc"})
                )
                payload = await _get_json(client, citing_url)
                citing = [
                    _openalex_card(w, abstract=False)
                    for w in (payload.get("results") or [])[:5]
                    if isinstance(w, dict)
                ]
    except Exception as exc:
        return {"error": f"Citation lookup failed for DOI '{value}': {exc}", "doi": value}
    references = work.get("referenced_works") or []
    return {
        "doi": value,
        "title": work.get("title") or work.get("display_name") or "",
        "cited_by_count": work.get("cited_by_count", 0),
        "references_count": len(references),
        "top_citing_works": citing,
    }


RESEARCH_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        "literature_search",
        "Search OpenAlex (broad, keyless citation index covering all fields) for papers matching a query. Returns title, first authors, year, venue, DOI, citation count, open-access PDF link, and abstract. Use year_from to restrict to recent work.",
        [
            ToolParameter("query", "string", "Free-text search query"),
            ToolParameter("max_results", "integer", "Maximum works to return (<=50)", required=False, default=10),
            ToolParameter("year_from", "integer", "Only include works published from this year on", required=False, default=None),
        ],
        _literature_search,
    ),
    ToolDefinition(
        "pubmed_search",
        "Search PubMed (NCBI E-utilities, keyless) for biomedical papers. Returns PMID, title, authors, journal, year, and DOI. Prefer over literature_search for clinical/biomedical topics; use search_literature when abstracts are also needed.",
        [
            ToolParameter("query", "string", "PubMed search query"),
            ToolParameter("max_results", "integer", "Maximum papers to return (<=50)", required=False, default=10),
            ToolParameter("email", "string", "Optional contact email for NCBI politeness", required=False, default=None),
        ],
        _pubmed_search,
    ),
    ToolDefinition(
        "arxiv_search",
        "Search arXiv preprints (keyless). Returns arXiv id, title, authors, published date, summary, and PDF URL. Best for very recent methods that have not yet appeared in journals.",
        [
            ToolParameter("query", "string", "arXiv search query"),
            ToolParameter("max_results", "integer", "Maximum papers to return (<=50)", required=False, default=10),
        ],
        _arxiv_search,
    ),
    ToolDefinition(
        "europepmc_search",
        "Search Europe PMC (keyless) for biomedical papers — covers PubMed plus bioRxiv/medRxiv preprints (the per-result 'source' field distinguishes them: MED/PMC vs PPR). Returns title, authors, journal, year, DOI/PMID, abstract, and open-access flag.",
        [
            ToolParameter("query", "string", "Europe PMC search query (supports fielded syntax, e.g. TITLE:\"deseq2\")"),
            ToolParameter("max_results", "integer", "Maximum papers to return (<=50)", required=False, default=10),
        ],
        _europepmc_search,
    ),
    ToolDefinition(
        "clinicaltrials_search",
        "Search ClinicalTrials.gov (API v2, keyless) for clinical studies. Returns NCT id, title, overall status, phase, lead sponsor, and URL. Use for translational/clinical context behind a target or therapy.",
        [
            ToolParameter("query", "string", "Condition, intervention, or keyword query"),
            ToolParameter("max_results", "integer", "Maximum studies to return (<=50)", required=False, default=10),
        ],
        _clinicaltrials_search,
    ),
    ToolDefinition(
        "get_paper",
        "Resolve a paper identifier to a full metadata card with abstract. Accepts a DOI (10.xxxx/...), an arXiv id (2401.12345), or a numeric PMID; the right API is chosen automatically.",
        [ToolParameter("identifier", "string", "DOI, arXiv id, or PMID")],
        _get_paper,
    ),
    ToolDefinition(
        "citation_lookup",
        "OpenAlex citation profile for a DOI: cited-by count, number of references, and the top 5 citing works. Use to judge a paper's influence or to enrich DOIs from a run's CITATION_DOIS export.",
        [ToolParameter("doi", "string", "DOI of the work, e.g. 10.1038/s41592-021-01238-6")],
        _citation_lookup,
    ),
]


__all__ = ["RESEARCH_TOOLS"]
