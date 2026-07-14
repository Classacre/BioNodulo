"""if — flow_control node(s). One tool per file (extracted from flow_control.py)."""
from __future__ import annotations
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
APIHttpClient: type[Any] | None = None
def _api_http_client_class() -> type[Any]:
    global APIHttpClient
    if APIHttpClient is None:
        from bionodulo.nodes.builtin.api.http import APIHttpClient as imported_client
        APIHttpClient = imported_client
    return APIHttpClient
def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {'', '0', 'false', 'f', 'no', 'n', 'off', 'none', 'null'}:
        return False
    return True
def _as_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(str(value).strip())
def _split_cases(value: str) -> list[str]:
    normalised = str(value or '').replace('\n', ',')
    return [item.strip() for item in normalised.split(',') if item.strip()]
def _coerce_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith('['):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
        path = Path(text)
        if path.exists() and path.is_file():
            return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        if '\n' in text or ',' in text:
            return [item.strip() for item in text.replace('\n', ',').split(',') if item.strip()]
        return [text]
    return [value]
def _split_error_types(value: Any) -> set[str]:
    return {item.strip().lower() for item in str(value or '').replace('\n', ',').split(',') if item.strip()}
def _error_type(error: Any) -> str:
    text = str(error or '').strip()
    if ':' in text:
        prefix = text.split(':', 1)[0].strip().lower()
        if prefix:
            return prefix
    lowered = text.lower()
    for candidate in ('validation', 'tool_error', 'timeout', 'oom', 'runtime'):
        if candidate in lowered:
            return candidate
    return 'runtime'
def _is_catchable(error: Any, catch_errors: Any) -> bool:
    allowed = _split_error_types(catch_errors)
    return not allowed or _error_type(error) in allowed


class IfConditionNode(BaseNode):
    """Route a value to a true or false output based on a condition."""
    NODE_ID = 'if_condition'
    DISPLAY_NAME = 'If Condition'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Route data down true or false branches using boolean, numeric, string, regex, or file checks.'
    SEARCH_ALIASES = ['if', 'condition', 'branch', 'route', 'gate', 'boolean']
    RETURN_TYPES = ('ANY', 'ANY', 'BOOLEAN')
    RETURN_NAMES = ('true', 'false', 'condition_result')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('ANY', {'description': 'Value to evaluate and route'}), 'condition_mode': (['boolean', 'numeric_equal', 'numeric_greater', 'numeric_less', 'numeric_greater_equal', 'numeric_less_equal', 'numeric_not_equal', 'string_equal', 'string_not_equal', 'string_contains', 'string_not_contains', 'string_startswith', 'string_endswith', 'regex_match', 'file_exists', 'is_empty', 'not_empty'], {'default': 'boolean', 'description': 'Condition evaluation mode'}), 'compare_to': ('STRING', {'default': '', 'description': 'Comparison value'})}, 'optional': {'invert': ('BOOLEAN', {'default': False}), 'case_sensitive': ('BOOLEAN', {'default': True}), 'combinator': ('STRING', {'default': 'and', 'options': ['and', 'or']}), 'condition_mode_2': (['none', 'boolean', 'numeric_equal', 'numeric_greater', 'numeric_less', 'numeric_greater_equal', 'numeric_less_equal', 'numeric_not_equal', 'string_equal', 'string_not_equal', 'string_contains', 'string_not_contains', 'string_startswith', 'string_endswith', 'regex_match', 'file_exists', 'is_empty', 'not_empty'], {'default': 'none', 'description': 'Optional second condition evaluation mode'}), 'compare_to_2': ('STRING', {'default': '', 'description': 'Comparison value for the second condition'}), 'output_mode': ('STRING', {'default': 'route', 'options': ['route', 'signal']})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        value = kwargs.get('value')
        mode = str(kwargs.get('condition_mode', 'boolean'))
        compare_to = kwargs.get('compare_to', '')
        case_sensitive = bool(kwargs.get('case_sensitive', True))
        invert = bool(kwargs.get('invert', False))
        combinator = str(kwargs.get('combinator', 'and') or 'and').lower()
        mode_2 = str(kwargs.get('condition_mode_2', 'none') or 'none')
        compare_to_2 = kwargs.get('compare_to_2', '')
        output_mode = str(kwargs.get('output_mode', 'route') or 'route').lower()
        condition_result = self._evaluate(value, mode, compare_to, case_sensitive)
        if mode_2 != 'none':
            condition_result_2 = self._evaluate(value, mode_2, compare_to_2, case_sensitive)
            if combinator == 'or':
                condition_result = condition_result or condition_result_2
            elif combinator == 'and':
                condition_result = condition_result and condition_result_2
            else:
                raise ValueError(f'Unsupported if_condition combinator: {combinator}')
        if invert:
            condition_result = not condition_result
        if output_mode not in {'route', 'signal'}:
            raise ValueError(f'Unsupported if_condition output_mode: {output_mode}')
        inactive = ['false'] if condition_result else ['true']
        if output_mode == 'signal':
            true_output = condition_result
            false_output = not condition_result
        else:
            true_output = value if condition_result else None
            false_output = value if not condition_result else None
        return {'outputs': {'true': true_output, 'false': false_output, 'condition_result': condition_result}, 'inactive_outputs': inactive}

    @staticmethod
    def _evaluate(value: Any, mode: str, compare_to: Any, case_sensitive: bool) -> bool:
        if mode == 'boolean':
            return _bool_value(value)
        if mode == 'file_exists':
            return bool(value) and Path(str(value)).exists()
        if mode == 'is_empty':
            if value is None:
                return True
            if isinstance(value, (list, tuple, dict, set)):
                return len(value) == 0
            return str(value).strip() == ''
        if mode == 'not_empty':
            if value is None:
                return False
            if isinstance(value, (list, tuple, dict, set)):
                return len(value) > 0
            return str(value).strip() != ''
        if mode.startswith('numeric_'):
            try:
                left = _as_float(value)
                right = _as_float(compare_to)
            except ValueError:
                return False
            if mode == 'numeric_equal':
                return left == right
            if mode == 'numeric_greater':
                return left > right
            if mode == 'numeric_less':
                return left < right
            if mode == 'numeric_greater_equal':
                return left >= right
            if mode == 'numeric_less_equal':
                return left <= right
            if mode == 'numeric_not_equal':
                return left != right
            return False
        left_text = str(value)
        right_text = str(compare_to)
        flags = 0
        if not case_sensitive:
            left_text = left_text.lower()
            right_text = right_text.lower()
            flags = re.IGNORECASE
        if mode == 'string_equal':
            return left_text == right_text
        if mode == 'string_not_equal':
            return left_text != right_text
        if mode == 'string_contains':
            return right_text in left_text
        if mode == 'string_not_contains':
            return right_text not in left_text
        if mode == 'string_startswith':
            return left_text.startswith(right_text)
        if mode == 'string_endswith':
            return left_text.endswith(right_text)
        if mode == 'regex_match':
            return re.search(str(compare_to), str(value), flags=flags) is not None
        return False
