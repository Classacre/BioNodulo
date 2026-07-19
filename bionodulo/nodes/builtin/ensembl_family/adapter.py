"""Shared Ensembl REST transport and identifier helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


ENSEMBL_BASE_URL = "https://rest.ensembl.org"
ENSEMBL_GRCH37_BASE_URL = "https://grch37.rest.ensembl.org"
ENSEMBL_USER_AGENT = "BioNodulo/2.0 (Ensembl REST nodes)"
ENSEMBL_SOURCE_COMMIT = "79f8dcc5cb3a0e8aef81273d118d7a514d43358d"
ENSEMBL_API_CACHE = APICache.from_environment(default_ttl_seconds=300.0)
ENSEMBL_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=5.0, burst=1)
ENSEMBL_JSON_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": ENSEMBL_USER_AGENT,
}
COMMON_ENSEMBL_SPECIES_OPTIONS = (
    "homo_sapiens",
    "mus_musculus",
    "rattus_norvegicus",
    "danio_rerio",
    "drosophila_melanogaster",
    "caenorhabditis_elegans",
    "saccharomyces_cerevisiae",
)


def node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output = base / node.NODE_ID
    output.mkdir(parents=True, exist_ok=True)
    return output


def base_url_for_assembly(assembly: str) -> str:
    return ENSEMBL_GRCH37_BASE_URL if str(assembly).strip().upper() == "GRCH37" else ENSEMBL_BASE_URL


def validate_assembly_species(assembly: str, species: str) -> None:
    if str(assembly).strip().upper() == "GRCH37" and species != "homo_sapiens":
        raise ValueError("Ensembl GRCh37 REST host is supported only for homo_sapiens")


def is_stable_id(query: str) -> bool:
    return bool(re.match(r"^ENS[A-Z]*[GTPE]\d+", query.strip(), re.IGNORECASE))


def coerce_species_list(value: Any) -> list[str]:
    return [part for part in re.split(r"[\s,;]+", str(value or "").strip()) if part]


async def request(
    method: str,
    resource: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    base_url: str = ENSEMBL_BASE_URL,
    retries: int = 3,
    timeout: float = 30.0,
) -> httpx.Response:
    url = f"{base_url.rstrip('/')}/{resource.lstrip('/')}"
    client = APIHttpClient(cache=ENSEMBL_API_CACHE, rate_limiter=ENSEMBL_RATE_LIMITER)
    try:
        return await client.request(
            method,
            url,
            params=params or {},
            json=json_body,
            headers=ENSEMBL_JSON_HEADERS,
            timeout=timeout,
            retries=retries,
            retry_delay=1.0,
            cache_ttl=300.0 if method.upper() == "GET" else None,
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ensembl {resource} failed with HTTP {exc.response.status_code}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ensembl {resource} request failed: {exc}") from exc


async def request_json(
    resource: str,
    params: dict[str, Any] | None = None,
    *,
    base_url: str = ENSEMBL_BASE_URL,
) -> dict[str, Any]:
    payload = (await request("GET", resource, params=params, base_url=base_url)).json()
    return payload if isinstance(payload, dict) else {}


async def post_json(
    resource: str,
    json_body: dict[str, Any],
    params: dict[str, Any] | None = None,
    *,
    base_url: str = ENSEMBL_BASE_URL,
) -> Any:
    return (await request("POST", resource, params=params, json_body=json_body, base_url=base_url)).json()
