"""debug — utils/dev node(s). One tool per file (extracted from utility_dev.py)."""
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


class DebugNode(BaseNode):
    """Print any value to console for debugging while passing it through."""
    NODE_ID = 'debug'
    DISPLAY_NAME = 'Debug'
    CATEGORY = 'utils/dev'
    DESCRIPTION = 'Print any value to console for debugging - passes value through unchanged'
    SEARCH_ALIASES = ['debug', 'print', 'log', 'inspect', 'trace', 'console', 'echo']
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('value',)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    _logger = logging.getLogger('bionodulo.debug')

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('STRING', {'default': '', 'multiline': True, 'description': 'Value to debug'})}, 'optional': {'label': ('STRING', {'default': '', 'description': 'Label for the debug output'}), 'log_level': (['info', 'warn', 'error', 'debug'], {'default': 'info', 'description': 'Log level'}), 'show_type': ('BOOLEAN', {'default': True, 'description': "Show the value's type"})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        value = kwargs.get('value', '')
        label = str(kwargs.get('label', '') or '')
        log_level = str(kwargs.get('log_level', 'info') or 'info')
        show_type = bool(kwargs.get('show_type', True))
        formatted = self._format_value(value)
        prefix = f'[{label}]' if label else '[DEBUG]'
        type_info = f' (type: {type(value).__name__})' if show_type else ''
        message = f'{prefix}{type_info}\n{formatted}'
        log_method = getattr(self._logger, 'warning' if log_level == 'warn' else log_level, self._logger.info)
        log_method(message)
        print(message)
        return (formatted,)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, ensure_ascii=True, default=str)
        return str(value)
