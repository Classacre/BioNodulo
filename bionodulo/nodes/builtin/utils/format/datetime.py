"""datetime — utils/format node(s). One tool per file (extracted from utility_dev.py)."""
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


class DateTimeNode(BaseNode):
    """Get current date/time, format timestamps, and add/subtract days."""
    NODE_ID = 'datetime'
    DISPLAY_NAME = 'Date / Time'
    CATEGORY = 'utils/format'
    DESCRIPTION = 'Get current date/time, format timestamps, add/subtract intervals'
    SEARCH_ALIASES = ['datetime', 'date', 'time', 'timestamp', 'now', 'format date', 'clock']
    RETURN_TYPES = ('STRING', 'INT', 'STRING')
    RETURN_NAMES = ('formatted', 'timestamp', 'iso')
    REQUIRES_EXTERNAL_TOOLS = False
    _PARSE_FORMATS = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d', '%Y%m%d%H%M%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f', '%a %b %d %H:%M:%S %Y']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        operations = ['now', 'format', 'parse', 'add_days', 'subtract_days', 'timestamp', 'iso']
        return {'required': {'operation': (operations, {'default': 'now', 'description': 'Date/time operation'})}, 'optional': {'format_string': ('STRING', {'default': '%Y-%m-%d %H:%M:%S', 'description': 'strftime format pattern'}), 'date_string': ('STRING', {'default': '', 'description': 'Date string to parse'}), 'days': ('INT', {'default': 0, 'description': 'Number of days'}), 'timezone': ('STRING', {'default': 'local', 'description': 'Timezone: local or UTC'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, int, str]:
        operation = str(kwargs.get('operation', 'now') or 'now')
        format_string = str(kwargs.get('format_string', '%Y-%m-%d %H:%M:%S') or '%Y-%m-%d %H:%M:%S')
        days = int(kwargs.get('days', 0) or 0)
        tz = timezone.utc if str(kwargs.get('timezone', 'local')).lower() == 'utc' else None
        now = datetime.now(tz)
        if operation == 'now':
            return self._render(now, format_string)
        if operation == 'format':
            date_string = str(kwargs.get('date_string', '') or '')
            if date_string.strip():
                parsed = self._parse_date(date_string)
                if tz is not None and parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=tz)
                return self._render(parsed, format_string)
            return self._render(now, format_string)
        if operation == 'timestamp':
            return (str(int(now.timestamp())), int(now.timestamp()), now.isoformat())
        if operation == 'iso':
            return (now.isoformat(), int(now.timestamp()), now.isoformat())
        if operation == 'add_days':
            return self._render(now + timedelta(days=days), format_string)
        if operation == 'subtract_days':
            return self._render(now - timedelta(days=days), format_string)
        if operation == 'parse':
            parsed = self._parse_date(str(kwargs.get('date_string', '') or ''))
            if tz is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
            return self._render(parsed, format_string)
        raise ValueError(f'Unsupported datetime operation: {operation}')

    @classmethod
    def _parse_date(cls, value: str) -> datetime:
        if not value.strip():
            raise ValueError('date_string is required for parse operation')
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            pass
        for fmt in cls._PARSE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f'Could not parse date string: {value}')

    @staticmethod
    def _render(value: datetime, format_string: str) -> tuple[str, int, str]:
        return (value.strftime(format_string), int(value.timestamp()), value.isoformat())
