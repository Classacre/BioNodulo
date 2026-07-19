"""KEGG REST pathway, gene, and compound text queries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


KEGG_BASE_URL = "https://rest.kegg.jp"
KEGG_API_MANUAL_URL = "https://www.kegg.jp/kegg/rest/keggapi.html"
KEGG_API_POLICY_URL = "https://www.kegg.jp/kegg/rest/"
KEGG_LEGAL_URL = "https://www.kegg.jp/kegg/legal.html"
KEGG_SOURCE_REVISION = "2026-07-20"
KEGG_API_MANUAL_SHA256 = "702ac03a09ad800cbc3ec689ad6788ceffc336b441166876b7ffd6a5cc645d2f"
KEGG_API_POLICY_SHA256 = "789b45cf28fb2e6951fbfc6fec476ac9d1e2835d02c2efdc084967055f887872"
KEGG_LEGAL_SHA256 = "b87105e6251b08a2cd0f0208ee4615d021fe448f4ad46983eb7b576358ddd8e7"
KEGG_USER_AGENT = "BioNodulo/2.0 (KEGG REST node)"
KEGG_API_CACHE = APICache.from_environment(default_ttl_seconds=300.0)
KEGG_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=3.0, burst=1)
QUERY_TYPES = (
    "pathway_info",
    "pathway_genes",
    "list_pathways",
    "gene_info",
    "find_genes",
    "compound_info",
    "find_compounds",
    "link_kegg",
)
KEGG_ORGANISMS = ("hsa", "mmu", "rno", "dre", "cel", "dme", "sce", "ath", "eco")
TABLE_QUERY_TYPES = {"pathway_genes", "list_pathways", "find_genes", "find_compounds", "link_kegg"}


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output = base / node.NODE_ID
    output.mkdir(parents=True, exist_ok=True)
    return output


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "kegg"


def _normalise_pathway_id(query: str, organism: str) -> str:
    text = str(query or "").strip()
    if text.startswith("path:"):
        text = text.split(":", 1)[1]
    return f"{organism}{text}" if re.fullmatch(r"\d{5}", text) else text


def _normalise_gene_id(query: str, organism: str) -> str:
    text = str(query or "").strip()
    return text if not text or ":" in text else f"{organism}:{text}"


def _resource_for(query: str, query_type: str, organism: str) -> tuple[str, str]:
    if query_type == "pathway_genes":
        effective = _normalise_pathway_id(query, organism)
        return f"link/{quote(organism, safe='')}/{quote(effective, safe=':')}", effective
    if query_type == "list_pathways":
        return f"list/pathway/{quote(organism, safe='')}", f"pathway:{organism}"
    if query_type == "gene_info":
        effective = _normalise_gene_id(query, organism)
        return f"get/{quote(effective, safe=':')}", effective
    if query_type == "find_genes":
        effective = str(query or "").strip().replace(" ", "+")
        return f"find/{quote(organism, safe='')}/{quote(effective, safe='+')}", effective
    if query_type == "compound_info":
        effective = str(query or "").strip()
        if effective and not effective.startswith("cpd:"):
            effective = f"cpd:{effective}"
        return f"get/{quote(effective, safe=':')}", effective
    if query_type == "find_compounds":
        effective = str(query or "").strip().replace(" ", "+")
        return f"find/compound/{quote(effective, safe='+')}", effective
    if query_type == "link_kegg":
        effective = "+".join(part for part in re.split(r"[\s,]+", str(query or "").strip()) if part)
        return f"link/pathway/{quote(effective, safe=':+')}", effective
    effective = _normalise_pathway_id(query, organism)
    return f"get/{quote(effective, safe=':')}", effective


async def _request_text(resource: str) -> str:
    url = f"{KEGG_BASE_URL}/{resource.lstrip('/')}"
    client = APIHttpClient(cache=KEGG_API_CACHE, rate_limiter=KEGG_RATE_LIMITER)
    try:
        response = await client.request(
            "GET",
            url,
            headers={"User-Agent": KEGG_USER_AGENT},
            timeout=30.0,
            retries=3,
            retry_delay=1.0,
            cache_ttl=300.0,
        )
        return response.text
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"KEGG {resource} failed with HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"KEGG {resource} request failed: {exc}") from exc


def _parse_table(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        left, separator, right = line.partition("\t")
        if separator:
            rows.append({"id": left.strip(), "value": right.strip()})
    return rows


def _append_field(entry: dict[str, Any], field: str, value: str) -> None:
    if field not in entry:
        entry[field] = value
    elif isinstance(entry[field], list):
        entry[field].append(value)
    else:
        entry[field] = [entry[field], value]


def _parse_flat_file(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    current_field = ""
    for line in text.splitlines():
        if line.strip() == "///":
            if current:
                entries.append(current)
            current = {}
            current_field = ""
            continue
        if not line.strip():
            continue
        field = line[:12].strip()
        value = line[12:].strip() if len(line) > 12 else ""
        if field:
            current_field = field
            _append_field(current, field, value)
        elif current_field and value:
            previous = current.get(current_field, "")
            if isinstance(previous, list):
                previous[-1] = f"{previous[-1]} {value}".strip()
            else:
                current[current_field] = f"{previous} {value}".strip()
    if current:
        entries.append(current)
    return entries


def _to_tsv(entries: list[dict[str, Any]], tabular: bool) -> str:
    if not entries:
        return "# No entries found\n"
    if tabular:
        return "id\tvalue\n" + "".join(f"{row.get('id', '')}\t{row.get('value', '')}\n" for row in entries)
    keys = sorted({key for row in entries for key in row})
    lines = ["\t".join(keys)]
    for row in entries:
        values = []
        for key in keys:
            value = row.get(key, "")
            if isinstance(value, list):
                value = "; ".join(str(item) for item in value)
            values.append(str(value).replace("\t", " ").replace("\n", " "))
        lines.append("\t".join(values))
    return "\n".join(lines) + "\n"


class KEGGPathwayNode(BaseNode):
    """Query documented KEGG REST text endpoints without undeclared image artifacts."""

    NODE_ID = "kegg_pathway"
    DISPLAY_NAME = "KEGG Pathway"
    CATEGORY = "api"
    DESCRIPTION = "Query KEGG REST pathway, gene, and compound text endpoints."
    SEARCH_ALIASES = ["KEGG", "pathway", "gene", "compound", "metabolism", "REST"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("pathway_data", "gene_list_tsv")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = f"KEGG REST {KEGG_SOURCE_REVISION} contract snapshot"
    SOURCE_URL = KEGG_API_MANUAL_URL
    SOURCE_REVISION = KEGG_SOURCE_REVISION
    SOURCE_SHA256 = KEGG_API_MANUAL_SHA256
    DOCUMENTATION_URL = SOURCE_URL
    POLICY_SOURCE_URL = KEGG_API_POLICY_URL
    POLICY_SOURCE_SHA256 = KEGG_API_POLICY_SHA256
    LICENSE_SOURCE_URL = KEGG_LEGAL_URL
    LICENSE_SOURCE_SHA256 = KEGG_LEGAL_SHA256
    UPSTREAM_SOURCE = "KEGG API naming conventions, status codes, and get/list/find/link operations"
    EXIT_SEMANTICS = "HTTP 400/404 and exhausted transport/server failures are fatal; empty successful searches are valid."
    RATE_LIMIT_SEMANTICS = "Requests are limited to the KEGG-documented maximum of three per second."
    LICENSE_SEMANTICS = (
        "KEGG REST is provided for academic use; commercial use and redistribution may require a KEGG subscription/license."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("STRING", {"default": "", "description": "Pathway ID, gene ID, compound ID, keyword, or ID list"}),
                "query_type": ("STRING", {"default": "pathway_info", "options": list(QUERY_TYPES)}),
            },
            "optional": {
                "organism": ("STRING", {"default": "hsa", "options": list(KEGG_ORGANISMS)}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        query_type = str(kwargs.get("query_type", "pathway_info") or "pathway_info")
        if query_type not in QUERY_TYPES:
            raise ValueError(f"Unsupported KEGG query_type: {query_type}")
        query = str(kwargs.get("query", "") or "").strip()
        if not query and query_type != "list_pathways":
            raise ValueError("KEGG Pathway requires a non-empty query")
        organism = str(kwargs.get("organism", "hsa") or "hsa").strip()
        resource, effective_query = _resource_for(query, query_type, organism)
        raw = await _request_text(resource)
        entries = _parse_table(raw) if query_type in TABLE_QUERY_TYPES else _parse_flat_file(raw)
        payload = {
            "query": query,
            "effective_query": effective_query,
            "query_type": query_type,
            "organism": organism,
            "resource": resource,
            "raw": raw,
            "entries": entries,
        }
        output = _node_output_dir(self, context)
        stem = _safe_filename(str(kwargs.get("output_name", "") or effective_query or query_type))
        json_path = output / f"{stem}.json"
        tsv_path = output / f"{stem}.tsv"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tsv_path.write_text(_to_tsv(entries, query_type in TABLE_QUERY_TYPES), encoding="utf-8")
        return {"outputs": {"pathway_data": str(json_path), "gene_list_tsv": str(tsv_path)}}
