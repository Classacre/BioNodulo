"""interpro — interpro node(s). One tool per file (extracted from interpro.py)."""
from __future__ import annotations
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any
import httpx
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
INTERPROSCAN_BASE_URL = 'https://www.ebi.ac.uk/Tools/services/rest/iprscan5'
INTERPROSCAN_USER_AGENT = 'BioNodulo/2.0 (workflow node; InterProScan REST)'
REQUEST_TIMEOUT_S = 60.0
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
INTERPROSCAN_CACHE_TTL_S = 300.0
INTERPROSCAN_RATE_LIMIT_PER_SECOND = 1.0
INTERPROSCAN_API_CACHE = APICache.from_environment(default_ttl_seconds=INTERPROSCAN_CACHE_TTL_S)
INTERPROSCAN_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=INTERPROSCAN_RATE_LIMIT_PER_SECOND, burst=1)
RUNNING_STATUSES = {'PENDING', 'RUNNING', 'QUEUED'}
FAILED_STATUSES = {'FAILURE', 'ERROR', 'NOT_FOUND'}
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _clean_sequence(value: Any) -> str:
    lines = []
    for line in str(value or '').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('>'):
            continue
        lines.append(stripped)
    return ''.join(lines).replace(' ', '')
def _sequence_input_text(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    path = Path(text).expanduser()
    if path.is_file():
        return path.read_text(encoding='utf-8')
    return text
def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}
async def _post_text(endpoint: str, data: dict[str, Any], *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> str:
    response = await _request('POST', endpoint, data=data, retries=retries, timeout=timeout)
    return response.text
async def _get_text(endpoint: str, *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> str:
    response = await _request('GET', endpoint, retries=retries, timeout=timeout)
    return response.text
async def _get_json(endpoint: str, *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> dict[str, Any]:
    response = await _request('GET', endpoint, retries=retries, timeout=timeout)
    return response.json()
async def _request(method: str, endpoint: str, *, data: dict[str, Any] | None=None, retries: int, timeout: float) -> httpx.Response:
    endpoint = endpoint.lstrip('/')
    url = f'{INTERPROSCAN_BASE_URL}/{endpoint}'
    client = APIHttpClient(cache=INTERPROSCAN_API_CACHE, rate_limiter=INTERPROSCAN_RATE_LIMITER)
    method = method.upper()
    request_kwargs: dict[str, Any] = {}
    if method == 'POST':
        request_kwargs['data'] = data
    try:
        return await client.request(method, url, **request_kwargs, headers={'User-Agent': INTERPROSCAN_USER_AGENT}, timeout=timeout, retries=retries, retry_delay=RETRY_DELAY_S, cache_ttl=None, follow_redirects=True)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f'InterProScan {endpoint} failed with HTTP {status}: {body}') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f'InterProScan {endpoint} request failed: {exc}') from exc
def _interpro_to_tsv(result: dict[str, Any]) -> str:
    lines = ['accession\tname\tdatabase\tstart\tend\tevalue\tdescription']
    matches = result.get('matches', [])
    if not isinstance(matches, list):
        return '\n'.join(lines) + '\n'
    for match in matches:
        if not isinstance(match, dict):
            continue
        signature = match.get('signature', {})
        if not isinstance(signature, dict):
            signature = {}
        entry = signature.get('entry', {})
        if not isinstance(entry, dict):
            entry = {}
        locations = match.get('locations', [])
        if not isinstance(locations, list):
            locations = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            lines.append('\t'.join([str(signature.get('accession', '')), str(signature.get('name', '')), str(entry.get('type', '')), str(location.get('start', '')), str(location.get('end', '')), str(location.get('evalue', '')), str(entry.get('description', ''))]))
    return '\n'.join(lines) + '\n'


class InterProNode(InterProScanNode):
    """Compatibility wrapper for the original InterPro roadmap node ID."""
    NODE_ID = 'interpro'
    DISPLAY_NAME = 'InterPro'
    DESCRIPTION = 'Submit protein sequences to InterProScan and return InterPro domain annotations.'
    SEARCH_ALIASES = ['interpro', 'interproscan', 'domain', 'family', 'protein', 'pfam', 'smart', 'scan']
