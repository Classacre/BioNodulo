"""STRING 12.0 version-pinned text API queries."""

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


STRING_VERSION = "12.0"
STRING_STABLE_ADDRESS = "https://version-12-0.string-db.org"
STRING_BASE_URL = f"{STRING_STABLE_ADDRESS}/api"
STRING_VERSION_ENDPOINT = "https://string-db.org/api/json/version"
STRING_API_DOCUMENTATION_URL = f"{STRING_STABLE_ADDRESS}/help/api/"
STRING_API_DOCUMENTATION_REVISION = "2026-06-02T11:15:10Z"
# SHA-256 of the help HTML fetched with ``Range: bytes=0-``, which omits Cloudflare's injected link.
STRING_API_DOCUMENTATION_SHA256 = "4c5af2b0805b739902ea439ac410882969a56f3a00fd6125c7449fc5ba96544c"
STRING_USER_AGENT = "BioNodulo/2.0 (STRING 12.0 node)"
STRING_API_CACHE = APICache.from_environment(default_ttl_seconds=300.0)
STRING_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=1.0, burst=1)
STRING_QUERY_TYPES = ("network", "interactions", "enrichment", "mapping")
NETWORK_TYPES = ("functional", "physical")

INTERACTION_COLUMNS = frozenset(
    {
        "stringId_A",
        "stringId_B",
        "preferredName_A",
        "preferredName_B",
        "ncbiTaxonId",
        "score",
        "nscore",
        "fscore",
        "pscore",
        "ascore",
        "escore",
        "dscore",
        "tscore",
    }
)
STRING_REQUIRED_TSV_COLUMNS = {
    "network": INTERACTION_COLUMNS,
    "interactions": INTERACTION_COLUMNS,
    "enrichment": frozenset(
        {
            "category",
            "term",
            "number_of_genes",
            "number_of_genes_in_background",
            "ncbiTaxonId",
            "inputGenes",
            "preferredNames",
            "p_value",
            "fdr",
            "description",
        }
    ),
    "mapping": frozenset(
        {
            "queryIndex",
            "stringId",
            "ncbiTaxonId",
            "taxonName",
            "preferredName",
            "annotation",
        }
    ),
}


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output = base / node.NODE_ID
    output.mkdir(parents=True, exist_ok=True)
    return output


def _coerce_identifiers(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        values = [str(item).strip() for item in value]
    else:
        text = str(value or "").strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                values = [str(item).strip() for item in parsed]
            else:
                values = re.split(r"[\s,;]+", text)
        else:
            values = re.split(r"[\s,;]+", text)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _read_identifier_table(path: str | Path, column: str) -> list[str]:
    if not column:
        raise ValueError("id_column is required when protein_table is provided")
    with Path(path).open(newline="", encoding="utf-8") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        # Decide the delimiter from the HEADER, not by sniffing a byte window.
        # Sniffer inspects a truncated sample and, on a real results table, can
        # settle on a delimiter that appears inside quoted text; the whole line
        # then parses as one field and csv raises "field larger than field
        # limit (131072)" -- which reads like a data problem rather than a
        # mis-detected dialect.
        header = sample.splitlines()[0] if sample.strip() else ""
        if "\t" in header and ("," not in header or header.count("\t") >= header.count(",")):
            dialect: Any = csv.excel_tab
        elif "," in header:
            dialect = csv.excel
        else:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t") if sample.strip() else csv.excel_tab
            except csv.Error:
                dialect = csv.excel_tab
        reader = csv.DictReader(handle, dialect=dialect)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(f"Column {column!r} not found in STRING identifier table")
        return [str(row.get(column, "")).strip() for row in reader if str(row.get(column, "")).strip()]


def _parse_tsv(text: str, query_type: str) -> list[dict[str, str]]:
    if not text.strip():
        raise RuntimeError(f"STRING {query_type} returned an empty TSV response")

    reader = csv.DictReader(StringIO(text.lstrip("\ufeff")), delimiter="\t")
    fieldnames = reader.fieldnames or []
    missing = sorted(STRING_REQUIRED_TSV_COLUMNS[query_type].difference(fieldnames))
    if missing:
        raise RuntimeError(
            f"STRING {query_type} returned an invalid TSV header; missing documented fields: "
            f"{', '.join(missing)}"
        )

    rows: list[dict[str, str]] = []
    for line_number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"STRING {query_type} returned a malformed TSV row at line {line_number}")
        rows.append(dict(row))
    return rows


async def _request_text(endpoint: str, data: dict[str, Any]) -> str:
    client = APIHttpClient(cache=STRING_API_CACHE, rate_limiter=STRING_RATE_LIMITER)
    url = f"{STRING_BASE_URL}/{endpoint.lstrip('/')}"
    try:
        response = await client.request(
            "POST",
            url,
            data=data,
            headers={"User-Agent": STRING_USER_AGENT},
            timeout=30.0,
            retries=3,
            retry_delay=1.0,
            cache_ttl=None,
        )
        return response.text
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"STRING {endpoint} failed with HTTP {exc.response.status_code}: {exc.response.text[:500]}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"STRING {endpoint} request failed: {exc}") from exc


def _request_contract(
    *,
    identifiers: list[str],
    species: int,
    query_type: str,
    required_score: int,
    add_nodes: int,
    interaction_limit: int,
    network_type: str,
) -> tuple[str, dict[str, Any]]:
    data: dict[str, Any] = {
        "identifiers": "\r".join(identifiers),
        "species": species,
        "caller_identity": "BioNodulo",
    }
    if query_type == "network":
        data.update(
            {
                "required_score": required_score,
                "add_nodes": add_nodes,
                "network_type": network_type,
            }
        )
        return "tsv/network", data
    if query_type == "interactions":
        data.update(
            {
                "required_score": required_score,
                "limit": interaction_limit,
                "network_type": network_type,
            }
        )
        return "tsv/interaction_partners", data
    if query_type == "enrichment":
        return "tsv/enrichment", data
    return "tsv/get_string_ids", data


class STRINGDBNode(BaseNode):
    """Query stable STRING 12.0 text endpoints."""

    NODE_ID = "string_db"
    DISPLAY_NAME = "STRING DB"
    CATEGORY = "api"
    DESCRIPTION = "Query STRING 12.0 protein networks, partners, enrichment, or identifier mapping."
    SEARCH_ALIASES = ["STRING", "protein interaction", "PPI", "network", "enrichment", "mapping"]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("interaction_network", "network_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = STRING_VERSION
    SOURCE_URL = STRING_API_DOCUMENTATION_URL
    SOURCE_REVISION = STRING_API_DOCUMENTATION_REVISION
    SOURCE_SHA256 = STRING_API_DOCUMENTATION_SHA256
    DOCUMENTATION_URL = STRING_API_DOCUMENTATION_URL
    VERSION_SOURCE_URL = STRING_VERSION_ENDPOINT
    UPSTREAM_SOURCE = (
        "version-specific API help: common conventions plus network, interaction_partners, enrichment, "
        "and get_string_ids contracts"
    )
    EXIT_SEMANTICS = (
        "HTTP and transport errors are fatal after three attempts; successful responses must contain the "
        "documented query-specific TSV header and structurally complete rows."
    )
    NETWORK_SEMANTICS = (
        "Production calls use the official version-specific STRING 12.0 address and POST bodies for long identifier lists."
    )
    LICENSE_SEMANTICS = "STRING data/API use remains subject to STRING licensing and attribution terms."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "protein_ids": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Identifiers as a list, JSON list, or separated text",
                        "displayOptions": {"show": {"protein_table": [""]}},
                    },
                ),
                "species": ("INT", {"default": 9606, "min": 1}),
                "query_type": ("STRING", {"default": "network", "options": list(STRING_QUERY_TYPES)}),
                "required_score": ("INT", {"default": 400, "min": 0, "max": 1000}),
                "network_type": ("STRING", {"default": "functional", "options": list(NETWORK_TYPES)}),
                "add_nodes": ("INT", {"default": 0, "min": 0, "max": 50}),
                "interaction_limit": ("INT", {"default": 10, "min": 1, "max": 1000}),
                "protein_table": ("FILE", {"default": "", "description": "Optional CSV/TSV identifier table"}),
                "id_column": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        identifiers = _coerce_identifiers(kwargs.get("protein_ids", ""))
        table = str(kwargs.get("protein_table", "") or "").strip()
        if table:
            identifiers = _coerce_identifiers(
                identifiers + _read_identifier_table(table, str(kwargs.get("id_column", "") or "").strip())
            )
        if not identifiers:
            raise ValueError("STRING DB requires at least one protein ID")
        query_type = str(kwargs.get("query_type", "network") or "network")
        if query_type not in STRING_QUERY_TYPES:
            raise ValueError(f"Unsupported STRING query_type: {query_type}")
        raw_species = kwargs.get("species", 9606)
        species = int(9606 if raw_species in (None, "") else raw_species)
        raw_required_score = kwargs.get("required_score", 400)
        required_score = int(400 if raw_required_score in (None, "") else raw_required_score)
        raw_add_nodes = kwargs.get("add_nodes", 0)
        add_nodes = int(0 if raw_add_nodes in (None, "") else raw_add_nodes)
        raw_interaction_limit = kwargs.get("interaction_limit", 10)
        interaction_limit = int(10 if raw_interaction_limit in (None, "") else raw_interaction_limit)
        network_type = str(kwargs.get("network_type", "functional") or "functional")
        if species < 1:
            raise ValueError("STRING species must be positive")
        if not 0 <= required_score <= 1000:
            raise ValueError("STRING required_score must be between 0 and 1000")
        if not 0 <= add_nodes <= 50:
            raise ValueError("STRING add_nodes must be between 0 and 50")
        if not 1 <= interaction_limit <= 1000:
            raise ValueError("STRING interaction_limit must be between 1 and 1000")
        if network_type not in NETWORK_TYPES:
            raise ValueError(f"Unsupported STRING network_type: {network_type}")
        endpoint, request_data = _request_contract(
            identifiers=identifiers,
            species=species,
            query_type=query_type,
            required_score=required_score,
            add_nodes=add_nodes,
            interaction_limit=interaction_limit,
            network_type=network_type,
        )
        text = await _request_text(endpoint, request_data)
        rows = _parse_tsv(text, query_type)
        output = _node_output_dir(self, context)
        tsv_path = output / "interaction_network.tsv"
        metadata_path = output / "network_metadata.json"
        tsv_path.write_text(text, encoding="utf-8")
        metadata = {
            "string_version": STRING_VERSION,
            "stable_address": STRING_STABLE_ADDRESS,
            "query_type": query_type,
            "endpoint": endpoint,
            "identifiers": identifiers,
            "species": species,
            "required_score": required_score,
            "network_type": network_type,
            "add_nodes": add_nodes,
            "interaction_limit": interaction_limit,
            "record_count": len(rows),
            "rows": rows,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"outputs": {"interaction_network": str(tsv_path), "network_metadata": str(metadata_path)}}
