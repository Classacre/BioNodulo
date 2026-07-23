"""AlphaFold DB API nodes pinned to OpenAPI 1.0.0."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/api"
ALPHAFOLD_OPENAPI_URL = f"{ALPHAFOLD_BASE_URL}/openapi.json"
ALPHAFOLD_OPENAPI_SHA256 = "714607265fd8edc581baf28df038ea804d96d871baa6034ff60d22d0cf893163"
ALPHAFOLD_USER_AGENT = "BioNodulo/2.0 (workflow node; AlphaFold DB)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0
ALPHAFOLD_CACHE_TTL_S = 300.0
ALPHAFOLD_RATE_LIMIT_PER_SECOND = 3.0
ALPHAFOLD_API_CACHE = APICache.from_environment(default_ttl_seconds=ALPHAFOLD_CACHE_TTL_S)
ALPHAFOLD_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=ALPHAFOLD_RATE_LIMIT_PER_SECOND, burst=1)
STRUCTURE_FORMATS = ("mmcif", "pdb")


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or "alphafold"


def _coerce_ids(value: Any) -> list[str]:
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
) -> Any:
    response = await _request(resource, params=params, retries=retries, timeout=timeout)
    return response.json()


async def _request(
    resource: str,
    *,
    params: dict[str, Any] | None = None,
    retries: int,
    timeout: float,
) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{ALPHAFOLD_BASE_URL}/{resource}"
    client = APIHttpClient(cache=ALPHAFOLD_API_CACHE, rate_limiter=ALPHAFOLD_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            params=params,
            headers={"User-Agent": ALPHAFOLD_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=ALPHAFOLD_CACHE_TTL_S,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"AlphaFold {resource} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AlphaFold {resource} request failed: {exc}") from exc


async def _download_file(
    url: str,
    path: Path,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> None:
    client = APIHttpClient(cache=ALPHAFOLD_API_CACHE, rate_limiter=ALPHAFOLD_RATE_LIMITER)
    try:
        response = await client.request(
            "GET",
            url,
            headers={"User-Agent": ALPHAFOLD_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
        path.write_bytes(response.content)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"AlphaFold download failed with HTTP {exc.response.status_code}: {url}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AlphaFold download failed: {url}: {exc}") from exc


def _entries_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        return [payload]
    return []


def _structure_url(entry: dict[str, Any], structure_format: str) -> str:
    if structure_format == "pdb":
        return str(entry.get("pdbUrl") or "")
    return str(entry.get("cifUrl") or entry.get("mmcifUrl") or "")


def _pae_url(entry: dict[str, Any]) -> str:
    return str(entry.get("paeDocUrl") or entry.get("paeUrl") or entry.get("paeJsonUrl") or "")


def _select_entry(entries: list[dict[str, Any]], qualifier: str) -> dict[str, Any] | None:
    """Return only an exact requested accession/model match."""

    expected = qualifier.upper()
    for entry in entries:
        identifiers = (
            entry.get("modelEntityId"),
            entry.get("entryId"),
            entry.get("uniprotAccession"),
        )
        if any(str(identifier or "").upper() == expected for identifier in identifiers):
            return entry
    return None


class AlphaFoldDBNode(BaseNode):
    """Fetch model metadata and linked structure artifacts by UniProt accession."""

    LEGACY_NODE_ID = "alphafold_db"
    DISPLAY_NAME = "AlphaFold DB"
    CATEGORY = "databases"
    DESCRIPTION = "Fetch predicted protein structure artifacts and metadata from AlphaFold DB API 1.0.0."
    SEARCH_ALIASES = ["alphafold", "structure", "pdb", "prediction", "3d", "protein folding", "mmcif"]
    RETURN_TYPES = ("FILE", "JSON", "FILE", "JSON", "DIRECTORY")
    RETURN_NAMES = (
        "structure_mmcif",
        "structure_metadata",
        "structure_file",
        "pae_json",
        "artifacts_directory",
    )
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = "1.0.0"
    GIT_URL = ALPHAFOLD_OPENAPI_URL
    GIT_COMMIT = ALPHAFOLD_OPENAPI_SHA256
    DOCUMENTATION_URL = "https://alphafold.ebi.ac.uk/api-docs"
    SOURCE_URL = ALPHAFOLD_OPENAPI_URL
    SOURCE_SHA256 = ALPHAFOLD_OPENAPI_SHA256
    UPSTREAM_SOURCE = (
        "/prediction/{qualifier}; sequence_checksum and include_complexes query parameters; "
        "response modelEntityId, cifUrl, pdbUrl, paeDocUrl"
    )
    EXIT_SEMANTICS = (
        "HTTP 4xx/5xx and transport failures are fatal after bounded retries; an empty prediction response "
        "or a response without an exact requested accession/model is fatal. Requested structure/PAE artifacts "
        "must expose their documented URLs before any download starts. A supplied sequence checksum is verified "
        "against the selected response record because the upstream endpoint currently does not reject mismatches."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "uniprot_ids": ("STRING", {"default": "", "description": "UniProt accession(s), comma-separated"}),
            },
            "optional": {
                "structure_format": ("STRING", {"default": "mmcif", "options": list(STRUCTURE_FORMATS)}),
                "sequence_checksum": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "description": (
                            "Optional MD5 checksum forwarded to AlphaFold DB and verified against returned metadata"
                        ),
                    },
                ),
                "include_complexes": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "advanced": True,
                        "description": "Download all complex models returned for one qualifier",
                    },
                ),
                "download_pae": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        ids = _coerce_ids(inputs.get("uniprot_ids", ""))
        if not ids:
            return "Input 'uniprot_ids' must contain at least one UniProt accession"
        if str(inputs.get("format", "") or "").strip():
            return "Input 'format' is unsupported; use 'structure_format'"
        structure_format = str(inputs.get("structure_format", "mmcif") or "mmcif").lower()
        if structure_format not in STRUCTURE_FORMATS:
            return f"Input 'structure_format' must be one of: {', '.join(STRUCTURE_FORMATS)}"
        if str(inputs.get("model_version", "") or "").strip():
            return "Input 'model_version' is unsupported; AlphaFold DB only documents latest-version lookup"
        sequence_checksum = str(inputs.get("sequence_checksum", "") or "").strip()
        if sequence_checksum and not re.fullmatch(r"[0-9a-fA-F]{32}", sequence_checksum):
            return "Input 'sequence_checksum' must be a 32-character MD5 hexadecimal digest"
        if sequence_checksum and len(ids) != 1:
            return "Input 'sequence_checksum' can only be used with one UniProt accession"
        if bool(inputs.get("include_complexes", False)) and len(ids) != 1:
            return "Input 'include_complexes' can only be used with one UniProt accession or model ID"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        ids = _coerce_ids(kwargs.get("uniprot_ids", ""))
        structure_format = str(kwargs.get("structure_format", "mmcif") or "mmcif").lower()
        sequence_checksum = str(kwargs.get("sequence_checksum", "") or "").strip()
        include_complexes = bool(kwargs.get("include_complexes", False))
        download_pae = bool(kwargs.get("download_pae", False))

        out_dir = _node_output_dir(self, context)
        raw: dict[str, Any] = {}
        plans: list[tuple[str, dict[str, Any], str, str, str, int]] = []
        structures: list[dict[str, Any]] = []
        first_structure = ""
        first_pae = ""
        ext = ".pdb" if structure_format == "pdb" else ".cif"

        artifact_stems: set[str] = set()
        for uniprot_id in ids:
            resource = f"prediction/{uniprot_id}"
            params: dict[str, Any] = {"include_complexes": include_complexes}
            if sequence_checksum:
                params["sequence_checksum"] = sequence_checksum
            payload = await _request_json(resource, params=params)
            raw[uniprot_id] = payload
            entries = _entries_from_payload(payload)
            if not entries:
                raise RuntimeError(f"AlphaFold prediction/{uniprot_id} returned no prediction records")

            primary_entry = _select_entry(entries, uniprot_id)
            if primary_entry is None:
                raise RuntimeError(f"AlphaFold prediction/{uniprot_id} did not contain an exact accession/model match")
            if sequence_checksum:
                returned_checksum = str(primary_entry.get("sequenceChecksum") or "").strip()
                if not returned_checksum:
                    raise RuntimeError(f"AlphaFold prediction/{uniprot_id} did not report a sequence checksum")
                if returned_checksum.lower() != sequence_checksum.lower():
                    raise RuntimeError(
                        f"AlphaFold prediction/{uniprot_id} sequence checksum did not match the requested value"
                    )
            selected_entries = [primary_entry]
            if include_complexes:
                selected_entries.extend(
                    entry for entry in entries if entry is not primary_entry and entry.get("isComplex") is True
                )

            for entry in selected_entries:
                is_primary = entry is primary_entry
                model_id = str(entry.get("modelEntityId") or entry.get("entryId") or "").strip()
                if not is_primary and not model_id:
                    raise RuntimeError(
                        f"AlphaFold prediction/{uniprot_id} returned a complex without a model identifier"
                    )
                artifact_stem = _safe_filename(uniprot_id if is_primary else model_id)
                if artifact_stem in artifact_stems:
                    raise RuntimeError(
                        f"AlphaFold prediction/{uniprot_id} returned duplicate artifact identifier {artifact_stem}"
                    )
                artifact_stems.add(artifact_stem)
                structure_url = _structure_url(entry, structure_format)
                if not structure_url:
                    raise RuntimeError(
                        f"AlphaFold prediction/{uniprot_id} model {model_id or uniprot_id} "
                        f"did not provide a {structure_format} URL"
                    )
                pae_url = _pae_url(entry) if download_pae else ""
                if download_pae and not pae_url:
                    raise RuntimeError(
                        f"AlphaFold prediction/{uniprot_id} model {model_id or uniprot_id} "
                        "did not provide a PAE document URL"
                    )
                plans.append(
                    (
                        uniprot_id,
                        entry,
                        artifact_stem,
                        structure_url,
                        pae_url,
                        len(entries),
                    )
                )

        for uniprot_id, entry, artifact_stem, structure_url, pae_url, response_count in plans:
            structure_path = out_dir / f"{artifact_stem}{ext}"
            await _download_file(structure_url, structure_path)
            structure_file = str(structure_path)
            if not first_structure:
                first_structure = structure_file

            pae_file = ""
            if download_pae:
                pae_path = out_dir / f"{artifact_stem}_pae.json"
                await _download_file(pae_url, pae_path)
                pae_file = str(pae_path)
                if not first_pae:
                    first_pae = pae_file

            structures.append(
                {
                    "uniprot_id": uniprot_id,
                    "entry_id": str(entry.get("modelEntityId") or entry.get("entryId") or ""),
                    "uniprot_accession": entry.get("uniprotAccession") or "",
                    "uniprot_name": str(entry.get("uniprotId", "")),
                    "latest_version": entry.get("latestVersion"),
                    "all_versions": entry.get("allVersions"),
                    "sequence_checksum": entry.get("sequenceChecksum"),
                    "is_complex": entry.get("isComplex"),
                    "response_record_count": response_count,
                    "structure_file": structure_path.name,
                    "pae_file": Path(pae_file).name if pae_file else "",
                }
            )

        metadata = {"record_count": len(structures), "structures": structures, "raw": raw}
        metadata_path = out_dir / "structure_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {
            "outputs": {
                "structure_mmcif": first_structure if structure_format == "mmcif" else "",
                "structure_metadata": str(metadata_path),
                "structure_file": first_structure,
                "pae_json": first_pae,
                "artifacts_directory": str(out_dir),
            }
        }


class AlphaFoldNode(AlphaFoldDBNode):
    """Compatibility ID for the original AlphaFold database node."""

    LEGACY_NODE_ID = "alphafold"
    DISPLAY_NAME = "AlphaFold"
    DESCRIPTION = "Fetch predicted protein structures and metadata from AlphaFold DB."
    SEARCH_ALIASES = ["alphafold", "alphafold db", "structure", "prediction", "protein folding", "mmcif"]
