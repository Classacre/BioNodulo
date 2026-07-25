"""EMBL-EBI InterProScan 5 Job Dispatcher contract."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


INTERPROSCAN_BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"
INTERPROSCAN_USER_AGENT = "BioNodulo/2.0 (InterProScan REST node)"
INTERPROSCAN_API_CACHE = APICache.from_environment(default_ttl_seconds=300.0)
INTERPROSCAN_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=1.0, burst=1)
REQUEST_TIMEOUT_S = 60.0
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
RUNNING_STATUSES = {"PENDING", "RUNNING", "QUEUED"}
FAILED_STATUSES = {"FAILURE", "ERROR", "NOT_FOUND"}


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output = base / node.NODE_ID
    output.mkdir(parents=True, exist_ok=True)
    return output


def _sequence_input_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    return path.read_text(encoding="utf-8") if path.is_file() else text


def _clean_sequence(value: Any) -> str:
    sequence = "".join(
        line.strip() for line in _sequence_input_text(value).splitlines() if line.strip() and not line.startswith(">")
    )
    sequence = re.sub(r"\s+", "", sequence).upper()
    if sequence and not re.fullmatch(r"[A-Z*.-]+", sequence):
        raise ValueError("InterProScan sequence contains unsupported characters")
    return sequence


async def _request(
    method: str,
    endpoint: str,
    *,
    data: dict[str, Any] | None = None,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> httpx.Response:
    url = f"{INTERPROSCAN_BASE_URL}/{endpoint.lstrip('/')}"
    client = APIHttpClient(cache=INTERPROSCAN_API_CACHE, rate_limiter=INTERPROSCAN_RATE_LIMITER)
    kwargs: dict[str, Any] = {"data": data} if method.upper() == "POST" else {}
    try:
        return await client.request(
            method,
            url,
            **kwargs,
            headers={"User-Agent": INTERPROSCAN_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"InterProScan {endpoint} failed with HTTP {exc.response.status_code}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"InterProScan {endpoint} request failed: {exc}") from exc


async def _post_text(endpoint: str, data: dict[str, Any]) -> str:
    return (await _request("POST", endpoint, data=data)).text


async def _get_text(endpoint: str) -> str:
    return (await _request("GET", endpoint)).text


async def _get_json(endpoint: str) -> Any:
    return (await _request("GET", endpoint)).json()


def _result_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [row for row in results if isinstance(row, dict)]
        if isinstance(payload.get("matches"), list):
            return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _interpro_to_tsv(payload: Any) -> str:
    lines = ["protein_accession\tsignature_accession\tsignature_name\tentry_accession\tentry_type\tstart\tend\tevalue"]
    for record in _result_records(payload):
        xref = record.get("xref") if isinstance(record.get("xref"), list) else []
        protein_accession = ""
        if xref and isinstance(xref[0], dict):
            protein_accession = str(xref[0].get("id", ""))
        for match in record.get("matches", []):
            if not isinstance(match, dict):
                continue
            signature = match.get("signature") if isinstance(match.get("signature"), dict) else {}
            entry = signature.get("entry") if isinstance(signature.get("entry"), dict) else {}
            for location in match.get("locations", []):
                if not isinstance(location, dict):
                    continue
                lines.append(
                    "\t".join(
                        str(value)
                        for value in (
                            protein_accession,
                            signature.get("accession", ""),
                            signature.get("name", ""),
                            entry.get("accession", ""),
                            entry.get("type", ""),
                            location.get("start", ""),
                            location.get("end", ""),
                            location.get("evalue", ""),
                        )
                    )
                )
    return "\n".join(lines) + "\n"


class InterProScanNode(BaseNode):
    """Submit one protein sequence to EMBL-EBI InterProScan 5."""

    NODE_ID = "interpro_scan"
    DISPLAY_NAME = "InterProScan"
    CATEGORY = "api"
    DESCRIPTION = "Submit a protein sequence to EMBL-EBI InterProScan 5 and retrieve JSON results."
    SEARCH_ALIASES = ["InterPro", "InterProScan", "Pfam", "protein domain", "Job Dispatcher"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("domain_annotations", "domains_tsv")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = "InterProScan 5 REST 2026-07-19 snapshot"
    SOURCE_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5/parameters"
    DOCUMENTATION_URL = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"
    UPSTREAM_SOURCE = "run; status/{job}; result/{job}/json; parameters and parameterdetails endpoints"
    NETWORK_SEMANTICS = (
        "EMBL-EBI requires a valid contact email, no more than 30 concurrent jobs, and retains submitted data/results for seven days."
    )
    EXIT_SEMANTICS = "Unknown or failed Job Dispatcher states, timeouts, HTTP failures, and missing job IDs fail closed."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": ("STRING", {"default": "", "multiline": True, "description": "Raw protein sequence, FASTA text, or FASTA file path"}),
                "email": ("STRING", {"default": "", "description": "Valid contact email required by EMBL-EBI"}),
            },
            "optional": {
                "applications": (
                    "STRING",
                    {"default": "", "description": "Optional comma-separated official appl values; empty uses service defaults"},
                ),
                "goterms": ("BOOLEAN", {"default": True}),
                "pathways": ("BOOLEAN", {"default": False}),
                "timeout_minutes": ("INT", {"default": 30, "min": 1, "max": 120}),
                "poll_interval_seconds": ("FLOAT", {"default": 10.0, "min": 1.0}),
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
        data: dict[str, Any] = {
            "email": email,
            "title": "bionodulo_interpro",
            "stype": "p",
            "sequence": sequence,
            "goterms": "true" if goterms else "false",
            "pathways": "true" if pathways else "false",
        }
        if applications:
            data["appl"] = applications
        job_id = (await _post_text("run", data)).strip()
        if not job_id:
            raise RuntimeError("InterProScan did not return a job ID")
        return job_id

    async def _poll_job(self, *, job_id: str, timeout_minutes: int, poll_interval_seconds: float) -> Any:
        started = time.monotonic()
        while True:
            if (time.monotonic() - started) / 60 > timeout_minutes:
                raise RuntimeError(f"InterProScan job {job_id} timed out after {timeout_minutes} minutes")
            status = (await _get_text(f"status/{job_id}")).strip().upper()
            if status == "FINISHED":
                return await _get_json(f"result/{job_id}/json")
            if status in FAILED_STATUSES:
                raise RuntimeError(f"InterProScan job {job_id} failed with status {status}")
            if status not in RUNNING_STATUSES:
                raise RuntimeError(f"InterProScan job {job_id} returned unrecognised status: {status}")
            await asyncio.sleep(poll_interval_seconds)

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        sequence = _clean_sequence(kwargs.get("sequence", ""))
        if not sequence:
            raise ValueError("InterProScan requires a protein sequence")
        email = str(kwargs.get("email", "") or os.environ.get("BIONODULO_EMAIL", "")).strip()
        if not email or "@" not in email:
            raise ValueError("InterProScan requires a valid contact email")
        applications = str(kwargs.get("applications", "") or "").strip()
        goterms = bool(kwargs.get("goterms", True))
        pathways = bool(kwargs.get("pathways", False))
        raw_timeout_minutes = kwargs.get("timeout_minutes", 30)
        timeout_minutes = int(30 if raw_timeout_minutes in (None, "") else raw_timeout_minutes)
        raw_poll_interval = kwargs.get("poll_interval_seconds", 10.0)
        poll_interval_seconds = float(10.0 if raw_poll_interval in (None, "") else raw_poll_interval)
        if not 1 <= timeout_minutes <= 120:
            raise ValueError("InterProScan timeout_minutes must be between 1 and 120")
        if poll_interval_seconds < 1:
            raise ValueError("InterProScan poll_interval_seconds must be at least 1")
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
        output = _node_output_dir(self, context)
        json_path = output / "domain_annotations.json"
        tsv_path = output / "domains.tsv"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tsv_path.write_text(_interpro_to_tsv(result), encoding="utf-8")
        return {"outputs": {"domain_annotations": str(json_path), "domains_tsv": str(tsv_path)}}
