"""type — utils/dev node(s). One tool per file (extracted from utility_dev.py)."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {'', '0', 'false', 'f', 'no', 'n', 'off', 'none', 'null'}:
        return False
    return True


class TypeCastNode(BaseNode):
    """Convert between primitive types and simple file content."""
    NODE_ID = 'type_cast'
    DISPLAY_NAME = 'Type Cast'
    CATEGORY = 'utils/dev'
    DESCRIPTION = 'Convert between types: STRING, INT, FLOAT, BOOLEAN, FILE'
    SEARCH_ALIASES = ['cast', 'convert', 'type', 'to_string', 'to_int', 'to_float', 'to_bool']
    RETURN_TYPES = ('STRING', 'INT', 'FLOAT', 'BOOLEAN', 'FILE')
    RETURN_NAMES = ('as_string', 'as_int', 'as_float', 'as_bool', 'as_file')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'target_type': (['STRING', 'INT', 'FLOAT', 'BOOLEAN', 'FILE_CONTENT', 'FILE_FROM_STRING'], {'default': 'STRING', 'description': 'Target type to convert to'}), 'value': ('STRING', {'default': '', 'multiline': True, 'description': 'Value to convert'})}, 'optional': {'default_on_error': ('STRING', {'default': '', 'description': 'Default if conversion fails'}), 'encoding': ('STRING', {'default': 'utf-8', 'description': 'File encoding'}), 'output_name': ('STRING', {'default': 'type_cast.txt', 'description': 'Filename for FILE_FROM_STRING'})}, 'hidden': {'context': ('ANY', {})}}

    async def run(self, **kwargs: Any) -> tuple[str, int, float, bool, str]:
        context = kwargs.get('context')
        target_type = str(kwargs.get('target_type', 'STRING') or 'STRING')
        value = kwargs.get('value', '')
        default = kwargs.get('default_on_error', '')
        encoding = str(kwargs.get('encoding', 'utf-8') or 'utf-8')
        as_string = '' if value is None else str(value)
        as_int = self._as_int(value, default)
        as_float = self._as_float(value, default)
        as_bool = _to_bool(value)
        as_file = ''
        if target_type == 'STRING':
            pass
        elif target_type == 'INT':
            as_string = str(as_int)
            as_float = float(as_int)
            as_bool = as_int != 0
        elif target_type == 'FLOAT':
            as_string = str(as_float)
            as_int = int(as_float)
            as_bool = as_float != 0.0
        elif target_type == 'BOOLEAN':
            as_string = 'true' if as_bool else 'false'
            as_int = 1 if as_bool else 0
            as_float = float(as_int)
        elif target_type == 'FILE_CONTENT':
            file_path = Path(str(value))
            if not file_path.exists():
                raise FileNotFoundError(f'File not found: {file_path}')
            as_string = file_path.read_text(encoding=encoding)
            as_int = self._as_int(as_string, default)
            as_float = self._as_float(as_string, default)
            as_bool = _to_bool(as_string)
            as_file = str(file_path)
        elif target_type == 'FILE_FROM_STRING':
            filename = Path(str(kwargs.get('output_name', 'type_cast.txt') or 'type_cast.txt')).name
            output_path = _node_output_dir(self, context) / filename
            output_path.write_text(as_string, encoding=encoding)
            as_file = str(output_path)
        else:
            raise ValueError(f'Unsupported target_type: {target_type}')
        return (as_string, as_int, as_float, as_bool, as_file)

    @staticmethod
    def _as_int(value: Any, default: Any='') -> int:
        try:
            if isinstance(value, bool):
                return 1 if value else 0
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return int(float(default)) if str(default).strip() else 0

    @staticmethod
    def _as_float(value: Any, default: Any='') -> float:
        try:
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return float(str(value).strip())
        except (TypeError, ValueError):
            return float(default) if str(default).strip() else 0.0
