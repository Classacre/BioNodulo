"""STRING DB REST API integration node."""
from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


STRING_BASE_URL = "https://string-db.org/api"
STRING_USER_AGENT = "BioNodulo/2.0 (workflow node; STRING DB API)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
STRING_CACHE_TTL_S = 300.0
STRING_RATE_LIMIT_PER_SECOND = 3.0
STRING_API_CACHE = APICache.from_environment(default_ttl_seconds=STRING_CACHE_TTL_S)
STRING_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=STRING_RATE_LIMIT_PER_SECOND, burst=1)
STRING_QUERY_TYPES = ("network", "interactions", "enrichment", "mapping", "image")
NETWORK_FLAVORS = ("evidence", "confidence", "actions")


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _coerce_identifiers(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [part for part in re.split(r"[\s,;]+", text) if part]


def _dedupe_identifiers(identifiers: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for identifier in identifiers:
        if identifier not in seen:
            seen.add(identifier)
            deduped.append(identifier)
    return deduped


def _read_identifier_table(path: str | Path, column: str) -> list[str]:
    source = Path(path)
    column = str(column or "").strip()
    if not column:
        raise ValueError("id_column is required when protein_table is provided")

    with source.open(newline="", encoding="utf-8") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        if not sample.strip():
            dialect = csv.excel_tab
        else:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
            except csv.Error:
                dialect = csv.excel_tab if "\t" in sample else csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(f"Column {column!r} not found in STRING identifier table")
        return [str(row.get(column, "")).strip() for row in reader if str(row.get(column, "")).strip()]


def _string_identifier_param(identifiers: list[str]) -> str:
    return "\r".join(identifiers)


def _parse_tsv(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []
    reader = csv.DictReader(StringIO(text), delimiter="\t")
    return [dict(row) for row in reader]


async def _request_text(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _request(endpoint, params=params, retries=retries, timeout=timeout)
    return response.text


async def _request(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int,
    timeout: float,
) -> httpx.Response:
    endpoint = endpoint.lstrip("/")
    url = f"{STRING_BASE_URL}/{endpoint}"
    client = APIHttpClient(cache=STRING_API_CACHE, rate_limiter=STRING_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            params=params,
            headers={"User-Agent": STRING_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=STRING_CACHE_TTL_S,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"STRING {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"STRING {endpoint} request failed: {exc}") from exc


def _params_for(
    *,
    identifiers: list[str],
    species: int,
    query_type: str,
    required_score: int,
    network_flavor: str,
    add_nodes: int,
) -> tuple[str, dict[str, Any]]:
    base: dict[str, Any] = {
        "identifiers": _string_identifier_param(identifiers),
        "species": species,
        "caller_identity": "BioNodulo",
    }
    if query_type == "network":
        base.update({
            "required_score": required_score,
            "add_nodes": add_nodes,
            "network_flavor": network_flavor,
        })
        return "tsv/network", base
    if query_type == "interactions":
        base["required_score"] = required_score
        return "tsv/interaction_partners", base
    if query_type == "enrichment":
        return "tsv/enrichment", base
    if query_type == "mapping":
        return "tsv/get_string_ids", base
    base.update({
        "required_score": required_score,
        "add_white_nodes": add_nodes,
        "network_flavor": network_flavor,
    })
    return "image/network", base


class STRINGDBNode(BaseNode):
    """Query STRING DB for protein interaction networks and enrichment."""

    NODE_ID = "string_db"
    DISPLAY_NAME = "STRING DB"
    CATEGORY = "api"
    DESCRIPTION = "Query protein-protein interaction networks and enrichment from STRING DB."
    SEARCH_ALIASES = ["string", "ppi", "network", "interaction", "protein-protein", "enrichment"]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("interaction_network", "network_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://string-db.org/cgi/help.pl?subpage=api"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "protein_ids": ("STRING", {"default": "", "description": "Protein IDs or gene symbols as a list, JSON list, or comma-separated string"}),
            },
            "optional": {
                "species": ("INT", {"default": 9606, "min": 1, "description": "NCBI taxonomy ID"}),
                "query_type": ("STRING", {"default": "network", "options": list(STRING_QUERY_TYPES)}),
                "required_score": ("INT", {"default": 400, "min": 0, "max": 1000}),
                "network_flavor": ("STRING", {"default": "evidence", "options": list(NETWORK_FLAVORS)}),
                "add_nodes": ("INT", {"default": 0, "min": 0, "max": 50}),
                "protein_table": ("FILE", {"default": "", "description": "Optional CSV/TSV table containing protein IDs or gene symbols"}),
                "id_column": ("STRING", {"default": "", "description": "Column to read from protein_table"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        identifiers = _coerce_identifiers(kwargs.get("protein_ids", ""))
        protein_table = str(kwargs.get("protein_table", "") or "").strip()
        if protein_table:
            identifiers.extend(_read_identifier_table(protein_table, str(kwargs.get("id_column", ""))))
        identifiers = _dedupe_identifiers(identifiers)
        if not identifiers:
            raise ValueError("STRING DB requires at least one protein ID")

        query_type = str(kwargs.get("query_type", "network") or "network")
        if query_type not in STRING_QUERY_TYPES:
            raise ValueError(f"Unsupported STRING query_type: {query_type}")
        species = int(kwargs.get("species", 9606) or 9606)
        required_score = int(kwargs.get("required_score", 400) or 400)
        network_flavor = str(kwargs.get("network_flavor", "evidence") or "evidence")
        if network_flavor not in NETWORK_FLAVORS:
            raise ValueError(f"Unsupported STRING network_flavor: {network_flavor}")
        add_nodes = int(kwargs.get("add_nodes", 0) or 0)

        endpoint, params = _params_for(
            identifiers=identifiers,
            species=species,
            query_type=query_type,
            required_score=required_score,
            network_flavor=network_flavor,
            add_nodes=add_nodes,
        )

        out_dir = _node_output_dir(self, context)
        if query_type == "image":
            image_url = f"{STRING_BASE_URL}/{endpoint}"
            image_path = out_dir / "string_network.png"
            response = await _request(endpoint, params=params, retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT_S)
            image_path.write_bytes(response.content)
            rows: list[dict[str, str]] = []
            text = "# STRING network image written to string_network.png\n"
            metadata_extra: dict[str, Any] = {
                "image_url": image_url,
                "image_path": str(image_path),
                "image_params": params,
            }
        else:
            text = await _request_text(endpoint, params)
            rows = _parse_tsv(text)
            metadata_extra = {}

        tsv_path = out_dir / "interaction_network.tsv"
        metadata_path = out_dir / "network_metadata.json"
        tsv_path.write_text(text, encoding="utf-8")
        metadata = {
            "query_type": query_type,
            "endpoint": endpoint,
            "identifiers": identifiers,
            "species": species,
            "required_score": required_score,
            "network_flavor": network_flavor,
            "add_nodes": add_nodes,
            "record_count": len(rows),
            "rows": rows,
            **metadata_extra,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "interaction_network": str(tsv_path),
                "network_metadata": str(metadata_path),
            }
        }
