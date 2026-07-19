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
ENSEMBL_SOURCE_REVISION = "2026-04-07T09:29:16+01:00"
ENSEMBL_API_VERSION = "15.12"
ENSEMBL_API_REVISION = "2026-07"
ENSEMBL_LOOKUP_DOCUMENTATION_SHA256 = "7ac58aff9772fea75ef3178767648d3bff889a7e5a58e5a86c842776e4d9ee00"
ENSEMBL_ID_LOOKUP_DOCUMENTATION_SHA256 = "81b1cf120ebcc6cc007885afc7b2a59869d2b7656e0d0906582b0e7c18e325c4"
ENSEMBL_HOMOLOGY_DOCUMENTATION_SHA256 = "3a0cdb7cbeb7b6a843b4687f6fb023bb06359171730b9c3f139ad32a9c784f37"
ENSEMBL_GRCH37_HOMOLOGY_DOCUMENTATION_SHA256 = "5fa524b1922b961cdde3f87673d7c8bffb95a31350e94d78f7a2a30ef2ac418e"
ENSEMBL_VEP_REGION_DOCUMENTATION_SHA256 = "6c26cc4d1baa6eda1d8773884d8f762660cdf941ef84de92e7ad173ee6497464"
ENSEMBL_VEP_HGVS_DOCUMENTATION_SHA256 = "dc03a41b4a2575569f3b6bf7fa7f8cf25f046e449dd25a31948ed1029a288646"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0
CACHE_TTL_SECONDS = 300.0
ENSEMBL_API_CACHE = APICache.from_environment(default_ttl_seconds=CACHE_TTL_SECONDS)
# The pinned production middleware advertises a public limit of 15 requests/second.
ENSEMBL_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=15.0, burst=1)
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
    normalized = str(assembly).strip().upper()
    if normalized not in {"CURRENT", "GRCH37", "GRCH38"}:
        raise ValueError(f"Unsupported Ensembl assembly: {assembly}")
    if normalized in {"GRCH37", "GRCH38"} and species != "homo_sapiens":
        raise ValueError(f"Ensembl {assembly} is supported only for homo_sapiens")


def is_stable_id(query: str) -> bool:
    return bool(re.fullmatch(r"ENS[A-Z]*[GTPE]\d+(?:\.\d+)?", query.strip(), re.IGNORECASE))


def coerce_species_list(value: Any) -> list[str]:
    return [part for part in re.split(r"[\s,;]+", str(value or "").strip()) if part]


async def request(
    method: str,
    resource: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    base_url: str = ENSEMBL_BASE_URL,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
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
            retry_delay=RETRY_DELAY_SECONDS,
            cache_ttl=CACHE_TTL_SECONDS if method.upper() == "GET" else None,
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
    payload = _decode_json(await request("GET", resource, params=params, base_url=base_url), resource)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Ensembl {resource} returned a non-object JSON response")
    if "error" in payload:
        raise RuntimeError(f"Ensembl {resource} returned an error response: {str(payload['error'])[:500]}")
    return payload


async def post_json(
    resource: str,
    json_body: dict[str, Any],
    params: dict[str, Any] | None = None,
    *,
    base_url: str = ENSEMBL_BASE_URL,
) -> Any:
    response = await request("POST", resource, params=params, json_body=json_body, base_url=base_url)
    return _decode_json(response, resource)


def _decode_json(response: httpx.Response, resource: str) -> Any:
    try:
        return response.json()
    except ValueError:
        raise RuntimeError(f"Ensembl {resource} returned invalid JSON") from None
