"""AlphaFold Protein Structure Database integration nodes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/api"
ALPHAFOLD_USER_AGENT = "BioNodulo/2.0 (workflow node; AlphaFold DB)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0
ALPHAFOLD_CACHE_TTL_S = 300.0
ALPHAFOLD_RATE_LIMIT_PER_SECOND = 3.0
ALPHAFOLD_API_CACHE = APICache(ttl_seconds=ALPHAFOLD_CACHE_TTL_S)
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
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> Any:
    response = await _request(resource, retries=retries, timeout=timeout)
    return response.json()


async def _request(resource: str, *, retries: int, timeout: float) -> httpx.Response:
    resource = resource.lstrip("/")
    url = f"{ALPHAFOLD_BASE_URL}/{resource}"
    client = APIHttpClient(cache=ALPHAFOLD_API_CACHE, rate_limiter=ALPHAFOLD_RATE_LIMITER)
    try:
        return await client.request(
            "GET",
            url,
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


class AlphaFoldDBNode(BaseNode):
    """Fetch predicted protein structures from AlphaFold DB."""

    NODE_ID = "alphafold_db"
    DISPLAY_NAME = "AlphaFold DB"
    CATEGORY = "databases"
    DESCRIPTION = "Fetch predicted protein structures and metadata from the AlphaFold Protein Structure Database."
    SEARCH_ALIASES = ["alphafold", "structure", "pdb", "prediction", "3d", "protein folding", "mmcif"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("structure_mmcif", "structure_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://alphafold.ebi.ac.uk/"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "uniprot_ids": ("STRING", {"default": "", "description": "UniProt accession(s), comma-separated"}),
            },
            "optional": {
                "structure_format": (list(STRUCTURE_FORMATS), {"default": "mmcif"}),
                "model_version": ("STRING", {"default": "", "advanced": True}),
                "download_pae": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        ids = _coerce_ids(kwargs.get("uniprot_ids", ""))
        if not ids:
            raise ValueError("AlphaFold DB requires at least one UniProt ID")
        structure_format = str(kwargs.get("structure_format", "mmcif") or "mmcif").lower()
        if structure_format not in STRUCTURE_FORMATS:
            raise ValueError(f"Unsupported structure_format: {structure_format}")
        model_version = str(kwargs.get("model_version", "") or "").strip()
        download_pae = bool(kwargs.get("download_pae", False))

        out_dir = _node_output_dir(self, context)
        raw: dict[str, Any] = {}
        structures: list[dict[str, Any]] = []
        first_structure = ""
        ext = ".pdb" if structure_format == "pdb" else ".cif"

        for uniprot_id in ids:
            resource = f"prediction/{uniprot_id}"
            if model_version:
                resource = f"{resource}?version={model_version}"
            payload = await _request_json(resource)
            raw[uniprot_id] = payload
            entries = _entries_from_payload(payload)
            if not entries:
                structures.append({
                    "uniprot_id": uniprot_id,
                    "entry_id": "",
                    "uniprot_accession": "",
                    "uniprot_name": "",
                    "latest_version": None,
                    "structure_file": "",
                    "pae_file": "",
                })
                continue

            entry = entries[0]
            structure_url = _structure_url(entry, structure_format)
            structure_file = ""
            if structure_url:
                structure_path = out_dir / f"{_safe_filename(uniprot_id)}{ext}"
                await _download_file(structure_url, structure_path)
                structure_file = str(structure_path)
                if not first_structure:
                    first_structure = structure_file

            pae_file = ""
            if download_pae:
                url = _pae_url(entry)
                if url:
                    pae_path = out_dir / f"{_safe_filename(uniprot_id)}_pae.json"
                    await _download_file(url, pae_path)
                    pae_file = str(pae_path)

            structures.append({
                "uniprot_id": uniprot_id,
                "entry_id": str(entry.get("entryId", "")),
                "uniprot_accession": str(entry.get("uniprotAccession", "")),
                "uniprot_name": str(entry.get("uniprotId", "")),
                "latest_version": entry.get("latestVersion"),
                "structure_file": structure_file,
                "pae_file": pae_file,
            })

        metadata = {
            "record_count": len(structures),
            "structures": structures,
            "raw": raw,
        }
        metadata_path = out_dir / "structure_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "structure_mmcif": first_structure,
                "structure_metadata": str(metadata_path),
            }
        }


class AlphaFoldNode(AlphaFoldDBNode):
    """Compatibility wrapper for the original AlphaFold roadmap node ID."""

    NODE_ID = "alphafold"
    DISPLAY_NAME = "AlphaFold"
    DESCRIPTION = "Fetch predicted protein structures and metadata from AlphaFold DB."
    SEARCH_ALIASES = ["alphafold", "alphafold db", "structure", "prediction", "protein folding", "mmcif"]


class ColabFoldBatchNode(CommandNode):
    """Predict protein structures with the ColabFold batch CLI."""

    NODE_ID = "colabfold_batch"
    DISPLAY_NAME = "ColabFold Batch"
    CATEGORY = "ai"
    DESCRIPTION = "Predict protein structures from FASTA sequences with ColabFold batch."
    SEARCH_ALIASES = ["colabfold", "alphafold", "structure", "prediction", "protein folding", "mmseqs2"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("prediction_dir",)
    REQUIRED_EXECUTABLES = ["colabfold_batch"]
    REQUIRED_CONDA_PACKAGES = ["colabfold"]
    DOCUMENTATION_URL = "https://github.com/sokrypton/ColabFold"
    VERSION = "1.5.5"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Input FASTA file with one or more protein sequences"}),
            },
            "optional": {
                "msa_only": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prediction_dir = Path(str(inputs.get("output", "."))) / "predictions"
        cmd = [
            "colabfold_batch",
            str(inputs.get("fasta", "")),
            str(prediction_dir),
        ]
        if inputs.get("msa_only"):
            cmd.append("--msa-only")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prediction_dir = Path(output_dir) / cls.NODE_ID / "predictions"
        prediction_dir.mkdir(parents=True, exist_ok=True)
        return [prediction_dir]


class ESMFoldPredictNode(CommandNode):
    """Predict protein structures with the ESMFold CLI."""

    NODE_ID = "esmfold_predict"
    DISPLAY_NAME = "ESMFold Predict"
    CATEGORY = "ai"
    DESCRIPTION = "Predict protein structures from FASTA sequences with ESMFold."
    SEARCH_ALIASES = [
        "esmfold",
        "esm-fold",
        "esm",
        "structure",
        "prediction",
        "protein folding",
        "single sequence",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("pdb_dir",)
    REQUIRED_EXECUTABLES = ["esm-fold"]
    REQUIRED_CONDA_PACKAGES = ["fair-esm"]
    DOCUMENTATION_URL = "https://github.com/facebookresearch/esm"
    VERSION = "2.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Input FASTA file with protein sequences"}),
            },
            "optional": {
                "num_recycles": ("INT", {"default": 4, "min": 1, "max": 48, "advanced": True}),
                "max_tokens_per_batch": ("INT", {"default": 1024, "min": 0, "advanced": True}),
                "chunk_size": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "cpu_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "cpu_offload": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        pdb_dir = Path(str(inputs.get("output", "."))) / "pdb"
        cmd = [
            "esm-fold",
            "-i",
            str(inputs.get("fasta", "")),
            "-o",
            str(pdb_dir),
            "--num-recycles",
            str(inputs.get("num_recycles", 4)),
            "--max-tokens-per-batch",
            str(inputs.get("max_tokens_per_batch", 1024)),
        ]
        chunk_size = int(inputs.get("chunk_size", 0) or 0)
        if chunk_size:
            cmd.extend(["--chunk-size", str(chunk_size)])
        if inputs.get("cpu_only"):
            cmd.append("--cpu-only")
        if inputs.get("cpu_offload"):
            cmd.append("--cpu-offload")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        pdb_dir = Path(output_dir) / cls.NODE_ID / "pdb"
        pdb_dir.mkdir(parents=True, exist_ok=True)
        return [pdb_dir]
