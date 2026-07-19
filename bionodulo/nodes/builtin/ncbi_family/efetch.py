"""NCBI EFetch pinned to the 2026-03-04 E-utilities reference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    NCBI_EUTILS_DOCUMENTATION_URL,
    NCBI_EUTILS_REVISION,
    NCBI_EUTILS_SOURCE_SHA256,
    chunked,
    coerce_ids,
    identified_params,
    node_output_dir,
    normalize_database,
    request_text,
    resolve_api_key,
    resolve_email,
    safe_filename,
    validate_email,
)


EFETCH_RETMODES = ("text", "xml", "json")
STRUCTURED_RETMODES = frozenset({"xml", "json"})


def default_extension(rettype: str, retmode: str) -> str:
    if retmode == "json":
        return ".json"
    if retmode == "xml":
        return ".xml"
    if rettype in {"fasta", "fasta_cds_na", "fasta_cds_aa"}:
        return ".fasta"
    if rettype in {"gb", "gbwithparts"}:
        return ".gb"
    return ".txt"


class NCBIEFetchNode(BaseNode):
    """Fetch one or more Entrez records into one response artifact."""

    NODE_ID = "ncbi_efetch"
    DISPLAY_NAME = "NCBI EFetch"
    CATEGORY = "databases"
    DESCRIPTION = "Fetch records from an NCBI Entrez database by UID or accession."
    SEARCH_ALIASES = ["ncbi", "entrez", "efetch", "pubmed", "gene", "fasta", "database"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("records", "metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = NCBI_EUTILS_REVISION
    DOCUMENTATION_URL = NCBI_EUTILS_DOCUMENTATION_URL
    SOURCE_URL = NCBI_EUTILS_DOCUMENTATION_URL
    SOURCE_REVISION = NCBI_EUTILS_REVISION
    SOURCE_SHA256 = NCBI_EUTILS_SOURCE_SHA256
    UPSTREAM_SOURCE = "EFetch: db, id, rettype, retmode; rettype/retmode validity is database-specific"
    EXIT_SEMANTICS = (
        "Invalid local inputs and unsupported structured multi-batch requests fail before submission; "
        "HTTP and transport errors are fatal after bounded retries."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "accessions": (
                    "STRING",
                    {"default": "", "description": "UIDs or accessions as a list or delimited string"},
                ),
                "database": ("STRING", {"default": "nuccore", "description": "Entrez database name"}),
            },
            "optional": {
                "rettype": (
                    "STRING",
                    {"default": "fasta", "description": "Database-specific EFetch retrieval type"},
                ),
                "retmode": (list(EFETCH_RETMODES), {"default": "text"}),
                "batch_size": ("INT", {"default": 100, "min": 1}),
                "email": ("STRING", {"default": "", "advanced": True}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "id_list": (
                    "ANY",
                    {"default": "", "advanced": True, "description": "Backward-compatible ID input"},
                ),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        ids = coerce_ids(inputs.get("accessions", "") or inputs.get("id_list", ""))
        if not ids:
            return "Input 'accessions' must contain at least one UID or accession"
        if not str(inputs.get("database", "")).strip():
            return "Input 'database' must be non-empty"
        if not str(inputs.get("rettype", "fasta")).strip():
            return "Input 'rettype' must be non-empty"
        retmode = str(inputs.get("retmode", "text") or "text").lower()
        if retmode not in EFETCH_RETMODES:
            return f"Input 'retmode' must be one of: {', '.join(EFETCH_RETMODES)}"
        batch_size = inputs.get("batch_size", 100)
        if isinstance(batch_size, bool) or not isinstance(batch_size, int):
            return "Input 'batch_size' must be an integer"
        if batch_size < 1:
            return "Input 'batch_size' must be at least 1"
        if retmode in STRUCTURED_RETMODES and len(ids) > batch_size:
            return (
                "Structured EFetch output cannot be split across batches because concatenated documents "
                "would be invalid; increase 'batch_size' or use retmode=text"
            )
        return validate_email(resolve_email(inputs.get("email", "")))

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        ids = coerce_ids(kwargs.get("accessions", "") or kwargs.get("id_list", ""))
        database = normalize_database(kwargs["database"], default="nuccore")
        rettype = str(kwargs.get("rettype", "fasta") or "fasta").strip()
        retmode = str(kwargs.get("retmode", "text") or "text").lower()
        batch_size = int(kwargs.get("batch_size", 100))
        email = resolve_email(kwargs.get("email", ""))
        api_key = resolve_api_key(kwargs.get("api_key", ""), context)
        batches = chunked(ids, batch_size)

        record_parts: list[str] = []
        for batch in batches:
            params: dict[str, Any] = {
                "db": database,
                "id": ",".join(batch),
                "rettype": rettype,
                "retmode": retmode,
                **identified_params(email=email),
            }
            if api_key:
                params["api_key"] = api_key
            record_parts.append(await request_text("efetch.fcgi", params))

        records = "\n".join(part.rstrip("\n") for part in record_parts if part)
        if records:
            records += "\n"
        output_name = str(kwargs.get("output_name", "")).strip()
        if output_name:
            filename = safe_filename(output_name, fallback="records")
        else:
            stem = safe_filename(f"{database}_{rettype}_{len(ids)}_records", fallback="records")
            filename = f"{stem}{default_extension(rettype, retmode)}"
        output_path: Path = node_output_dir(self, context) / filename
        output_path.write_text(records, encoding="utf-8")

        return {
            "outputs": {
                "records": str(output_path),
                "metadata": {
                    "database": database,
                    "ids": ids,
                    "rettype": rettype,
                    "retmode": retmode,
                    "record_count": len(ids),
                    "batch_size": batch_size,
                    "batch_count": len(batches),
                    "records_path": str(output_path),
                },
            }
        }
