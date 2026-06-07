"""UCSC Genome Browser API integration node."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


UCSC_BASE_URL = "https://api.genome.ucsc.edu"
UCSC_USER_AGENT = "BioNodulo/2.0 (workflow node; UCSC Genome Browser API)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
UCSC_CACHE_TTL_S = 300.0
UCSC_RATE_LIMIT_PER_SECOND = 3.0
UCSC_API_CACHE = APICache(ttl_seconds=UCSC_CACHE_TTL_S)
UCSC_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=UCSC_RATE_LIMIT_PER_SECOND, burst=1)
UCSC_QUERY_TYPES = ("sequence", "genes_in_region", "dna_sequence", "tracks")
UCSC_GENOMES = (
    "hg38",
    "hg19",
    "mm39",
    "mm10",
    "rn7",
    "rn6",
    "danRer11",
    "dm6",
    "ce11",
    "sacCer3",
)
UCSC_TRACKS = ("knownGene", "refGene", "ensGene", "ncbiRefSeq", "snp")


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


async def _request_json(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.json()


async def _request(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int,
    timeout: float,
) -> httpx.Response:
    endpoint = endpoint.lstrip("/")
    url = f"{UCSC_BASE_URL}/{endpoint}"
    client = APIHttpClient(cache=UCSC_API_CACHE, rate_limiter=UCSC_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            params=params,
            headers={"User-Agent": UCSC_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=UCSC_CACHE_TTL_S,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"UCSC {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"UCSC {endpoint} request failed: {exc}") from exc


def _parse_coordinates(value: Any) -> tuple[str, int, int]:
    text = str(value or "").strip().replace(",", "")
    match = re.fullmatch(r"([^:\s]+):(\d+)-(\d+)", text)
    if not match:
        raise ValueError("UCSC coordinates must look like chr1:1000000-1000500")
    chrom = match.group(1)
    start = int(match.group(2))
    end = int(match.group(3))
    if start < 0 or end <= start:
        raise ValueError("UCSC coordinates require end greater than start")
    return chrom, start, end


def _sequence_from_response(payload: dict[str, Any]) -> str:
    sequence = payload.get("dna")
    if sequence is None:
        sequence = payload.get("sequence")
    return "".join(str(sequence or "").split()).upper()


class UCSCGenomeBrowserNode(BaseNode):
    """Fetch sequence and annotation data from the UCSC Genome Browser API."""

    NODE_ID = "ucsc_genome_browser"
    DISPLAY_NAME = "UCSC Genome Browser"
    CATEGORY = "databases"
    DESCRIPTION = "Fetch genome sequence and region annotations from the UCSC Genome Browser API."
    SEARCH_ALIASES = [
        "ucsc",
        "genome browser",
        "sequence",
        "coordinates",
        "genome",
        "hg19",
        "hg38",
        "annotation",
    ]
    RETURN_TYPES = ("FASTA", "JSON")
    RETURN_NAMES = ("sequence_fasta", "annotations_json")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/api.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "coordinates": ("STRING", {"default": "", "description": "Genomic coordinates, e.g. chr17:43044295-43125364"}),
                "genome": (list(UCSC_GENOMES), {"default": "hg38"}),
            },
            "optional": {
                "query_type": (list(UCSC_QUERY_TYPES), {"default": "sequence"}),
                "track": (list(UCSC_TRACKS), {"default": "knownGene"}),
                "max_items": ("INT", {"default": 1000, "min": 1, "max": 100000, "advanced": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        coordinates = str(kwargs.get("coordinates", "") or "").strip()
        genome = str(kwargs.get("genome", "hg38") or "hg38")
        query_type = str(kwargs.get("query_type", "sequence") or "sequence")
        if query_type not in UCSC_QUERY_TYPES:
            raise ValueError(f"Unsupported UCSC query_type: {query_type}")
        chrom, start, end = _parse_coordinates(coordinates)

        out_dir = _node_output_dir(self, context)
        fasta_path = out_dir / "sequence.fasta"

        if query_type in {"sequence", "dna_sequence"}:
            payload = await _request_json(
                "getData/sequence",
                {
                    "genome": genome,
                    "chrom": chrom,
                    "start": start,
                    "end": end,
                },
            )
            sequence = _sequence_from_response(payload)
            metadata = {
                "query_type": query_type,
                "genome": genome,
                "coordinates": coordinates,
                "chrom": chrom,
                "start": start,
                "end": end,
                "sequence_length": len(sequence),
                "ucsc_response": payload,
            }
            json_path = out_dir / "sequence_info.json"
            fasta_path.write_text(f">{genome}:{coordinates}\n{sequence}\n", encoding="utf-8")
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        elif query_type == "genes_in_region":
            track = str(kwargs.get("track", "knownGene") or "knownGene")
            max_items = int(kwargs.get("max_items", 1000) or 1000)
            payload = await _request_json(
                "getData/track",
                {
                    "genome": genome,
                    "track": track,
                    "chrom": chrom,
                    "start": start,
                    "end": end,
                    "maxItemsOutput": max_items,
                },
            )
            metadata = {
                "query_type": query_type,
                "genome": genome,
                "coordinates": coordinates,
                "track": track,
                "chrom": chrom,
                "start": start,
                "end": end,
                "ucsc_response": payload,
            }
            json_path = out_dir / "annotations.json"
            fasta_path.write_text(f">{genome}:{coordinates}\n\n", encoding="utf-8")
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        else:
            payload = await _request_json("list/tracks", {"genome": genome})
            metadata = {
                "query_type": query_type,
                "genome": genome,
                "coordinates": coordinates,
                "ucsc_response": payload,
            }
            json_path = out_dir / "tracks.json"
            fasta_path.write_text(f">{genome}:{coordinates}\n\n", encoding="utf-8")
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "sequence_fasta": str(fasta_path),
                "annotations_json": str(json_path),
            }
        }
