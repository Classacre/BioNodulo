"""GEO metadata lookup through the documented GDS E-utilities database."""

from __future__ import annotations

import json
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    NCBI_EUTILS_DOCUMENTATION_URL,
    NCBI_EUTILS_REVISION,
    NCBI_EUTILS_SOURCE_SHA256,
    identified_params,
    node_output_dir,
    request_json,
    resolve_api_key,
    resolve_email,
    validate_email,
)


GEO_QUERY_TYPES = ("search", "series", "sample", "platform")
GEO_ENTRY_TYPES = {"series": "gse", "sample": "gsm", "platform": "gpl"}


def summaries_from_esummary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return []
    uids = [str(uid) for uid in result.get("uids", []) if str(uid)]
    if uids:
        return [result[uid] for uid in uids if isinstance(result.get(uid), dict)]
    return [value for key, value in result.items() if key != "uids" and isinstance(value, dict)]


def record_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            if isinstance(value, list):
                return ",".join(str(item) for item in value)
            return str(value).replace("\t", " ").replace("\n", " ")
    return ""


def summaries_to_tsv(summaries: list[dict[str, Any]]) -> str:
    lines = ["uid\taccession\ttitle\tentry_type\tgds_type\tn_samples\torganism\tplatform\tpublication_date"]
    for record in summaries:
        lines.append(
            "\t".join(
                [
                    record_value(record, "uid"),
                    record_value(record, "accession", "Accession"),
                    record_value(record, "title"),
                    record_value(record, "entryType", "entry_type"),
                    record_value(record, "gdsType", "gds_type"),
                    record_value(record, "n_samples", "nSamples"),
                    record_value(record, "taxon", "organism"),
                    record_value(record, "GPL", "platform"),
                    record_value(record, "PDAT", "pdat", "publication_date"),
                ]
            )
        )
    return "\n".join(lines) + "\n"


class GEOQueryNode(BaseNode):
    """Run a GDS ESearch followed by ESummary for GEO metadata."""

    NODE_ID = "geo_query"
    DISPLAY_NAME = "GEO Query"
    CATEGORY = "databases"
    DESCRIPTION = "Search or retrieve GEO series, sample, and platform metadata through Entrez GDS."
    SEARCH_ALIASES = ["geo", "gene expression omnibus", "metadata", "series", "sample", "gds"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("geo_metadata", "sample_table")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = NCBI_EUTILS_REVISION
    DOCUMENTATION_URL = "https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html"
    SOURCE_URL = NCBI_EUTILS_DOCUMENTATION_URL
    SOURCE_REVISION = NCBI_EUTILS_REVISION
    SOURCE_SHA256 = NCBI_EUTILS_SOURCE_SHA256
    UPSTREAM_SOURCE = "ESearch db=gds followed by ESummary db=gds; GEO ACCN and ETYP fields"
    EXIT_SEMANTICS = (
        "Invalid local inputs fail before submission; ESearch or ESummary HTTP and transport errors are fatal."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("STRING", {"default": "", "description": "GEO accession or search query"}),
            },
            "optional": {
                "query_type": (list(GEO_QUERY_TYPES), {"default": "series"}),
                "max_results": ("INT", {"default": 10, "min": 1, "max": 10000}),
                "email": ("STRING", {"default": "", "advanced": True}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "accession": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Backward-compatible accession input"},
                ),
                "search_query": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Backward-compatible search input"},
                ),
                "dataset_type": (
                    "STRING",
                    {"default": "", "options": list(GEO_QUERY_TYPES), "advanced": True},
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        query_type = str(inputs.get("query_type", "") or inputs.get("dataset_type", "") or "series").lower()
        if query_type not in GEO_QUERY_TYPES:
            return f"Input 'query_type' must be one of: {', '.join(GEO_QUERY_TYPES)}"
        query = str(inputs.get("query", "") or inputs.get("accession", "") or inputs.get("search_query", "")).strip()
        if not query:
            return "Input 'query' must be non-empty"
        max_results = inputs.get("max_results", 10)
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            return "Input 'max_results' must be an integer"
        if not 1 <= max_results <= 10000:
            return "Input 'max_results' must be between 1 and 10000"
        return validate_email(resolve_email(inputs.get("email", "")))

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        query_type = str(kwargs.get("query_type", "") or kwargs.get("dataset_type", "") or "series").lower()
        query = str(kwargs.get("query", "") or kwargs.get("accession", "") or kwargs.get("search_query", "")).strip()
        term = query if query_type == "search" else f"{query}[ACCN] AND {GEO_ENTRY_TYPES[query_type]}[ETYP]"
        email = resolve_email(kwargs.get("email", ""))
        api_key = resolve_api_key(kwargs.get("api_key", ""), context)
        search_params: dict[str, Any] = {
            "db": "gds",
            "term": term,
            "retmode": "json",
            "retmax": kwargs.get("max_results", 10),
            **identified_params(email=email),
        }
        if api_key:
            search_params["api_key"] = api_key
        search_payload = await request_json("esearch.fcgi", search_params)
        search_result = search_payload.get("esearchresult", {})
        if not isinstance(search_result, dict):
            raise RuntimeError("GEO ESearch returned an invalid esearchresult object")
        uids = [str(uid) for uid in search_result.get("idlist", [])]
        try:
            total_count = int(search_result.get("count", 0))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("GEO ESearch returned an invalid count") from exc

        summaries: list[dict[str, Any]] = []
        if uids:
            summary_params: dict[str, Any] = {
                "db": "gds",
                "id": ",".join(uids),
                "retmode": "json",
                **identified_params(email=email),
            }
            if api_key:
                summary_params["api_key"] = api_key
            summaries = summaries_from_esummary(await request_json("esummary.fcgi", summary_params))

        metadata = {
            "query": term,
            "query_type": query_type,
            "uids": uids,
            "total_count": total_count,
            "record_count": len(summaries),
            "summaries": summaries,
        }
        output_dir = node_output_dir(self, context)
        metadata_path = output_dir / ("geo_search_results.json" if query_type == "search" else "geo_metadata.json")
        table_path = output_dir / ("geo_results.tsv" if query_type == "search" else "sample_table.tsv")
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        table_path.write_text(summaries_to_tsv(summaries), encoding="utf-8")
        return {
            "outputs": {
                "geo_metadata": str(metadata_path),
                "sample_table": str(table_path),
            }
        }
