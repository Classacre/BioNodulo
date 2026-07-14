"""merge — data_transform node(s). One tool per file (extracted from data_transform.py)."""
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


class MergeTablesNode(BaseNode):
    """Join two CSV/TSV tables by a shared key column."""
    NODE_ID = 'merge_tables'
    DISPLAY_NAME = 'Merge Tables'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Join two CSV/TSV tables by a shared or mapped key using inner, left, right, outer, or cross joins.'
    SEARCH_ALIASES = ['merge', 'join', 'table', 'csv', 'tsv', 'annotation', 'left join', 'right join', 'outer join', 'cross join']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('merged_table',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table_a': ('FILE', {'description': 'Left CSV/TSV table'}), 'table_b': ('FILE', {'description': 'Right CSV/TSV table'})}, 'optional': {'join_key': ('STRING', {'default': '', 'description': 'Shared column name to join on; empty auto-detects a common column'}), 'key_column_a': ('STRING', {'default': '', 'description': 'Column name in table A; empty uses join_key or auto-detected common column'}), 'key_column_b': ('STRING', {'default': '', 'description': 'Column name in table B; empty uses key_column_a/join_key'}), 'join_type': ('STRING', {'default': 'inner', 'options': ['inner', 'left', 'right', 'outer', 'cross']}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']}), 'suffix_a': ('STRING', {'default': '_a', 'advanced': True}), 'suffix_b': ('STRING', {'default': '_b', 'advanced': True}), 'right_suffix': ('STRING', {'default': '_right', 'advanced': True}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        table_a = kwargs['table_a']
        table_b = kwargs['table_b']
        delim = _delimiter(str(kwargs.get('delimiter', 'auto')), table_a)
        fields_a, rows_a = _read_table(table_a, delim)
        fields_b, rows_b = _read_table(table_b, delim)
        join_type = str(kwargs.get('join_type', 'inner'))
        if join_type not in {'inner', 'left', 'right', 'outer', 'cross'}:
            raise ValueError(f'Unsupported join_type: {join_type}')
        key_a, key_b = ('', '') if join_type == 'cross' else self._resolve_join_keys(kwargs, fields_a, fields_b)
        suffix_a, suffix_b = self._resolve_suffixes(kwargs)
        left_output_names, right_output_names = self._output_name_maps(fields_a, fields_b, key_a, key_b, suffix_a, suffix_b)
        output_fields = list(left_output_names.values()) + list(right_output_names.values())
        if join_type == 'cross':
            output_rows = [self._combine(left, right, left_output_names, right_output_names) for left in rows_a for right in rows_b]
            output_delim, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), table_a, table_b)
            out_path = _node_output_dir(self, context) / f'{Path(str(table_a)).stem}.merged{extension}'
            _write_table(out_path, output_fields, output_rows, output_delim)
            return (str(out_path),)
        right_by_key: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows_b:
            right_by_key.setdefault(row.get(key_b, ''), []).append(row)
        left_by_key: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows_a:
            left_by_key.setdefault(row.get(key_a, ''), []).append(row)
        output_rows: list[dict[str, Any]] = []
        if join_type in {'inner', 'left', 'outer'}:
            for left in rows_a:
                matches = right_by_key.get(left.get(key_a, ''), [])
                if matches:
                    for right in matches:
                        output_rows.append(self._combine(left, right, left_output_names, right_output_names))
                elif join_type in {'left', 'outer'}:
                    output_rows.append(self._combine(left, None, left_output_names, right_output_names))
        if join_type in {'right', 'outer'}:
            for right in rows_b:
                matches = left_by_key.get(right.get(key_b, ''), [])
                if join_type == 'right' and matches:
                    for left in matches:
                        output_rows.append(self._combine(left, right, left_output_names, right_output_names))
                elif not matches:
                    left_stub = {field: '' for field in fields_a}
                    left_stub[key_a] = right.get(key_b, '')
                    output_rows.append(self._combine(left_stub, right, left_output_names, right_output_names))
        output_delim, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), table_a, table_b)
        out_path = _node_output_dir(self, context) / f'{Path(str(table_a)).stem}.merged{extension}'
        _write_table(out_path, output_fields, output_rows, output_delim)
        return (str(out_path),)

    @staticmethod
    def _resolve_suffixes(kwargs: dict[str, Any]) -> tuple[str, str]:
        has_suffix_a = 'suffix_a' in kwargs
        has_suffix_b = 'suffix_b' in kwargs
        if has_suffix_a or has_suffix_b:
            return (str(kwargs.get('suffix_a', '_a')), str(kwargs.get('suffix_b', kwargs.get('right_suffix', '_b'))))
        return ('', str(kwargs.get('right_suffix', '_right')))

    @staticmethod
    def _resolve_join_keys(kwargs: dict[str, Any], fields_a: list[str], fields_b: list[str]) -> tuple[str, str]:
        shared_key = str(kwargs.get('join_key', '') or '').strip()
        key_a = str(kwargs.get('key_column_a', '') or '').strip() or shared_key
        key_b = str(kwargs.get('key_column_b', '') or '').strip() or key_a or shared_key
        if not key_a and (not key_b):
            common = [field for field in fields_a if field in fields_b]
            if not common:
                raise ValueError('No common columns found. Please specify join_key or key_column_a/key_column_b.')
            key_a = key_b = common[0]
        elif key_a and (not key_b):
            key_b = key_a
        elif key_b and (not key_a):
            key_a = key_b
        if key_a not in fields_a:
            raise ValueError(f'Key column {key_a!r} must exist in table A')
        if key_b not in fields_b:
            raise ValueError(f'Key column {key_b!r} must exist in table B')
        return (key_a, key_b)

    @staticmethod
    def _output_name_maps(fields_a: list[str], fields_b: list[str], key_a: str, key_b: str, suffix_a: str, suffix_b: str) -> tuple[OrderedDict[str, str], OrderedDict[str, str]]:
        left_names: OrderedDict[str, str] = OrderedDict()
        right_names: OrderedDict[str, str] = OrderedDict()
        overlapping = set(fields_a) & set(fields_b)
        overlapping.discard(key_a)
        overlapping.discard(key_b)
        for field in fields_a:
            left_names[field] = f'{field}{suffix_a}' if suffix_a and field in overlapping else field
        for field in fields_b:
            if field == key_b:
                continue
            right_names[field] = f'{field}{suffix_b}' if field in overlapping else field
        return (left_names, right_names)

    @staticmethod
    def _output_format(output_type: str, table_a: str | Path, table_b: str | Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == 'CSV':
            return (',', '.csv')
        if normalized == 'TSV':
            return ('\t', '.tsv')
        if normalized == 'AUTO':
            inputs_are_csv = Path(str(table_a)).suffix.lower() == '.csv' and Path(str(table_b)).suffix.lower() == '.csv'
            return (',', '.csv') if inputs_are_csv else ('\t', '.tsv')
        raise ValueError(f'Unsupported output_type: {output_type}')

    @staticmethod
    def _combine(left: dict[str, str], right: dict[str, str] | None, left_output_names: OrderedDict[str, str], right_output_names: dict[str, str]) -> dict[str, str]:
        row = {output_field: left.get(left_field, '') for left_field, output_field in left_output_names.items()}
        for right_field, output_field in right_output_names.items():
            row[output_field] = right.get(right_field, '') if right else ''
        return row
