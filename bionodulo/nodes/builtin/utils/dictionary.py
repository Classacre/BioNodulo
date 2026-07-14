"""dictionary — utils node(s). One tool per file (extracted from utility_collections.py)."""
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


class DictionaryNode(BaseNode):
    """JSON object dictionary operations."""
    NODE_ID = 'dictionary'
    DISPLAY_NAME = 'Dictionary'
    CATEGORY = 'utils'
    DESCRIPTION = 'JSON object operations: get, set, keys, values, merge, remove, has_key'
    SEARCH_ALIASES = ['dict', 'map', 'dictionary', 'key-value', 'json', 'object', 'properties']
    RETURN_TYPES = ('STRING', 'STRING', 'INT')
    RETURN_NAMES = ('result_json', 'value', 'count')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'operation': (['get', 'set', 'keys', 'values', 'merge', 'remove', 'has_key'], {'default': 'get', 'description': 'Dictionary operation'}), 'dictionary': ('STRING', {'default': '{}', 'multiline': True, 'description': 'Dictionary as JSON object'})}, 'optional': {'key': ('STRING', {'default': '', 'description': 'Key'}), 'value': ('STRING', {'default': '', 'description': 'Value for set'}), 'dictionary_b': ('STRING', {'default': '{}', 'multiline': True, 'description': 'Second JSON object for merge'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, str, int]:
        operation = str(kwargs.get('operation', 'get'))
        data = _parse_json_object(kwargs.get('dictionary', '{}'))
        key = str(kwargs.get('key', ''))
        result_json = _to_json(data)
        if operation == 'get':
            return (result_json, _json_value(data.get(key, '')), len(data))
        if operation == 'set':
            data[key] = str(kwargs.get('value', ''))
            return (_to_json(data), _json_value(data[key]), len(data))
        if operation == 'keys':
            return (result_json, _to_json(list(data.keys())), len(data))
        if operation == 'values':
            return (result_json, _to_json(list(data.values())), len(data))
        if operation == 'merge':
            data.update(_parse_json_object(kwargs.get('dictionary_b', '{}'), field_name='dictionary_b'))
            return (_to_json(data), '', len(data))
        if operation == 'remove':
            data.pop(key, None)
            return (_to_json(data), '', len(data))
        if operation == 'has_key':
            return (result_json, 'true' if key in data else 'false', len(data))
        raise ValueError(f'Unsupported dictionary operation: {operation}')
