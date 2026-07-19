"""Mock-friendly PhyloT hosted-service owner."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter

from .evidence import source_pinned
from .legacy import _coerce_phylot_taxa, _html_to_text, _phylogeny_node_output_dir, _safe_filename


PHYLOT_BASE_URL = "https://phylot.biobyte.de"
PHYLOT_USER_AGENT = "BioNodulo/2.0 (workflow node; PhyloT)"
PHYLOT_CACHE_TTL_S = 300.0
PHYLOT_RATE_LIMIT_PER_SECOND = 1.0
PHYLOT_API_CACHE = APICache.from_environment(default_ttl_seconds=PHYLOT_CACHE_TTL_S)
PHYLOT_RATE_LIMITER = TokenBucketRateLimiter(
    rate_per_second=PHYLOT_RATE_LIMIT_PER_SECOND,
    burst=1,
)
PHYLOT_OUTPUT_FORMATS = ("newick", "nexus", "phyloxml")
PHYLOT_FORMAT_EXTENSIONS = {"newick": ".nwk", "nexus": ".nex", "phyloxml": ".xml"}
PHYLOT_NCBI_NODE_IDENTIFIERS = ("name", "id", "nameid", "idname")
PHYLOT_INTERRUPT_LEVELS = ("0", "species", "genus", "family", "order", "class", "phylum")
PHYLOT_GTDB_SOURCES = ("bac", "ar")
PHYLOT_GTDB_VERSIONS = ("202", "207", "214", "220", "232")
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0


def _validate_phylot_tree_response(text: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise RuntimeError("PhyloT returned an empty tree response")
    if re.search(r"(?is)<\s*(?:!doctype\s+html|html|body|head|title|h[1-6])\b", stripped):
        summary = _html_to_text(stripped)[:500] or "HTML error response"
        raise RuntimeError(f"PhyloT returned an error page: {summary}")


async def _phylot_request_text(
    endpoint: str,
    data: dict[str, str],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _phylot_request(endpoint, data=data, retries=retries, timeout=timeout)
    return response.text


async def _phylot_request(
    endpoint: str,
    *,
    data: dict[str, str],
    retries: int,
    timeout: float,
) -> httpx.Response:
    endpoint = endpoint.lstrip("/")
    url = f"{PHYLOT_BASE_URL}/{endpoint}"
    client = APIHttpClient(cache=PHYLOT_API_CACHE, rate_limiter=PHYLOT_RATE_LIMITER)
    try:
        return await client.request(
            "POST",
            url,
            data=data,
            headers={"User-Agent": PHYLOT_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"PhyloT {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"PhyloT {endpoint} request failed: {exc}") from exc


@source_pinned("phylot")
class PhyloTNode(BaseNode):
    """Generate taxonomy-derived trees through the PhyloT web service."""

    NODE_ID = "phylot"
    DISPLAY_NAME = "PhyloT"
    CATEGORY = "phylogeny"
    DESCRIPTION = (
        "Generate taxonomy-derived phylogenetic trees from taxon names, taxonomy IDs, "
        "or accessions via PhyloT."
    )
    SEARCH_ALIASES = [
        "phylot",
        "taxonomy tree",
        "newick",
        "ncbi taxonomy",
        "gtdb",
        "tree generator",
    ]
    RETURN_TYPES = ("NEWICK", "JSON")
    RETURN_NAMES = ("tree", "request_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://phylot.biobyte.de/help.cgi"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "taxa": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": (
                            "Taxon names, taxonomy IDs, accessions, or subtree requests "
                            "separated by newlines or commas"
                        ),
                    },
                ),
            },
            "optional": {
                "taxonomy_source": ("STRING", {"default": "ncbi", "options": ["ncbi", "gtdb"]}),
                "output_format": (
                    "STRING",
                    {"default": "newick", "options": list(PHYLOT_OUTPUT_FORMATS)},
                ),
                "node_identifiers": (
                    "STRING",
                    {"default": "name", "options": list(PHYLOT_NCBI_NODE_IDENTIFIERS)},
                ),
                "collapse_internal_nodes": ("BOOLEAN", {"default": False}),
                "force_binary_tree": ("BOOLEAN", {"default": False}),
                "interrupt_at": (
                    "STRING",
                    {"default": "0", "options": list(PHYLOT_INTERRUPT_LEVELS)},
                ),
                "filter_terms": ("STRING", {"default": "", "advanced": True}),
                "ignore_errors": ("BOOLEAN", {"default": False, "advanced": True}),
                "gtdb_source": (
                    "STRING",
                    {"default": "bac", "options": list(PHYLOT_GTDB_SOURCES), "advanced": True},
                ),
                "include_gtdb_branch_support": (
                    "BOOLEAN",
                    {"default": True, "advanced": True},
                ),
                "include_gtdb_genome_ids": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
                "gtdb_version": (
                    "STRING",
                    {"default": "232", "options": list(PHYLOT_GTDB_VERSIONS), "advanced": True},
                ),
                "output_name": (
                    "STRING",
                    {"default": "", "description": "Optional output filename stem"},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        taxa = _coerce_phylot_taxa(kwargs.get("taxa"))
        if len(taxa) < 2 and not any("|subtree" in item.lower() for item in taxa):
            raise ValueError("PhyloT requires at least two taxa or one subtree request")

        taxonomy_source = str(kwargs.get("taxonomy_source", "ncbi") or "ncbi").lower()
        if taxonomy_source not in {"ncbi", "gtdb"}:
            raise ValueError(f"Unsupported taxonomy_source: {taxonomy_source}")
        output_format = str(kwargs.get("output_format", "newick") or "newick").lower()
        if output_format not in PHYLOT_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output_format: {output_format}")
        interrupt_at = str(kwargs.get("interrupt_at", "0") or "0").lower()
        if interrupt_at not in PHYLOT_INTERRUPT_LEVELS:
            raise ValueError(f"Unsupported interrupt_at: {interrupt_at}")

        output_name = _safe_filename(str(kwargs.get("output_name", "") or ""), "phylot_tree")
        endpoint, params = self._request_params(
            taxa=taxa,
            taxonomy_source=taxonomy_source,
            output_format=output_format,
            output_name=output_name,
            interrupt_at=interrupt_at,
            kwargs=kwargs,
        )
        tree_text = await _phylot_request_text(endpoint, params)
        _validate_phylot_tree_response(tree_text)
        out_dir = _phylogeny_node_output_dir(self, context)
        tree_path = out_dir / f"{output_name}{PHYLOT_FORMAT_EXTENSIONS[output_format]}"
        metadata_path = out_dir / "request_metadata.json"
        tree_path.write_text(
            tree_text if tree_text.endswith("\n") else tree_text + "\n",
            encoding="utf-8",
        )
        metadata = {
            "endpoint": endpoint,
            "format": output_format,
            "taxonomy_source": taxonomy_source,
            "taxa_count": len(taxa),
            "tree": str(tree_path),
            "params": params,
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return str(tree_path), str(metadata_path)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_format = str(inputs.get("output_format", "newick") or "newick").lower()
        if output_format not in PHYLOT_OUTPUT_FORMATS:
            output_format = "newick"
        output_name = _safe_filename(str(inputs.get("output_name", "") or ""), "phylot_tree")
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / f"{output_name}{PHYLOT_FORMAT_EXTENSIONS[output_format]}",
            node_out / "request_metadata.json",
        ]

    def _request_params(
        self,
        *,
        taxa: list[str],
        taxonomy_source: str,
        output_format: str,
        output_name: str,
        interrupt_at: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, str]]:
        common = {
            "itol": "0",
            "itolProject": "0",
            "treeElements": "\n".join(taxa),
            "filter": str(kwargs.get("filter_terms", "") or ""),
            "interrupt": interrupt_at,
            "format": output_format,
            "fileName": output_name,
            "noerror": "1" if bool(kwargs.get("ignore_errors", False)) else "0",
        }
        if taxonomy_source == "gtdb":
            gtdb_source = str(kwargs.get("gtdb_source", "bac") or "bac").lower()
            if gtdb_source not in PHYLOT_GTDB_SOURCES:
                raise ValueError(f"Unsupported gtdb_source: {gtdb_source}")
            gtdb_version = str(kwargs.get("gtdb_version", "232") or "232")
            if gtdb_version not in PHYLOT_GTDB_VERSIONS:
                raise ValueError(f"Unsupported gtdb_version: {gtdb_version}")
            params = {
                "phylotgtd": "1",
                **common,
                "src": gtdb_source,
                "boot": "1" if bool(kwargs.get("include_gtdb_branch_support", True)) else "0",
                "gid": "1" if bool(kwargs.get("include_gtdb_genome_ids", False)) else "0",
                "gtdb_version": gtdb_version,
            }
            return "treeGeneratorGTD.cgi", params

        node_identifiers = str(kwargs.get("node_identifiers", "name") or "name").lower()
        if node_identifiers not in PHYLOT_NCBI_NODE_IDENTIFIERS:
            raise ValueError(f"Unsupported node_identifiers: {node_identifiers}")
        params = {
            "phylot": "1",
            **common,
            "ids": node_identifiers,
            "collapse": "1" if bool(kwargs.get("collapse_internal_nodes", False)) else "0",
            "binary": "1" if bool(kwargs.get("force_binary_tree", False)) else "0",
        }
        return "treeGenerator.cgi", params
