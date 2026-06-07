"""Ensembl REST API integration nodes."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


ENSEMBL_BASE_URL = "https://rest.ensembl.org"
ENSEMBL_GRCH37_BASE_URL = "https://grch37.rest.ensembl.org"
ENSEMBL_USER_AGENT = "BioNodulo/2.0 (workflow node; Ensembl REST)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
ENSEMBL_CACHE_TTL_S = 300.0
ENSEMBL_RATE_LIMIT_PER_SECOND = 5.0
ENSEMBL_JSON_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": ENSEMBL_USER_AGENT,
}
VEP_TABLE_COLUMNS = (
    "input",
    "gene_symbol",
    "gene_id",
    "transcript_id",
    "consequence_terms",
    "impact",
)
ENSEMBL_API_CACHE = APICache(ttl_seconds=ENSEMBL_CACHE_TTL_S)
ENSEMBL_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=ENSEMBL_RATE_LIMIT_PER_SECOND, burst=1)


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


async def _request_json(
    resource: str,
    params: dict[str, Any] | None = None,
    *,
    base_url: str = ENSEMBL_BASE_URL,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request(resource, params or {}, base_url=base_url, retries=retries, timeout=timeout)
    return response.json()


async def _post_json(
    resource: str,
    json_body: dict[str, Any],
    params: dict[str, Any] | None = None,
    *,
    base_url: str = ENSEMBL_BASE_URL,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> Any:
    response = await _post(resource, json_body, params or {}, base_url=base_url, retries=retries, timeout=timeout)
    return response.json()


async def _request(
    resource: str,
    params: dict[str, Any],
    *,
    base_url: str,
    retries: int,
    timeout: float,
) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{base_url.rstrip('/')}/{resource}"
    client = APIHttpClient(cache=ENSEMBL_API_CACHE, rate_limiter=ENSEMBL_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            params=params,
            headers=ENSEMBL_JSON_HEADERS,
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=ENSEMBL_CACHE_TTL_S,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"Ensembl {resource} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ensembl {resource} request failed: {exc}") from exc


async def _post(
    resource: str,
    json_body: dict[str, Any],
    params: dict[str, Any],
    *,
    base_url: str,
    retries: int,
    timeout: float,
) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{base_url.rstrip('/')}/{resource}"
    client = APIHttpClient(cache=ENSEMBL_API_CACHE, rate_limiter=ENSEMBL_RATE_LIMITER)
    try:
        return await client.request(
            "POST",
            url,
            params=params,
            headers=ENSEMBL_JSON_HEADERS,
            json=json_body,
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"Ensembl {resource} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ensembl {resource} request failed: {exc}") from exc


def _base_url_for_assembly(assembly: str) -> str:
    if str(assembly).strip().upper() == "GRCH37":
        return ENSEMBL_GRCH37_BASE_URL
    return ENSEMBL_BASE_URL


def _is_stable_id(query: str) -> bool:
    return bool(re.match(r"^ENS[A-Z]*[GTPE]\d+", query.strip(), re.IGNORECASE))


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    seq_region = payload.get("seq_region_name", "")
    start = payload.get("start", "")
    end = payload.get("end", "")
    strand = payload.get("strand", "")
    location = f"{seq_region}:{start}-{end}:{strand}" if seq_region and start and end else ""
    return {
        "id": str(payload.get("id", "")),
        "display_name": str(payload.get("display_name", "")),
        "description": str(payload.get("description", "")),
        "species": str(payload.get("species", "")),
        "assembly_name": str(payload.get("assembly_name", "")),
        "object_type": str(payload.get("object_type", "")),
        "biotype": str(payload.get("biotype", "")),
        "location": location,
    }


def _vcf_variants(vcf_file: str | Path) -> list[str]:
    path = Path(vcf_file)
    variants: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 5:
                raise ValueError(f"VCF record on line {line_number} must have at least 5 columns")
            variants.append(" ".join(fields[:8] if len(fields) >= 8 else fields))
    if not variants:
        raise ValueError("Ensembl VEP requires at least one VCF variant record")
    return variants


def _vep_summary_rows(payload: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    records = payload if isinstance(payload, list) else []
    for record in records:
        if not isinstance(record, dict):
            continue
        input_value = str(record.get("input", ""))
        consequences = record.get("transcript_consequences")
        if not isinstance(consequences, list) or not consequences:
            rows.append({
                "input": input_value,
                "gene_symbol": "",
                "gene_id": "",
                "transcript_id": "",
                "consequence_terms": "",
                "impact": "",
            })
            continue
        for consequence in consequences:
            if not isinstance(consequence, dict):
                continue
            terms = consequence.get("consequence_terms", [])
            if isinstance(terms, list):
                terms_text = ",".join(str(term) for term in terms)
            else:
                terms_text = str(terms or "")
            rows.append({
                "input": input_value,
                "gene_symbol": str(consequence.get("gene_symbol", "")),
                "gene_id": str(consequence.get("gene_id", "")),
                "transcript_id": str(consequence.get("transcript_id", "")),
                "consequence_terms": terms_text,
                "impact": str(consequence.get("impact", "")),
            })
    return rows


def _write_vep_table(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=VEP_TABLE_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


class EnsemblGeneLookupNode(BaseNode):
    """Lookup Ensembl genes by symbol or stable ID."""

    NODE_ID = "ensembl_gene_lookup"
    DISPLAY_NAME = "Ensembl Gene Lookup"
    CATEGORY = "databases"
    DESCRIPTION = "Lookup Ensembl gene information by symbol or stable ID via Ensembl REST."
    SEARCH_ALIASES = ["ensembl", "gene", "lookup", "symbol", "transcript", "database"]
    RETURN_TYPES = ("JSON", "JSON")
    RETURN_NAMES = ("gene_info", "transcripts")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://rest.ensembl.org/documentation/info/symbol_lookup"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gene_symbol": ("STRING", {"default": "", "description": "Gene symbol or Ensembl stable ID"}),
                "species": ("STRING", {"default": "homo_sapiens"}),
            },
            "optional": {
                "query": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Backward-compatible gene symbol or stable ID input",
                    },
                ),
                "expand": ("BOOLEAN", {"default": True, "description": "Include transcripts when available"}),
                "assembly": ("STRING", {"default": "current", "options": ["current", "GRCh37"]}),
                "fetch_homologs": ("BOOLEAN", {"default": False, "advanced": True}),
                "homolog_species": ("STRING", {"default": "", "advanced": True, "description": "Optional target species for homology lookup"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        query = str(kwargs.get("gene_symbol", "") or kwargs.get("query", "")).strip()
        if not query:
            raise ValueError("Ensembl Gene Lookup requires a non-empty gene_symbol")
        species = str(kwargs.get("species", "homo_sapiens")).strip() or "homo_sapiens"
        expand = bool(kwargs.get("expand", True))
        base_url = _base_url_for_assembly(str(kwargs.get("assembly", "current")))
        params = {"expand": 1 if expand else 0}
        fetch_homologs = bool(kwargs.get("fetch_homologs", False))
        homolog_species = str(kwargs.get("homolog_species", "") or "").strip()

        if _is_stable_id(query):
            resource = f"lookup/id/{quote(query, safe='')}"
        else:
            resource = f"lookup/symbol/{quote(species, safe='')}/{quote(query, safe='')}"

        payload = await _request_json(resource, params=params, base_url=base_url)
        transcripts = payload.get("Transcript", [])
        if not isinstance(transcripts, list):
            transcripts = []
        gene_info = dict(payload)
        gene_id = str(payload.get("id", "") or "").strip()
        if fetch_homologs and gene_id:
            homolog_params: dict[str, Any] = {"type": "orthologues"}
            if homolog_species:
                homolog_params["target_species"] = homolog_species
            gene_info["homologs"] = await _request_json(
                f"homology/id/{quote(gene_id, safe='')}",
                params=homolog_params,
                base_url=base_url,
            )
        gene_info["summary"] = _summary(payload)
        return {
            "outputs": {
                "gene_info": gene_info,
                "transcripts": transcripts,
            }
        }


class EnsemblVEPNode(BaseNode):
    """Annotate VCF variants with Ensembl Variant Effect Predictor."""

    NODE_ID = "ensembl_vep"
    DISPLAY_NAME = "Ensembl VEP"
    CATEGORY = "databases"
    DESCRIPTION = "Annotate VCF variant records with Ensembl VEP via Ensembl REST."
    SEARCH_ALIASES = ["ensembl", "vep", "variant", "annotation", "vcf", "sift", "polyphen", "database"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("vep_json", "annotation_table")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://rest.ensembl.org/documentation/info/vep_region_post"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf_file": ("VCF", {"default": "", "description": "VCF file containing variants to annotate"}),
                "species": ("STRING", {"default": "homo_sapiens"}),
            },
            "optional": {
                "assembly": ("STRING", {"default": "current", "options": ["current", "GRCh38", "GRCh37"]}),
                "canonical": ("BOOLEAN", {"default": True}),
                "domains": ("BOOLEAN", {"default": False}),
                "gene_phenotype": ("BOOLEAN", {"default": False}),
                "variant_class": ("BOOLEAN", {"default": True}),
                "sift": ("BOOLEAN", {"default": True, "advanced": True}),
                "polyphen": ("BOOLEAN", {"default": True, "advanced": True}),
                "maf": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        vcf_file = str(kwargs.get("vcf_file", "")).strip()
        if not vcf_file:
            raise ValueError("Ensembl VEP requires a VCF file")

        species = str(kwargs.get("species", "homo_sapiens")).strip() or "homo_sapiens"
        base_url = _base_url_for_assembly(str(kwargs.get("assembly", "current")))
        params = {
            "canonical": 1 if bool(kwargs.get("canonical", True)) else 0,
            "domains": 1 if bool(kwargs.get("domains", False)) else 0,
            "gene_phenotype": 1 if bool(kwargs.get("gene_phenotype", False)) else 0,
            "variant_class": 1 if bool(kwargs.get("variant_class", True)) else 0,
            "SiftPrediction": "yes" if bool(kwargs.get("sift", True)) else "no",
            "PolyPhen": "yes" if bool(kwargs.get("polyphen", True)) else "no",
            "MAF": "yes" if bool(kwargs.get("maf", False)) else "no",
        }
        payload = await _post_json(
            f"vep/{quote(species, safe='')}/region",
            {"variants": _vcf_variants(vcf_file)},
            params=params,
            base_url=base_url,
        )

        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "vep_results.json"
        table_path = out_dir / "annotation_table.tsv"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _write_vep_table(table_path, _vep_summary_rows(payload))

        return {
            "outputs": {
                "vep_json": str(json_path),
                "annotation_table": str(table_path),
            }
        }
