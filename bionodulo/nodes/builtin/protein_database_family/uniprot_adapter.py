"""UniProt REST API nodes pinned to the 2025-12-17 help contract."""

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
UNIPROT_HELP_SNAPSHOT_DATE = "2025-12-17"
UNIPROT_QUERY_HELP_SHA256 = "ec7d2c52f3a77767db7342a44ec5a2c28964374cb059479cc2dc853797b5d4d4"
UNIPROT_RETRIEVE_HELP_SHA256 = "a5f12acc8f94c7ae9201389cc5912d398cbc7099617a0e1570cbccf4c2dcfb92"
UNIPROT_USER_AGENT = "BioNodulo/2.0 (workflow node; UniProt REST)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
UNIPROT_CACHE_TTL_S = 300.0
UNIPROT_RATE_LIMIT_PER_SECOND = 5.0
_UNIPROT_CACHE = APICache.from_environment(default_ttl_seconds=UNIPROT_CACHE_TTL_S)
_UNIPROT_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=UNIPROT_RATE_LIMIT_PER_SECOND, burst=1)
UNIPROT_SEARCH_FIELDS = "accession,id,gene_names,organism_name,protein_name,length"
UNIPROT_SEARCH_DATABASES = ("uniprotkb", "uniref", "uniparc")
UNIPROT_SEARCH_FORMATS_BY_DATABASE = {
    "uniprotkb": ("json", "tsv", "xml", "fasta", "rdf", "gff"),
    "uniref": ("json", "tsv", "xml", "fasta", "rdf"),
    "uniparc": ("json", "tsv", "xml", "fasta", "rdf"),
}
UNIPROT_SEARCH_FORMATS = tuple(
    dict.fromkeys(output_format for formats in UNIPROT_SEARCH_FORMATS_BY_DATABASE.values() for output_format in formats)
)
DEFAULT_SEARCH_SIZE = 25
MAX_SEARCH_SIZE = 500
ISOFORM_SEARCH_SIZE = 500
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


def _coerce_optional_int(value: Any, name: str) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"Input '{name}' must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Input '{name}' must be an integer") from exc


def _resolve_search_size(inputs: dict[str, Any]) -> int:
    """Resolve the canonical limit and the legacy ``size`` alias once."""

    max_results = _coerce_optional_int(inputs.get("max_results"), "max_results")
    legacy_size = _coerce_optional_int(inputs.get("size"), "size")
    if legacy_size is not None:
        if max_results not in (None, DEFAULT_SEARCH_SIZE, legacy_size):
            raise ValueError("Inputs 'max_results' and legacy 'size' must not conflict")
        return legacy_size
    return DEFAULT_SEARCH_SIZE if max_results is None else max_results


def _search_params(
    *,
    database: str,
    query: str,
    output_format: str,
    size: int,
    fields: str,
    include_isoform: bool,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "format": output_format,
        "size": size,
    }
    if database == "uniprotkb":
        if output_format in {"json", "tsv"}:
            params["fields"] = fields
        if include_isoform:
            params["includeIsoform"] = "true"
    return params


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
    if isinstance(payload.get("representativeMember"), dict):
        representative = payload["representativeMember"]
        common_taxon = payload.get("commonTaxon") if isinstance(payload.get("commonTaxon"), dict) else {}
        accessions = representative.get("accessions") if isinstance(representative.get("accessions"), list) else []
        sequence = representative.get("sequence") if isinstance(representative.get("sequence"), dict) else {}
        enriched = dict(payload)
        enriched["summary"] = {
            "accession": str(accessions[0] if accessions else representative.get("memberId", "")),
            "entry_name": str(payload.get("id", "")),
            "protein_name": str(representative.get("proteinName") or payload.get("name", "")).removeprefix("Cluster: "),
            "organism": str(common_taxon.get("scientificName", "")),
            "gene_names": [],
            "sequence_length": representative.get("sequenceLength") or sequence.get("length"),
            "member_count": payload.get("memberCount"),
        }
        return enriched

    if payload.get("uniParcId"):
        accessions = payload.get("uniProtKBAccessions") if isinstance(payload.get("uniProtKBAccessions"), list) else []
        common_taxons = payload.get("commonTaxons") if isinstance(payload.get("commonTaxons"), list) else []
        organism = ""
        for taxon in common_taxons:
            if not isinstance(taxon, dict):
                continue
            common_taxon = str(taxon.get("commonTaxon", "") or "")
            if common_taxon and common_taxon != "synthetic construct":
                organism = common_taxon
                break
        if not organism and common_taxons and isinstance(common_taxons[0], dict):
            organism = str(common_taxons[0].get("commonTaxon", "") or "")
        sequence = payload.get("sequence") if isinstance(payload.get("sequence"), dict) else {}
        enriched = dict(payload)
        enriched["summary"] = {
            "accession": str(accessions[0] if accessions else ""),
            "entry_name": str(payload.get("uniParcId", "")),
            "protein_name": "",
            "organism": organism,
            "gene_names": [],
            "sequence_length": sequence.get("length"),
            "cross_reference_count": payload.get("crossReferenceCount"),
        }
        return enriched

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
    """Search a supported UniProt database and write normalized plus raw results."""

    LEGACY_NODE_ID = "uniprot_search"
    DISPLAY_NAME = "UniProt Search"
    CATEGORY = "databases"
    DESCRIPTION = "Search UniProtKB, UniRef, or UniParc and return a normalized TSV plus the requested raw format."
    SEARCH_ALIASES = ["uniprot", "protein", "search", "query", "swissprot", "trembl", "database"]
    RETURN_TYPES = ("TSV", "JSON", "FILE")
    RETURN_NAMES = ("results_table", "results_data", "raw_results")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = UNIPROT_HELP_SNAPSHOT_DATE
    GIT_URL = "https://rest.uniprot.org/help/api_queries"
    GIT_COMMIT = UNIPROT_QUERY_HELP_SHA256
    DOCUMENTATION_URL = "https://www.uniprot.org/help/api_queries"
    SOURCE_URL = "https://rest.uniprot.org/help/api_queries"
    SOURCE_SHA256 = UNIPROT_QUERY_HELP_SHA256
    UPSTREAM_SOURCE = (
        "/{database}/search query, format, and size parameters; UniProtKB-only fields and includeIsoform parameters"
    )
    EXIT_SEMANTICS = (
        "HTTP 4xx/5xx and transport failures are fatal after bounded retries; malformed result payloads "
        "produce an empty deterministic summary rather than invented records."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": (
                    "STRING",
                    {"default": "", "description": "UniProt query, e.g. gene:TP53 AND organism_id:9606"},
                ),
            },
            "optional": {
                "database": ("STRING", {"default": "uniprotkb", "options": list(UNIPROT_SEARCH_DATABASES)}),
                "max_results": ("INT", {"default": DEFAULT_SEARCH_SIZE, "min": 1, "max": MAX_SEARCH_SIZE}),
                "size": (
                    "INT",
                    {
                        "default": None,
                        "min": 1,
                        "max": MAX_SEARCH_SIZE,
                        "advanced": True,
                        "description": "Legacy alias for max_results",
                    },
                ),
                "format": ("STRING", {"default": "json", "options": list(UNIPROT_SEARCH_FORMATS), "advanced": True}),
                "reviewed_only": (
                    "BOOLEAN",
                    {"default": False, "description": "UniProtKB only"},
                ),
                "include_isoform": (
                    "BOOLEAN",
                    {"default": False, "advanced": True, "description": "UniProtKB only"},
                ),
                "fields": (
                    "STRING",
                    {"default": UNIPROT_SEARCH_FIELDS, "advanced": True, "description": "UniProtKB only"},
                ),
                "output_name": ("STRING", {"default": "", "description": "Optional TSV filename stem"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("query", "") or "").strip():
            return "Input 'query' must be non-empty"
        database = str(inputs.get("database", "uniprotkb") or "uniprotkb").lower()
        if database not in UNIPROT_SEARCH_DATABASES:
            return f"Input 'database' must be one of: {', '.join(UNIPROT_SEARCH_DATABASES)}"
        output_format = str(inputs.get("format", "json") or "json").lower()
        supported_formats = UNIPROT_SEARCH_FORMATS_BY_DATABASE[database]
        if output_format not in supported_formats:
            return f"Input 'format' for {database} must be one of: {', '.join(supported_formats)}"
        if database != "uniprotkb" and bool(inputs.get("reviewed_only", False)):
            return "Input 'reviewed_only' is supported only for database 'uniprotkb'"
        if database != "uniprotkb" and bool(inputs.get("include_isoform", False)):
            return "Input 'include_isoform' is supported only for database 'uniprotkb'"
        try:
            size = _resolve_search_size(inputs)
        except ValueError as exc:
            return str(exc)
        if not 1 <= size <= MAX_SEARCH_SIZE:
            return f"Input 'max_results' must be between 1 and {MAX_SEARCH_SIZE}"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        query = str(kwargs.get("query", "") or "").strip()
        max_results = _resolve_search_size(kwargs)
        database = str(kwargs.get("database", "uniprotkb") or "uniprotkb").strip().lower()
        output_format = str(kwargs.get("format", "json") or "json").strip().lower()

        effective_query = (
            f"({query}) AND reviewed:true"
            if database == "uniprotkb" and bool(kwargs.get("reviewed_only", False))
            else query
        )
        fields = str(kwargs.get("fields", "") or UNIPROT_SEARCH_FIELDS).strip()
        include_isoform = database == "uniprotkb" and bool(kwargs.get("include_isoform", False))

        output_name = str(kwargs.get("output_name", "") or "").strip()
        stem = _safe_filename(output_name or "uniprot_search")
        out_dir = _node_output_dir(self, context)
        table_path = out_dir / f"{stem}.tsv"
        raw_path = out_dir / f"{stem}.raw.{output_format}"

        normalized_params = _search_params(
            database=database,
            query=effective_query,
            output_format="json",
            size=max_results,
            fields=fields,
            include_isoform=include_isoform,
        )
        payload = await _request_json(f"{database}/search", params=normalized_params)
        raw_entries = payload.get("results", [])
        if not isinstance(raw_entries, list):
            raw_entries = []
        entries = [_with_summary(entry) for entry in raw_entries if isinstance(entry, dict)]

        _write_summary_tsv(table_path, entries)

        if output_format == "json":
            raw_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            raw_params = _search_params(
                database=database,
                query=effective_query,
                output_format=output_format,
                size=max_results,
                fields=fields,
                include_isoform=include_isoform,
            )
            raw_text = await _request_text(f"{database}/search", params=raw_params)
            raw_path.write_text(raw_text, encoding="utf-8")

        return {
            "outputs": {
                "results_table": str(table_path),
                "results_data": {
                    "query": query,
                    "effective_query": effective_query,
                    "database": database,
                    "format": output_format,
                    "record_count": len(entries),
                    "entries": entries,
                    "raw_path": str(raw_path),
                },
                "raw_results": str(raw_path),
            }
        }


class UniProtRetrieveNode(BaseNode):
    """Retrieve UniProtKB entries and FASTA sequences by accession."""

    LEGACY_NODE_ID = "uniprot_retrieve"
    DISPLAY_NAME = "UniProt Retrieve"
    CATEGORY = "databases"
    DESCRIPTION = "Retrieve UniProtKB protein entries and optional FASTA sequences by accession."
    SEARCH_ALIASES = [
        "uniprot",
        "protein",
        "retrieve",
        "fetch",
        "sequence",
        "fasta",
        "annotation",
        "swissprot",
        "trembl",
        "database",
    ]
    RETURN_TYPES = ("JSON", "FASTA")
    RETURN_NAMES = ("protein_data", "sequence")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = UNIPROT_HELP_SNAPSHOT_DATE
    GIT_URL = "https://rest.uniprot.org/help/api_retrieve_entries"
    GIT_COMMIT = UNIPROT_RETRIEVE_HELP_SHA256
    DOCUMENTATION_URL = "https://www.uniprot.org/help/api"
    SOURCE_URL = "https://rest.uniprot.org/help/api_retrieve_entries"
    SOURCE_SHA256 = UNIPROT_RETRIEVE_HELP_SHA256
    UPSTREAM_SOURCE = (
        "/uniprotkb/{accession}.json and /uniprotkb/{accession}.fasta; "
        "/uniprotkb/search with includeIsoform=true for canonical-plus-isoform expansion"
    )
    EXIT_SEMANTICS = (
        "Each requested accession is fetched independently; any HTTP or transport failure is fatal after "
        "bounded retries, so partial multi-accession outputs are not reported as complete."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "uniprot_ids": ("STRING", {"default": "", "description": "UniProt accession(s), comma-separated"}),
            },
            "optional": {
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
            "hidden": {
                "format": (
                    "STRING",
                    {
                        "description": (
                            "Legacy compatibility only: when include_fasta is absent, fasta enables sequence output"
                        )
                    },
                )
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        effective_inputs = dict(inputs)
        if not _coerce_accessions(effective_inputs.get("uniprot_ids", "")):
            effective_inputs["uniprot_ids"] = effective_inputs.get("accession", "")
        validation = super().VALIDATE_INPUTS(effective_inputs)
        if validation is not True:
            return validation
        if not _coerce_accessions(effective_inputs.get("uniprot_ids", "")):
            return "Input 'uniprot_ids' must contain at least one accession"
        legacy_format = str(inputs.get("format", "") or "").lower()
        if legacy_format and legacy_format not in {"json", "fasta"}:
            return "Input 'format' must be one of: json, fasta"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        accessions = _coerce_accessions(kwargs.get("uniprot_ids", "") or kwargs.get("accession", ""))
        entries: list[dict[str, Any]] = []
        fasta_records: list[str] = []
        legacy_format = str(kwargs.get("format", "") or "").strip().lower()
        if "include_fasta" in kwargs:
            include_fasta = bool(kwargs["include_fasta"])
        elif legacy_format:
            include_fasta = legacy_format == "fasta"
        else:
            include_fasta = True
        include_isoform = bool(kwargs.get("include_isoform", False))
        for accession in accessions:
            if include_isoform:
                query = f"accession:{accession}"
                isoform_json_params = {
                    "query": query,
                    "format": "json",
                    "size": ISOFORM_SEARCH_SIZE,
                    "includeIsoform": "true",
                }
                payload = await _request_json("uniprotkb/search", params=isoform_json_params)
                raw_entries = payload.get("results", [])
                if not isinstance(raw_entries, list) or not raw_entries:
                    raise RuntimeError(f"UniProt isoform search returned no entries for {accession}")
                entries.extend(_with_summary(entry) for entry in raw_entries if isinstance(entry, dict))
                if include_fasta:
                    fasta_records.append(
                        await _request_text(
                            "uniprotkb/search",
                            params={**isoform_json_params, "format": "fasta"},
                        )
                    )
            else:
                entries.append(_with_summary(await _request_json(f"uniprotkb/{accession}.json")))
                if include_fasta:
                    fasta_records.append(await _request_text(f"uniprotkb/{accession}.fasta"))

        protein_data: dict[str, Any]
        if len(entries) == 1:
            protein_data = entries[0]
        else:
            protein_data = {
                "accessions": accessions,
                "retrieved_accessions": [
                    str(entry.get("summary", {}).get("accession", ""))
                    for entry in entries
                    if isinstance(entry.get("summary"), dict)
                ],
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
