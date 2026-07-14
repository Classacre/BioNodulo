"""join — data_transform node(s). One tool per file (extracted from data_transform.py)."""
from __future__ import annotations
import ast
import csv
import json
import math
import operator
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import _shell_join
from bionodulo.nodes.types import file_extension_for
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _delimiter(value: str, path: str | Path | None=None) -> str:
    mode = (value or 'auto').strip().lower()
    if mode == 'csv':
        return ','
    if mode == 'tsv':
        return '\t'
    if path and str(path).lower().endswith('.csv'):
        return ','
    return '\t'
def _read_table(path: str | Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f'Table has no header row: {path}')
        return (list(reader.fieldnames), [dict(row) for row in reader])
def _write_table(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], delimiter: str) -> None:
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=delimiter, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _format_scalar(row.get(name, '')) for name in fieldnames})
def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or '').split(',') if item.strip()]
def _parse_rename_map(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in _split_csv(value):
        if ':' not in item:
            raise ValueError(f'Rename entry must be old:new, got {item!r}')
        old, new = item.split(':', 1)
        old = old.strip()
        new = new.strip()
        if not old or not new:
            raise ValueError(f'Rename entry must be old:new, got {item!r}')
        mapping[old] = new
    return mapping
def _format_scalar(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
def _as_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(str(value).strip())
def _normalise_table_format(value: str, path: str | Path | None=None) -> str:
    requested = str(value or 'auto').strip().lower()
    if requested == 'auto':
        suffixes = ''.join(Path(str(path)).suffixes).lower() if path else ''
        if suffixes.endswith('.json'):
            return 'json'
        if suffixes.endswith('.csv'):
            return 'csv'
        return 'tsv'
    if requested not in {'csv', 'tsv', 'json'}:
        raise ValueError(f'Unsupported table format: {value}')
    return requested
def _fieldnames_from_records(records: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            name = str(key)
            if name not in seen:
                seen.add(name)
                fieldnames.append(name)
    return fieldnames
def _read_records(path: str | Path, input_format: str) -> list[dict[str, Any]]:
    if input_format in {'csv', 'tsv'}:
        _fieldnames, rows = _read_table(path, ',' if input_format == 'csv' else '\t')
        return rows
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(payload, dict) and isinstance(payload.get('rows'), list):
        payload = payload['rows']
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not all((isinstance(item, dict) for item in payload)):
        raise ValueError('JSON input must be an object, a list of objects, or an object with a rows list')
    return [dict(item) for item in payload]
def _write_records(path: Path, output_format: str, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == 'json':
        path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        return
    fieldnames = _fieldnames_from_records(records)
    _write_table(path, fieldnames, records, ',' if output_format == 'csv' else '\t')
def _fasta_header(value: Any) -> str:
    header = re.sub('\\s+', '_', str(value or '').strip())
    header = re.sub('[^A-Za-z0-9_.|:-]', '_', header)
    return header or 'sequence'
def _fasta_sequence(value: Any) -> str:
    return re.sub('\\s+', '', str(value or '')).upper()
def _wrap_sequence(sequence: str, line_width: int) -> list[str]:
    if line_width <= 0:
        return [sequence]
    return [sequence[index:index + line_width] for index in range(0, len(sequence), line_width)]


class JoinTablesNode(BaseNode):
    """Join two CSV/TSV tables with multi-key and index join support."""
    NODE_ID = 'join_tables'
    DISPLAY_NAME = 'Join Tables'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Join two CSV/TSV tables with multi-key, suffix, and index-join options.'
    SEARCH_ALIASES = ['join', 'tables', 'multi-key', 'index join', 'advanced join', 'csv', 'tsv']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('joined_table',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table_a': ('FILE', {'description': 'Left CSV/TSV table'}), 'table_b': ('FILE', {'description': 'Right CSV/TSV table'}), 'join_keys': ('STRING', {'default': '', 'description': 'Comma-separated join keys; empty joins by row index'})}, 'optional': {'how': ('STRING', {'default': 'inner', 'options': ['inner', 'left', 'right', 'outer']}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']}), 'left_suffix': ('STRING', {'default': '_left', 'advanced': True}), 'right_suffix': ('STRING', {'default': '_right', 'advanced': True})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        table_a = kwargs['table_a']
        table_b = kwargs['table_b']
        delim = _delimiter(str(kwargs.get('delimiter', 'auto')), table_a)
        fields_a, rows_a = _read_table(table_a, delim)
        fields_b, rows_b = _read_table(table_b, delim)
        join_keys = _split_csv(str(kwargs.get('join_keys', '')))
        how = str(kwargs.get('how', 'inner') or 'inner').lower()
        left_suffix = str(kwargs.get('left_suffix', '_left'))
        right_suffix = str(kwargs.get('right_suffix', '_right'))
        if how not in {'inner', 'left', 'right', 'outer'}:
            raise ValueError(f'Unsupported join mode: {how}')
        output_fields = self._output_fields(fields_a, fields_b, join_keys, left_suffix, right_suffix)
        output_rows = self._join_by_index(rows_a, rows_b, fields_a, fields_b, output_fields, how, left_suffix, right_suffix) if not join_keys else self._join_by_keys(rows_a, rows_b, fields_a, fields_b, output_fields, join_keys, how, left_suffix, right_suffix)
        out_path = _node_output_dir(self, context) / 'joined.tsv'
        _write_table(out_path, output_fields, output_rows, '\t')
        return (str(out_path),)

    @staticmethod
    def _output_fields(fields_a: list[str], fields_b: list[str], join_keys: list[str], left_suffix: str, right_suffix: str) -> list[str]:
        for key in join_keys:
            if key not in fields_a or key not in fields_b:
                raise ValueError(f'Join key {key!r} must exist in both tables')
        overlapping = (set(fields_a) & set(fields_b)) - set(join_keys)
        output_fields: list[str] = []
        for field in fields_a:
            output_fields.append(f'{field}{left_suffix}' if field in overlapping else field)
        for field in fields_b:
            if field in join_keys:
                continue
            output_fields.append(f'{field}{right_suffix}' if field in overlapping else field)
        return output_fields

    @classmethod
    def _join_by_keys(cls, rows_a: list[dict[str, str]], rows_b: list[dict[str, str]], fields_a: list[str], fields_b: list[str], output_fields: list[str], join_keys: list[str], how: str, left_suffix: str, right_suffix: str) -> list[dict[str, str]]:
        right_by_key: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        for row in rows_b:
            right_by_key.setdefault(cls._key(row, join_keys), []).append(row)
        left_by_key: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        for row in rows_a:
            left_by_key.setdefault(cls._key(row, join_keys), []).append(row)
        output_rows: list[dict[str, str]] = []
        if how in {'inner', 'left', 'outer'}:
            for left in rows_a:
                matches = right_by_key.get(cls._key(left, join_keys), [])
                if matches:
                    for right in matches:
                        output_rows.append(cls._combine(left, right, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
                elif how in {'left', 'outer'}:
                    output_rows.append(cls._combine(left, None, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
        if how in {'right', 'outer'}:
            for right in rows_b:
                matches = left_by_key.get(cls._key(right, join_keys), [])
                if how == 'right' and matches:
                    for left in matches:
                        output_rows.append(cls._combine(left, right, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
                elif not matches:
                    output_rows.append(cls._combine(None, right, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
        return output_rows

    @classmethod
    def _join_by_index(cls, rows_a: list[dict[str, str]], rows_b: list[dict[str, str]], fields_a: list[str], fields_b: list[str], output_fields: list[str], how: str, left_suffix: str, right_suffix: str) -> list[dict[str, str]]:
        if how == 'inner':
            indexes = range(min(len(rows_a), len(rows_b)))
        elif how == 'left':
            indexes = range(len(rows_a))
        elif how == 'right':
            indexes = range(len(rows_b))
        else:
            indexes = range(max(len(rows_a), len(rows_b)))
        return [cls._combine(rows_a[index] if index < len(rows_a) else None, rows_b[index] if index < len(rows_b) else None, fields_a, fields_b, [], output_fields, left_suffix, right_suffix) for index in indexes]

    @staticmethod
    def _key(row: dict[str, str], join_keys: list[str]) -> tuple[str, ...]:
        return tuple((row.get(key, '') for key in join_keys))

    @staticmethod
    def _combine(left: dict[str, str] | None, right: dict[str, str] | None, fields_a: list[str], fields_b: list[str], join_keys: list[str], output_fields: list[str], left_suffix: str, right_suffix: str) -> dict[str, str]:
        overlapping = (set(fields_a) & set(fields_b)) - set(join_keys)
        row = {field: '' for field in output_fields}
        for field in fields_a:
            out_field = f'{field}{left_suffix}' if field in overlapping else field
            row[out_field] = left.get(field, '') if left else right.get(field, '') if right and field in join_keys else ''
        for field in fields_b:
            if field in join_keys:
                if row.get(field, '') == '' and right:
                    row[field] = right.get(field, '')
                continue
            out_field = f'{field}{right_suffix}' if field in overlapping else field
            row[out_field] = right.get(field, '') if right else ''
        return row
