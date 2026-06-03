"""RCSB Protein Data Bank download nodes."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode


logger = logging.getLogger(__name__)

RCSB_FILE_BASE_URL = "https://files.rcsb.org/download"
RCSB_DATA_BASE_URL = "https://data.rcsb.org/rest/v1/core"
RCSB_MAP_BASE_URL = "https://maps.rcsb.org/x-ray"
RCSB_USER_AGENT = "BioNodulo/2.0 (workflow node; RCSB PDB)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0
PDB_FORMATS = ("cif", "pdb", "xml", "sf")


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
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": RCSB_USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status < 500 or attempt >= retries - 1:
                body = exc.response.text[:500]
                raise RuntimeError(f"RCSB PDB {resource} failed with HTTP {status}: {body}") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise RuntimeError(f"RCSB PDB {resource} request failed: {exc}") from exc
        await asyncio.sleep(RETRY_DELAY_S * (2 ** attempt))
    raise RuntimeError(f"RCSB PDB {resource} request failed: {last_error}")


async def _download_file(
    url: str,
    path: Path,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> None:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": RCSB_USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
            response.raise_for_status()
            path.write_bytes(response.content)
            return
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code < 500 or attempt >= retries - 1:
                raise RuntimeError(f"RCSB PDB download failed with HTTP {exc.response.status_code}: {url}") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise RuntimeError(f"RCSB PDB download failed: {url}: {exc}") from exc
        await asyncio.sleep(RETRY_DELAY_S * (2 ** attempt))
    raise RuntimeError(f"RCSB PDB download failed: {url}: {last_error}")


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
    DOCUMENTATION_URL = "https://www.rcsb.org/docs/programmatic-access/file-download-services"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pdb_ids": ("STRING", {"default": "", "description": "PDB ID(s), comma-separated"}),
                "format": (list(PDB_FORMATS), {"default": "cif"}),
            },
            "optional": {
                "fetch_metadata": ("BOOLEAN", {"default": True}),
                "download_density": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        pdb_ids = _coerce_ids(kwargs.get("pdb_ids", ""))
        if not pdb_ids:
            raise ValueError("PDB Download requires at least one PDB ID")
        fmt = str(kwargs.get("format", "cif") or "cif").lower()
        if fmt not in PDB_FORMATS:
            raise ValueError(f"Unsupported PDB format: {fmt}")
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
