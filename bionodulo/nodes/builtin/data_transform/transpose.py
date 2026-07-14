"""transpose — data_transform node(s). One tool per file (extracted from data_transform.py)."""
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


class TransposeTableNode(BaseNode):
    """Transpose rows and columns of a CSV/TSV table."""
    NODE_ID = 'transpose_table'
    DISPLAY_NAME = 'Transpose Table'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Transpose rows and columns of a table. The first column, or specified ID column, becomes the new header row.'
    SEARCH_ALIASES = ['transpose', 'pivot', 'flip', 'rotate', 'swap axes', 'expression matrix transpose', 'count table transpose', 'genes as rows', 'samples as columns']
    RETURN_TYPES = ('CSV',)
    RETURN_NAMES = ('transposed_table',)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = '1.0.0'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table': ('FILE', {'description': 'CSV or TSV table with a header row'})}, 'optional': {'id_column': ('STRING', {'default': '', 'description': 'Column to use as transposed header IDs'}), 'new_header': ('STRING', {'default': '', 'description': 'Name for the new index column'}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        input_path = Path(str(kwargs['table']))
        input_delim = _delimiter(str(kwargs.get('delimiter', 'auto')), input_path)
        fieldnames, rows = _read_table(input_path, input_delim)
        id_column = str(kwargs.get('id_column', '') or fieldnames[0])
        if id_column not in fieldnames:
            raise ValueError(f'ID column {id_column!r} not found')
        output_ids = [row.get(id_column, '') for row in rows]
        duplicate_ids = sorted({value for value in output_ids if output_ids.count(value) > 1})
        if duplicate_ids:
            raise ValueError(f"ID column contains duplicate values: {', '.join(duplicate_ids)}")
        index_header = str(kwargs.get('new_header', '') or id_column)
        value_columns = [name for name in fieldnames if name != id_column]
        output_fields = [index_header] + output_ids
        output_rows = [{index_header: column, **{row.get(id_column, ''): row.get(column, '') for row in rows}} for column in value_columns]
        output_delim, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), input_path)
        output_path = _node_output_dir(self, context) / f'{input_path.stem}.transposed{extension}'
        _write_table(output_path, output_fields, output_rows, output_delim)
        return (str(output_path),)

    @staticmethod
    def _output_format(output_type: str, input_path: Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == 'CSV':
            return (',', '.csv')
        if normalized == 'TSV':
            return ('\t', '.tsv')
        if normalized == 'AUTO':
            return (',', '.csv') if input_path.suffix.lower() == '.csv' else ('\t', '.tsv')
        raise ValueError(f'Unsupported output_type: {output_type}')
