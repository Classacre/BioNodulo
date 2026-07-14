"""compare — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class CompareResultsNode(BaseNode):
    """Compare outputs from two workflow branches."""
    NODE_ID = 'compare_results'
    DISPLAY_NAME = 'Compare Results'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Compare outputs from two branches. Diff, checksum, or statistical comparison. Generate comparison report.'
    SEARCH_ALIASES = ['compare', 'diff', 'checksum', 'validate', 'benchmark', 'test']
    RETURN_TYPES = ('JSON', 'BOOLEAN', 'FILE')
    RETURN_NAMES = ('comparison_report', 'match', 'diff_file')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'result_a': ('ANY', {}), 'result_b': ('ANY', {})}, 'optional': {'comparison_method': (['checksum', 'diff', 'exact', 'size', 'statistical'], {'default': 'checksum'}), 'tolerance': ('FLOAT', {'default': 0.0, 'min': 0.0}), 'output_format': (['json', 'html', 'txt'], {'default': 'json'}), 'ignore_patterns': ('STRING', {'default': ''})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[str, bool, str]:
        context = kwargs.pop('context', None)
        result_a = kwargs.get('result_a')
        result_b = kwargs.get('result_b')
        method = str(kwargs.get('comparison_method', 'checksum') or 'checksum').lower()
        tolerance = max(0.0, float(kwargs.get('tolerance', 0.0) or 0.0))
        output_format = str(kwargs.get('output_format', 'json') or 'json').lower()
        ignore_patterns = self._parse_ignore_patterns(kwargs.get('ignore_patterns', ''))
        report: dict[str, Any] = {'comparison_method': method, 'result_a_type': type(result_a).__name__, 'result_b_type': type(result_b).__name__, 'tolerance': tolerance, 'ignored_patterns': ignore_patterns}
        diff_content = ''
        if method == 'checksum':
            checksum_a = self._compute_checksum(result_a)
            checksum_b = self._compute_checksum(result_b)
            match = checksum_a == checksum_b
            report.update({'checksum_a': checksum_a, 'checksum_b': checksum_b, 'match': match})
        elif method == 'exact':
            match = result_a == result_b
            report['match'] = match
        elif method == 'diff':
            diff_content = self._diff_results(result_a, result_b, ignore_patterns)
            match = diff_content == ''
            report.update({'match': match, 'diff_lines': len(diff_content.splitlines())})
        elif method == 'size':
            size_a = self._size_of(result_a)
            size_b = self._size_of(result_b)
            difference = abs(size_a - size_b)
            match = difference <= tolerance
            report.update({'size_a': size_a, 'size_b': size_b, 'size_difference': difference, 'match': match})
        elif method == 'statistical':
            match = self._statistical_compare(result_a, result_b, tolerance, report)
        else:
            raise ValueError(f'Unsupported comparison method: {method}')
        report['overall_match'] = match
        diff_file = self._write_artifact(context, output_format, report, diff_content)
        level = 'info' if match else 'warning'
        _ctx_log(context, level, f'Compare Results [{method}]: match={match}')
        return (_json_text(report), match, diff_file)

    @staticmethod
    def _parse_ignore_patterns(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [pattern.strip() for pattern in str(value or '').split(',') if pattern.strip()]

    def _compute_checksum(self, value: Any) -> str:
        return hashlib.sha256(self._canonical_bytes(value)).hexdigest()

    def _canonical_bytes(self, value: Any) -> bytes:
        path = self._existing_path(value)
        if path is not None:
            return path.read_bytes()
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
        return str(value).encode('utf-8')

    @staticmethod
    def _existing_path(value: Any) -> Path | None:
        if not isinstance(value, (str, Path)):
            return None
        try:
            path = Path(value)
            return path if path.exists() and path.is_file() else None
        except OSError:
            return None

    def _diff_results(self, result_a: Any, result_b: Any, ignore_patterns: list[str]) -> str:
        lines_a = self._lines_for_diff(result_a)
        lines_b = self._lines_for_diff(result_b)
        if ignore_patterns:
            regexes = [re.compile(pattern) for pattern in ignore_patterns]
            lines_a = [line for line in lines_a if not any((regex.search(line) for regex in regexes))]
            lines_b = [line for line in lines_b if not any((regex.search(line) for regex in regexes))]
        diff = difflib.unified_diff(lines_a, lines_b, fromfile='result_a', tofile='result_b', lineterm='')
        return '\n'.join(diff)

    @staticmethod
    def _lines_for_diff(value: Any) -> list[str]:
        path = CompareResultsNode._existing_path(value)
        if path is not None:
            try:
                return path.read_text(encoding='utf-8').splitlines()
            except UnicodeDecodeError:
                return [path.read_bytes().hex()]
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, indent=2, sort_keys=True, default=str).splitlines()
        return str(value).splitlines()

    def _size_of(self, value: Any) -> int:
        path = self._existing_path(value)
        if path is not None:
            return path.stat().st_size
        return len(self._canonical_bytes(value))

    def _statistical_compare(self, result_a: Any, result_b: Any, tolerance: float, report: dict[str, Any]) -> bool:
        values_a = self._numeric_values(result_a)
        values_b = self._numeric_values(result_b)
        if len(values_a) != len(values_b):
            report.update({'match': False, 'shape_mismatch': f'{len(values_a)} vs {len(values_b)}'})
            return False
        if not values_a:
            report.update({'match': True, 'max_difference': 0.0, 'mean_difference': 0.0})
            return True
        differences = [abs(a - b) for a, b in zip(values_a, values_b, strict=True)]
        max_difference = max(differences)
        mean_difference = math.fsum(differences) / len(differences)
        match = all((difference <= tolerance for difference in differences))
        report.update({'match': match, 'count': len(differences), 'max_difference': max_difference, 'mean_difference': mean_difference})
        return match

    @staticmethod
    def _numeric_values(value: Any) -> list[float]:
        if isinstance(value, dict):
            value = list(value.values())
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        return [float(value)]

    def _write_artifact(self, context: Any, output_format: str, report: dict[str, Any], diff_content: str) -> str:
        if context is None:
            return ''
        output_dir = _node_output_dir(self, context)
        if output_format == 'html':
            path = output_dir / 'comparison_report.html'
            path.write_text(self._format_html_report(report, diff_content), encoding='utf-8')
            return str(path)
        if output_format == 'txt':
            path = output_dir / 'comparison_report.txt'
            path.write_text(self._format_text_report(report, diff_content), encoding='utf-8')
            return str(path)
        if diff_content:
            path = output_dir / 'diff.txt'
            path.write_text(diff_content, encoding='utf-8')
            return str(path)
        return ''

    @staticmethod
    def _format_text_report(report: dict[str, Any], diff_content: str) -> str:
        sections = ['Comparison Report', json.dumps(report, indent=2, sort_keys=True, default=str)]
        if diff_content:
            sections.extend(['Diff', diff_content])
        return '\n\n'.join(sections)

    @staticmethod
    def _format_html_report(report: dict[str, Any], diff_content: str) -> str:
        status_color = '#15803d' if report.get('match') else '#b91c1c'
        status_text = 'MATCH' if report.get('match') else 'MISMATCH'
        report_json = html.escape(json.dumps(report, indent=2, sort_keys=True, default=str))
        diff_html = html.escape(diff_content[:20000])
        return f'<!doctype html><html><head><meta charset="utf-8"><title>Comparison Report</title><style>body{{font-family:system-ui,sans-serif;padding:24px;max-width:960px;margin:0 auto}}pre{{background:#f8fafc;padding:16px;border-radius:4px;overflow:auto}}.status{{display:inline-block;padding:4px 10px;border-radius:4px;color:white;background:{status_color}}}</style></head><body><h1>Comparison Report <span class="status">{status_text}</span></h1><pre>{report_json}</pre><h2>Diff</h2><pre>{diff_html}</pre></body></html>'
