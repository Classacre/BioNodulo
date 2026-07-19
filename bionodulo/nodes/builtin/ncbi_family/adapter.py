"""Shared HTTP, validation, and filesystem helpers for NCBI nodes."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


NCBI_EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_BLAST_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
NCBI_EUTILS_DOCUMENTATION_URL = "https://www.ncbi.nlm.nih.gov/books/NBK25499/"
NCBI_EUTILS_REVISION = "2026-03-04"
NCBI_EUTILS_SOURCE_SHA256 = "69c3cbd73e1fe38484809221f46e2380cee7d5a354b7dffa2b5f612a52785ee1"
NCBI_BLAST_DOCUMENTATION_URL = "https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html"
NCBI_BLAST_DEVELOPER_URL = "https://blast.ncbi.nlm.nih.gov/doc/blast-help/developerinfo.html"
NCBI_BLAST_URL_API_SHA256 = "c864df25b8608d705cde6aee9344aba3e3a5ef7b16a0c8ca9e221e418aab83f3"
NCBI_BLAST_DEVELOPER_SHA256 = "73dd88056332b1b21de8bfc2cbd272af03cae803c15c0cedf33c9c45a2171682"
NCBI_USER_AGENT = "BioNodulo/2.0 (workflow node; NCBI)"
NCBI_TOOL = "bionodulo"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0
NCBI_CACHE_TTL_SECONDS = 300.0

_EUTILS_CACHE = APICache.from_environment(default_ttl_seconds=NCBI_CACHE_TTL_SECONDS)
_EUTILS_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=3.0, burst=1)
_EUTILS_API_KEY_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=10.0, burst=1)
_BLAST_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=0.1, burst=1)


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


def resolve_api_key(explicit: Any, context: Any) -> str:
    return resolve_secret_value(
        explicit,
        context,
        "ncbi_api_key",
        "BIONODULO_NCBI_API_KEY",
        "NCBI_API_KEY",
        default=os.environ.get("BIONODULO_NCBI_API_KEY", "") or os.environ.get("NCBI_API_KEY", ""),
    )


def resolve_email(explicit: Any) -> str:
    return str(explicit or os.environ.get("BIONODULO_EMAIL", "") or os.environ.get("NCBI_EMAIL", "")).strip()


def validate_email(email: str) -> bool | str:
    if not email:
        return True
    if any(char.isspace() for char in email) or email.count("@") != 1:
        return "Input 'email' must be a valid email address without whitespace"
    local, domain = email.split("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return "Input 'email' must be a valid email address without whitespace"
    return True


def identified_params(*, email: str = "") -> dict[str, str]:
    params = {"tool": NCBI_TOOL}
    if email:
        params["email"] = email
    return params


async def request_json(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    response = await request_eutils(endpoint, params)
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"NCBI {endpoint} returned a non-object JSON response")
    return payload


async def request_text(endpoint: str, params: dict[str, Any]) -> str:
    response = await request_eutils(endpoint, params)
    return response.text


async def request_eutils(endpoint: str, params: dict[str, Any]) -> httpx.Response:
    clean = clean_params(params)
    limiter = _EUTILS_API_KEY_RATE_LIMITER if clean.get("api_key") else _EUTILS_RATE_LIMITER
    client = APIHttpClient(cache=_EUTILS_CACHE, rate_limiter=limiter)
    try:
        return await client.request(
            "GET",
            f"{NCBI_EUTILS_BASE_URL}/{endpoint}",
            params=clean,
            headers={"User-Agent": NCBI_USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY_SECONDS,
            cache_ttl=NCBI_CACHE_TTL_SECONDS,
        )
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500]
        raise RuntimeError(f"NCBI {endpoint} failed with HTTP {exc.response.status_code}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"NCBI {endpoint} request failed: {exc}") from exc


async def request_blast_text(method: str, params: dict[str, Any]) -> str:
    clean = clean_params(params)
    request_kwargs: dict[str, Any] = {"data": clean} if method.upper() == "POST" else {"params": clean}
    client = APIHttpClient(cache=None, rate_limiter=_BLAST_RATE_LIMITER)
    try:
        response = await client.request(
            method.upper(),
            NCBI_BLAST_URL,
            **request_kwargs,
            headers={"User-Agent": NCBI_USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY_SECONDS,
            cache_ttl=None,
            follow_redirects=True,
        )
        return response.text
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500]
        raise RuntimeError(f"NCBI BLAST request failed with HTTP {exc.response.status_code}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"NCBI BLAST request failed: {exc}") from exc


def coerce_ids(value: Any) -> list[str]:
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


def chunked(values: list[str], size: int) -> list[list[str]]:
    if size < 1:
        raise ValueError("batch_size must be at least 1")
    return [values[index : index + size] for index in range(0, len(values), size)]


def node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output_dir = base / node.NODE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def safe_filename(value: str, *, fallback: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or fallback


def normalize_database(database: Any, *, default: str) -> str:
    value = str(database or default).strip().lower()
    return "nuccore" if value == "nucleotide" else value


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_command_result(result: Any) -> dict[str, Any]:
    def result_value(key: str, default: Any = "") -> Any:
        if isinstance(result, dict):
            return result.get(key, default)
        return getattr(result, key, default)

    def process_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return str(value)

    return {
        "returncode": int(result_value("returncode", 0) or 0),
        "stdout": process_text(result_value("stdout", "")),
        "stderr": process_text(result_value("stderr", "")),
    }


async def run_command(command: list[str], cwd: Path, context: Any) -> dict[str, Any]:
    if context is not None and hasattr(context, "run_command"):
        return normalize_command_result(await context.run_command(command, cwd=str(cwd)))

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return normalize_command_result({"returncode": process.returncode, "stdout": stdout, "stderr": stderr})
