"""set — data_transform node(s). One tool per file (extracted from data_transform.py)."""
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


class SetFieldsNode(BaseNode):
    """Add or update table fields using constant values or row templates."""
    NODE_ID = 'set_fields'
    DISPLAY_NAME = 'Set Fields'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Add, update, or keep selected CSV/TSV fields using JSON field assignments.'
    SEARCH_ALIASES = ['set', 'fields', 'field mapping', 'assign', 'update columns', 'add columns', 'data mapping', 'table transform']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('updated_table',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table': ('FILE', {'description': 'CSV or TSV table with a header row'}), 'assignments': ('STRING', {'default': '{}', 'multiline': True, 'description': 'JSON object mapping output fields to constants or "{column}" templates'})}, 'optional': {'keep_only_set': ('BOOLEAN', {'default': False, 'description': 'Only emit fields listed in assignments or field_order'}), 'field_order': ('STRING', {'default': '', 'description': 'Comma-separated output field order override'}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        input_path = Path(str(kwargs['table']))
        input_delim = _delimiter(str(kwargs.get('delimiter', 'auto')), input_path)
        fieldnames, rows = _read_table(input_path, input_delim)
        assignments = self._parse_assignments(str(kwargs.get('assignments', '{}') or '{}'))
        if not assignments:
            raise ValueError('assignments must include at least one field')
        updated_rows = [self._apply_assignments(row, assignments) for row in rows]
        output_fields = self._output_fields(fieldnames, assignments, str(kwargs.get('field_order', '') or ''), bool(kwargs.get('keep_only_set', False)))
        output_delim, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), input_path)
        output_path = _node_output_dir(self, context) / f'{input_path.stem}.set{extension}'
        _write_table(output_path, output_fields, updated_rows, output_delim)
        return (str(output_path),)

    @staticmethod
    def _parse_assignments(value: str) -> OrderedDict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f'assignments must be a JSON object: {exc.msg}') from exc
        if not isinstance(parsed, dict):
            raise ValueError('assignments must be a JSON object')
        assignments: OrderedDict[str, Any] = OrderedDict()
        for key, assigned_value in parsed.items():
            field = str(key).strip()
            if not field:
                raise ValueError('assignment field names must be non-empty')
            assignments[field] = assigned_value
        return assignments

    @classmethod
    def _apply_assignments(cls, row: dict[str, str], assignments: OrderedDict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = dict(row)
        for field, value in assignments.items():
            output[field] = cls._render_value(value, row)
        return output

    @staticmethod
    def _render_value(value: Any, row: dict[str, str]) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return value.format_map(row)
        except KeyError as exc:
            missing = str(exc.args[0])
            raise ValueError(f'Unknown template field: {missing}') from exc

    @staticmethod
    def _output_fields(fieldnames: list[str], assignments: OrderedDict[str, Any], field_order: str, keep_only_set: bool) -> list[str]:
        explicit_order = _split_csv(field_order)
        if explicit_order:
            unknown = [field for field in explicit_order if field not in fieldnames and field not in assignments]
            if unknown:
                raise ValueError(f"field_order includes unknown field(s): {', '.join(unknown)}")
            return explicit_order
        if keep_only_set:
            return list(assignments.keys())
        output_fields = list(fieldnames)
        output_fields.extend((field for field in assignments if field not in fieldnames))
        return output_fields

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
