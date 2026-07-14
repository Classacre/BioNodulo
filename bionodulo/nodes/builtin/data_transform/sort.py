"""sort — data_transform node(s). One tool per file (extracted from data_transform.py)."""
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


class SortFileNode(BaseNode):
    """Sort delimited text files by named columns or zero-based column indices."""
    NODE_ID = 'sort_file'
    DISPLAY_NAME = 'Sort File'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Sort a delimited table by one or more columns using numeric, string, or automatic comparison.'
    SEARCH_ALIASES = ['sort', 'order', 'reorder', 'ascending', 'descending', 'numeric sort', 'table sort']
    RETURN_TYPES = ('CSV',)
    RETURN_NAMES = ('sorted_file',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file': ('FILE', {'description': 'Delimited text file to sort'}), 'sort_column': ('STRING', {'default': '', 'description': 'Column name or 0-based index; comma-separated'})}, 'optional': {'sort_type': ('STRING', {'default': 'auto', 'options': ['auto', 'string', 'numeric']}), 'ascending': ('BOOLEAN', {'default': True}), 'stable': ('BOOLEAN', {'default': True}), 'has_header': ('BOOLEAN', {'default': True}), 'separator': ('STRING', {'default': 'auto', 'options': ['auto', 'comma', 'tab', 'space']}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        input_path = Path(str(kwargs['file']))
        sort_column = str(kwargs.get('sort_column', '') or '')
        sort_type = str(kwargs.get('sort_type', 'auto') or 'auto').lower()
        ascending = bool(kwargs.get('ascending', True))
        has_header = bool(kwargs.get('has_header', True))
        separator = self._separator(str(kwargs.get('separator', 'auto') or 'auto'), input_path)
        output_type = str(kwargs.get('output_type', 'AUTO') or 'AUTO').upper()
        if sort_type not in {'auto', 'string', 'numeric'}:
            raise ValueError(f'Unsupported sort_type: {sort_type}')
        rows = self._read_rows(input_path, separator)
        header: list[str] | None = rows[0] if has_header and rows else None
        data_rows = rows[1:] if header else rows
        sort_indexes = self._sort_indexes(sort_column, header, data_rows)
        sorted_rows = sorted(data_rows, key=lambda row: self._sort_key(row, sort_indexes, sort_type), reverse=not ascending)
        output_sep, extension = self._output_format(output_type, input_path)
        output_path = _node_output_dir(self, context) / f'{input_path.stem}.sorted{extension}'
        with output_path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh, delimiter=output_sep, lineterminator='\n')
            if header:
                writer.writerow(header)
            writer.writerows(sorted_rows)
        return (str(output_path),)

    @staticmethod
    def _separator(separator: str, path: Path) -> str:
        mode = separator.lower()
        if mode == 'comma':
            return ','
        if mode == 'tab':
            return '\t'
        if mode == 'space':
            return ' '
        if mode == 'auto':
            return ',' if path.suffix.lower() == '.csv' else '\t'
        raise ValueError(f'Unsupported separator: {separator}')

    @staticmethod
    def _read_rows(path: Path, separator: str) -> list[list[str]]:
        with path.open(newline='', encoding='utf-8') as fh:
            return [row for row in csv.reader(fh, delimiter=separator)]

    @staticmethod
    def _sort_indexes(sort_column: str, header: list[str] | None, rows: list[list[str]]) -> list[int]:
        width = max((len(row) for row in rows), default=len(header or []))
        if not sort_column.strip():
            return list(range(width))
        indexes: list[int] = []
        for item in _split_csv(sort_column):
            if header is not None and (not item.isdigit()):
                if item not in header:
                    raise ValueError(f'Sort column {item!r} not found')
                indexes.append(header.index(item))
            else:
                index = int(item)
                if index < 0:
                    raise ValueError(f'Sort column index must be non-negative: {item}')
                indexes.append(index)
        return indexes

    @classmethod
    def _sort_key(cls, row: list[str], indexes: list[int], sort_type: str) -> tuple[Any, ...]:
        return tuple((cls._coerce_sort_value(row[index] if index < len(row) else '', sort_type) for index in indexes))

    @staticmethod
    def _coerce_sort_value(value: str, sort_type: str) -> Any:
        if sort_type == 'string':
            return str(value)
        if sort_type == 'numeric':
            try:
                return (0, _as_number(value))
            except ValueError:
                return (1, str(value))
        try:
            return (0, _as_number(value))
        except ValueError:
            return (1, str(value))

    @staticmethod
    def _output_format(output_type: str, input_path: Path) -> tuple[str, str]:
        if output_type == 'CSV':
            return (',', '.csv')
        if output_type == 'TSV':
            return ('\t', '.tsv')
        if output_type == 'AUTO':
            return (',', '.csv') if input_path.suffix.lower() == '.csv' else ('\t', '.tsv')
        raise ValueError(f'Unsupported output_type: {output_type}')
