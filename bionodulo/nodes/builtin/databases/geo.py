"""geo — databases node(s). One tool per file (extracted from ncbi.py)."""
from __future__ import annotations
import asyncio
import csv
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
import httpx
from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
NCBI_BASE_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
NCBI_BLAST_BASE_URL = 'https://blast.ncbi.nlm.nih.gov/Blast.cgi'
NCBI_USER_AGENT = 'BioNodulo/2.0 (workflow node; NCBI E-utilities)'
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 30.0
NCBI_CACHE_TTL_S = 300.0
NCBI_RATE_LIMIT_PER_SECOND = 3.0
NCBI_API_KEY_RATE_LIMIT_PER_SECOND = 10.0
BLAST_PROGRAMS = ('blastn', 'blastp', 'blastx', 'tblastn', 'tblastx', 'megablast')
BLAST_DATABASES = ('nt', 'nr', 'refseq_rna', 'refseq_protein', 'pdb', 'est', 'gss', 'pat', 'env_nr')
BLAST_OUTPUT_FORMATS = ('JSON2', 'XML', 'Tabular', 'Text', 'XML2', 'CSV', 'SAM')
BLAST_PARSE_INPUT_FORMATS = ('auto', 'JSON2', 'XML')
BLAST_PARSE_OUTPUT_FORMATS = ('TSV', 'JSON')
BLAST_HIT_FIELDS = ['query', 'subject_id', 'subject_title', 'scientific_name', 'percent_identity', 'evalue', 'bit_score', 'alignment_length', 'query_from', 'query_to', 'subject_from', 'subject_to']
BLAST_EXTENSIONS = {'JSON2': '.json', 'XML': '.xml', 'XML2': '.xml', 'Tabular': '.tsv', 'Text': '.txt', 'CSV': '.csv', 'SAM': '.sam'}
GEO_QUERY_TYPES = ('search', 'series', 'sample', 'platform')
GEO_ENTRY_TYPES = {'series': 'gse', 'sample': 'gsm', 'platform': 'gpl'}
SRA_OUTPUT_FORMATS = ('fastq', 'fasta')
NCBI_EFETCH_RETTYPES = ('fasta', 'gb', 'gbwithparts', 'gbc', 'ft', 'xml', 'acc', 'seqid', 'docsum')
NCBI_EFETCH_RETMODES = ('text', 'xml', 'json', 'asn.1')
NCBI_EFETCH_DATABASES = ('pubmed', 'gene', 'snp', 'sra', 'nuccore', 'nucleotide', 'protein', 'assembly', 'gds', 'taxonomy')
NCBI_ESEARCH_DATABASES = (*NCBI_EFETCH_DATABASES, 'mesh')
SRA_FILE_SUFFIXES = {'fastq': ('.fastq', '.fq', '.fastq.gz', '.fq.gz'), 'fasta': ('.fasta', '.fa', '.fna', '.fasta.gz', '.fa.gz', '.fna.gz')}
logger = logging.getLogger(__name__)
NCBI_API_CACHE = APICache.from_environment(default_ttl_seconds=NCBI_CACHE_TTL_S)
NCBI_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=NCBI_RATE_LIMIT_PER_SECOND, burst=1)
NCBI_API_KEY_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=NCBI_API_KEY_RATE_LIMIT_PER_SECOND, burst=1)
def _resolve_api_key(explicit: Any, context: Any) -> str:
    return resolve_secret_value(explicit, context, 'ncbi_api_key', 'BIONODULO_NCBI_API_KEY', 'NCBI_API_KEY', default=os.environ.get('BIONODULO_NCBI_API_KEY', '') or os.environ.get('NCBI_API_KEY', ''))
def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, '')}
async def _request_json(endpoint: str, params: dict[str, Any], *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> dict[str, Any]:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.json()
async def _request_text(endpoint: str, params: dict[str, Any], *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> str:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.text
async def _request(endpoint: str, params: dict[str, Any], *, retries: int, timeout: float) -> httpx.Response:
    url = f'{NCBI_BASE_URL}/{endpoint}'
    clean = _clean_params(params)
    rate_limiter = NCBI_API_KEY_RATE_LIMITER if clean.get('api_key') else NCBI_RATE_LIMITER
    client = APIHttpClient(cache=NCBI_API_CACHE, rate_limiter=rate_limiter)
    try:
        return await client.request('GET', url, params=clean, headers={'User-Agent': NCBI_USER_AGENT}, timeout=timeout, retries=retries, retry_delay=RETRY_DELAY_S, cache_ttl=NCBI_CACHE_TTL_S)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f'NCBI {endpoint} failed with HTTP {status}: {body}') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f'NCBI {endpoint} request failed: {exc}') from exc
async def _blast_request_text(method: str, params: dict[str, Any], *, retries: int=MAX_RETRIES, timeout: float=REQUEST_TIMEOUT_S) -> str:
    clean = _clean_params(params)
    method = method.upper()
    client = APIHttpClient(cache=NCBI_API_CACHE, rate_limiter=NCBI_RATE_LIMITER)
    request_kwargs: dict[str, Any] = {}
    if method == 'POST':
        request_kwargs['data'] = clean
    else:
        request_kwargs['params'] = clean
    try:
        response = await client.request(method, NCBI_BLAST_BASE_URL, **request_kwargs, headers={'User-Agent': NCBI_USER_AGENT}, timeout=timeout, retries=retries, retry_delay=RETRY_DELAY_S, cache_ttl=None, follow_redirects=True)
        return response.text
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f'NCBI BLAST request failed with HTTP {status}: {body}') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f'NCBI BLAST request failed: {exc}') from exc
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
def _chunked(values: list[str], size: int) -> list[list[str]]:
    if size < 1:
        raise ValueError('batch_size must be at least 1')
    return [values[index:index + size] for index in range(0, len(values), size)]
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _safe_filename(value: str) -> str:
    name = re.sub('[^A-Za-z0-9._-]+', '_', value).strip('._')
    return name or 'records'
def _default_extension(rettype: str, retmode: str) -> str:
    if retmode == 'json':
        return '.json'
    if retmode == 'xml':
        return '.xml'
    if retmode == 'asn.1':
        return '.asn1'
    if rettype in {'fasta', 'fasta_cds_na', 'fasta_cds_aa'}:
        return '.fasta'
    if rettype in {'gb', 'gbwithparts'}:
        return '.gb'
    return '.txt'
def _default_ncbi_email() -> str:
    return os.environ.get('BIONODULO_EMAIL', 'bionodulo@example.com')
def _normalise_ncbi_database(database: Any) -> str:
    value = str(database or 'nuccore')
    return 'nuccore' if value == 'nucleotide' else value
def _normalise_blast_query(query: Any) -> str:
    text = str(query or '').strip()
    if not text:
        raise ValueError('NCBI BLAST requires a query_sequence')
    path = Path(text).expanduser()
    if path.is_file():
        text = path.read_text(encoding='utf-8').strip()
        if not text:
            raise ValueError('NCBI BLAST requires a query_sequence')
    if text.startswith('>'):
        return text
    sequence = ''.join(text.split())
    if not sequence:
        raise ValueError('NCBI BLAST requires a query_sequence')
    return f'>query\n{sequence}'
def _parse_blast_submission(text: str) -> tuple[str, int | None]:
    rid_match = re.search('\\bRID\\s*=\\s*([A-Za-z0-9_-]+)', text)
    if not rid_match:
        raise RuntimeError('Failed to get BLAST RID from submission response')
    rtoe_match = re.search('\\bRTOE\\s*=\\s*(\\d+)', text)
    return (rid_match.group(1), int(rtoe_match.group(1)) if rtoe_match else None)
def _blast_status(text: str) -> str:
    status_match = re.search('\\bStatus\\s*=\\s*([A-Z]+)', text)
    return status_match.group(1) if status_match else ''
def _blast_result_summary(raw_results: str, output_format: str) -> dict[str, Any]:
    if output_format != 'JSON2':
        return {}
    try:
        payload = json.loads(raw_results)
    except json.JSONDecodeError:
        return {}
    output = payload.get('BlastOutput2') if isinstance(payload, dict) else None
    if not isinstance(output, list) or not output:
        return {}
    first = output[0]
    if not isinstance(first, dict):
        return {}
    report = first.get('report', {})
    if not isinstance(report, dict):
        return {}
    search = report.get('results', {}).get('search', {})
    if not isinstance(search, dict):
        return {}
    hits = search.get('hits', [])
    summary: dict[str, Any] = {'num_hits': len(hits) if isinstance(hits, list) else 0}
    if search.get('query_title') is not None:
        summary['query'] = search.get('query_title')
    if isinstance(search.get('stat'), dict):
        summary['stat'] = search.get('stat')
    return summary
def _blast_parse_format(path: Path, requested: str) -> str:
    value = str(requested or 'auto')
    if value != 'auto':
        if value not in {'JSON2', 'XML'}:
            raise ValueError(f'Unsupported BLAST parse input_format: {requested}')
        return value
    suffix = path.suffix.lower()
    if suffix == '.json':
        return 'JSON2'
    if suffix == '.xml':
        return 'XML'
    text = path.read_text(encoding='utf-8', errors='replace').lstrip()
    if text.startswith('<'):
        return 'XML'
    return 'JSON2'
def _blast_float(value: Any, default: float=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
def _blast_int(value: Any) -> int | str:
    try:
        return int(value)
    except (TypeError, ValueError):
        return ''
def _blast_percent_identity(identity: Any, alignment_length: Any) -> float:
    length = _blast_float(alignment_length)
    if length <= 0:
        return 0.0
    return round(_blast_float(identity) / length * 100.0, 2)
def _clean_blast_text(value: Any) -> str:
    return str(value or '').replace('\t', ' ').replace('\n', ' ').strip()
def _json2_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ''):
            return mapping[key]
    return ''
def _parse_blast_json2_hits(raw_results: str) -> list[dict[str, Any]]:
    payload = json.loads(raw_results)
    output = payload.get('BlastOutput2') if isinstance(payload, dict) else payload
    if not isinstance(output, list):
        raise ValueError('BLAST JSON2 results must contain a BlastOutput2 list')
    rows: list[dict[str, Any]] = []
    for record in output:
        if not isinstance(record, dict):
            continue
        report = record.get('report', {})
        if not isinstance(report, dict):
            continue
        search = report.get('results', {}).get('search', {})
        if not isinstance(search, dict):
            continue
        query = _clean_blast_text(search.get('query_title') or search.get('query_id') or search.get('query'))
        hits = search.get('hits', [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            descriptions = hit.get('description', [])
            description = descriptions[0] if descriptions and isinstance(descriptions[0], dict) else {}
            hsps = hit.get('hsps', [])
            hsp = hsps[0] if hsps and isinstance(hsps[0], dict) else {}
            alignment_length = _blast_int(_json2_value(hsp, 'align_len', 'align-len', 'alignment_length'))
            rows.append({'query': query, 'subject_id': _clean_blast_text(description.get('id') or hit.get('id')), 'subject_title': _clean_blast_text(description.get('title') or hit.get('title')), 'scientific_name': _clean_blast_text(description.get('sciname') or description.get('scientific_name')), 'percent_identity': _blast_percent_identity(_json2_value(hsp, 'identity'), alignment_length), 'evalue': _json2_value(hsp, 'evalue'), 'bit_score': _json2_value(hsp, 'bit_score', 'bit-score'), 'alignment_length': alignment_length, 'query_from': _blast_int(_json2_value(hsp, 'query_from', 'query-from')), 'query_to': _blast_int(_json2_value(hsp, 'query_to', 'query-to')), 'subject_from': _blast_int(_json2_value(hsp, 'hit_from', 'hit-from')), 'subject_to': _blast_int(_json2_value(hsp, 'hit_to', 'hit-to'))})
    return rows
def _xml_text(element: ET.Element, path: str) -> str:
    return _clean_blast_text(element.findtext(path, default=''))
def _parse_blast_xml_hits(raw_results: str) -> list[dict[str, Any]]:
    root = ET.fromstring(raw_results)
    rows: list[dict[str, Any]] = []
    for iteration in root.findall('.//Iteration'):
        query = _xml_text(iteration, 'Iteration_query-def') or _xml_text(iteration, 'Iteration_query-ID')
        for hit in iteration.findall('./Iteration_hits/Hit'):
            hsp = hit.find('./Hit_hsps/Hsp')
            alignment_length = _blast_int(_xml_text(hsp, 'Hsp_align-len')) if hsp is not None else ''
            rows.append({'query': query, 'subject_id': _xml_text(hit, 'Hit_id'), 'subject_title': _xml_text(hit, 'Hit_def'), 'scientific_name': '', 'percent_identity': _blast_percent_identity(_xml_text(hsp, 'Hsp_identity'), alignment_length) if hsp is not None else 0.0, 'evalue': _xml_text(hsp, 'Hsp_evalue') if hsp is not None else '', 'bit_score': _blast_float(_xml_text(hsp, 'Hsp_bit-score')) if hsp is not None else 0.0, 'alignment_length': alignment_length, 'query_from': _blast_int(_xml_text(hsp, 'Hsp_query-from')) if hsp is not None else '', 'query_to': _blast_int(_xml_text(hsp, 'Hsp_query-to')) if hsp is not None else '', 'subject_from': _blast_int(_xml_text(hsp, 'Hsp_hit-from')) if hsp is not None else '', 'subject_to': _blast_int(_xml_text(hsp, 'Hsp_hit-to')) if hsp is not None else ''})
    return rows
def _format_blast_tsv_value(field: str, value: Any) -> str:
    if field == 'percent_identity':
        return f'{_blast_float(value):.2f}'
    return _clean_blast_text(value)
def _write_blast_hits_tsv(path: Path, hits: list[dict[str, Any]]) -> None:
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=BLAST_HIT_FIELDS, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for hit in hits:
            writer.writerow({field: _format_blast_tsv_value(field, hit.get(field, '')) for field in BLAST_HIT_FIELDS})
def _geo_summaries_from_esummary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get('result', {})
    if not isinstance(result, dict):
        return []
    uids = [str(uid) for uid in result.get('uids', []) if str(uid)]
    summaries: list[dict[str, Any]] = []
    if uids:
        for uid in uids:
            record = result.get(uid)
            if isinstance(record, dict):
                summaries.append(record)
        return summaries
    for key, value in result.items():
        if key == 'uids':
            continue
        if isinstance(value, dict):
            summaries.append(value)
    return summaries
def _geo_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ''):
            if isinstance(value, list):
                return ','.join((str(item) for item in value))
            return str(value).replace('\t', ' ').replace('\n', ' ')
    return ''
def _geo_summaries_to_tsv(summaries: list[dict[str, Any]]) -> str:
    lines = ['uid\taccession\ttitle\tentry_type\tgds_type\tn_samples\torganism\tplatform\tpublication_date']
    for record in summaries:
        lines.append('\t'.join([_geo_value(record, 'uid'), _geo_value(record, 'accession', 'Accession'), _geo_value(record, 'title'), _geo_value(record, 'entryType', 'entry_type'), _geo_value(record, 'gdsType', 'gds_type'), _geo_value(record, 'n_samples', 'nSamples'), _geo_value(record, 'taxon', 'organism'), _geo_value(record, 'GPL', 'platform'), _geo_value(record, 'PDAT', 'pdat', 'publication_date')]))
    return '\n'.join(lines) + '\n'
def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}
def _result_value(result: Any, key: str, default: Any='') -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)
def _decode_process_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode(errors='replace')
    return str(value)
def _normalise_command_result(result: Any) -> dict[str, Any]:
    return {'returncode': int(_result_value(result, 'returncode', 0) or 0), 'stdout': _decode_process_text(_result_value(result, 'stdout', '')), 'stderr': _decode_process_text(_result_value(result, 'stderr', ''))}
async def _run_command(command: list[str], cwd: Path, context: Any) -> dict[str, Any]:
    if context is not None and hasattr(context, 'run_command'):
        result = await context.run_command(command, cwd=str(cwd))
        return _normalise_command_result(result)
    proc = await asyncio.create_subprocess_exec(*command, cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    return _normalise_command_result({'returncode': proc.returncode, 'stdout': stdout, 'stderr': stderr})
def _collect_sra_files(out_dir: Path, accession: str, output_format: str) -> list[str]:
    files: dict[Path, None] = {}
    for suffix in SRA_FILE_SUFFIXES[output_format]:
        for path in out_dir.glob(f'{accession}*{suffix}'):
            if path.is_file():
                files[path] = None
    return [str(path) for path in sorted(files, key=lambda item: item.name)]


class GEOQueryNode(BaseNode):
    """Query NCBI GEO metadata through the GDS E-utilities database."""
    NODE_ID = 'geo_query'
    DISPLAY_NAME = 'GEO Query'
    CATEGORY = 'databases'
    DESCRIPTION = 'Search or look up NCBI GEO series, sample, and platform metadata.'
    SEARCH_ALIASES = ['geo', 'gene expression omnibus', 'microarray', 'rnaseq', 'metadata', 'series', 'sample', 'gds']
    RETURN_TYPES = ('JSON', 'TSV')
    RETURN_NAMES = ('geo_metadata', 'sample_table')
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = 'https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'accession': ('STRING', {'default': '', 'description': 'GEO accession, e.g. GSE, GSM, or GPL'})}, 'optional': {'query_type': (list(GEO_QUERY_TYPES), {'default': 'series'}), 'search_query': ('STRING', {'default': '', 'description': 'Used when query_type=search'}), 'query': ('STRING', {'default': '', 'advanced': True, 'description': 'Backward-compatible GEO search query'}), 'dataset_type': ('STRING', {'default': '', 'options': list(GEO_QUERY_TYPES), 'advanced': True}), 'max_results': ('INT', {'default': 10, 'min': 1, 'max': 500}), 'api_key': ('STRING', {'default': '', 'advanced': True})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop('context', None)
        query_type = str(kwargs.get('query_type', '') or kwargs.get('dataset_type', '') or 'series').lower()
        if query_type not in GEO_QUERY_TYPES:
            raise ValueError(f'Unsupported GEO query_type: {query_type}')
        query_alias = str(kwargs.get('query', '') or '').strip()
        accession = str(kwargs.get('accession', '') or (query_alias if query_type != 'search' else '')).strip()
        search_query = str(kwargs.get('search_query', '') or (query_alias if query_type == 'search' else '')).strip()
        max_results = int(kwargs.get('max_results', 10) or 10)
        if max_results < 1:
            raise ValueError('max_results must be at least 1')
        if query_type == 'search':
            term = search_query or accession
            if not term:
                raise ValueError('GEO Query requires search_query or accession')
        else:
            if not accession:
                raise ValueError('GEO Query requires accession')
            term = f'{accession}[ACCN] AND {GEO_ENTRY_TYPES[query_type]}[ETYP]'
        api_key = _resolve_api_key(kwargs.get('api_key', ''), context)
        email = _default_ncbi_email()
        search_params: dict[str, Any] = {'db': 'gds', 'term': term, 'retmode': 'json', 'retmax': max_results, 'tool': 'bionodulo', 'email': email}
        if api_key:
            search_params['api_key'] = api_key
        search_payload = await _request_json('esearch.fcgi', search_params)
        search_result = search_payload.get('esearchresult', {})
        uids = [str(uid) for uid in search_result.get('idlist', [])]
        total_count = int(search_result.get('count', 0))
        summaries: list[dict[str, Any]] = []
        if uids:
            summary_params: dict[str, Any] = {'db': 'gds', 'id': ','.join(uids), 'retmode': 'json', 'tool': 'bionodulo', 'email': email}
            if api_key:
                summary_params['api_key'] = api_key
            summary_payload = await _request_json('esummary.fcgi', summary_params)
            summaries = _geo_summaries_from_esummary(summary_payload)
        metadata = {'query': term, 'query_type': query_type, 'uids': uids, 'total_count': total_count, 'record_count': len(summaries), 'summaries': summaries}
        out_dir = _node_output_dir(self, context)
        if query_type == 'search':
            metadata_path = out_dir / 'geo_search_results.json'
            table_path = out_dir / 'geo_results.tsv'
        else:
            metadata_path = out_dir / 'geo_metadata.json'
            table_path = out_dir / 'sample_table.tsv'
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding='utf-8')
        table_path.write_text(_geo_summaries_to_tsv(summaries), encoding='utf-8')
        return {'outputs': {'geo_metadata': str(metadata_path), 'sample_table': str(table_path)}}
