"""NCBI E-utilities integration nodes."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_BLAST_BASE_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
NCBI_USER_AGENT = "BioNodulo/2.0 (workflow node; NCBI E-utilities)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
NCBI_CACHE_TTL_S = 300.0
NCBI_RATE_LIMIT_PER_SECOND = 3.0
NCBI_API_KEY_RATE_LIMIT_PER_SECOND = 10.0
BLAST_PROGRAMS = ("blastn", "blastp", "blastx", "tblastn", "tblastx", "megablast")
BLAST_DATABASES = ("nt", "nr", "refseq_rna", "refseq_protein", "pdb", "est", "gss", "pat", "env_nr")
BLAST_OUTPUT_FORMATS = ("JSON2", "XML", "Tabular", "Text", "XML2", "CSV", "SAM")
BLAST_EXTENSIONS = {
    "JSON2": ".json",
    "XML": ".xml",
    "XML2": ".xml",
    "Tabular": ".tsv",
    "Text": ".txt",
    "CSV": ".csv",
    "SAM": ".sam",
}
GEO_QUERY_TYPES = ("search", "series", "sample", "platform")
GEO_ENTRY_TYPES = {
    "series": "gse",
    "sample": "gsm",
    "platform": "gpl",
}
SRA_OUTPUT_FORMATS = ("fastq", "fasta")
NCBI_EFETCH_RETTYPES = ("fasta", "gb", "gbwithparts", "gbc", "ft", "xml", "acc", "seqid", "docsum")
NCBI_EFETCH_RETMODES = ("text", "xml", "json", "asn.1")
NCBI_EFETCH_DATABASES = ("pubmed", "gene", "snp", "sra", "nuccore", "nucleotide", "protein", "assembly", "gds", "taxonomy")
NCBI_ESEARCH_DATABASES = NCBI_EFETCH_DATABASES
SRA_FILE_SUFFIXES = {
    "fastq": (".fastq", ".fq", ".fastq.gz", ".fq.gz"),
    "fasta": (".fasta", ".fa", ".fna", ".fasta.gz", ".fa.gz", ".fna.gz"),
}

logger = logging.getLogger(__name__)
NCBI_API_CACHE = APICache(ttl_seconds=NCBI_CACHE_TTL_S)
NCBI_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=NCBI_RATE_LIMIT_PER_SECOND, burst=1)
NCBI_API_KEY_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=NCBI_API_KEY_RATE_LIMIT_PER_SECOND, burst=1)


def _resolve_api_key(explicit: Any, context: Any) -> str:
    return resolve_secret_value(
        explicit,
        context,
        "ncbi_api_key",
        "BIONODULO_NCBI_API_KEY",
        "NCBI_API_KEY",
        default=os.environ.get("BIONODULO_NCBI_API_KEY", "") or os.environ.get("NCBI_API_KEY", ""),
    )


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


async def _request_json(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.json()


async def _request_text(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.text


async def _request(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int,
    timeout: float,
) -> httpx.Response:
    url = f"{NCBI_BASE_URL}/{endpoint}"
    clean = _clean_params(params)
    rate_limiter = NCBI_API_KEY_RATE_LIMITER if clean.get("api_key") else NCBI_RATE_LIMITER
    client = APIHttpClient(cache=NCBI_API_CACHE, rate_limiter=rate_limiter)
    try:
        return await client.request(
            "GET",
            url,
            params=clean,
            headers={"User-Agent": NCBI_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=NCBI_CACHE_TTL_S,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"NCBI {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"NCBI {endpoint} request failed: {exc}") from exc


async def _blast_request_text(
    method: str,
    params: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    clean = _clean_params(params)
    method = method.upper()
    client = APIHttpClient(cache=NCBI_API_CACHE, rate_limiter=NCBI_RATE_LIMITER)
    request_kwargs: dict[str, Any] = {}
    if method == "POST":
        request_kwargs["data"] = clean
    else:
        request_kwargs["params"] = clean
    try:
        response = await client.request(
            method,
            NCBI_BLAST_BASE_URL,
            **request_kwargs,
            headers={"User-Agent": NCBI_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
        return response.text
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"NCBI BLAST request failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"NCBI BLAST request failed: {exc}") from exc


def _coerce_ids(value: Any) -> list[str]:
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


def _chunked(values: list[str], size: int) -> list[list[str]]:
    if size < 1:
        raise ValueError("batch_size must be at least 1")
    return [values[index:index + size] for index in range(0, len(values), size)]


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or "records"


def _default_extension(rettype: str, retmode: str) -> str:
    if retmode == "json":
        return ".json"
    if retmode == "xml":
        return ".xml"
    if retmode == "asn.1":
        return ".asn1"
    if rettype in {"fasta", "fasta_cds_na", "fasta_cds_aa"}:
        return ".fasta"
    if rettype in {"gb", "gbwithparts"}:
        return ".gb"
    return ".txt"


def _default_ncbi_email() -> str:
    return os.environ.get("BIONODULO_EMAIL", "bionodulo@example.com")


def _normalise_ncbi_database(database: Any) -> str:
    value = str(database or "nuccore")
    return "nuccore" if value == "nucleotide" else value


def _normalise_blast_query(query: Any) -> str:
    text = str(query or "").strip()
    if not text:
        raise ValueError("NCBI BLAST requires a query_sequence")
    path = Path(text).expanduser()
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("NCBI BLAST requires a query_sequence")
    if text.startswith(">"):
        return text
    sequence = "".join(text.split())
    if not sequence:
        raise ValueError("NCBI BLAST requires a query_sequence")
    return f">query\n{sequence}"


def _parse_blast_submission(text: str) -> tuple[str, int | None]:
    rid_match = re.search(r"\bRID\s*=\s*([A-Za-z0-9_-]+)", text)
    if not rid_match:
        raise RuntimeError("Failed to get BLAST RID from submission response")
    rtoe_match = re.search(r"\bRTOE\s*=\s*(\d+)", text)
    return rid_match.group(1), int(rtoe_match.group(1)) if rtoe_match else None


def _blast_status(text: str) -> str:
    status_match = re.search(r"\bStatus\s*=\s*([A-Z]+)", text)
    return status_match.group(1) if status_match else ""


def _blast_result_summary(raw_results: str, output_format: str) -> dict[str, Any]:
    if output_format != "JSON2":
        return {}
    try:
        payload = json.loads(raw_results)
    except json.JSONDecodeError:
        return {}
    output = payload.get("BlastOutput2") if isinstance(payload, dict) else None
    if not isinstance(output, list) or not output:
        return {}
    first = output[0]
    if not isinstance(first, dict):
        return {}
    report = first.get("report", {})
    if not isinstance(report, dict):
        return {}
    search = report.get("results", {}).get("search", {})
    if not isinstance(search, dict):
        return {}
    hits = search.get("hits", [])
    summary: dict[str, Any] = {"num_hits": len(hits) if isinstance(hits, list) else 0}
    if search.get("query_title") is not None:
        summary["query"] = search.get("query_title")
    if isinstance(search.get("stat"), dict):
        summary["stat"] = search.get("stat")
    return summary


def _geo_summaries_from_esummary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return []
    uids = [str(uid) for uid in result.get("uids", []) if str(uid)]
    summaries: list[dict[str, Any]] = []
    if uids:
        for uid in uids:
            record = result.get(uid)
            if isinstance(record, dict):
                summaries.append(record)
        return summaries
    for key, value in result.items():
        if key == "uids":
            continue
        if isinstance(value, dict):
            summaries.append(value)
    return summaries


def _geo_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            if isinstance(value, list):
                return ",".join(str(item) for item in value)
            return str(value).replace("\t", " ").replace("\n", " ")
    return ""


def _geo_summaries_to_tsv(summaries: list[dict[str, Any]]) -> str:
    lines = ["uid\taccession\ttitle\tentry_type\tgds_type\tn_samples\torganism\tplatform\tpublication_date"]
    for record in summaries:
        lines.append("\t".join([
            _geo_value(record, "uid"),
            _geo_value(record, "accession", "Accession"),
            _geo_value(record, "title"),
            _geo_value(record, "entryType", "entry_type"),
            _geo_value(record, "gdsType", "gds_type"),
            _geo_value(record, "n_samples", "nSamples"),
            _geo_value(record, "taxon", "organism"),
            _geo_value(record, "GPL", "platform"),
            _geo_value(record, "PDAT", "pdat", "publication_date"),
        ]))
    return "\n".join(lines) + "\n"


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _result_value(result: Any, key: str, default: Any = "") -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def _decode_process_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _normalise_command_result(result: Any) -> dict[str, Any]:
    return {
        "returncode": int(_result_value(result, "returncode", 0) or 0),
        "stdout": _decode_process_text(_result_value(result, "stdout", "")),
        "stderr": _decode_process_text(_result_value(result, "stderr", "")),
    }


async def _run_command(command: list[str], cwd: Path, context: Any) -> dict[str, Any]:
    if context is not None and hasattr(context, "run_command"):
        result = await context.run_command(command, cwd=str(cwd))
        return _normalise_command_result(result)

    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return _normalise_command_result(
        {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    )


def _collect_sra_files(out_dir: Path, accession: str, output_format: str) -> list[str]:
    files: dict[Path, None] = {}
    for suffix in SRA_FILE_SUFFIXES[output_format]:
        for path in out_dir.glob(f"{accession}*{suffix}"):
            if path.is_file():
                files[path] = None
    return [str(path) for path in sorted(files, key=lambda item: item.name)]


class NCBIESearchNode(BaseNode):
    """Search NCBI Entrez databases and return matching IDs."""

    NODE_ID = "ncbi_esearch"
    DISPLAY_NAME = "NCBI ESearch"
    CATEGORY = "databases"
    DESCRIPTION = "Search NCBI Entrez databases and return matching record IDs."
    SEARCH_ALIASES = ["ncbi", "entrez", "esearch", "pubmed", "gene", "sra", "database"]
    RETURN_TYPES = ("JSON", "INT", "STRING")
    RETURN_NAMES = ("id_list", "total_count", "query_translation")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("STRING", {"default": "", "description": "NCBI Entrez search query"}),
                "database": (list(NCBI_ESEARCH_DATABASES), {"default": "pubmed"}),
            },
            "optional": {
                "max_results": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "retstart": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sort": ("STRING", {"default": "relevance"}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "return_uids": ("BOOLEAN", {"default": True, "advanced": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        query = str(kwargs.get("query", "")).strip()
        if not query:
            raise ValueError("NCBI ESearch requires a non-empty query")
        max_results = int(kwargs.get("max_results", 20))
        if max_results < 1:
            raise ValueError("max_results must be at least 1")
        retstart = int(kwargs.get("retstart", 0) or 0)
        if retstart < 0:
            raise ValueError("retstart must be at least 0")
        database = _normalise_ncbi_database(kwargs.get("database", "pubmed"))
        params: dict[str, Any] = {
            "db": database,
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "tool": "bionodulo",
            "email": _default_ncbi_email(),
        }
        if "retstart" in kwargs:
            params["retstart"] = retstart
        sort = str(kwargs.get("sort", "relevance"))
        if sort:
            params["sort"] = sort
        api_key = _resolve_api_key(kwargs.get("api_key", ""), context)
        if api_key:
            params["api_key"] = api_key

        payload = await _request_json("esearch.fcgi", params)
        result = payload.get("esearchresult", {})
        ids = [str(item) for item in result.get("idlist", [])]
        count = int(result.get("count", 0))
        return_uids = bool(kwargs.get("return_uids", True))
        result_ids = ids
        if not return_uids and ids:
            fetch_params: dict[str, Any] = {
                "db": database,
                "id": ",".join(ids),
                "rettype": "acc",
                "retmode": "text",
                "tool": "bionodulo",
                "email": _default_ncbi_email(),
            }
            if api_key:
                fetch_params["api_key"] = api_key
            accession_text = await _request_text("efetch.fcgi", fetch_params)
            result_ids = [line.strip() for line in accession_text.splitlines() if line.strip()]
        return {
            "outputs": {
                "id_list": result_ids,
                "total_count": count,
                "query_translation": str(result.get("querytranslation", "")),
            }
        }


class NCBIEFetchNode(BaseNode):
    """Fetch NCBI Entrez records by ID and write them to a file."""

    NODE_ID = "ncbi_efetch"
    DISPLAY_NAME = "NCBI EFetch"
    CATEGORY = "databases"
    DESCRIPTION = "Fetch records from NCBI Entrez databases by ID and write the response to a file."
    SEARCH_ALIASES = ["ncbi", "entrez", "efetch", "pubmed", "gene", "fasta", "database"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("records", "metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "accessions": ("STRING", {"default": "", "description": "Record IDs or accessions as a list, JSON list, or comma-separated string"}),
                "database": (list(NCBI_EFETCH_DATABASES), {"default": "nuccore"}),
            },
            "optional": {
                "rettype": ("STRING", {"default": "fasta", "options": list(NCBI_EFETCH_RETTYPES)}),
                "retmode": ("STRING", {"default": "text", "options": list(NCBI_EFETCH_RETMODES)}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "batch_size": ("INT", {"default": 100, "min": 1, "max": 500}),
                "email": ("STRING", {"default": "", "advanced": True}),
                "id_list": ("ANY", {"default": "", "advanced": True, "description": "Backward-compatible record ID input"}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        ids = _coerce_ids(kwargs.get("accessions", "") or kwargs.get("id_list", ""))
        if not ids:
            raise ValueError("NCBI EFetch requires at least one ID")
        database = _normalise_ncbi_database(kwargs.get("database", "nuccore"))
        rettype = str(kwargs.get("rettype", "fasta"))
        retmode = str(kwargs.get("retmode", "text"))
        batch_size = int(kwargs.get("batch_size", 100) or 100)
        api_key = _resolve_api_key(kwargs.get("api_key", ""), context)
        email = str(kwargs.get("email", "") or _default_ncbi_email())

        batches = _chunked(ids, batch_size)
        record_parts: list[str] = []
        for batch in batches:
            params: dict[str, Any] = {
                "db": database,
                "id": ",".join(batch),
                "rettype": rettype,
                "retmode": retmode,
                "tool": "bionodulo",
                "email": email,
            }
            if api_key:
                params["api_key"] = api_key
            record_parts.append(await _request_text("efetch.fcgi", params))

        records = "\n".join(part.rstrip("\n") for part in record_parts if part) + ("\n" if record_parts else "")
        output_name = str(kwargs.get("output_name", "")).strip()
        if output_name:
            filename = _safe_filename(output_name)
        else:
            stem = f"{database}_{rettype}_{len(ids)}_records"
            filename = _safe_filename(stem) + _default_extension(rettype, retmode)
        out_path = _node_output_dir(self, context) / filename
        out_path.write_text(records, encoding="utf-8")

        return {
            "outputs": {
                "records": str(out_path),
                "metadata": {
                    "database": database,
                    "ids": ids,
                    "rettype": rettype,
                    "retmode": retmode,
                    "record_count": len(ids),
                    "batch_size": batch_size,
                    "batch_count": len(batches),
                    "records_path": str(out_path),
                },
            }
        }


class NCBIBLASTNode(BaseNode):
    """Run BLAST searches through the NCBI BLAST URL API."""

    NODE_ID = "ncbi_blast"
    DISPLAY_NAME = "NCBI BLAST"
    CATEGORY = "databases"
    DESCRIPTION = "Run BLAST searches through the NCBI BLAST URL API with asynchronous job polling."
    SEARCH_ALIASES = ["ncbi", "blast", "alignment", "homology", "search", "cloud blast"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("blast_results", "blast_summary")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_sequence": ("STRING", {"default": "", "multiline": True, "description": "FASTA or raw query sequence"}),
                "program": (list(BLAST_PROGRAMS), {"default": "blastn"}),
                "database": (list(BLAST_DATABASES), {"default": "nt"}),
            },
            "optional": {
                "evalue": ("FLOAT", {"default": 10.0, "min": 0.0001}),
                "max_hits": ("INT", {"default": 50, "min": 1, "max": 5000}),
                "output_format": (list(BLAST_OUTPUT_FORMATS), {"default": "JSON2"}),
                "timeout_minutes": ("INT", {"default": 30, "min": 1, "max": 120}),
                "poll_interval_seconds": ("FLOAT", {"default": 60.0, "min": 1, "advanced": True}),
                "email": ("STRING", {"default": "", "advanced": True}),
            },
            "hidden": {},
        }

    async def _submit_blast_job(
        self,
        *,
        query: str,
        program: str,
        database: str,
        evalue: float,
        max_hits: int,
        output_format: str,
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
            "FORMAT_TYPE": output_format,
            "tool": "bionodulo",
            "email": email,
        }
        if program == "megablast":
            params["MEGABLAST"] = "on"
        response = await _blast_request_text("POST", params)
        return _parse_blast_submission(response)

    async def _poll_blast_results(
        self,
        *,
        rid: str,
        output_format: str,
        timeout_minutes: int,
        poll_interval_seconds: float,
    ) -> str:
        started = time.monotonic()
        while True:
            elapsed_minutes = (time.monotonic() - started) / 60
            if elapsed_minutes > timeout_minutes:
                raise RuntimeError(f"BLAST job {rid} timed out after {timeout_minutes} minutes")
            await asyncio.sleep(poll_interval_seconds)
            status_text = await _blast_request_text(
                "GET",
                {
                    "CMD": "Get",
                    "RID": rid,
                    "FORMAT_OBJECT": "SearchInfo",
                },
            )
            status = _blast_status(status_text)
            if status == "WAITING":
                continue
            if status == "READY":
                return await _blast_request_text(
                    "GET",
                    {
                        "CMD": "Get",
                        "RID": rid,
                        "FORMAT_TYPE": output_format,
                    },
                )
            if status == "FAILED":
                raise RuntimeError(f"BLAST job {rid} failed on the NCBI server")
            if status == "UNKNOWN":
                raise RuntimeError(f"BLAST job {rid} is unknown or expired")
            raise RuntimeError(f"BLAST job {rid} returned an unrecognised status: {status_text[:200]}")

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        query = _normalise_blast_query(kwargs.get("query_sequence", ""))
        program = str(kwargs.get("program", "blastn") or "blastn").lower()
        if program not in BLAST_PROGRAMS:
            raise ValueError(f"Unsupported BLAST program: {program}")
        database = str(kwargs.get("database", "nt") or "nt")
        if not database:
            raise ValueError("NCBI BLAST requires a database")
        evalue = float(kwargs.get("evalue", 10.0) or 10.0)
        max_hits = int(kwargs.get("max_hits", 50) or 50)
        output_format = str(kwargs.get("output_format", "JSON2") or "JSON2")
        if output_format not in BLAST_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported BLAST output_format: {output_format}")
        timeout_minutes = int(kwargs.get("timeout_minutes", 30) or 30)
        poll_interval_seconds = float(kwargs.get("poll_interval_seconds", 60.0) or 60.0)
        email = str(kwargs.get("email", "") or os.environ.get("BIONODULO_EMAIL", "") or "bionodulo@example.com")

        rid, rtoe_seconds = await self._submit_blast_job(
            query=query,
            program=program,
            database=database,
            evalue=evalue,
            max_hits=max_hits,
            output_format=output_format,
            email=email,
        )
        logger.info("Submitted NCBI BLAST job: RID=%s", rid)
        raw_results = await self._poll_blast_results(
            rid=rid,
            output_format=output_format,
            timeout_minutes=timeout_minutes,
            poll_interval_seconds=poll_interval_seconds,
        )

        out_dir = _node_output_dir(self, context)
        extension = BLAST_EXTENSIONS.get(output_format, ".txt")
        result_path = out_dir / f"blast_results{extension}"
        result_path.write_text(raw_results, encoding="utf-8")

        summary: dict[str, Any] = {
            "rid": rid,
            "rtoe_seconds": rtoe_seconds,
            "program": program,
            "database": database,
            "format": output_format,
            "results_path": str(result_path),
        }
        summary.update(_blast_result_summary(raw_results, output_format))
        summary_path = out_dir / "blast_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "blast_results": str(result_path),
                "blast_summary": str(summary_path),
            }
        }


class GEOQueryNode(BaseNode):
    """Query NCBI GEO metadata through the GDS E-utilities database."""

    NODE_ID = "geo_query"
    DISPLAY_NAME = "GEO Query"
    CATEGORY = "databases"
    DESCRIPTION = "Search or look up NCBI GEO series, sample, and platform metadata."
    SEARCH_ALIASES = ["geo", "gene expression omnibus", "microarray", "rnaseq", "metadata", "series", "sample", "gds"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("geo_metadata", "sample_table")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "accession": ("STRING", {"default": "", "description": "GEO accession, e.g. GSE, GSM, or GPL"}),
            },
            "optional": {
                "query_type": (list(GEO_QUERY_TYPES), {"default": "series"}),
                "search_query": ("STRING", {"default": "", "description": "Used when query_type=search"}),
                "query": ("STRING", {"default": "", "advanced": True, "description": "Backward-compatible GEO search query"}),
                "dataset_type": (
                    "STRING",
                    {"default": "", "options": list(GEO_QUERY_TYPES), "advanced": True},
                ),
                "max_results": ("INT", {"default": 10, "min": 1, "max": 500}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        query_type = str(kwargs.get("query_type", "") or kwargs.get("dataset_type", "") or "series").lower()
        if query_type not in GEO_QUERY_TYPES:
            raise ValueError(f"Unsupported GEO query_type: {query_type}")
        query_alias = str(kwargs.get("query", "") or "").strip()
        accession = str(kwargs.get("accession", "") or (query_alias if query_type != "search" else "")).strip()
        search_query = str(kwargs.get("search_query", "") or (query_alias if query_type == "search" else "")).strip()
        max_results = int(kwargs.get("max_results", 10) or 10)
        if max_results < 1:
            raise ValueError("max_results must be at least 1")

        if query_type == "search":
            term = search_query or accession
            if not term:
                raise ValueError("GEO Query requires search_query or accession")
        else:
            if not accession:
                raise ValueError("GEO Query requires accession")
            term = f"{accession}[ACCN] AND {GEO_ENTRY_TYPES[query_type]}[ETYP]"

        api_key = _resolve_api_key(kwargs.get("api_key", ""), context)
        email = _default_ncbi_email()
        search_params: dict[str, Any] = {
            "db": "gds",
            "term": term,
            "retmode": "json",
            "retmax": max_results,
            "tool": "bionodulo",
            "email": email,
        }
        if api_key:
            search_params["api_key"] = api_key

        search_payload = await _request_json("esearch.fcgi", search_params)
        search_result = search_payload.get("esearchresult", {})
        uids = [str(uid) for uid in search_result.get("idlist", [])]
        total_count = int(search_result.get("count", 0))

        summaries: list[dict[str, Any]] = []
        if uids:
            summary_params: dict[str, Any] = {
                "db": "gds",
                "id": ",".join(uids),
                "retmode": "json",
                "tool": "bionodulo",
                "email": email,
            }
            if api_key:
                summary_params["api_key"] = api_key
            summary_payload = await _request_json("esummary.fcgi", summary_params)
            summaries = _geo_summaries_from_esummary(summary_payload)

        metadata = {
            "query": term,
            "query_type": query_type,
            "uids": uids,
            "total_count": total_count,
            "record_count": len(summaries),
            "summaries": summaries,
        }
        out_dir = _node_output_dir(self, context)
        if query_type == "search":
            metadata_path = out_dir / "geo_search_results.json"
            table_path = out_dir / "geo_results.tsv"
        else:
            metadata_path = out_dir / "geo_metadata.json"
            table_path = out_dir / "sample_table.tsv"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        table_path.write_text(_geo_summaries_to_tsv(summaries), encoding="utf-8")

        return {
            "outputs": {
                "geo_metadata": str(metadata_path),
                "sample_table": str(table_path),
            }
        }


class SRADownloadNode(BaseNode):
    """Download FASTQ/FASTA files from NCBI SRA using sra-toolkit."""

    NODE_ID = "sra_download"
    DISPLAY_NAME = "SRA Download"
    CATEGORY = "databases"
    DESCRIPTION = "Download FASTQ or FASTA files from NCBI Sequence Read Archive using sra-toolkit."
    SEARCH_ALIASES = [
        "sra",
        "sequence read archive",
        "download",
        "fastq",
        "fasta",
        "ngs",
        "reads",
        "prefetch",
    ]
    RETURN_TYPES = ("FASTQ_LIST", "JSON")
    RETURN_NAMES = ("fastq_files", "download_report")
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["prefetch", "fasterq-dump"]
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://github.com/ncbi/sra-tools"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "accessions": (
                    "STRING",
                    {
                        "default": "",
                        "description": "SRR/ERR/DRR accessions as a list, JSON list, or comma-separated string",
                    },
                ),
            },
            "optional": {
                "accession": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Backward-compatible singular SRR/ERR/DRR accession",
                    },
                ),
                "split_files": ("BOOLEAN", {"default": True, "description": "Split paired-end reads into separate files"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 32}),
                "skip_technical": ("BOOLEAN", {"default": True}),
                "output_format": (list(SRA_OUTPUT_FORMATS), {"default": "fastq"}),
                "format": ("STRING", {"default": "fastq", "options": ["fastq", "fasta"], "advanced": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        accessions = _coerce_ids(kwargs.get("accessions", "") or kwargs.get("accession", ""))
        if not accessions:
            raise ValueError("SRA Download requires at least one accession")

        split_files = _coerce_bool(kwargs.get("split_files", True))
        skip_technical = _coerce_bool(kwargs.get("skip_technical", True))
        threads = int(kwargs.get("threads", 4) or 4)
        if threads < 1:
            raise ValueError("threads must be at least 1")
        output_format = str(kwargs.get("output_format", "") or kwargs.get("format", "fastq") or "fastq").lower()
        if output_format not in SRA_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported SRA output_format: {output_format}")

        out_dir = _node_output_dir(self, context)
        downloaded_files: list[str] = []
        reports: list[dict[str, Any]] = []

        for accession in accessions:
            report: dict[str, Any] = {
                "accession": accession,
                "status": "pending",
                "files": [],
            }

            prefetch_cmd = ["prefetch", "-O", str(out_dir), accession]
            try:
                prefetch_result = await _run_command(prefetch_cmd, out_dir, context)
                if prefetch_result["returncode"] != 0:
                    report["status"] = "prefetch_failed"
                    report["error"] = prefetch_result["stderr"]
                    reports.append(report)
                    continue

                dump_cmd = [
                    "fasterq-dump",
                    "--outdir",
                    str(out_dir),
                    "--threads",
                    str(threads),
                ]
                if output_format == "fasta":
                    dump_cmd.append("--fasta")
                if split_files:
                    dump_cmd.append("--split-files")
                if skip_technical:
                    dump_cmd.append("--skip-technical")
                dump_cmd.append(accession)

                dump_result = await _run_command(dump_cmd, out_dir, context)
                if dump_result["returncode"] != 0:
                    report["status"] = "dump_failed"
                    report["error"] = dump_result["stderr"]
                    reports.append(report)
                    continue

                files = _collect_sra_files(out_dir, accession, output_format)
                downloaded_files.extend(files)
                report["status"] = "completed"
                report["files"] = files
            except Exception as exc:
                report["status"] = "error"
                report["error"] = str(exc)

            reports.append(report)

        report_path = out_dir / "download_report.json"
        report_path.write_text(json.dumps(reports, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "fastq_files": downloaded_files,
                "download_report": str(report_path),
            }
        }


class SRAFetchNode(SRADownloadNode):
    """Compatibility wrapper for the original SRA fetch roadmap node ID."""

    NODE_ID = "sra_fetch"
    DISPLAY_NAME = "SRA Fetch"
    DESCRIPTION = "Fetch FASTQ or FASTA files from NCBI Sequence Read Archive using sra-toolkit."
    SEARCH_ALIASES = [
        "sra fetch",
        "sra",
        "sequence read archive",
        "download",
        "fastq",
        "fasta",
        "ngs",
        "reads",
        "prefetch",
    ]
