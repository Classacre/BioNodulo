"""esmfold — ai node(s). One tool per file (extracted from alphafold.py)."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
import httpx
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
ALPHAFOLD_BASE_URL = 'https://alphafold.ebi.ac.uk/api'
ALPHAFOLD_USER_AGENT = 'BioNodulo/2.0 (workflow node; AlphaFold DB)'
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0
ALPHAFOLD_CACHE_TTL_S = 300.0
ALPHAFOLD_RATE_LIMIT_PER_SECOND = 3.0
ALPHAFOLD_API_CACHE = APICache.from_environment(default_ttl_seconds=ALPHAFOLD_CACHE_TTL_S)
ALPHAFOLD_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=ALPHAFOLD_RATE_LIMIT_PER_SECOND, burst=1)
STRUCTURE_FORMATS = ('mmcif', 'pdb')
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _safe_filename(value: str) -> str:
    name = re.sub('[^A-Za-z0-9._-]+', '_', value).strip('._')
    return name or 'alphafold'
def _coerce_ids(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or '').strip()
    if not text:
        return []
    if text.startswith('['):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [part for part in re.split('[\\s,;]+', text) if part]
async def _request_json(resource: str, *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> Any:
    response = await _request(resource, retries=retries, timeout=timeout)
    return response.json()
async def _request(resource: str, *, retries: int, timeout: float) -> httpx.Response:
    resource = resource.lstrip('/')
    url = f'{ALPHAFOLD_BASE_URL}/{resource}'
    client = APIHttpClient(cache=ALPHAFOLD_API_CACHE, rate_limiter=ALPHAFOLD_RATE_LIMITER)
    try:
        return await client.request('GET', url, headers={'User-Agent': ALPHAFOLD_USER_AGENT}, timeout=timeout, retries=retries, retry_delay=RETRY_DELAY_S, cache_ttl=ALPHAFOLD_CACHE_TTL_S, follow_redirects=True)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f'AlphaFold {resource} failed with HTTP {status}: {body}') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f'AlphaFold {resource} request failed: {exc}') from exc
async def _download_file(url: str, path: Path, *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> None:
    client = APIHttpClient(cache=ALPHAFOLD_API_CACHE, rate_limiter=ALPHAFOLD_RATE_LIMITER)
    try:
        response = await client.request('GET', url, headers={'User-Agent': ALPHAFOLD_USER_AGENT}, timeout=timeout, retries=retries, retry_delay=RETRY_DELAY_S, cache_ttl=None, follow_redirects=True)
        path.write_bytes(response.content)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f'AlphaFold download failed with HTTP {exc.response.status_code}: {url}') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f'AlphaFold download failed: {url}: {exc}') from exc
def _entries_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict):
        entries = payload.get('entries')
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        return [payload]
    return []
def _structure_url(entry: dict[str, Any], structure_format: str) -> str:
    if structure_format == 'pdb':
        return str(entry.get('pdbUrl') or '')
    return str(entry.get('cifUrl') or entry.get('mmcifUrl') or '')
def _pae_url(entry: dict[str, Any]) -> str:
    return str(entry.get('paeDocUrl') or entry.get('paeUrl') or entry.get('paeJsonUrl') or '')


class ESMFoldPredictNode(CommandNode):
    """Predict protein structures with the ESMFold CLI."""
    NODE_ID = 'esmfold_predict'
    DISPLAY_NAME = 'ESMFold Predict'
    CATEGORY = 'ai'
    DESCRIPTION = 'Predict protein structures from FASTA sequences with ESMFold.'
    SEARCH_ALIASES = ['esmfold', 'esm-fold', 'esm', 'structure', 'prediction', 'protein folding', 'single sequence']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('pdb_dir',)
    REQUIRED_EXECUTABLES = ['esm-fold']
    REQUIRED_CONDA_PACKAGES = ['fair-esm']
    DOCUMENTATION_URL = 'https://github.com/facebookresearch/esm'
    VERSION = '2.0.0'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fasta': ('FASTA', {'description': 'Input FASTA file with protein sequences'})}, 'optional': {'num_recycles': ('INT', {'default': 4, 'min': 1, 'max': 48, 'advanced': True}), 'max_tokens_per_batch': ('INT', {'default': 1024, 'min': 0, 'advanced': True}), 'chunk_size': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'cpu_only': ('BOOLEAN', {'default': False, 'advanced': True}), 'cpu_offload': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        pdb_dir = Path(str(inputs.get('output', '.'))) / 'pdb'
        cmd = ['esm-fold', '-i', str(inputs.get('fasta', '')), '-o', str(pdb_dir), '--num-recycles', str(inputs.get('num_recycles', 4)), '--max-tokens-per-batch', str(inputs.get('max_tokens_per_batch', 1024))]
        chunk_size = int(inputs.get('chunk_size', 0) or 0)
        if chunk_size:
            cmd.extend(['--chunk-size', str(chunk_size)])
        if inputs.get('cpu_only'):
            cmd.append('--cpu-only')
        if inputs.get('cpu_offload'):
            cmd.append('--cpu-offload')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        pdb_dir = Path(output_dir) / cls.NODE_ID / 'pdb'
        pdb_dir.mkdir(parents=True, exist_ok=True)
        return [pdb_dir]
