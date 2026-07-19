"""AlphaFold Protein Structure Database integration nodes."""
# ruff: noqa: F401
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
from bionodulo.nodes.builtin.protein_database_family.alphafold_db import (
    AlphaFoldDBNode,
    AlphaFoldNode,
)
from bionodulo.nodes.builtin.protein_structure_design_family.colabfold_batch import ColabFoldBatchNode
from bionodulo.nodes.builtin.protein_structure_design_family.esmfold_predict import ESMFoldPredictNode
from bionodulo.nodes.builtin.protein_structure_design_family.proteinmpnn_design import ProteinMPNNDesignNode


ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/api"
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


class _LegacyAlphaFoldDBNode(BaseNode):
    """Fetch predicted protein structures from AlphaFold DB."""

    LEGACY_NODE_ID = "alphafold_db"
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
                "format": ("STRING", {"default": "mmcif", "options": list(STRUCTURE_FORMATS), "advanced": True}),
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
        structure_format = str(kwargs.get("format") or kwargs.get("structure_format", "mmcif") or "mmcif").lower()
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


class _LegacyAlphaFoldNode(_LegacyAlphaFoldDBNode):
    """Compatibility wrapper for the original AlphaFold roadmap node ID."""

    LEGACY_NODE_ID = "alphafold"
    DISPLAY_NAME = "AlphaFold"
    DESCRIPTION = "Fetch predicted protein structures and metadata from AlphaFold DB."
    SEARCH_ALIASES = ["alphafold", "alphafold db", "structure", "prediction", "protein folding", "mmcif"]


class _LegacyColabFoldBatchNode(CommandNode):
    """Predict protein structures with the ColabFold batch CLI."""

    LEGACY_NODE_ID = "colabfold_batch"
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


class _LegacyESMFoldPredictNode(CommandNode):
    """Predict protein structures with the ESMFold CLI."""

    LEGACY_NODE_ID = "esmfold_predict"
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


class _LegacyProteinMPNNDesignNode(CommandNode):
    """Design protein sequences for a backbone with a local ProteinMPNN checkout."""

    LEGACY_NODE_ID = "proteinmpnn_design"
    DISPLAY_NAME = "ProteinMPNN Design"
    CATEGORY = "ai"
    DESCRIPTION = "Design protein sequences from a backbone PDB using ProteinMPNN."
    SEARCH_ALIASES = [
        "proteinmpnn",
        "protein mpnn",
        "inverse folding",
        "protein design",
        "sequence design",
        "backbone design",
    ]
    RETURN_TYPES = ("DIRECTORY", "FASTA")
    RETURN_NAMES = ("design_dir", "designed_sequences")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["numpy", "torch"]
    DOCUMENTATION_URL = "https://github.com/dauparas/ProteinMPNN"
    VERSION = "1.0.0"
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "script_path": ("FILE", {"description": "Path to protein_mpnn_run.py from a ProteinMPNN checkout"}),
                "pdb_path": ("FILE", {"description": "Input backbone PDB file"}),
            },
            "optional": {
                "pdb_path_chains": ("STRING", {"default": "", "advanced": True}),
                "num_seq_per_target": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "batch_size": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "sampling_temp": ("STRING", {"default": "0.1", "advanced": True}),
                "model_name": ("STRING", {"default": "v_48_020", "advanced": True}),
                "path_to_model_weights": ("DIRECTORY", {"default": "", "advanced": True}),
                "ca_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "use_soluble_model": ("BOOLEAN", {"default": False, "advanced": True}),
                "seed": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "save_score": ("BOOLEAN", {"default": False, "advanced": True}),
                "save_probs": ("BOOLEAN", {"default": False, "advanced": True}),
                "score_only": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "python",
            str(inputs.get("script_path", "")),
            "--pdb_path",
            str(inputs.get("pdb_path", "")),
            "--out_folder",
            str(inputs.get("output", ".")),
            "--num_seq_per_target",
            str(inputs.get("num_seq_per_target", 1)),
            "--batch_size",
            str(inputs.get("batch_size", 1)),
            "--sampling_temp",
            str(inputs.get("sampling_temp", "0.1") or "0.1"),
            "--model_name",
            str(inputs.get("model_name", "v_48_020") or "v_48_020"),
        ]
        if inputs.get("pdb_path_chains"):
            cmd.extend(["--pdb_path_chains", str(inputs["pdb_path_chains"])])
        if inputs.get("path_to_model_weights"):
            cmd.extend(["--path_to_model_weights", str(inputs["path_to_model_weights"])])
        seed = int(inputs.get("seed", 0) or 0)
        if seed:
            cmd.extend(["--seed", str(seed)])
        if inputs.get("ca_only"):
            cmd.append("--ca_only")
        if inputs.get("use_soluble_model"):
            cmd.append("--use_soluble_model")
        if inputs.get("save_score"):
            cmd.extend(["--save_score", "1"])
        if inputs.get("save_probs"):
            cmd.extend(["--save_probs", "1"])
        if inputs.get("score_only"):
            cmd.extend(["--score_only", "1"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        design_dir = Path(output_dir) / cls.NODE_ID
        seqs_dir = design_dir / "seqs"
        seqs_dir.mkdir(parents=True, exist_ok=True)
        stem = _safe_filename(Path(str(inputs.get("pdb_path", "proteinmpnn"))).stem)
        return [design_dir, seqs_dir / f"{stem}.fa"]
