"""string — utils node(s). One tool per file (extracted from utility_collections.py)."""
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


class StringOperationsNode(BaseNode):
    """Multi-mode string manipulation node."""
    NODE_ID = 'string_operations'
    DISPLAY_NAME = 'String Operations'
    CATEGORY = 'utils'
    DESCRIPTION = 'String manipulation: concat, replace, trim, case conversion, regex, split, length, contains'
    SEARCH_ALIASES = ['string', 'text', 'concat', 'concatenate', 'uppercase', 'lowercase', 'regex', 'replace', 'trim', 'split', 'length', 'contains', 'startswith', 'endswith']
    RETURN_TYPES = ('STRING', 'INT', 'BOOLEAN')
    RETURN_NAMES = ('result', 'length', 'matched')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        operations = ['concat', 'concatenate', 'upper', 'uppercase', 'lower', 'lowercase', 'regex_replace', 'regex_match', 'split', 'replace', 'trim', 'length', 'substring', 'contains', 'startswith', 'endswith']
        return {'required': {'operation': (operations, {'default': 'concat', 'description': 'String operation'}), 'string': ('STRING', {'default': '', 'multiline': True, 'description': 'Primary string'})}, 'optional': {'string_b': ('STRING', {'default': '', 'description': 'Secondary string'}), 'delimiter': ('STRING', {'default': '', 'description': 'Delimiter for concat or split'}), 'old': ('STRING', {'default': '', 'description': 'Text to replace'}), 'new': ('STRING', {'default': '', 'description': 'Replacement text'}), 'start': ('INT', {'default': 0, 'description': 'Start index for substring'}), 'end': ('INT', {'default': -1, 'description': 'End index for substring; -1 means end'}), 'pattern': ('STRING', {'default': '', 'description': 'Regex pattern'}), 'replacement': ('STRING', {'default': '', 'description': 'Regex replacement'}), 'index': ('INT', {'default': 0, 'description': 'Split item index'}), 'group': ('INT', {'default': 0, 'min': 0, 'description': 'Regex match capture group'}), 'count': ('INT', {'default': -1, 'description': 'Maximum replacements; -1 replaces all'}), 'substring': ('STRING', {'default': '', 'description': 'Substring to search for'}), 'prefix': ('STRING', {'default': '', 'description': 'Prefix to test for startswith'}), 'suffix': ('STRING', {'default': '', 'description': 'Suffix to test for endswith'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, int, bool]:
        operation = str(kwargs.get('operation', 'concat'))
        text = str(kwargs.get('string', ''))
        if operation in {'concat', 'concatenate'}:
            delimiter = _decode_delimiter(kwargs.get('delimiter', ''), default='')
            result = f"{text}{delimiter}{kwargs.get('string_b', '')}"
            return (result, len(result), False)
        if operation in {'upper', 'uppercase'}:
            result = text.upper()
            return (result, len(result), False)
        if operation in {'lower', 'lowercase'}:
            result = text.lower()
            return (result, len(result), False)
        if operation == 'regex_replace':
            pattern = str(kwargs.get('pattern', ''))
            if not pattern:
                raise ValueError('regex_replace requires a non-empty pattern')
            try:
                result, count = re.subn(pattern, str(kwargs.get('replacement', '')), text)
            except re.error as exc:
                raise ValueError(f'Invalid regex pattern: {exc}') from exc
            return (result, len(result), count > 0)
        if operation == 'regex_match':
            pattern = str(kwargs.get('pattern', ''))
            if not pattern:
                raise ValueError('regex_match requires a non-empty pattern')
            group = int(kwargs.get('group', 0))
            try:
                match = re.search(pattern, text)
            except re.error as exc:
                raise ValueError(f'Invalid regex pattern: {exc}') from exc
            if match is None:
                return ('', 0, False)
            if group > len(match.groups()):
                raise ValueError(f'group {group} is out of range for {len(match.groups())} capture groups')
            return (match.group(group), len(match.groups()), True)
        if operation == 'split':
            delimiter = _decode_delimiter(kwargs.get('delimiter', ','))
            if delimiter == '':
                raise ValueError('split requires a non-empty delimiter')
            parts = text.split(delimiter)
            index = int(kwargs.get('index', 0))
            if not -len(parts) <= index < len(parts):
                raise ValueError(f'split index {index} is out of range for {len(parts)} items')
            return (parts[index], len(parts), True)
        if operation == 'replace':
            old = str(kwargs.get('old', ''))
            if old == '':
                raise ValueError('replace requires non-empty old text')
            new = str(kwargs.get('new', ''))
            count = int(kwargs.get('count', -1))
            result = text.replace(old, new, count if count >= 0 else -1)
            return (result, len(result), False)
        if operation == 'trim':
            result = text.strip()
            return (result, len(result), False)
        if operation == 'length':
            return (text, len(text), False)
        if operation == 'substring':
            start = int(kwargs.get('start', 0))
            end = int(kwargs.get('end', -1))
            result = text[start:] if end < 0 else text[start:end]
            return (result, len(result), False)
        if operation == 'contains':
            substring = str(kwargs.get('substring', kwargs.get('string_b', '')))
            return ('', 0, substring in text)
        if operation == 'startswith':
            prefix = str(kwargs.get('prefix', kwargs.get('string_b', '')))
            return ('', 0, text.startswith(prefix))
        if operation == 'endswith':
            suffix = str(kwargs.get('suffix', kwargs.get('string_b', '')))
            return ('', 0, text.endswith(suffix))
        raise ValueError(f'Unsupported string operation: {operation}')
