"""PubMed retrieval with optional LLM query expansion and synthesis."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from bionodulo.ai.llm_backend import LLMConfig
from bionodulo.core.credentials import resolve_secret_value
from .adapter import (
    LiteLLMNode,
    _llm_config_from_kwargs,
    _messages,
    _node_output_dir,
    call_llm,
    require_artifacts,
    safe_json_parse,
    validate_choice,
)


NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


NCBI_USER_AGENT = "BioNodulo/2.0 (AI literature search node)"


NCBI_REQUEST_TIMEOUT_S = 30.0


NCBI_MAX_RETRIES = 3


def _resolve_ncbi_api_key(explicit: Any, context: Any) -> str:
    return resolve_secret_value(
        explicit, context, "ncbi_api_key", "NCBI_API_KEY", default=os.environ.get("NCBI_API_KEY", "")
    )


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


async def _request_json(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = NCBI_MAX_RETRIES,
    timeout: float = NCBI_REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.json()


async def _request_text(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = NCBI_MAX_RETRIES,
    timeout: float = NCBI_REQUEST_TIMEOUT_S,
) -> str:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.text


async def _request(endpoint: str, params: dict[str, Any], *, retries: int, timeout: float) -> httpx.Response:
    url = f"{NCBI_BASE_URL}/{endpoint}"
    clean = _clean_params(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": NCBI_USER_AGENT}) as client:
                response = await client.get(url, params=clean)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status < 500 or attempt >= retries - 1:
                body = exc.response.text[:500]
                raise RuntimeError(f"NCBI literature search failed with HTTP {status}: {body}") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise RuntimeError(f"NCBI literature search request failed: {exc}") from exc
    raise RuntimeError(f"NCBI literature search request failed: {last_error}")


class AILiteratureSearchNode(LiteLLMNode):
    """Search PubMed and synthesize biomedical literature with an LLM."""

    NODE_ID = "ai_literature_search"
    DISPLAY_NAME = "AI Literature Search"
    CATEGORY = "ai"
    DESCRIPTION = "Search PubMed for papers relevant to a research question and synthesize findings with citations."
    SEARCH_ALIASES = ["pubmed", "literature", "search", "papers", "references", "biomedical", "review", "citations"]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("papers_json", "summary_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True
    AUDIT_STATUS = "contract-checked-no-provider-execution"
    CITATION_URLS = [
        "https://www.ncbi.nlm.nih.gov/books/NBK25499/",
        "https://docs.litellm.ai/docs/completion/input",
    ]
    SOURCE_AUTHORITIES = {
        "litellm": "cc9b99c2e35795476c7a00e34a85ee0573d6d66c",
        "ncbi_eutils_revision": "2026-03-04",
        "ncbi_eutils_sha256": "69c3cbd73e1fe38484809221f46e2380cee7d5a354b7dffa2b5f612a52785ee1",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "research_question": (
                    "STRING",
                    {
                        "default": "What is known about the role of BRCA1 in ovarian cancer?",
                        "multiline": True,
                        "description": "Research question or topic to search for",
                    },
                ),
            },
            "optional": {
                "databases": (
                    "STRING",
                    {
                        "default": "pubmed",
                        "options": ["pubmed"],
                        "description": "Implemented source: PubMed through pinned NCBI E-utilities",
                    },
                ),
                "max_results": ("INT", {"default": 10, "min": 1, "max": 100}),
                "year_range": ("STRING", {"default": "", "description": "Year filter such as 2020:2026"}),
                "search_depth": ("STRING", {"default": "standard", "options": ["quick", "standard", "deep"]}),
                "include_abstracts": ("BOOLEAN", {"default": True}),
                "ncbi_api_key": ("STRING", {"default": "", "advanced": True, "password": True}),
                "email": ("STRING", {"default": "", "advanced": True}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": (
                    "STRING",
                    {"default": "", "password": True, "description": "Optional LLM API key override"},
                ),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        question = str(kwargs.get("research_question", "") or "").strip()
        if not question:
            raise ValueError("AI Literature Search requires a research_question")
        databases = validate_choice(
            kwargs.get("databases", "pubmed"),
            "databases",
            ("pubmed",),
        )
        max_results = max(1, min(int(kwargs.get("max_results", 10) or 10), 100))
        year_range = str(kwargs.get("year_range", "") or "").strip()
        search_depth = validate_choice(
            kwargs.get("search_depth", "standard"),
            "search_depth",
            ("quick", "standard", "deep"),
        )
        include_abstracts = bool(kwargs.get("include_abstracts", True))
        api_key = _resolve_ncbi_api_key(kwargs.get("ncbi_api_key", ""), context)
        email = str(kwargs.get("email", "") or os.environ.get("BIONODULO_EMAIL", "")).strip()

        config = _llm_config_from_kwargs(kwargs)
        queries, query_usage = await _literature_queries(question, search_depth, config)
        search_result = await _search_pubmed_literature(
            queries=queries,
            max_results=max_results,
            year_range=year_range,
            api_key=api_key,
            email=email,
            include_abstracts=include_abstracts,
        )

        if search_result["papers"]:
            summary, synthesis_usage = await _synthesize_literature(question, search_result["papers"], config)
        else:
            summary = "No papers found for the given research question."
            synthesis_usage = {}

        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "papers.json"
        summary_path = out_dir / "summary.txt"
        payload = {
            "research_question": question,
            "databases": databases,
            "max_results": max_results,
            "year_range": year_range,
            "search_depth": search_depth,
            "include_abstracts": include_abstracts,
            "queries_used": queries,
            "query_translations": search_result["query_translations"],
            "papers_found": len(search_result["papers"]),
            "papers": search_result["papers"],
            "summary": summary,
            "model": config.model,
            "usage": {"query_generation": query_usage, "synthesis": synthesis_usage},
            "papers_json_path": str(json_path),
            "summary_path": str(summary_path),
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary_path.write_text(summary, encoding="utf-8")
        require_artifacts(json_path, summary_path)
        return {"outputs": {"papers_json": payload, "summary_text": summary}}


async def _literature_queries(question: str, search_depth: str, config: LLMConfig) -> tuple[list[str], dict[str, Any]]:
    desired = {"quick": 1, "standard": 3, "deep": 5}.get(search_depth, 3)
    prompt = (
        f"Research question:\n{question}\n\n"
        f"Generate up to {desired} PubMed search queries that cover the question with precise biomedical terms. "
        "Return a JSON object with a queries array. Each item must be a valid PubMed search query."
    )
    response = await call_llm(
        config,
        _messages(
            system_prompt="You are a biomedical literature search expert. Generate concise PubMed queries only.",
            prompt=prompt,
        ),
        json_mode=True,
    )
    parsed = safe_json_parse(response.content)
    queries = _normalise_literature_queries(parsed, question, desired)
    return queries, response.usage


def _normalise_literature_queries(parsed: dict[str, Any], question: str, max_queries: int) -> list[str]:
    raw_queries: Any = parsed.get("queries", []) if isinstance(parsed, dict) else []
    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]
    queries: list[str] = []
    if isinstance(raw_queries, list):
        for raw_query in raw_queries:
            query = str(raw_query or "").strip()
            if query and query not in queries:
                queries.append(query)
            if len(queries) >= max_queries:
                break
    return queries or [question]


async def _search_pubmed_literature(
    *,
    queries: list[str],
    max_results: int,
    year_range: str,
    api_key: str,
    email: str,
    include_abstracts: bool,
) -> dict[str, Any]:
    papers_by_pmid: dict[str, dict[str, Any]] = {}
    query_translations: list[str] = []
    for query in queries:
        if len(papers_by_pmid) >= max_results:
            break
        remaining = max_results - len(papers_by_pmid)
        search_payload = await _request_json(
            "esearch.fcgi",
            _pubmed_esearch_params(
                query=query,
                max_results=remaining,
                year_range=year_range,
                api_key=api_key,
                email=email,
            ),
        )
        result = search_payload.get("esearchresult", {})
        translation = str(result.get("querytranslation", "") or "")
        if translation:
            query_translations.append(translation)
        pmids = [str(item) for item in result.get("idlist", []) if str(item)]
        new_pmids = [pmid for pmid in pmids if pmid not in papers_by_pmid]
        if not new_pmids:
            continue
        summaries = await _pubmed_summaries(new_pmids, api_key=api_key, email=email)
        abstracts = await _pubmed_abstracts(new_pmids, api_key=api_key, email=email) if include_abstracts else {}
        for pmid in new_pmids:
            summary = summaries.get(pmid, {})
            if not summary:
                continue
            paper = _paper_from_summary(pmid, summary)
            paper["abstract"] = abstracts.get(pmid, "")
            papers_by_pmid[pmid] = paper
            if len(papers_by_pmid) >= max_results:
                break
    return {"papers": list(papers_by_pmid.values())[:max_results], "query_translations": query_translations}


def _pubmed_esearch_params(
    *,
    query: str,
    max_results: int,
    year_range: str,
    api_key: str,
    email: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance",
        "tool": "bionodulo",
        "email": email,
    }
    start, end = _parse_year_range(year_range)
    if start and end:
        params.update({"mindate": start, "maxdate": end, "datetype": "pdat"})
    if api_key:
        params["api_key"] = api_key
    return params


async def _pubmed_summaries(pmids: list[str], *, api_key: str, email: str) -> dict[str, dict[str, Any]]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "tool": "bionodulo",
        "email": email,
    }
    if api_key:
        params["api_key"] = api_key
    payload = await _request_json("esummary.fcgi", params)
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return {}
    summaries: dict[str, dict[str, Any]] = {}
    for pmid in pmids:
        item = result.get(pmid, {})
        if isinstance(item, dict):
            summaries[pmid] = item
    return summaries


async def _pubmed_abstracts(pmids: list[str], *, api_key: str, email: str) -> dict[str, str]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
        "tool": "bionodulo",
        "email": email,
    }
    if api_key:
        params["api_key"] = api_key
    return _parse_pubmed_abstracts(await _request_text("efetch.fcgi", params))


def _parse_pubmed_abstracts(xml_text: str) -> dict[str, str]:
    if not str(xml_text or "").strip():
        return {}
    root = ET.fromstring(xml_text)
    abstracts: dict[str, str] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = "".join(article.findtext(".//PMID", default="").split())
        if not pmid:
            continue
        parts = []
        for abstract_text in article.findall(".//AbstractText"):
            label = abstract_text.attrib.get("Label", "")
            text = "".join(abstract_text.itertext()).strip()
            if text:
                parts.append(f"{label}: {text}" if label else text)
        abstracts[pmid] = " ".join(parts)[:2500]
    return abstracts


def _paper_from_summary(pmid: str, summary: dict[str, Any]) -> dict[str, Any]:
    authors = summary.get("authors", [])
    author_names = []
    if isinstance(authors, list):
        author_names = [str(author.get("name", "")).strip() for author in authors if isinstance(author, dict)]
    doi = _extract_doi(str(summary.get("elocationid", "") or ""))
    pubdate = str(summary.get("pubdate", "") or "")
    return {
        "pmid": pmid,
        "title": str(summary.get("title", "") or ""),
        "journal": str(summary.get("fulljournalname") or summary.get("source") or ""),
        "year": _extract_year(pubdate),
        "pubdate": pubdate,
        "authors": [name for name in author_names if name][:5],
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _parse_year_range(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if ":" not in text:
        return "", ""
    start, end = [part.strip() for part in text.split(":", 1)]
    return (start, end) if start and end else ("", "")


def _extract_year(value: str) -> str:
    for token in str(value or "").replace("/", " ").split():
        if len(token) >= 4 and token[:4].isdigit():
            return token[:4]
    return ""


def _extract_doi(value: str) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("doi:"):
        return text[4:].strip()
    return text


async def _synthesize_literature(
    question: str,
    papers: list[dict[str, Any]],
    config: LLMConfig,
) -> tuple[str, dict[str, Any]]:
    response = await call_llm(
        config,
        _messages(
            system_prompt=(
                "You are a biomedical research assistant. Synthesize only the supplied papers, cite PMIDs, "
                "and distinguish strong evidence from gaps."
            ),
            prompt=_literature_synthesis_prompt(question, papers),
        ),
        json_mode=False,
    )
    return response.content, response.usage


def _literature_synthesis_prompt(question: str, papers: list[dict[str, Any]]) -> str:
    return (
        f"Research question: {question}\n\n"
        "Relevant papers:\n"
        f"{_literature_context(papers)}\n\n"
        "Write a concise synthesis with: overview, key findings with PMID citations, limitations or contradictions, "
        "and suggested next research steps."
    )


def _literature_context(papers: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    total = 0
    for paper in papers:
        block = (
            f"[PMID:{paper.get('pmid', '')}] {paper.get('title', '')} "
            f"({paper.get('year', '')}; {paper.get('journal', '')})\n"
            f"Authors: {', '.join(paper.get('authors', []))}\n"
            f"Abstract: {str(paper.get('abstract', ''))[:900]}"
        )
        if total + len(block) > 10000:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)
