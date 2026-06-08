"""InterProScan REST API integration node."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


INTERPROSCAN_BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"
INTERPROSCAN_USER_AGENT = "BioNodulo/2.0 (workflow node; InterProScan REST)"
REQUEST_TIMEOUT_S = 60.0
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
INTERPROSCAN_CACHE_TTL_S = 300.0
INTERPROSCAN_RATE_LIMIT_PER_SECOND = 1.0
INTERPROSCAN_API_CACHE = APICache.from_environment(default_ttl_seconds=INTERPROSCAN_CACHE_TTL_S)
INTERPROSCAN_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=INTERPROSCAN_RATE_LIMIT_PER_SECOND, burst=1)
RUNNING_STATUSES = {"PENDING", "RUNNING", "QUEUED"}
FAILED_STATUSES = {"FAILURE", "ERROR", "NOT_FOUND"}


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _clean_sequence(value: Any) -> str:
    lines = []
    for line in str(value or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        lines.append(stripped)
    return "".join(lines).replace(" ", "")


def _sequence_input_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return text


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def _post_text(
    endpoint: str,
    data: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _request("POST", endpoint, data=data, retries=retries, timeout=timeout)
    return response.text


async def _get_text(
    endpoint: str,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _request("GET", endpoint, retries=retries, timeout=timeout)
    return response.text


async def _get_json(
    endpoint: str,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request("GET", endpoint, retries=retries, timeout=timeout)
    return response.json()


async def _request(
    method: str,
    endpoint: str,
    *,
    data: dict[str, Any] | None = None,
    retries: int,
    timeout: float,
) -> httpx.Response:
    endpoint = endpoint.lstrip("/")
    url = f"{INTERPROSCAN_BASE_URL}/{endpoint}"
    client = APIHttpClient(cache=INTERPROSCAN_API_CACHE, rate_limiter=INTERPROSCAN_RATE_LIMITER)
    method = method.upper()
    request_kwargs: dict[str, Any] = {}
    if method == "POST":
        request_kwargs["data"] = data
    try:
        return await client.request(
            method,
            url,
            **request_kwargs,
            headers={"User-Agent": INTERPROSCAN_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"InterProScan {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"InterProScan {endpoint} request failed: {exc}") from exc


def _interpro_to_tsv(result: dict[str, Any]) -> str:
    lines = ["accession\tname\tdatabase\tstart\tend\tevalue\tdescription"]
    matches = result.get("matches", [])
    if not isinstance(matches, list):
        return "\n".join(lines) + "\n"
    for match in matches:
        if not isinstance(match, dict):
            continue
        signature = match.get("signature", {})
        if not isinstance(signature, dict):
            signature = {}
        entry = signature.get("entry", {})
        if not isinstance(entry, dict):
            entry = {}
        locations = match.get("locations", [])
        if not isinstance(locations, list):
            locations = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            lines.append("\t".join([
                str(signature.get("accession", "")),
                str(signature.get("name", "")),
                str(entry.get("type", "")),
                str(location.get("start", "")),
                str(location.get("end", "")),
                str(location.get("evalue", "")),
                str(entry.get("description", "")),
            ]))
    return "\n".join(lines) + "\n"


class InterProScanNode(BaseNode):
    """Protein domain and family analysis through InterProScan REST."""

    NODE_ID = "interpro_scan"
    DISPLAY_NAME = "InterProScan"
    CATEGORY = "api"
    DESCRIPTION = "Submit protein sequences to InterProScan and return domain annotations."
    SEARCH_ALIASES = ["interpro", "domain", "family", "protein", "pfam", "smart", "gene3d", "scan"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("domain_annotations", "domains_tsv")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": ("STRING", {"default": "", "multiline": True, "description": "Protein sequence in FASTA or raw amino-acid form"}),
            },
            "optional": {
                "applications": ("STRING", {"default": "pfam,gene3d,superfamily,smart"}),
                "goterms": ("BOOLEAN", {"default": True}),
                "pathways": ("BOOLEAN", {"default": False}),
                "email": ("STRING", {"default": "", "advanced": True}),
                "timeout_minutes": ("INT", {"default": 30, "min": 1, "max": 60}),
                "poll_interval_seconds": ("FLOAT", {"default": 10.0, "min": 0.1, "advanced": True}),
            },
            "hidden": {},
        }

    async def _submit_job(
        self,
        *,
        sequence: str,
        applications: str,
        goterms: bool,
        pathways: bool,
        email: str,
    ) -> str:
        job_id = await _post_text(
            "run",
            {
                "email": email,
                "title": "bionodulo_interpro",
                "sequence": sequence,
                "appl": applications,
                "goterms": "true" if goterms else "false",
                "pathways": "true" if pathways else "false",
            },
        )
        job_id = job_id.strip()
        if not job_id:
            raise RuntimeError("InterProScan did not return a job ID")
        return job_id

    async def _poll_job(
        self,
        *,
        job_id: str,
        timeout_minutes: int,
        poll_interval_seconds: float,
    ) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            elapsed_minutes = (time.monotonic() - started) / 60
            if elapsed_minutes > timeout_minutes:
                raise RuntimeError(f"InterProScan job {job_id} timed out after {timeout_minutes} minutes")

            status = (await _get_text(f"status/{job_id}")).strip().upper()
            if status == "FINISHED":
                return await _get_json(f"result/{job_id}/json")
            if status in FAILED_STATUSES:
                raise RuntimeError(f"InterProScan job {job_id} failed with status {status}")
            if status in RUNNING_STATUSES:
                await asyncio.sleep(poll_interval_seconds)
                continue
            raise RuntimeError(f"InterProScan job {job_id} returned unrecognised status: {status}")

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        sequence = _clean_sequence(_sequence_input_text(kwargs.get("sequence", "")))
        if not sequence:
            raise ValueError("InterProScan requires a protein sequence")

        applications = str(kwargs.get("applications", "pfam,gene3d,superfamily,smart") or "pfam,gene3d,superfamily,smart").strip()
        goterms = _coerce_bool(kwargs.get("goterms", True))
        pathways = _coerce_bool(kwargs.get("pathways", False))
        email = str(kwargs.get("email", "") or os.environ.get("BIONODULO_EMAIL", "") or "bionodulo@example.com").strip()
        timeout_minutes = int(kwargs.get("timeout_minutes", 30) or 30)
        poll_interval_seconds = float(kwargs.get("poll_interval_seconds", 10.0) or 10.0)

        job_id = await self._submit_job(
            sequence=sequence,
            applications=applications,
            goterms=goterms,
            pathways=pathways,
            email=email,
        )
        result = await self._poll_job(
            job_id=job_id,
            timeout_minutes=timeout_minutes,
            poll_interval_seconds=poll_interval_seconds,
        )

        payload = {
            "job_id": job_id,
            "applications": applications,
            "goterms": goterms,
            "pathways": pathways,
            "interproscan_result": result,
        }
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "domain_annotations.json"
        tsv_path = out_dir / "domains.tsv"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tsv_path.write_text(_interpro_to_tsv(result), encoding="utf-8")

        return {
            "outputs": {
                "domain_annotations": str(json_path),
                "domains_tsv": str(tsv_path),
            }
        }


class InterProNode(InterProScanNode):
    """Compatibility wrapper for the original InterPro roadmap node ID."""

    NODE_ID = "interpro"
    DISPLAY_NAME = "InterPro"
    DESCRIPTION = "Submit protein sequences to InterProScan and return InterPro domain annotations."
    SEARCH_ALIASES = ["interpro", "interproscan", "domain", "family", "protein", "pfam", "smart", "scan"]
