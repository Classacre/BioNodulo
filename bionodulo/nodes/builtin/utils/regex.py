"""regex — utils node(s). One tool per file (extracted from utility_collections.py)."""
from __future__ import annotations
import json
import random
import re
import string
from typing import Any
from bionodulo.nodes.base import BaseNode
def _decode_delimiter(delimiter: Any, default: str='\n') -> str:
    text = str(delimiter if delimiter is not None else default)
    return {'\\n': '\n', '\\t': '\t', '\\r': '\r'}.get(text, text)
def _parse_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value if value is not None else '').strip()
    if not text:
        return []
    if text[0] in '[{':
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'items must be valid JSON or comma/newline text: {exc.msg}') from exc
        if not isinstance(parsed, list):
            raise ValueError('items JSON must be a list')
        return [str(item) for item in parsed]
    separator = '\n' if '\n' in text else ','
    return [item.strip() for item in text.split(separator) if item.strip()]
def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
def _parse_json_object(value: Any, field_name: str='dictionary') -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = str(value if value is not None else '').strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{field_name} must be valid JSON object: {exc.msg}') from exc
    if not isinstance(parsed, dict):
        raise ValueError(f'{field_name} must be a JSON object')
    return dict(parsed)
def _parse_json_value(value: Any, field_name: str) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f'{field_name} must be valid JSON')
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'{field_name} must be valid JSON: {exc.msg}') from exc
    return value
def _sort_key(item: str) -> tuple[int, float | str]:
    try:
        return (0, float(item))
    except ValueError:
        return (1, item)
def _flatten_value(value: Any, max_depth: int, depth: int=0) -> list[Any]:
    should_descend = max_depth < 0 or depth <= max_depth
    if isinstance(value, list) and should_descend:
        result: list[Any] = []
        for item in value:
            result.extend(_flatten_value(item, max_depth=max_depth, depth=depth + 1))
        return result
    if isinstance(value, dict) and should_descend:
        result = []
        for item in value.values():
            result.extend(_flatten_value(item, max_depth=max_depth, depth=depth + 1))
        return result
    return [value]
def _json_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return _to_json(value)


class RegexExtractNode(BaseNode):
    """Extract regex matches from text."""
    NODE_ID = 'regex_extract'
    DISPLAY_NAME = 'Regex Extract'
    CATEGORY = 'utils'
    DESCRIPTION = 'Extract text using regular expressions with capture group selection'
    SEARCH_ALIASES = ['regex', 'extract', 'capture', 'pattern', 'match', 'text parse']
    RETURN_TYPES = ('STRING', 'INT')
    RETURN_NAMES = ('matches_json', 'count')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'text': ('STRING', {'default': '', 'multiline': True, 'description': 'Text to search'}), 'pattern': ('STRING', {'default': '', 'description': 'Regular expression pattern'})}, 'optional': {'group': ('INT', {'default': 0, 'min': 0, 'description': 'Capture group to return; 0 returns full match'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, int]:
        text = str(kwargs.get('text', ''))
        pattern = str(kwargs.get('pattern', '') or '')
        if not pattern:
            raise ValueError('pattern is required')
        group = int(kwargs.get('group', 0))
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f'Invalid regex pattern: {exc}') from exc
        matches: list[str] = []
        for match in compiled.finditer(text):
            if group > len(match.groups()):
                raise ValueError(f'group {group} is out of range for {len(match.groups())} capture groups')
            matches.append(match.group(group))
        return (_to_json(matches), len(matches))
