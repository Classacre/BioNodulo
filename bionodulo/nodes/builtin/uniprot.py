"""UniProt REST API integration nodes."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


UNIPROT_BASE_URL = "https://rest.uniprot.org"
UNIPROT_USER_AGENT = "BioNodulo/2.0 (workflow node; UniProt REST)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
UNIPROT_CACHE_TTL_S = 300.0
UNIPROT_RATE_LIMIT_PER_SECOND = 5.0
_UNIPROT_CACHE = APICache(ttl_seconds=UNIPROT_CACHE_TTL_S)
_UNIPROT_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=UNIPROT_RATE_LIMIT_PER_SECOND, burst=1)
UNIPROT_SEARCH_FIELDS = "accession,id,gene_names,organism_name,protein_name,length"
UNIPROT_SEARCH_DATABASES = ("uniprotkb", "uniref", "uniparc")
UNIPROT_SUMMARY_COLUMNS = (
    "accession",
    "entry_name",
    "protein_name",
    "organism",
    "gene_names",
    "sequence_length",
)


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or "uniprot"


def _coerce_accessions(value: Any) -> list[str]:
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


async def _request_json(
    resource: str,
    *,
    params: dict[str, Any] | None = None,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request(resource, params=params, retries=retries, timeout=timeout)
    return response.json()


async def _request_text(
    resource: str,
    *,
    params: dict[str, Any] | None = None,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _request(resource, params=params, retries=retries, timeout=timeout)
    return response.text


async def _request(
    resource: str,
    *,
    params: dict[str, Any] | None,
    retries: int,
    timeout: float,
) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{UNIPROT_BASE_URL}/{resource}"
    client = APIHttpClient(cache=_UNIPROT_CACHE, rate_limiter=_UNIPROT_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            params=params,
            headers={"User-Agent": UNIPROT_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=UNIPROT_CACHE_TTL_S,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"UniProt {resource} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"UniProt {resource} request failed: {exc}") from exc


def _first_protein_name(payload: dict[str, Any]) -> str:
    description = payload.get("proteinDescription")
    if not isinstance(description, dict):
        return ""
    candidates: list[Any] = []
    if isinstance(description.get("recommendedName"), dict):
        candidates.append(description["recommendedName"])
    submission_names = description.get("submissionNames")
    if isinstance(submission_names, list):
        candidates.extend(item for item in submission_names if isinstance(item, dict))
    for candidate in candidates:
        full_name = candidate.get("fullName")
        if isinstance(full_name, dict) and full_name.get("value"):
            return str(full_name["value"])
    return ""


def _gene_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for gene in payload.get("genes", []) if isinstance(payload.get("genes"), list) else []:
        if not isinstance(gene, dict):
            continue
        gene_name = gene.get("geneName")
        if isinstance(gene_name, dict) and gene_name.get("value"):
            names.append(str(gene_name["value"]))
        for synonym in gene.get("synonyms", []) if isinstance(gene.get("synonyms"), list) else []:
            if isinstance(synonym, dict) and synonym.get("value"):
                names.append(str(synonym["value"]))
    return names


def _with_summary(payload: dict[str, Any]) -> dict[str, Any]:
    sequence = payload.get("sequence") if isinstance(payload.get("sequence"), dict) else {}
    organism = payload.get("organism") if isinstance(payload.get("organism"), dict) else {}
    enriched = dict(payload)
    enriched["summary"] = {
        "accession": str(payload.get("primaryAccession", "")),
        "entry_name": str(payload.get("uniProtkbId", "")),
        "protein_name": _first_protein_name(payload),
        "organism": str(organism.get("scientificName", "")),
        "gene_names": _gene_names(payload),
        "sequence_length": sequence.get("length"),
    }
    return enriched


def _summary_row(payload: dict[str, Any]) -> dict[str, str]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    gene_names = summary.get("gene_names")
    if isinstance(gene_names, list):
        gene_text = ";".join(str(item) for item in gene_names)
    else:
        gene_text = str(gene_names or "")
    sequence_length = summary.get("sequence_length")
    return {
        "accession": str(summary.get("accession") or ""),
        "entry_name": str(summary.get("entry_name") or ""),
        "protein_name": str(summary.get("protein_name") or ""),
        "organism": str(summary.get("organism") or ""),
        "gene_names": gene_text,
        "sequence_length": "" if sequence_length is None else str(sequence_length),
    }


def _write_summary_tsv(path: Path, entries: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(UNIPROT_SUMMARY_COLUMNS),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(_summary_row(entry))


class UniProtSearchNode(BaseNode):
    """Search UniProtKB and write a summary table."""

    NODE_ID = "uniprot_search"
    DISPLAY_NAME = "UniProt Search"
    CATEGORY = "databases"
    DESCRIPTION = "Search UniProtKB and return matching protein entries as JSON plus a TSV summary."
    SEARCH_ALIASES = ["uniprot", "protein", "swissprot", "trembl", "search", "database"]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("results_table", "results_data")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://www.uniprot.org/help/api_queries"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("STRING", {"default": "", "description": "UniProt query, e.g. gene:TP53 AND organism_id:9606"}),
            },
            "optional": {
                "database": ("STRING", {"default": "uniprotkb", "options": list(UNIPROT_SEARCH_DATABASES)}),
                "max_results": ("INT", {"default": 25, "min": 1, "max": 500}),
                "size": ("INT", {"default": 25, "min": 1, "max": 500, "advanced": True}),
                "reviewed_only": ("BOOLEAN", {"default": False}),
                "include_isoform": ("BOOLEAN", {"default": False, "advanced": True}),
                "fields": ("STRING", {"default": UNIPROT_SEARCH_FIELDS, "advanced": True}),
                "output_name": ("STRING", {"default": "", "description": "Optional TSV filename stem"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        query = str(kwargs.get("query", "") or "").strip()
        if not query:
            raise ValueError("UniProt Search requires a non-empty query")
        max_results = int(kwargs.get("size") or kwargs.get("max_results", 25))
        if max_results < 1:
            raise ValueError("max_results must be at least 1")
        database = str(kwargs.get("database", "uniprotkb") or "uniprotkb").strip().lower()
        if database not in UNIPROT_SEARCH_DATABASES:
            allowed = ", ".join(UNIPROT_SEARCH_DATABASES)
            raise ValueError(f"UniProt Search database must be one of: {allowed}")

        effective_query = f"({query}) AND reviewed:true" if bool(kwargs.get("reviewed_only", False)) else query
        fields = str(kwargs.get("fields", "") or UNIPROT_SEARCH_FIELDS).strip()
        params: dict[str, Any] = {
            "query": effective_query,
            "format": "json",
            "fields": fields,
            "size": max_results,
        }
        if bool(kwargs.get("include_isoform", False)):
            params["includeIsoform"] = "true"

        payload = await _request_json(f"{database}/search", params=params)
        raw_entries = payload.get("results", [])
        if not isinstance(raw_entries, list):
            raw_entries = []
        entries = [_with_summary(entry) for entry in raw_entries if isinstance(entry, dict)]

        output_name = str(kwargs.get("output_name", "") or "").strip()
        filename = _safe_filename(output_name or "uniprot_search") + ".tsv"
        table_path = _node_output_dir(self, context) / filename
        _write_summary_tsv(table_path, entries)

        return {
            "outputs": {
                "results_table": str(table_path),
                "results_data": {
                    "query": query,
                    "effective_query": effective_query,
                    "record_count": len(entries),
                    "entries": entries,
                },
            }
        }


class UniProtRetrieveNode(BaseNode):
    """Retrieve UniProtKB entries and FASTA sequences by accession."""

    NODE_ID = "uniprot_retrieve"
    DISPLAY_NAME = "UniProt Retrieve"
    CATEGORY = "databases"
    DESCRIPTION = "Retrieve UniProtKB protein entries and optional FASTA sequences by accession."
    SEARCH_ALIASES = ["uniprot", "protein", "swissprot", "trembl", "fasta", "database"]
    RETURN_TYPES = ("JSON", "FASTA")
    RETURN_NAMES = ("protein_data", "sequence")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://www.uniprot.org/help/api"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "uniprot_ids": ("STRING", {"default": "", "description": "UniProt accession(s), comma-separated"}),
            },
            "optional": {
                "format": ("STRING", {"default": "json", "options": ["json", "fasta"]}),
                "accession": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Backward-compatible UniProt accession(s), comma-separated",
                    },
                ),
                "include_fasta": ("BOOLEAN", {"default": True}),
                "include_isoform": ("BOOLEAN", {"default": False, "advanced": True}),
                "output_name": ("STRING", {"default": "", "description": "Optional FASTA filename stem"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        accessions = _coerce_accessions(kwargs.get("uniprot_ids", "") or kwargs.get("accession", ""))
        if not accessions:
            raise ValueError("UniProt Retrieve requires at least one uniprot_id")
        output_format = str(kwargs.get("format", "json") or "json").strip().lower()
        if output_format not in {"json", "fasta"}:
            raise ValueError("UniProt Retrieve format must be one of: json, fasta")

        entries: list[dict[str, Any]] = []
        fasta_records: list[str] = []
        include_fasta = bool(kwargs["include_fasta"]) if "include_fasta" in kwargs else output_format == "fasta"
        params = {"includeIsoform": "true"} if bool(kwargs.get("include_isoform", False)) else None
        for accession in accessions:
            entries.append(_with_summary(await _request_json(f"uniprotkb/{accession}.json", params=params)))
            if include_fasta:
                fasta_records.append(await _request_text(f"uniprotkb/{accession}.fasta", params=params))

        protein_data: dict[str, Any]
        if len(entries) == 1:
            protein_data = entries[0]
        else:
            protein_data = {
                "accessions": accessions,
                "record_count": len(entries),
                "entries": entries,
            }

        sequence_path = ""
        if include_fasta:
            output_name = str(kwargs.get("output_name", "") or "").strip()
            if output_name:
                filename = _safe_filename(output_name) + ".fasta"
            elif len(accessions) == 1:
                filename = _safe_filename(accessions[0]) + ".fasta"
            else:
                filename = f"{len(accessions)}_uniprot_sequences.fasta"
            out_path = _node_output_dir(self, context) / filename
            out_path.write_text("".join(record.rstrip("\n") + "\n" for record in fasta_records), encoding="utf-8")
            sequence_path = str(out_path)

        return {
            "outputs": {
                "protein_data": protein_data,
                "sequence": sequence_path,
            }
        }
