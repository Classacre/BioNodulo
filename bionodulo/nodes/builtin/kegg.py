"""KEGG REST API integration nodes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


KEGG_BASE_URL = "https://rest.kegg.jp"
KEGG_USER_AGENT = "BioNodulo/2.0 (workflow node; KEGG REST)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
KEGG_CACHE_TTL_S = 300.0
KEGG_RATE_LIMIT_PER_SECOND = 3.0
KEGG_API_CACHE = APICache(ttl_seconds=KEGG_CACHE_TTL_S)
KEGG_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=KEGG_RATE_LIMIT_PER_SECOND, burst=1)
QUERY_TYPES = (
    "pathway_info",
    "pathway_genes",
    "pathway_image",
    "list_pathways",
    "gene_info",
    "find_genes",
    "compound_info",
    "find_compounds",
    "link_kegg",
)
KEGG_ORGANISMS = ("hsa", "mmu", "rno", "dre", "cel", "dme", "sce", "ath", "eco")


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or "kegg"


async def _request_text(
    resource: str,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _request(resource, retries=retries, timeout=timeout)
    return response.text


async def _request(resource: str, *, retries: int, timeout: float) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{KEGG_BASE_URL}/{resource}"
    client = APIHttpClient(cache=KEGG_API_CACHE, rate_limiter=KEGG_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            headers={"User-Agent": KEGG_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=KEGG_CACHE_TTL_S,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"KEGG {resource} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"KEGG {resource} request failed: {exc}") from exc


async def _download_file(
    url: str,
    path: Path,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> None:
    client = APIHttpClient(cache=KEGG_API_CACHE, rate_limiter=KEGG_RATE_LIMITER)
    try:
        response = await client.request(
            "GET",
            url,
            headers={"User-Agent": KEGG_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=KEGG_CACHE_TTL_S,
            follow_redirects=True,
        )
        path.write_bytes(response.content)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise RuntimeError(f"KEGG pathway image download failed with HTTP {status}: {url}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"KEGG pathway image download failed: {url}: {exc}") from exc


def _normalise_pathway_id(query: str, organism: str) -> str:
    text = str(query or "").strip()
    if text.startswith("path:"):
        text = text.split(":", 1)[1]
    if re.fullmatch(r"[a-z]{3}\d{5}", text):
        return text
    if re.fullmatch(r"\d{5}", text):
        return f"{organism}{text}"
    return text


def _resource_for(query: str, query_type: str, organism: str) -> tuple[str, str]:
    if query_type == "pathway_genes":
        pathway_id = _normalise_pathway_id(query, organism)
        return f"link/genes/{pathway_id}", pathway_id
    if query_type == "list_pathways":
        return f"list/pathway/{organism}", f"pathway:{organism}"
    if query_type == "gene_info":
        gene_id = str(query or "").strip()
        return f"get/{gene_id}", gene_id
    if query_type == "find_genes":
        term = str(query or "").strip().replace(" ", "+")
        return f"find/{organism}/{term}", term
    if query_type == "compound_info":
        compound_id = str(query or "").strip()
        if compound_id and not compound_id.startswith("cpd:"):
            compound_id = f"cpd:{compound_id}"
        return f"get/{compound_id}", compound_id
    if query_type == "find_compounds":
        term = str(query or "").strip().replace(" ", "+")
        return f"find/compound/{term}", term
    if query_type == "link_kegg":
        source = str(query or "").strip().replace(",", "+").replace(" ", "+")
        return f"link/pathway/{source}", source
    if query_type == "pathway_image":
        pathway_id = _normalise_pathway_id(query, organism)
        return f"get/{pathway_id}", pathway_id
    pathway_id = _normalise_pathway_id(query, organism)
    return f"get/{pathway_id}", pathway_id


def _parse_table(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        left, sep, right = line.partition("\t")
        if sep:
            entries.append({"id": left.strip(), "value": right.strip()})
    return entries


def _append_field(entry: dict[str, Any], field: str, value: str) -> None:
    if field in entry:
        current = entry[field]
        if isinstance(current, list):
            current.append(value)
        else:
            entry[field] = [current, value]
    else:
        entry[field] = value


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
            existing = current.get(current_field, "")
            if isinstance(existing, list) and existing:
                existing[-1] = f"{existing[-1]} {value}".strip()
            else:
                current[current_field] = f"{existing} {value}".strip()
    if current:
        entries.append(current)
    return entries


def _parse_kegg_text(text: str, query_type: str) -> dict[str, Any]:
    if query_type in {"pathway_genes", "list_pathways", "link_kegg", "find_genes", "find_compounds"}:
        entries: list[dict[str, Any]] = _parse_table(text)
    else:
        entries = _parse_flat_file(text)
    return {
        "raw": text,
        "entries": entries,
    }


def _kegg_to_tsv(data: dict[str, Any], query_type: str) -> str:
    entries = data.get("entries", [])
    if not isinstance(entries, list) or not entries:
        return "# No entries found\n"
    if query_type in {"pathway_genes", "list_pathways", "link_kegg", "find_genes", "find_compounds"}:
        lines = ["id\tvalue"]
        for entry in entries:
            if isinstance(entry, dict):
                lines.append(f"{entry.get('id', '')}\t{entry.get('value', '')}")
        return "\n".join(lines) + "\n"

    keys = sorted({key for entry in entries if isinstance(entry, dict) for key in entry})
    lines = ["\t".join(keys)]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        values: list[str] = []
        for key in keys:
            value = entry.get(key, "")
            if isinstance(value, list):
                value = "; ".join(str(item) for item in value)
            values.append(str(value).replace("\t", " ").replace("\n", " "))
        lines.append("\t".join(values))
    return "\n".join(lines) + "\n"


class KEGGPathwayNode(BaseNode):
    """Query KEGG pathways, genes, and compounds through KEGG REST."""

    NODE_ID = "kegg_pathway"
    DISPLAY_NAME = "KEGG Pathway"
    CATEGORY = "api"
    DESCRIPTION = "Query KEGG pathways, gene lists, and pathway maps."
    SEARCH_ALIASES = ["kegg", "pathway", "metabolism", "gene", "orthology", "ko", "map"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("pathway_data", "gene_list_tsv")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://www.kegg.jp/kegg/rest/keggapi.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("STRING", {"default": "", "description": "Pathway ID, gene ID, keyword, or KEGG ID list"}),
                "query_type": ("STRING", {"default": "pathway_info", "options": list(QUERY_TYPES)}),
            },
            "optional": {
                "organism": ("STRING", {"default": "hsa", "options": list(KEGG_ORGANISMS)}),
                "download_image": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        query = str(kwargs.get("query", "") or "").strip()
        if not query and str(kwargs.get("query_type", "pathway_info")) != "list_pathways":
            raise ValueError("KEGG Pathway requires a non-empty query")
        query_type = str(kwargs.get("query_type", "pathway_info") or "pathway_info")
        if query_type not in QUERY_TYPES:
            raise ValueError(f"Unsupported KEGG query_type: {query_type}")
        organism = str(kwargs.get("organism", "hsa") or "hsa").strip() or "hsa"
        download_image = bool(kwargs.get("download_image", False))

        resource, effective_query = _resource_for(query, query_type, organism)
        text = await _request_text(resource)
        parsed = _parse_kegg_text(text, query_type)
        data = {
            "query": query,
            "effective_query": effective_query,
            "query_type": query_type,
            "organism": organism,
            "resource": resource,
            **parsed,
        }

        output_name = str(kwargs.get("output_name", "") or "").strip()
        stem = _safe_filename(output_name or effective_query or query_type)
        out_dir = _node_output_dir(self, context)
        if download_image and query_type in {"pathway_info", "pathway_image"}:
            image_path = out_dir / f"{_safe_filename(effective_query)}.png"
            image_url = f"https://www.kegg.jp/kegg/pathway/{organism}/{effective_query}.png"
            await _download_file(image_url, image_path)
            data["pathway_image"] = str(image_path)
            data["pathway_image_url"] = image_url
        json_path = out_dir / f"{stem}.json"
        tsv_path = out_dir / f"{stem}.tsv"
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tsv_path.write_text(_kegg_to_tsv(data, query_type), encoding="utf-8")

        return {
            "outputs": {
                "pathway_data": str(json_path),
                "gene_list_tsv": str(tsv_path),
            }
        }
