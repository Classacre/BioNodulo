"""filter — data_transform node(s). One tool per file (extracted from data_transform.py)."""
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


class FilterRowsNode(BaseNode):
    """Filter CSV/TSV rows by a column condition."""
    NODE_ID = 'filter_rows'
    DISPLAY_NAME = 'Filter Rows'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Filter CSV/TSV rows using numeric, string, regex, or emptiness conditions.'
    SEARCH_ALIASES = ['filter', 'rows', 'table', 'csv', 'tsv', 'quality gate', 'subset rows', 'select rows', 'where', 'query', 'conditional filter', 'table filter', 'csv filter', 'tsv filter']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('filtered_table',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table': ('FILE', {'description': 'CSV or TSV table with a header row'}), 'column': ('STRING', {'description': 'Column to test'}), 'operator': ('STRING', {'default': 'equals', 'options': ['equals', 'not_equals', '==', '!=', 'contains', 'not_contains', 'startswith', 'endswith', 'regex', 'greater_than', '>', 'greater_or_equal', '>=', 'less_than', '<', 'less_or_equal', '<=', 'in', 'not_in', 'is_empty', 'is_not_empty', 'is_null', 'is_not_null']}), 'value': ('STRING', {'default': '', 'description': 'Comparison value'})}, 'optional': {'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']}), 'case_sensitive': ('BOOLEAN', {'default': True}), 'invert': ('BOOLEAN', {'default': False}), 'logical_op': ('STRING', {'default': 'AND', 'options': ['AND', 'OR']}), 'column_2': ('STRING', {'default': ''}), 'operator_2': ('STRING', {'default': '', 'options': ['', 'equals', 'not_equals', '==', '!=', 'contains', 'not_contains', 'startswith', 'endswith', 'regex', 'greater_than', '>', 'greater_or_equal', '>=', 'less_than', '<', 'less_or_equal', '<=', 'in', 'not_in', 'is_empty', 'is_not_empty', 'is_null', 'is_not_null']}), 'value_2': ('STRING', {'default': ''}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        table = kwargs['table']
        delim = _delimiter(str(kwargs.get('delimiter', 'auto')), table)
        fieldnames, rows = _read_table(table, delim)
        column = str(kwargs['column'])
        if column not in fieldnames:
            raise ValueError(f'Column {column!r} not found in table')
        operator_name = str(kwargs.get('operator', 'equals'))
        expected = str(kwargs.get('value', ''))
        column_2 = str(kwargs.get('column_2', '') or '')
        operator_2 = str(kwargs.get('operator_2', '') or '')
        expected_2 = str(kwargs.get('value_2', ''))
        logical_op = str(kwargs.get('logical_op', 'AND') or 'AND').upper()
        case_sensitive = bool(kwargs.get('case_sensitive', True))
        invert = bool(kwargs.get('invert', False))
        if logical_op not in {'AND', 'OR'}:
            raise ValueError(f'Unsupported logical_op: {logical_op}')
        if operator_2:
            if not column_2:
                raise ValueError('column_2 is required when operator_2 is set')
            if column_2 not in fieldnames:
                raise ValueError(f'Column {column_2!r} not found in table')
        filtered: list[dict[str, str]] = []
        for row in rows:
            passed = self._matches(row.get(column, ''), operator_name, expected, case_sensitive)
            if operator_2:
                second_passed = self._matches(row.get(column_2, ''), operator_2, expected_2, case_sensitive)
                passed = passed and second_passed if logical_op == 'AND' else passed or second_passed
            if invert:
                passed = not passed
            if passed:
                filtered.append(row)
        if 'output_type' in kwargs:
            output_delim, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), table)
            output_name = f'{Path(str(table)).stem}.filtered{extension}'
        else:
            output_delim = '\t'
            output_name = 'filtered.tsv'
        out_path = _node_output_dir(self, context) / output_name
        _write_table(out_path, fieldnames, filtered, output_delim)
        return (str(out_path),)

    @staticmethod
    def _matches(actual: str, operator_name: str, expected: str, case_sensitive: bool) -> bool:
        operator_name = FilterRowsNode._normalise_operator(operator_name)
        text = str(actual or '')
        compare_to = str(expected or '')
        if not case_sensitive:
            text_cmp = text.lower()
            expected_cmp = compare_to.lower()
        else:
            text_cmp = text
            expected_cmp = compare_to
        if operator_name == 'equals':
            return text_cmp == expected_cmp
        if operator_name == 'not_equals':
            return text_cmp != expected_cmp
        if operator_name == 'contains':
            return expected_cmp in text_cmp
        if operator_name == 'not_contains':
            return expected_cmp not in text_cmp
        if operator_name == 'startswith':
            return text_cmp.startswith(expected_cmp)
        if operator_name == 'endswith':
            return text_cmp.endswith(expected_cmp)
        if operator_name == 'regex':
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.search(compare_to, text, flags=flags) is not None
        if operator_name in {'is_empty', 'is_null'}:
            return text.strip() == ''
        if operator_name in {'is_not_empty', 'is_not_null'}:
            return text.strip() != ''
        if operator_name in {'in', 'not_in'}:
            values = _split_csv(expected_cmp)
            matched = text_cmp in values
            return matched if operator_name == 'in' else not matched
        comparisons: dict[str, Callable[[float, float], bool]] = {'greater_than': operator.gt, 'greater_or_equal': operator.ge, 'less_than': operator.lt, 'less_or_equal': operator.le}
        if operator_name in comparisons:
            try:
                return comparisons[operator_name](_as_number(text), _as_number(compare_to))
            except ValueError:
                return False
        raise ValueError(f'Unsupported filter operator: {operator_name}')

    @staticmethod
    def _normalise_operator(operator_name: str) -> str:
        aliases = {'==': 'equals', '!=': 'not_equals', '>': 'greater_than', '>=': 'greater_or_equal', '<': 'less_than', '<=': 'less_or_equal', 'is_null': 'is_empty', 'is_not_null': 'is_not_empty'}
        return aliases.get(str(operator_name or '').strip(), str(operator_name or '').strip())

    @staticmethod
    def _output_format(output_type: str, input_path: str | Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == 'CSV':
            return (',', '.csv')
        if normalized == 'TSV':
            return ('\t', '.tsv')
        if normalized == 'AUTO':
            return (',', '.csv') if Path(str(input_path)).suffix.lower() == '.csv' else ('\t', '.tsv')
        raise ValueError(f'Unsupported output_type: {output_type}')
