"""RCSB PDB download nodes pinned to Data API schema 1.56.1."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


logger = logging.getLogger(__name__)

RCSB_FILE_BASE_URL = "https://files.rcsb.org/download"
RCSB_DATA_BASE_URL = "https://data.rcsb.org/rest/v1/core"
RCSB_MAP_BASE_URL = "https://maps.rcsb.org/x-ray"
RCSB_OPENAPI_URL = "https://data.rcsb.org/v3/api-docs"
RCSB_OPENAPI_SHA256 = "57e2e0f19131015c997b1e35e57267039a64e4647bb3dc1654219507ba656fb8"
RCSB_USER_AGENT = "BioNodulo/2.0 (workflow node; RCSB PDB)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0
RCSB_CACHE_TTL_S = 300.0
RCSB_RATE_LIMIT_PER_SECOND = 3.0
RCSB_API_CACHE = APICache.from_environment(default_ttl_seconds=RCSB_CACHE_TTL_S)
RCSB_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=RCSB_RATE_LIMIT_PER_SECOND, burst=1)
PDB_FORMATS = ("cif", "mmcif", "pdb", "xml", "sf")
PDB_FORMAT_ALIASES = {"mmcif": "cif"}


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or "pdb"


def _coerce_ids(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip().upper() for item in parsed if str(item).strip()]
    return [part.upper() for part in re.split(r"[\s,;]+", text) if part]


def _format_suffix(fmt: str) -> str:
    if fmt == "sf":
        return "-sf.cif"
    return f".{fmt}"


def _normalise_pdb_format(fmt: Any) -> str:
    value = str(fmt or "cif").lower()
    return PDB_FORMAT_ALIASES.get(value, value)


async def _request_json(
    resource: str,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> Any:
    response = await _request(resource, retries=retries, timeout=timeout)
    return response.json()


async def _request(resource: str, *, retries: int, timeout: float) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{RCSB_DATA_BASE_URL}/{resource}"
    client = APIHttpClient(cache=RCSB_API_CACHE, rate_limiter=RCSB_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
            headers={"User-Agent": RCSB_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=RCSB_CACHE_TTL_S,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"RCSB PDB {resource} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"RCSB PDB {resource} request failed: {exc}") from exc


async def _download_file(
    url: str,
    path: Path,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> None:
    client = APIHttpClient(cache=RCSB_API_CACHE, rate_limiter=RCSB_RATE_LIMITER)
    try:
        response = await client.request(
            "GET",
            url,
            headers={"User-Agent": RCSB_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
        path.write_bytes(response.content)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"RCSB PDB download failed with HTTP {exc.response.status_code}: {url}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"RCSB PDB download failed: {url}: {exc}") from exc


class PDBDownloadNode(BaseNode):
    """Download protein structures and entry metadata from RCSB PDB."""

    NODE_ID = "pdb_download"
    DISPLAY_NAME = "PDB Download"
    CATEGORY = "api"
    DESCRIPTION = "Download protein structures from RCSB PDB in PDB, mmCIF, XML, or structure-factor format."
    SEARCH_ALIASES = ["pdb", "rcsb", "structure", "download", "protein", "3d", "x-ray", "cryo-em", "mmcif"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("structure_file", "pdb_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = "1.56.1"
    GIT_URL = RCSB_OPENAPI_URL
    GIT_COMMIT = RCSB_OPENAPI_SHA256
    DOCUMENTATION_URL = "https://www.rcsb.org/docs/programmatic-access/file-download-services"
    SOURCE_URL = RCSB_OPENAPI_URL
    SOURCE_SHA256 = RCSB_OPENAPI_SHA256
    UPSTREAM_SOURCE = "/rest/v1/core/entry/{entry_id}; files.rcsb.org download naming contract"
    EXIT_SEMANTICS = (
        "Structure and requested metadata downloads fail the node on HTTP or transport errors after bounded "
        "retries; optional density-map absence is recorded as an empty density path."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pdb_ids": ("STRING", {"default": "", "description": "PDB ID(s), comma-separated"}),
                "format": ("STRING", {"default": "cif", "options": list(PDB_FORMATS)}),
            },
            "optional": {
                "fetch_metadata": ("BOOLEAN", {"default": True}),
                "download_density": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        pdb_ids = _coerce_ids(inputs.get("pdb_ids", ""))
        if not pdb_ids:
            return "Input 'pdb_ids' must contain at least one PDB ID"
        invalid = [pdb_id for pdb_id in pdb_ids if not re.fullmatch(r"[0-9][A-Z0-9]{3}", pdb_id)]
        if invalid:
            return f"Invalid four-character PDB ID(s): {', '.join(invalid)}"
        requested_format = str(inputs.get("format", "cif") or "cif").lower()
        if requested_format not in PDB_FORMATS:
            return f"Unsupported PDB format: {requested_format}"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        pdb_ids = _coerce_ids(kwargs.get("pdb_ids", ""))
        requested_format = str(kwargs.get("format", "cif") or "cif").lower()
        fmt = _normalise_pdb_format(requested_format)
        fetch_metadata = bool(kwargs.get("fetch_metadata", True))
        download_density = bool(kwargs.get("download_density", False))

        out_dir = _node_output_dir(self, context)
        suffix = _format_suffix(fmt)
        structures: list[dict[str, Any]] = []
        first_structure = ""

        for pdb_id in pdb_ids:
            safe_id = _safe_filename(pdb_id)
            structure_path = out_dir / f"{safe_id}{suffix}"
            structure_url = f"{RCSB_FILE_BASE_URL}/{pdb_id}{suffix}"
            await _download_file(structure_url, structure_path)
            if not first_structure:
                first_structure = str(structure_path)

            metadata: Any = {}
            if fetch_metadata:
                metadata = await _request_json(f"entry/{pdb_id}")

            density_file = ""
            if download_density:
                density_url = f"{RCSB_MAP_BASE_URL}/{pdb_id.lower()}/cell/"
                density_path = out_dir / f"{safe_id}_density.bcif"
                try:
                    await _download_file(density_url, density_path)
                    density_file = str(density_path)
                except RuntimeError as exc:
                    logger.warning("Density map not available for %s: %s", pdb_id, exc)

            structures.append({
                "pdb_id": pdb_id,
                "format": fmt,
                "structure_file": str(structure_path),
                "density_file": density_file,
                "metadata": metadata,
            })

        metadata_path = out_dir / "pdb_metadata.json"
        metadata_path.write_text(
            json.dumps({"record_count": len(structures), "structures": structures}, indent=2),
            encoding="utf-8",
        )

        return {
            "outputs": {
                "structure_file": first_structure,
                "pdb_metadata": str(metadata_path),
            }
        }


class PDBRetrieveNode(PDBDownloadNode):
    """Compatibility wrapper for the original PDB retrieval roadmap node ID."""

    NODE_ID = "pdb_retrieve"
    DISPLAY_NAME = "PDB Retrieve"
    DESCRIPTION = "Retrieve protein structures and metadata from RCSB PDB."
    SEARCH_ALIASES = ["pdb retrieve", "pdb", "rcsb", "structure", "download", "protein", "3d", "mmcif"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        inputs = super().INPUT_TYPES()
        inputs["optional"] = {
            "pdb_id": ("STRING", {"default": "", "advanced": True, "description": "Backward-compatible singular PDB ID"}),
            **inputs["optional"],
        }
        return inputs

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        if not _coerce_ids(kwargs.get("pdb_ids", "")) and "pdb_id" in kwargs:
            kwargs["pdb_ids"] = kwargs["pdb_id"]
        return await super().run(**kwargs)
