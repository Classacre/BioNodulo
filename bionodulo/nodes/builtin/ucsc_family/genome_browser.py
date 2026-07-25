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
UCSC_API_CACHE = APICache.from_environment(default_ttl_seconds=UCSC_CACHE_TTL_S)
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
UCSC_TRACKS = ("", "refGene", "knownGene", "snp151")


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
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"UCSC {endpoint} returned a non-object JSON response")
    if payload.get("error"):
        raise RuntimeError(f"UCSC {endpoint} returned an error: {payload['error']}")
    return payload


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
    CATEGORY = "api"
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
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/ucscGenomeBrowser/kent.git"
    GIT_COMMIT = "f665d4cc3b02924a8507b2f910eaf85eab54d433"
    PROVIDER_AUTHORITY_DATE = "2026-07-19"
    PRODUCT_SOURCE_COMMIT = "4382f1f4b19a9202dbd3cca0d25c300b9e1e2af6"
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/api.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "coordinates": ("STRING", {"default": "", "description": "Zero-based, half-open genomic coordinates, e.g. chr17:43044295-43125364"}),
                "genome": ("STRING", {"default": "hg38", "options": list(UCSC_GENOMES)}),
            },
            "optional": {
                "query_type": ("STRING", {"default": "sequence", "options": list(UCSC_QUERY_TYPES)}),
                "track": ("STRING", {"default": "", "options": list(UCSC_TRACKS)}),
                "max_items": ("INT", {"default": 1000, "min": 1, "max": 100000, "advanced": True}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        genome = str(inputs.get("genome", "hg38") or "hg38")
        if genome not in UCSC_GENOMES:
            return f"Unsupported UCSC genome: {genome}"
        query_type = str(inputs.get("query_type", "sequence") or "sequence")
        if query_type not in UCSC_QUERY_TYPES:
            return f"Unsupported UCSC query_type: {query_type}"
        if query_type == "genes_in_region":
            track = str(inputs.get("track", "") or "knownGene")
            if track not in UCSC_TRACKS:
                return f"Unsupported UCSC track: {track}"
        raw_max_items = inputs.get("max_items", 1000)
        if raw_max_items is None or str(raw_max_items).strip() == "":
            raw_max_items = 1000
        try:
            max_items = int(raw_max_items)
        except (TypeError, ValueError):
            return "max_items must be an integer"
        if max_items < 1 or max_items > 100000:
            return "max_items must be between 1 and 100000"
        if query_type != "tracks":
            try:
                _parse_coordinates(inputs.get("coordinates"))
            except ValueError as exc:
                return str(exc)
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(validation)
        coordinates = str(kwargs.get("coordinates", "") or "").strip()
        genome = str(kwargs.get("genome", "hg38") or "hg38")
        query_type = str(kwargs.get("query_type", "sequence") or "sequence")

        out_dir = _node_output_dir(self, context)

        if query_type == "tracks":
            payload = await _request_json("list/tracks", {"genome": genome})
            metadata = {
                "query_type": query_type,
                "genome": genome,
                "coordinates": coordinates,
                "ucsc_response": payload,
            }
            json_path = out_dir / "tracks.json"
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return {
                "outputs": {"annotations_json": str(json_path)},
                "inactive_outputs": ["sequence_fasta"],
            }

        chrom, start, end = _parse_coordinates(coordinates)

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
            if not sequence:
                raise RuntimeError("UCSC sequence response did not include DNA")
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
            fasta_path = out_dir / "sequence.fasta"
            fasta_path.write_text(f">{genome}:{coordinates}\n{sequence}\n", encoding="utf-8")
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return {
                "outputs": {
                    "sequence_fasta": str(fasta_path),
                    "annotations_json": str(json_path),
                }
            }

        if query_type == "genes_in_region":
            track = str(kwargs.get("track", "knownGene") or "knownGene")
            raw_max_items = kwargs.get("max_items", 1000)
            max_items = int(1000 if raw_max_items in (None, "") else raw_max_items)
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
            json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return {
                "outputs": {"annotations_json": str(json_path)},
                "inactive_outputs": ["sequence_fasta"],
            }

        raise AssertionError(f"Unhandled UCSC query_type: {query_type}")
