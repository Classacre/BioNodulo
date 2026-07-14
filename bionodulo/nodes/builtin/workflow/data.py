"""data — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
from __future__ import annotations
import asyncio
import csv
import difflib
import gzip
import html
import hashlib
import json
import math
import os
import platform
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from bionodulo.execution.pause_state import PauseStateStore
from bionodulo.nodes.base import BaseNode
def _ctx_log(context: Any, level: str, message: str) -> None:
    if context is not None and hasattr(context, 'log'):
        context.log(level, message)
def _ctx_emit(context: Any, event: str, payload: dict[str, Any]) -> None:
    if context is not None and hasattr(context, 'emit'):
        context.emit(event, payload)
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    base.mkdir(parents=True, exist_ok=True)
    return base
def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class DataValidatorNode(BaseNode):
    """Validate file/data quality before downstream workflow steps."""
    NODE_ID = 'data_validator'
    DISPLAY_NAME = 'Data Validator'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Validate data quality, file format, required fields, record counts, and checksums'
    SEARCH_ALIASES = ['validate', 'validator', 'qc', 'check', 'verify', 'sanity', 'format']
    RETURN_TYPES = ('ANY', 'BOOLEAN', 'JSON', 'FILE')
    RETURN_NAMES = ('passthrough', 'passed', 'validation_report', 'report_file')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'File path or data value to validate'})}, 'optional': {'expected_format': (['auto', 'fasta', 'fastq', 'vcf', 'bam', 'csv', 'tsv', 'json', 'yaml', 'text', 'directory'], {'default': 'auto'}), 'min_size_bytes': ('INT', {'default': 0, 'min': 0}), 'max_size_bytes': ('INT', {'default': 0, 'min': 0}), 'required_fields': ('STRING', {'default': '', 'description': 'Comma-separated required fields'}), 'min_records': ('INT', {'default': 0, 'min': 0}), 'checksum_expected': ('STRING', {'default': '', 'description': 'Expected SHA-256 checksum'}), 'fail_on_error': ('BOOLEAN', {'default': True})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        expected_format = str(kwargs.get('expected_format', 'auto') or 'auto').lower()
        min_size = int(kwargs.get('min_size_bytes', 0) or 0)
        max_size = int(kwargs.get('max_size_bytes', 0) or 0)
        required_fields = [field.strip() for field in str(kwargs.get('required_fields', '') or '').split(',') if field.strip()]
        min_records = int(kwargs.get('min_records', 0) or 0)
        checksum_expected = str(kwargs.get('checksum_expected', '') or '').strip()
        fail_on_error = bool(kwargs.get('fail_on_error', True))
        report: dict[str, Any] = {'input': str(data)[:500], 'expected_format': expected_format, 'checks': {}, 'warnings': [], 'errors': []}
        passed = True
        if data == []:
            report['errors'].append('No input data provided')
            passed = False
        elif self._is_path_list(data, expected_format):
            passed = self._validate_path_list([Path(str(item)) for item in data], expected_format, report, min_size, max_size, required_fields)
            if passed and min_records > 0:
                records = self._record_count(report)
                if records < min_records:
                    report['errors'].append(f'Too few records: {records} (min: {min_records})')
                    passed = False
            if passed and checksum_expected:
                report['errors'].append('Checksum validation is not supported for multiple inputs')
                passed = False
        else:
            path = self._materialize_input(data, context)
            if path is None:
                report['errors'].append('No input data provided')
                passed = False
            else:
                passed = self._validate_path(path, expected_format, report, min_size, max_size)
                if passed and checksum_expected:
                    passed = self._verify_checksum(path, checksum_expected, report)
                if passed and min_records > 0:
                    records = self._record_count(report)
                    if records < min_records:
                        report['errors'].append(f'Too few records: {records} (min: {min_records})')
                        passed = False
                if passed and required_fields:
                    passed = self._check_required_fields(path, expected_format, required_fields, report)
        report['passed'] = passed
        report['check_count'] = len(report['checks'])
        report['error_count'] = len(report['errors'])
        report_file = ''
        if context is not None:
            report_path = _node_output_dir(self, context) / 'validation_report.json'
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding='utf-8')
            report_file = str(report_path)
        _ctx_log(context, 'info' if passed else 'warning', f"Validation: {('PASSED' if passed else 'FAILED')} ({report['error_count']} errors)")
        if not passed and fail_on_error:
            raise RuntimeError(f"Data validation failed: {'; '.join(report['errors'])}")
        return (data, passed, _json_text(report), report_file)

    @staticmethod
    def _is_path_list(data: Any, expected_format: str) -> bool:
        path_formats = {'auto', 'fasta', 'fastq', 'vcf', 'bam', 'csv', 'tsv', 'text', 'directory'}
        return expected_format in path_formats and isinstance(data, (list, tuple)) and bool(data) and all((isinstance(item, (str, Path)) for item in data))

    @staticmethod
    def _record_count(report: dict[str, Any]) -> int:
        checks = report.get('checks', {})
        return int(checks.get('record_count', checks.get('row_count', checks.get('variant_count', 0))) or 0)

    def _materialize_input(self, data: Any, context: Any) -> Path | None:
        if data is None:
            return None
        if isinstance(data, (str, Path)):
            return Path(str(data))
        if context is None:
            return None
        path = _node_output_dir(self, context) / 'validator_input.data'
        if isinstance(data, (dict, list)):
            path.write_text(json.dumps(data, sort_keys=True, default=str), encoding='utf-8')
        else:
            path.write_text(str(data), encoding='utf-8')
        return path

    def _validate_path_list(self, paths: list[Path], expected_format: str, report: dict[str, Any], min_size: int, max_size: int, required_fields: list[str]) -> bool:
        file_reports: list[dict[str, Any]] = []
        passed = True
        total_size = 0
        total_records = 0
        for index, path in enumerate(paths, start=1):
            file_report: dict[str, Any] = {'input': str(path), 'checks': {}, 'warnings': [], 'errors': []}
            file_passed = self._validate_path(path, expected_format, file_report, min_size, max_size)
            if file_passed and required_fields:
                file_passed = self._check_required_fields(path, expected_format, required_fields, file_report)
            if not file_passed:
                passed = False
                for error in file_report['errors']:
                    report['errors'].append(f'Input {index} ({path}): {error}')
            report['warnings'].extend((f'Input {index} ({path}): {warning}' for warning in file_report['warnings']))
            total_size += int(file_report['checks'].get('file_size_bytes', 0) or 0)
            total_records += self._record_count(file_report)
            file_reports.append(file_report)
        report['checks']['file_count'] = len(paths)
        report['checks']['total_size_bytes'] = total_size
        report['checks']['record_count'] = total_records
        report['checks']['files'] = file_reports
        return passed

    def _validate_path(self, path: Path, expected_format: str, report: dict[str, Any], min_size: int, max_size: int) -> bool:
        if not path.exists():
            report['errors'].append(f'File not found: {path}')
            return False
        if expected_format == 'directory':
            return self._validate_directory(path, report, min_size, max_size)
        if not path.is_file():
            report['errors'].append(f'Path is not a file: {path}')
            return False
        size = path.stat().st_size
        report['checks']['file_exists'] = True
        report['checks']['file_size_bytes'] = size
        if min_size > 0 and size < min_size:
            report['errors'].append(f'File too small: {size} bytes (min: {min_size})')
            return False
        if max_size > 0 and size > max_size:
            report['errors'].append(f'File too large: {size} bytes (max: {max_size})')
            return False
        report['checks']['size_ok'] = True
        fmt = self._detect_format(path, expected_format)
        report['checks']['detected_format'] = fmt
        validator = {'fasta': self._validate_fasta, 'fastq': self._validate_fastq, 'vcf': self._validate_vcf, 'bam': self._validate_bam, 'csv': self._validate_csv, 'tsv': self._validate_tsv, 'json': self._validate_json, 'yaml': self._validate_yaml, 'text': self._validate_text}.get(fmt, self._validate_text)
        return validator(path, report)

    @staticmethod
    def _detect_format(path: Path, expected_format: str) -> str:
        if expected_format != 'auto':
            return expected_format
        suffixes = [suffix.lower() for suffix in path.suffixes]
        if '.fasta' in suffixes or '.fa' in suffixes or '.fna' in suffixes:
            return 'fasta'
        if '.fastq' in suffixes or '.fq' in suffixes:
            return 'fastq'
        if '.vcf' in suffixes:
            return 'vcf'
        if '.bam' in suffixes:
            return 'bam'
        if '.csv' in suffixes:
            return 'csv'
        if '.tsv' in suffixes:
            return 'tsv'
        if '.json' in suffixes:
            return 'json'
        if '.yaml' in suffixes or '.yml' in suffixes:
            return 'yaml'
        return 'text'

    def _validate_directory(self, path: Path, report: dict[str, Any], min_size: int, max_size: int) -> bool:
        if not path.is_dir():
            report['errors'].append(f'Path is not a directory: {path}')
            return False
        file_count = 0
        directory_count = 0
        total_size = 0
        try:
            for child in path.rglob('*'):
                if child.is_file():
                    file_count += 1
                    total_size += child.stat().st_size
                elif child.is_dir():
                    directory_count += 1
        except OSError as exc:
            report['errors'].append(f'Directory validation error: {exc}')
            return False
        report['checks']['directory_exists'] = True
        report['checks']['file_count'] = file_count
        report['checks']['directory_count'] = directory_count
        report['checks']['total_size_bytes'] = total_size
        if min_size > 0 and total_size < min_size:
            report['errors'].append(f'Directory contents too small: {total_size} bytes (min: {min_size})')
            return False
        if max_size > 0 and total_size > max_size:
            report['errors'].append(f'Directory contents too large: {total_size} bytes (max: {max_size})')
            return False
        report['checks']['size_ok'] = True
        report['checks']['format_valid'] = True
        return True

    @staticmethod
    def _read_text_lines(path: Path) -> list[str]:
        if path.suffix.lower() == '.gz':
            with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as handle:
                return handle.read().splitlines()
        return path.read_text(encoding='utf-8', errors='replace').splitlines()

    def _validate_fasta(self, path: Path, report: dict[str, Any]) -> bool:
        records = 0
        saw_sequence = False
        try:
            for line in self._read_text_lines(path):
                if line.startswith('>'):
                    records += 1
                    saw_sequence = False
                elif line.strip():
                    saw_sequence = True
            if records == 0 or not saw_sequence:
                report['errors'].append('FASTA: missing header or sequence')
                return False
            report['checks']['record_count'] = records
            report['checks']['format_valid'] = True
            return True
        except OSError as exc:
            report['errors'].append(f'FASTA validation error: {exc}')
            return False

    def _validate_fastq(self, path: Path, report: dict[str, Any]) -> bool:
        lines = self._read_text_lines(path)
        if len(lines) == 0 or len(lines) % 4 != 0:
            report['errors'].append(f'FASTQ: line count {len(lines)} is not divisible by 4')
            return False
        for idx in range(0, len(lines), 4):
            if not lines[idx].startswith('@') or not lines[idx + 2].startswith('+'):
                report['errors'].append(f'FASTQ: invalid record starting at line {idx + 1}')
                return False
        report['checks']['record_count'] = len(lines) // 4
        report['checks']['format_valid'] = True
        return True

    def _validate_vcf(self, path: Path, report: dict[str, Any]) -> bool:
        header_lines = 0
        variant_count = 0
        for line in self._read_text_lines(path):
            if line.startswith('#'):
                header_lines += 1
            elif line.strip():
                variant_count += 1
        if header_lines == 0:
            report['errors'].append('VCF: no header lines found')
            return False
        report['checks']['header_lines'] = header_lines
        report['checks']['variant_count'] = variant_count
        report['checks']['format_valid'] = True
        return True

    def _validate_bam(self, path: Path, report: dict[str, Any]) -> bool:
        with path.open('rb') as handle:
            magic = handle.read(4)
        if magic == b'BAM\x01':
            report['checks']['bam_container'] = 'uncompressed'
        elif magic.startswith(b'\x1f\x8b'):
            report['checks']['bam_container'] = 'bgzf_or_gzip'
        else:
            report['warnings'].append('BAM: file does not start with recognized BAM or BGZF magic; cannot deeply validate here')
        report['checks']['format_valid'] = True
        return True

    def _validate_csv(self, path: Path, report: dict[str, Any]) -> bool:
        return self._validate_delimited(path, report, delimiter=',', label='CSV')

    def _validate_tsv(self, path: Path, report: dict[str, Any]) -> bool:
        return self._validate_delimited(path, report, delimiter='\t', label='TSV')

    def _validate_delimited(self, path: Path, report: dict[str, Any], *, delimiter: str, label: str) -> bool:
        try:
            with path.open(newline='', encoding='utf-8', errors='replace') as handle:
                rows = list(csv.reader(handle, delimiter=delimiter))
        except csv.Error as exc:
            report['errors'].append(f'{label}: {exc}')
            return False
        if not rows:
            report['errors'].append(f'{label}: empty file')
            return False
        report['checks']['column_count'] = len(rows[0])
        report['checks']['row_count'] = max(0, len(rows) - 1)
        report['checks']['format_valid'] = True
        return True

    def _validate_json(self, path: Path, report: dict[str, Any]) -> bool:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            report['errors'].append(f'JSON validation error: {exc}')
            return False
        if isinstance(data, list):
            report['checks']['record_count'] = len(data)
        elif isinstance(data, dict):
            report['checks']['field_count'] = len(data)
        report['checks']['format_valid'] = True
        return True

    def _validate_yaml(self, path: Path, report: dict[str, Any]) -> bool:
        try:
            import yaml
        except ImportError:
            report['errors'].append('YAML validation requires PyYAML')
            return False
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
        except Exception as exc:
            report['errors'].append(f'YAML validation error: {exc}')
            return False
        if isinstance(data, list):
            report['checks']['record_count'] = len(data)
        elif isinstance(data, dict):
            report['checks']['field_count'] = len(data)
        report['checks']['format_valid'] = True
        return True

    def _validate_text(self, path: Path, report: dict[str, Any]) -> bool:
        report['checks']['line_count'] = len(self._read_text_lines(path))
        report['checks']['format_valid'] = True
        return True

    def _verify_checksum(self, path: Path, expected: str, report: dict[str, Any]) -> bool:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        report['checks']['checksum_expected'] = expected
        report['checks']['checksum_actual'] = actual
        if actual.lower() != expected.lower():
            report['errors'].append(f'Checksum mismatch: expected {expected[:16]}..., got {actual[:16]}...')
            return False
        report['checks']['checksum_ok'] = True
        return True

    def _check_required_fields(self, path: Path, expected_format: str, required_fields: list[str], report: dict[str, Any]) -> bool:
        fmt = self._detect_format(path, expected_format)
        fields: set[str] = set()
        if fmt in {'csv', 'tsv'}:
            delimiter = '\t' if fmt == 'tsv' else ','
            with path.open(newline='', encoding='utf-8', errors='replace') as handle:
                rows = csv.reader(handle, delimiter=delimiter)
                fields = set(next(rows, []))
        elif fmt == 'json':
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                fields = set(data.keys())
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                fields = set(data[0].keys())
        else:
            report['warnings'].append(f'Required fields are not supported for {fmt}')
            return True
        missing = [field for field in required_fields if field not in fields]
        if missing:
            report['errors'].append(f'Missing required fields: {missing}')
            return False
        report['checks']['required_fields_ok'] = True
        return True
