"""ebi node(s) — phylogeny category (extracted, one tool per file)."""
from __future__ import annotations

from __future__ import annotations
import asyncio
import json
import os
import re
import shlex
import time
from pathlib import Path
from io import StringIO
from typing import Any
from xml.etree import ElementTree as ET
import httpx
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.phylogeny._shared import MAX_RETRIES, REQUEST_TIMEOUT_S, RETRY_DELAY_S, _html_to_text, _safe_filename


EBI_CLUSTALO_BASE_URL = 'https://www.ebi.ac.uk/Tools/services/rest/clustalo'

EBI_CLUSTALO_USER_AGENT = 'BioNodulo/2.0 (workflow node; EMBL-EBI Clustal Omega)'

EBI_CLUSTALO_CACHE_TTL_S = 300.0

EBI_CLUSTALO_RATE_LIMIT_PER_SECOND = 1.0

EBI_CLUSTALO_API_CACHE = APICache.from_environment(default_ttl_seconds=EBI_CLUSTALO_CACHE_TTL_S)

EBI_CLUSTALO_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=EBI_CLUSTALO_RATE_LIMIT_PER_SECOND, burst=1)

EBI_CLUSTALO_SEQUENCE_TYPES = ('protein', 'dna', 'rna')

EBI_CLUSTALO_OUTPUT_FORMATS = ('fa', 'clustal', 'clustal_num', 'msf', 'nexus', 'phylip', 'selex', 'stockholm', 'vienna')

EBI_CLUSTALO_MAX_ITERATIONS = 5

EBI_CLUSTALO_ALIGNMENT_EXTENSIONS = {'fa': '.fasta', 'clustal': '.aln', 'clustal_num': '.aln', 'msf': '.msf', 'nexus': '.nex', 'phylip': '.phy', 'selex': '.slx', 'stockholm': '.stk', 'vienna': '.vie'}

EBI_CLUSTALO_RUNNING_STATUSES = {'PENDING', 'RUNNING', 'QUEUED'}

EBI_CLUSTALO_FAILED_STATUSES = {'FAILURE', 'ERROR', 'NOT_FOUND', 'CANCELLED'}

def _count_fasta_records(value: str) -> int:
    return sum((1 for line in value.splitlines() if line.lstrip().startswith('>')))

async def _ebi_clustalo_post_text(endpoint: str, data: dict[str, Any], *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> str:
    response = await _ebi_clustalo_request('POST', endpoint, data=data, retries=retries, timeout=timeout)
    return response.text

async def _ebi_clustalo_get_text(endpoint: str, *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> str:
    response = await _ebi_clustalo_request('GET', endpoint, retries=retries, timeout=timeout)
    return response.text

async def _ebi_clustalo_request(method: str, endpoint: str, *, data: dict[str, Any] | None=None, retries: int, timeout: float) -> httpx.Response:
    endpoint = endpoint.lstrip('/')
    url = f'{EBI_CLUSTALO_BASE_URL}/{endpoint}'
    client = APIHttpClient(cache=EBI_CLUSTALO_API_CACHE, rate_limiter=EBI_CLUSTALO_RATE_LIMITER)
    method = method.upper()
    request_kwargs: dict[str, Any] = {}
    if method == 'POST':
        request_kwargs['data'] = data
    try:
        return await client.request(method, url, **request_kwargs, headers={'User-Agent': EBI_CLUSTALO_USER_AGENT}, timeout=timeout, retries=retries, retry_delay=RETRY_DELAY_S, cache_ttl=None, follow_redirects=True)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f'EBI Clustal Omega {endpoint} failed with HTTP {status}: {body}') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f'EBI Clustal Omega {endpoint} request failed: {exc}') from exc

def _ebi_clustalo_result_types(xml_text: str) -> list[str]:
    identifiers: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return identifiers
    for element in root.iter():
        if element.tag.rsplit('}', 1)[-1] == 'identifier' and element.text:
            identifiers.append(element.text.strip())
    return [identifier for identifier in identifiers if identifier]

def _ebi_clustalo_alignment_result_type(output_format: str, result_types: list[str]) -> str:
    preferred = {'fa': 'aln-fasta', 'clustal': 'aln-clustal', 'clustal_num': 'aln-clustal_num', 'msf': 'aln-msf', 'nexus': 'aln-nexus', 'phylip': 'aln-phylip', 'selex': 'aln-selex', 'stockholm': 'aln-stockholm', 'vienna': 'aln-vienna'}[output_format]
    if preferred in result_types:
        return preferred
    for result_type in result_types:
        if result_type.startswith('aln-'):
            return result_type
    return preferred

def _validate_ebi_clustalo_result(text: str, label: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise RuntimeError(f'EBI Clustal Omega returned an empty {label} response')
    if re.search('(?is)<\\s*(?:!doctype\\s+html|html|body|head|title|h[1-6]|error)\\b', stripped):
        summary = _html_to_text(stripped)[:500] or f'{label} error response'
        raise RuntimeError(f'EBI Clustal Omega returned an error page for {label}: {summary}')


class EBIClustalOmegaNode(BaseNode):
    """Run Clustal Omega through the EMBL-EBI Job Dispatcher service."""
    NODE_ID = 'ebi_clustal_omega'
    DISPLAY_NAME = 'EBI Clustal Omega'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Run multiple sequence alignment through EMBL-EBI Clustal Omega web services.'
    SEARCH_ALIASES = ['ebi', 'clustal omega', 'clustalo', 'msa', 'alignment', 'web service']
    RETURN_TYPES = ('ALIGNMENT', 'NEWICK', 'JSON')
    RETURN_NAMES = ('alignment', 'tree', 'job_metadata')
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = 'https://www.ebi.ac.uk/Tools/services/rest/clustalo'
    VERSION = '1.0.0'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sequences': ('FASTA', {'description': 'Three or more sequences in FASTA format'}), 'email': ('STRING', {'default': '', 'description': 'Email address required by EMBL-EBI Job Dispatcher'})}, 'optional': {'sequence_type': ('STRING', {'default': 'protein', 'options': list(EBI_CLUSTALO_SEQUENCE_TYPES)}), 'output_format': ('STRING', {'default': 'fa', 'options': list(EBI_CLUSTALO_OUTPUT_FORMATS)}), 'order': ('STRING', {'default': 'aligned', 'options': ['aligned', 'input']}), 'dealign': ('BOOLEAN', {'default': False, 'advanced': True}), 'add_formats': ('BOOLEAN', {'default': False, 'advanced': True}), 'iterations': ('INT', {'default': 0, 'min': 0, 'max': EBI_CLUSTALO_MAX_ITERATIONS, 'advanced': True}), 'timeout_minutes': ('INT', {'default': 30, 'min': 1, 'max': 240}), 'poll_interval_seconds': ('FLOAT', {'default': 10.0, 'min': 0.1, 'advanced': True}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop('context', None)
        sequences = str(kwargs.get('sequences', '') or '')
        if _count_fasta_records(sequences) < 3:
            raise ValueError('EBI Clustal Omega requires at least three FASTA records')
        email = str(kwargs.get('email', '') or '').strip()
        if not email:
            raise ValueError('EBI Clustal Omega requires an email address')
        sequence_type = str(kwargs.get('sequence_type', 'protein') or 'protein').lower()
        if sequence_type not in EBI_CLUSTALO_SEQUENCE_TYPES:
            raise ValueError(f'Unsupported sequence_type: {sequence_type}')
        output_format = str(kwargs.get('output_format', 'fa') or 'fa').lower()
        if output_format not in EBI_CLUSTALO_OUTPUT_FORMATS:
            raise ValueError(f'Unsupported output_format: {output_format}')
        order = str(kwargs.get('order', 'aligned') or 'aligned').lower()
        if order not in {'aligned', 'input'}:
            raise ValueError(f'Unsupported order: {order}')
        output_name = _safe_filename(str(kwargs.get('output_name', '') or ''), 'clustal_omega')
        timeout_minutes = int(kwargs.get('timeout_minutes', 30) or 30)
        poll_interval_seconds = float(kwargs.get('poll_interval_seconds', 10.0) or 10.0)
        params = self._submit_params(sequences=sequences, email=email, sequence_type=sequence_type, output_format=output_format, order=order, kwargs=kwargs)
        job_id = await self._submit_job(params)
        status_history = await self._poll_job(job_id=job_id, timeout_minutes=timeout_minutes, poll_interval_seconds=poll_interval_seconds)
        result_types = _ebi_clustalo_result_types(await _ebi_clustalo_get_text(f'resulttypes/{job_id}'))
        alignment_result_type = _ebi_clustalo_alignment_result_type(output_format, result_types)
        tree_result_type = 'phylotree' if 'phylotree' in result_types else 'guidetree'
        if tree_result_type not in result_types:
            raise RuntimeError(f'EBI Clustal Omega job {job_id} did not provide a tree result')
        alignment_text = await _ebi_clustalo_get_text(f'result/{job_id}/{alignment_result_type}')
        _validate_ebi_clustalo_result(alignment_text, 'alignment')
        tree_text = await _ebi_clustalo_get_text(f'result/{job_id}/{tree_result_type}')
        _validate_ebi_clustalo_result(tree_text, 'tree')
        alignment_path, tree_path, metadata_path = self.PLAN_OUTPUTS({'output_name': output_name, 'output_format': output_format}, Path(getattr(context, 'node_dir', '.') if context else '.'))
        alignment_path.write_text(alignment_text if alignment_text.endswith('\n') else alignment_text + '\n', encoding='utf-8')
        tree_path.write_text(tree_text if tree_text.endswith('\n') else tree_text + '\n', encoding='utf-8')
        metadata = {'alignment': str(alignment_path), 'alignment_result_type': alignment_result_type, 'job_id': job_id, 'params': params, 'result_types': result_types, 'status_history': status_history, 'tree': str(tree_path), 'tree_result_type': tree_result_type}
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return {'outputs': {'alignment': str(alignment_path), 'tree': str(tree_path), 'job_metadata': str(metadata_path)}}

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_format = str(inputs.get('output_format', 'fa') or 'fa').lower()
        if output_format not in EBI_CLUSTALO_OUTPUT_FORMATS:
            output_format = 'fa'
        output_name = _safe_filename(str(inputs.get('output_name', '') or ''), 'clustal_omega')
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f'{output_name}_alignment{EBI_CLUSTALO_ALIGNMENT_EXTENSIONS[output_format]}', node_out / f'{output_name}_tree.nwk', node_out / 'job_metadata.json']

    def _submit_params(self, *, sequences: str, email: str, sequence_type: str, output_format: str, order: str, kwargs: dict[str, Any]) -> dict[str, str]:
        params = {'email': email, 'title': 'bionodulo_ebi_clustal_omega', 'sequence': sequences, 'stype': sequence_type, 'outfmt': output_format, 'order': order, 'guidetreeout': 'true'}
        if bool(kwargs.get('dealign', False)):
            params['dealign'] = 'true'
        if bool(kwargs.get('add_formats', False)):
            params['addformats'] = 'true'
        iterations = int(kwargs.get('iterations', 0) or 0)
        if not 0 <= iterations <= EBI_CLUSTALO_MAX_ITERATIONS:
            raise ValueError(f'EBI Clustal Omega iterations must be between 0 and {EBI_CLUSTALO_MAX_ITERATIONS}')
        if iterations:
            params['iterations'] = str(iterations)
        return params

    async def _submit_job(self, params: dict[str, str]) -> str:
        job_id = (await _ebi_clustalo_post_text('run', params)).strip()
        if not job_id:
            raise RuntimeError('EBI Clustal Omega did not return a job ID')
        return job_id

    async def _poll_job(self, *, job_id: str, timeout_minutes: int, poll_interval_seconds: float) -> list[str]:
        started = time.monotonic()
        history: list[str] = []
        while True:
            elapsed_minutes = (time.monotonic() - started) / 60
            if elapsed_minutes > timeout_minutes:
                raise RuntimeError(f'EBI Clustal Omega job {job_id} timed out after {timeout_minutes} minutes')
            status = (await _ebi_clustalo_get_text(f'status/{job_id}')).strip().upper()
            history.append(status)
            if status == 'FINISHED':
                return history
            if status in EBI_CLUSTALO_FAILED_STATUSES:
                raise RuntimeError(f'EBI Clustal Omega job {job_id} failed with status {status}')
            if status in EBI_CLUSTALO_RUNNING_STATUSES:
                await asyncio.sleep(poll_interval_seconds)
                continue
            raise RuntimeError(f'EBI Clustal Omega job {job_id} returned unrecognised status: {status}')
