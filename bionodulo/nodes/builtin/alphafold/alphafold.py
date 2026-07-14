"""alphafold — alphafold node(s). One tool per file (extracted from alphafold.py)."""
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


class AlphaFoldNode(AlphaFoldDBNode):
    """Compatibility wrapper for the original AlphaFold roadmap node ID."""
    NODE_ID = 'alphafold'
    DISPLAY_NAME = 'AlphaFold'
    DESCRIPTION = 'Fetch predicted protein structures and metadata from AlphaFold DB.'
    SEARCH_ALIASES = ['alphafold', 'alphafold db', 'structure', 'prediction', 'protein folding', 'mmcif']
