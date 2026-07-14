"""deduplicate — data_transform node(s). One tool per file (extracted from data_transform.py)."""
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


class DeduplicateNode(BaseNode):
    """Remove duplicate rows from CSV/TSV tables or duplicate FASTA sequences."""
    NODE_ID = 'deduplicate'
    DISPLAY_NAME = 'Deduplicate'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Remove duplicate table rows or FASTA records based on selected key columns or sequence content.'
    SEARCH_ALIASES = ['deduplicate', 'remove duplicates', 'unique', 'distinct', 'drop duplicates', 'dedup', 'unique rows', 'fasta dedup', 'sequence dedup']
    RETURN_TYPES = ('CSV', 'CSV')
    RETURN_NAMES = ('deduplicated', 'duplicates')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table': ('FILE', {'description': 'CSV or TSV table with a header row'}), 'subset_columns': ('STRING', {'default': '', 'description': 'Comma-separated duplicate key columns'})}, 'optional': {'keep': ('STRING', {'default': 'first', 'options': ['first', 'last', 'none']}), 'report_dups': ('BOOLEAN', {'default': False}), 'sort_before': ('BOOLEAN', {'default': False}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop('context', None)
        input_path = Path(str(kwargs['table']))
        keep = str(kwargs.get('keep', 'first') or 'first').lower()
        if keep not in {'first', 'last', 'none'}:
            raise ValueError(f'Unsupported keep strategy: {keep}')
        if self._is_fasta(input_path):
            return self._deduplicate_fasta(input_path, keep, bool(kwargs.get('report_dups', False)), context)
        input_delim = _delimiter(str(kwargs.get('delimiter', 'auto')), input_path)
        fieldnames, rows = _read_table(input_path, input_delim)
        subset_columns = _split_csv(str(kwargs.get('subset_columns', '')))
        key_columns = subset_columns or list(fieldnames)
        missing = [name for name in key_columns if name not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")
        working_rows = list(rows)
        if bool(kwargs.get('sort_before', False)):
            working_rows.sort(key=lambda row: tuple((row.get(name, '') for name in fieldnames)))
        deduplicated, duplicates = self._deduplicate_rows(working_rows, key_columns, keep)
        output_delim, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), input_path)
        output_dir = _node_output_dir(self, context)
        deduplicated_path = output_dir / f'{input_path.stem}.deduplicated{extension}'
        duplicates_path = output_dir / f'{input_path.stem}.duplicates{extension}'
        _write_table(deduplicated_path, fieldnames, deduplicated, output_delim)
        if bool(kwargs.get('report_dups', False)):
            _write_table(duplicates_path, fieldnames, duplicates, output_delim)
        else:
            duplicates_path = deduplicated_path
        return (str(deduplicated_path), str(duplicates_path))

    @staticmethod
    def _row_key(row: dict[str, str], key_columns: list[str]) -> tuple[str, ...]:
        return tuple((row.get(column, '') for column in key_columns))

    @classmethod
    def _deduplicate_rows(cls, rows: list[dict[str, str]], key_columns: list[str], keep: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        if keep == 'none':
            counts: OrderedDict[tuple[str, ...], int] = OrderedDict()
            for row in rows:
                key = cls._row_key(row, key_columns)
                counts[key] = counts.get(key, 0) + 1
            return ([row for row in rows if counts[cls._row_key(row, key_columns)] == 1], [row for row in rows if counts[cls._row_key(row, key_columns)] > 1])
        keep_indexes: set[int] = set()
        duplicate_indexes: set[int] = set()
        seen: dict[tuple[str, ...], int] = {}
        row_range = range(len(rows)) if keep == 'first' else range(len(rows) - 1, -1, -1)
        for index in row_range:
            key = cls._row_key(rows[index], key_columns)
            if key in seen:
                duplicate_indexes.add(index)
            else:
                seen[key] = index
                keep_indexes.add(index)
        return ([row for index, row in enumerate(rows) if index in keep_indexes], [row for index, row in enumerate(rows) if index in duplicate_indexes])

    @classmethod
    def _deduplicate_fasta(cls, input_path: Path, keep: str, report_dups: bool, context: Any) -> tuple[str, str]:
        records = cls._read_fasta(input_path)
        kept, duplicates = cls._deduplicate_fasta_records(records, keep)
        base = Path(getattr(context, 'node_dir', '.') if context else '.')
        output_dir = base / cls.NODE_ID
        output_dir.mkdir(parents=True, exist_ok=True)
        deduplicated_path = output_dir / f'{input_path.stem}.deduplicated.fasta'
        duplicates_path = output_dir / f'{input_path.stem}.duplicates.fasta'
        cls._write_fasta(deduplicated_path, kept)
        if report_dups:
            cls._write_fasta(duplicates_path, duplicates)
        else:
            duplicates_path = deduplicated_path
        return (str(deduplicated_path), str(duplicates_path))

    @staticmethod
    def _is_fasta(path: Path) -> bool:
        return ''.join(path.suffixes).lower() in {'.fa', '.fna', '.faa', '.fasta'}

    @staticmethod
    def _read_fasta(path: Path) -> list[tuple[str, str]]:
        records: list[tuple[str, str]] = []
        header = ''
        seq_parts: list[str] = []
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('>'):
                if header:
                    records.append((header, ''.join(seq_parts).upper()))
                header = line
                seq_parts = []
            else:
                seq_parts.append(line)
        if header:
            records.append((header, ''.join(seq_parts).upper()))
        if not records:
            raise ValueError(f'FASTA file has no records: {path}')
        return records

    @classmethod
    def _deduplicate_fasta_records(cls, records: list[tuple[str, str]], keep: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        if keep == 'none':
            counts: OrderedDict[str, int] = OrderedDict()
            for _header, sequence in records:
                counts[sequence] = counts.get(sequence, 0) + 1
            return ([record for record in records if counts[record[1]] == 1], [record for record in records if counts[record[1]] > 1])
        kept_indexes: set[int] = set()
        duplicate_indexes: set[int] = set()
        seen: set[str] = set()
        row_range = range(len(records)) if keep == 'first' else range(len(records) - 1, -1, -1)
        for index in row_range:
            sequence = records[index][1]
            if sequence in seen:
                duplicate_indexes.add(index)
            else:
                seen.add(sequence)
                kept_indexes.add(index)
        return ([record for index, record in enumerate(records) if index in kept_indexes], [record for index, record in enumerate(records) if index in duplicate_indexes])

    @staticmethod
    def _write_fasta(path: Path, records: list[tuple[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as fh:
            for header, sequence in records:
                fh.write(f'{header}\n')
                for line in _wrap_sequence(sequence, 60):
                    fh.write(f'{line}\n')

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
