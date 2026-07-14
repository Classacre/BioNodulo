"""reshape — pivot_table node(s). One tool per file (extracted from pivot_table.py)."""
from __future__ import annotations
import csv
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class ReshapeTableNode(PivotTableNode):
    """Proposal-compatible table reshape node with wide/long terminology."""
    NODE_ID = 'reshape_table'
    DISPLAY_NAME = 'Reshape Table'
    DESCRIPTION = 'Convert tables between wide and long formats using melt and pivot operations.'
    SEARCH_ALIASES = ['reshape', 'melt', 'pivot_longer', 'pivot_wider', 'wide', 'long', 'table', 'csv', 'tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'table': ('FILE', {'description': 'CSV or TSV table with a header row'}), 'direction': ('STRING', {'default': 'long', 'options': ['long', 'wide']}), 'id_vars': ('STRING', {'description': 'Comma-separated columns to preserve as identifiers'})}, 'optional': {'value_vars': ('STRING', {'default': '', 'description': 'Columns to gather when reshaping long'}), 'names_to': ('STRING', {'default': 'variable', 'description': 'Name of the long-format variable column'}), 'values_to': ('STRING', {'default': 'value', 'description': 'Name of the long-format value column'}), 'names_from': ('STRING', {'default': '', 'description': 'Column whose values become wide headers'}), 'values_from': ('STRING', {'default': '', 'description': 'Column whose values fill wide cells'}), 'fill_value': ('STRING', {'default': ''}), 'delimiter': ('STRING', {'default': 'auto', 'options': ['auto', 'tsv', 'csv']}), 'output_type': ('STRING', {'default': 'AUTO', 'options': ['AUTO', 'CSV', 'TSV']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        input_path = Path(str(kwargs['table']))
        input_delimiter = self._delimiter(str(kwargs.get('delimiter', 'auto')), input_path)
        fieldnames, rows = self._read_table(input_path, input_delimiter)
        direction = str(kwargs.get('direction', 'long') or 'long').lower()
        if direction == 'long':
            suffix = 'long'
            out_fields, out_rows = self._melt_long(fieldnames, rows, str(kwargs.get('id_vars', '') or ''), str(kwargs.get('value_vars', '') or ''), str(kwargs.get('names_to', 'variable') or 'variable'), str(kwargs.get('values_to', 'value') or 'value'))
        elif direction == 'wide':
            suffix = 'wide'
            out_fields, out_rows = self._pivot_wide(fieldnames, rows, str(kwargs.get('id_vars', '') or ''), str(kwargs.get('names_from', '') or ''), str(kwargs.get('values_from', '') or ''), str(kwargs.get('fill_value', '') or ''), aggregate=False)
        else:
            raise ValueError(f'Unsupported reshape direction: {direction}')
        output_delimiter, extension = self._output_format(str(kwargs.get('output_type', 'AUTO') or 'AUTO'), input_path)
        out_path = self._output_dir(context) / f'{input_path.stem}.{suffix}{extension}'
        self._write_table(out_path, out_fields, out_rows, output_delimiter)
        return (str(out_path),)
