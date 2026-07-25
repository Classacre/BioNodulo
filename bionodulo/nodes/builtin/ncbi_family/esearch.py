"""NCBI ESearch pinned to the 2026-03-04 E-utilities reference."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    NCBI_EUTILS_DOCUMENTATION_URL,
    NCBI_EUTILS_REVISION,
    NCBI_EUTILS_SOURCE_SHA256,
    identified_params,
    normalize_database,
    request_json,
    resolve_api_key,
    resolve_email,
    validate_email,
)


class NCBIESearchNode(BaseNode):
    """Search one Entrez database and return the documented UID list."""

    NODE_ID = "ncbi_esearch"
    DISPLAY_NAME = "NCBI ESearch"
    CATEGORY = "databases"
    DESCRIPTION = "Search an NCBI Entrez database and return matching UIDs."
    SEARCH_ALIASES = ["ncbi", "entrez", "esearch", "pubmed", "gene", "sra", "database"]
    RETURN_TYPES = ("JSON", "INT", "STRING")
    RETURN_NAMES = ("id_list", "total_count", "query_translation")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = NCBI_EUTILS_REVISION
    DOCUMENTATION_URL = NCBI_EUTILS_DOCUMENTATION_URL
    SOURCE_URL = NCBI_EUTILS_DOCUMENTATION_URL
    SOURCE_REVISION = NCBI_EUTILS_REVISION
    SOURCE_SHA256 = NCBI_EUTILS_SOURCE_SHA256
    UPSTREAM_SOURCE = "ESearch: db, term, retstart, retmax, sort, retmode=json; output idlist UIDs"
    EXIT_SEMANTICS = (
        "Invalid local inputs fail before submission; HTTP and transport errors are fatal after bounded retries."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("STRING", {"default": "", "description": "Entrez search term"}),
                "database": ("STRING", {"default": "pubmed", "description": "Entrez database name"}),
            },
            "optional": {
                "max_results": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "retstart": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sort": (
                    "STRING",
                    {"default": "", "description": "Database-specific sort; empty uses the NCBI default"},
                ),
                "email": ("STRING", {"default": "", "advanced": True}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("query", "")).strip():
            return "Input 'query' must be non-empty"
        if not str(inputs.get("database", "")).strip():
            return "Input 'database' must be non-empty"
        max_results = inputs.get("max_results", 20)
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            return "Input 'max_results' must be an integer"
        if not 1 <= max_results <= 10000:
            return "Input 'max_results' must be between 1 and 10000"
        retstart = inputs.get("retstart", 0)
        if isinstance(retstart, bool) or not isinstance(retstart, int):
            return "Input 'retstart' must be an integer"
        if retstart < 0:
            return "Input 'retstart' must be at least 0"
        return validate_email(resolve_email(inputs.get("email", "")))

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        email = resolve_email(kwargs.get("email", ""))
        params: dict[str, Any] = {
            "db": normalize_database(kwargs["database"], default="pubmed"),
            "term": str(kwargs["query"]).strip(),
            "retmode": "json",
            "retmax": kwargs.get("max_results", 20),
            "retstart": kwargs.get("retstart", 0),
            **identified_params(email=email),
        }
        sort = str(kwargs.get("sort", "")).strip()
        if sort:
            params["sort"] = sort
        api_key = resolve_api_key(kwargs.get("api_key", ""), context)
        if api_key:
            params["api_key"] = api_key

        payload = await request_json("esearch.fcgi", params)
        result = payload.get("esearchresult", {})
        if not isinstance(result, dict):
            raise RuntimeError("NCBI ESearch returned an invalid esearchresult object")
        ids = [str(item) for item in result.get("idlist", [])]
        try:
            count = int(result.get("count", 0))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("NCBI ESearch returned an invalid count") from exc
        return {
            "outputs": {
                "id_list": ids,
                "total_count": count,
                "query_translation": str(result.get("querytranslation", "")),
            }
        }
