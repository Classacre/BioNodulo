"""NCBI BLAST Common URL API node with source-mandated polling intervals."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    NCBI_BLAST_DEVELOPER_SHA256,
    NCBI_BLAST_DEVELOPER_URL,
    NCBI_BLAST_DOCUMENTATION_URL,
    NCBI_BLAST_URL_API_SHA256,
    identified_params,
    node_output_dir,
    request_blast_text,
    resolve_email,
    validate_email,
)


BLAST_PROGRAMS = ("blastn", "blastp", "blastx", "tblastn", "tblastx", "megablast")
BLAST_OUTPUT_FORMATS = (
    "JSON2",
    "JSON2_S",
    "JSONSA",
    "XML2",
    "XML2_S",
    "SAM",
    "Text",
    "HTML",
    "Tabular",
    "CSV",
)
BLAST_OUTPUT_EXTENSIONS = {
    "JSON2": ".json",
    "JSON2_S": ".json",
    "JSONSA": ".json",
    "XML2": ".xml",
    "XML2_S": ".xml",
    "SAM": ".sam",
    "Text": ".txt",
    "HTML": ".html",
    "Tabular": ".tsv",
    "CSV": ".csv",
}
MINIMUM_BLAST_REQUEST_INTERVAL_SECONDS = 10.0
MINIMUM_RID_POLL_INTERVAL_SECONDS = 60.0


def normalize_query(query: Any) -> str:
    text = str(query or "").strip()
    if not text:
        raise ValueError("NCBI BLAST requires a query_sequence")
    try:
        path = Path(text).expanduser()
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    if not text:
        raise ValueError("NCBI BLAST requires a query_sequence")
    if text.startswith(">"):
        return text
    sequence = "".join(text.split())
    if not sequence:
        raise ValueError("NCBI BLAST requires a query_sequence")
    return f">query\n{sequence}"


def parse_submission(text: str) -> tuple[str, int | None]:
    rid_match = re.search(r"\bRID\s*=\s*([A-Za-z0-9_-]+)", text)
    if not rid_match:
        raise RuntimeError("Failed to get BLAST RID from submission response")
    rtoe_match = re.search(r"\bRTOE\s*=\s*(\d+)", text)
    return rid_match.group(1), int(rtoe_match.group(1)) if rtoe_match else None


def blast_status(text: str) -> str:
    match = re.search(r"\bStatus\s*=\s*([A-Z]+)", text)
    return match.group(1) if match else ""


def normalize_output_format(value: Any) -> str:
    requested = str(value or "JSON2").strip()
    by_lower = {item.lower(): item for item in BLAST_OUTPUT_FORMATS}
    normalized = by_lower.get(requested.lower())
    if normalized is None:
        raise ValueError(f"Unsupported BLAST output_format: {requested}")
    return normalized


def retrieval_params(rid: str, output_format: str) -> dict[str, str]:
    params = {"CMD": "Get", "RID": rid}
    if output_format == "Tabular":
        params.update({"FORMAT_TYPE": "Text", "ALIGNMENT_VIEW": "Tabular"})
    elif output_format == "CSV":
        params.update({"FORMAT_TYPE": "CSV", "ALIGNMENT_VIEW": "Tabular"})
    else:
        params["FORMAT_TYPE"] = output_format
    return params


def json2_summary(raw_results: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_results)
    except json.JSONDecodeError:
        return {}
    output = payload.get("BlastOutput2") if isinstance(payload, dict) else None
    if not isinstance(output, list) or not output or not isinstance(output[0], dict):
        return {}
    report = output[0].get("report", {})
    if not isinstance(report, dict):
        return {}
    results = report.get("results", {})
    search = results.get("search", {}) if isinstance(results, dict) else {}
    if not isinstance(search, dict):
        return {}
    hits = search.get("hits", [])
    summary: dict[str, Any] = {"num_hits": len(hits) if isinstance(hits, list) else 0}
    if search.get("query_title") is not None:
        summary["query"] = search["query_title"]
    if isinstance(search.get("stat"), dict):
        summary["stat"] = search["stat"]
    return summary


class NCBIBLASTNode(BaseNode):
    """Submit one BLAST job and retrieve its result from the Common URL API."""

    NODE_ID = "ncbi_blast"
    DISPLAY_NAME = "NCBI BLAST"
    CATEGORY = "databases"
    DESCRIPTION = "Run one remote BLAST search through the NCBI Common URL API."
    SEARCH_ALIASES = ["ncbi", "blast", "alignment", "homology", "search", "remote blast"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("blast_results", "blast_summary")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = "Common URL API 2026-07-19 snapshot"
    DOCUMENTATION_URL = NCBI_BLAST_DOCUMENTATION_URL
    SOURCE_URL = NCBI_BLAST_DOCUMENTATION_URL
    SOURCE_SHA256 = NCBI_BLAST_URL_API_SHA256
    DEVELOPER_SOURCE_URL = NCBI_BLAST_DEVELOPER_URL
    DEVELOPER_SOURCE_SHA256 = NCBI_BLAST_DEVELOPER_SHA256
    UPSTREAM_SOURCE = "CMD=Put/Get Common URL API; developer usage limits for request and RID polling"
    EXIT_SEMANTICS = (
        "Submission parse errors, FAILED/UNKNOWN jobs, timeouts, and HTTP or transport errors are fatal; "
        "the node never polls one RID more frequently than once per minute."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_sequence": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "FASTA, raw sequence, or FASTA path"},
                ),
                "program": (list(BLAST_PROGRAMS), {"default": "blastn"}),
                "database": ("STRING", {"default": "nt", "description": "NCBI BLAST database name"}),
            },
            "optional": {
                "evalue": ("FLOAT", {"default": 10.0, "min": 0.0}),
                "max_hits": ("INT", {"default": 100, "min": 1}),
                "output_format": (list(BLAST_OUTPUT_FORMATS), {"default": "JSON2"}),
                "timeout_minutes": ("INT", {"default": 30, "min": 1}),
                "poll_interval_seconds": (
                    "FLOAT",
                    {"default": 60.0, "min": 60.0, "advanced": True},
                ),
                "email": ("STRING", {"default": "", "advanced": True}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        try:
            normalize_query(inputs.get("query_sequence", ""))
        except ValueError as exc:
            return str(exc)
        program = str(inputs.get("program", "blastn") or "blastn").lower()
        if program not in BLAST_PROGRAMS:
            return f"Input 'program' must be one of: {', '.join(BLAST_PROGRAMS)}"
        if not str(inputs.get("database", "")).strip():
            return "Input 'database' must be non-empty"
        evalue = inputs.get("evalue", 10.0)
        if isinstance(evalue, bool) or not isinstance(evalue, (int, float)):
            return "Input 'evalue' must be a number"
        if float(evalue) <= 0:
            return "Input 'evalue' must be greater than 0"
        max_hits = inputs.get("max_hits", 100)
        if isinstance(max_hits, bool) or not isinstance(max_hits, int):
            return "Input 'max_hits' must be an integer"
        if max_hits < 1:
            return "Input 'max_hits' must be at least 1"
        try:
            normalize_output_format(inputs.get("output_format", "JSON2"))
        except ValueError as exc:
            return str(exc)
        timeout_minutes = inputs.get("timeout_minutes", 30)
        if isinstance(timeout_minutes, bool) or not isinstance(timeout_minutes, int):
            return "Input 'timeout_minutes' must be an integer"
        if timeout_minutes < 1:
            return "Input 'timeout_minutes' must be at least 1"
        poll_interval = inputs.get("poll_interval_seconds", 60.0)
        if isinstance(poll_interval, bool) or not isinstance(poll_interval, (int, float)):
            return "Input 'poll_interval_seconds' must be a number"
        if float(poll_interval) < MINIMUM_RID_POLL_INTERVAL_SECONDS:
            return "Input 'poll_interval_seconds' must be at least 60"
        return validate_email(resolve_email(inputs.get("email", "")))

    async def _submit_blast_job(
        self,
        *,
        query: str,
        program: str,
        database: str,
        evalue: float,
        max_hits: int,
        email: str,
    ) -> tuple[str, int | None]:
        api_program = "blastn" if program == "megablast" else program
        params: dict[str, Any] = {
            "CMD": "Put",
            "QUERY": query,
            "PROGRAM": api_program,
            "DATABASE": database,
            "EXPECT": str(evalue),
            "HITLIST_SIZE": str(max_hits),
            **identified_params(email=email),
        }
        if program == "megablast":
            params["MEGABLAST"] = "on"
        return parse_submission(await request_blast_text("POST", params))

    async def _poll_blast_results(
        self,
        *,
        rid: str,
        output_format: str,
        rtoe_seconds: int | None,
        timeout_minutes: int,
        poll_interval_seconds: float,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> str:
        sleep = sleep or asyncio.sleep
        clock = clock or time.monotonic
        timeout_seconds = float(timeout_minutes) * 60.0
        poll_interval = max(MINIMUM_RID_POLL_INTERVAL_SECONDS, poll_interval_seconds)
        initial_wait = max(poll_interval, float(rtoe_seconds or 0))
        if initial_wait > timeout_seconds:
            raise RuntimeError(f"BLAST job {rid} cannot be polled before its timeout")

        started = clock()
        await sleep(initial_wait)
        params = retrieval_params(rid, output_format)
        while True:
            if clock() - started > timeout_seconds:
                raise RuntimeError(f"BLAST job {rid} timed out after {timeout_minutes} minutes")
            response = await request_blast_text("GET", params)
            status = blast_status(response)
            if not status:
                return response
            if status == "WAITING":
                await sleep(poll_interval)
                continue
            if status == "READY":
                await sleep(MINIMUM_BLAST_REQUEST_INTERVAL_SECONDS)
                response = await request_blast_text("GET", params)
                if blast_status(response) in {"WAITING", "READY"}:
                    await sleep(poll_interval)
                    continue
                return response
            if status == "FAILED":
                raise RuntimeError(f"BLAST job {rid} failed on the NCBI server")
            if status == "UNKNOWN":
                raise RuntimeError(f"BLAST job {rid} is unknown or expired")
            raise RuntimeError(f"BLAST job {rid} returned an unrecognized status: {status}")

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        query = normalize_query(kwargs["query_sequence"])
        program = str(kwargs.get("program", "blastn") or "blastn").lower()
        database = str(kwargs["database"]).strip()
        evalue = float(kwargs.get("evalue", 10.0))
        max_hits = int(kwargs.get("max_hits", 100))
        output_format = normalize_output_format(kwargs.get("output_format", "JSON2"))
        timeout_minutes = int(kwargs.get("timeout_minutes", 30))
        poll_interval = float(kwargs.get("poll_interval_seconds", 60.0))
        email = resolve_email(kwargs.get("email", ""))

        rid, rtoe_seconds = await self._submit_blast_job(
            query=query,
            program=program,
            database=database,
            evalue=evalue,
            max_hits=max_hits,
            email=email,
        )
        raw_results = await self._poll_blast_results(
            rid=rid,
            output_format=output_format,
            rtoe_seconds=rtoe_seconds,
            timeout_minutes=timeout_minutes,
            poll_interval_seconds=poll_interval,
        )

        output_dir = node_output_dir(self, context)
        result_path = output_dir / f"blast_results{BLAST_OUTPUT_EXTENSIONS[output_format]}"
        result_path.write_text(raw_results, encoding="utf-8")
        summary: dict[str, Any] = {
            "rid": rid,
            "rtoe_seconds": rtoe_seconds,
            "program": program,
            "database": database,
            "format": output_format,
            "results_path": str(result_path),
        }
        if output_format == "JSON2":
            summary.update(json2_summary(raw_results))
        summary_path = output_dir / "blast_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return {
            "outputs": {
                "blast_results": str(result_path),
                "blast_summary": str(summary_path),
            }
        }
