"""switch — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class SwitchNode(BaseNode):
    """Route a value to one of several case outputs or a default output."""
    NODE_ID = 'switch'
    DISPLAY_NAME = 'Switch'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Route data to one of several outputs by matching a value against comma-separated cases.'
    SEARCH_ALIASES = ['switch', 'case', 'route', 'branch', 'match']
    RETURN_TYPES = ('ANY', 'ANY', 'ANY', 'ANY', 'ANY')
    RETURN_NAMES = ('output_1', 'output_2', 'output_3', 'output_4', 'default')
    DEFAULT_NUM_BRANCHES = 4
    MIN_NUM_BRANCHES = 1
    MAX_NUM_BRANCHES = 32
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('ANY', {'description': 'Value to match against cases'}), 'cases': ('STRING', {'default': '', 'multiline': True, 'description': 'Comma- or newline-separated case values; map in order to output_1..output_N'})}, 'optional': {'passthrough_data': ('ANY', {'description': 'Data to emit on the matched output; defaults to value'}), 'num_branches': ('INT', {'default': cls.DEFAULT_NUM_BRANCHES, 'min': cls.MIN_NUM_BRANCHES, 'max': cls.MAX_NUM_BRANCHES, 'dynamic_outputs': {'prefix': 'output_', 'count_input': 'num_branches', 'default_output': 'default', 'type': 'ANY'}}), 'case_sensitive': ('BOOLEAN', {'default': True}), 'rules': ('STRING', {'default': '[]', 'multiline': True, 'description': 'Optional JSON rules with branch_index, match_type, and pattern/min/max fields'}), 'fallback': ('STRING', {'default': 'last', 'options': ['drop', 'last', 'error']}), 'match_mode': ('STRING', {'default': 'first', 'options': ['first', 'all']}), 'auto_numeric': ('BOOLEAN', {'default': True})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        value = kwargs.get('value')
        passthrough = kwargs.get('passthrough_data', value)
        case_sensitive = bool(kwargs.get('case_sensitive', True))
        rules = self._parse_rules(kwargs.get('rules', '[]'))
        return_names = self._return_names_for(kwargs.get('num_branches', self.DEFAULT_NUM_BRANCHES))
        if rules:
            selected_names = self._selected_rule_outputs(value=value, rules=rules, case_sensitive=case_sensitive, match_mode=str(kwargs.get('match_mode', 'first') or 'first'), fallback=str(kwargs.get('fallback', 'last') or 'last'), return_names=return_names)
            outputs = {name: None for name in return_names}
            for name in selected_names:
                outputs[name] = passthrough
            return {'outputs': outputs, 'inactive_outputs': [name for name in return_names if name not in selected_names]}
        branch_names = return_names[:-1]
        cases = _split_cases(str(kwargs.get('cases', '')))[:len(branch_names)]
        matched_index: int | None = None
        value_text = str(value)
        value_cmp = value_text if case_sensitive else value_text.lower()
        for idx, case in enumerate(cases):
            case_cmp = case if case_sensitive else case.lower()
            if value_cmp == case_cmp:
                matched_index = idx
                break
        selected_name = 'default' if matched_index is None else branch_names[matched_index]
        outputs = {name: None for name in return_names}
        outputs[selected_name] = passthrough
        return {'outputs': outputs, 'inactive_outputs': [name for name in return_names if name != selected_name]}

    @classmethod
    def _return_names_for(cls, num_branches: Any) -> tuple[str, ...]:
        branch_count = int(num_branches)
        if not cls.MIN_NUM_BRANCHES <= branch_count <= cls.MAX_NUM_BRANCHES:
            raise ValueError(f'Switch num_branches must be between {cls.MIN_NUM_BRANCHES} and {cls.MAX_NUM_BRANCHES}')
        return tuple((f'output_{index}' for index in range(1, branch_count + 1))) + ('default',)

    @staticmethod
    def _parse_rules(raw_rules: Any) -> list[dict[str, Any]]:
        if raw_rules in (None, ''):
            return []
        if isinstance(raw_rules, str):
            try:
                parsed = json.loads(raw_rules)
            except json.JSONDecodeError as exc:
                raise ValueError(f'Switch rules must be valid JSON: {exc}') from exc
        else:
            parsed = raw_rules
        if not isinstance(parsed, list):
            raise ValueError('Switch rules must be a JSON array')
        if not all((isinstance(rule, dict) for rule in parsed)):
            raise ValueError('Switch rules must contain JSON objects')
        return [dict(rule) for rule in parsed]

    @classmethod
    def _selected_rule_outputs(cls, *, value: Any, rules: list[dict[str, Any]], case_sensitive: bool, match_mode: str, fallback: str, return_names: tuple[str, ...] | None=None) -> list[str]:
        return_names = return_names or cls.RETURN_NAMES
        branch_names = return_names[:-1]
        match_mode = match_mode.lower()
        fallback = fallback.lower()
        if match_mode not in {'first', 'all'}:
            raise ValueError(f'Unsupported switch match_mode: {match_mode}')
        if fallback not in {'drop', 'last', 'error'}:
            raise ValueError(f'Unsupported switch fallback: {fallback}')
        selected: list[str] = []
        for index, rule in enumerate(rules):
            branch_index = int(rule.get('branch_index', -1))
            if not 0 <= branch_index < len(branch_names):
                raise ValueError(f'Switch rule {index} branch_index must be between 0 and {len(branch_names) - 1}')
            if cls._rule_matches(value, rule, case_sensitive):
                output_name = branch_names[branch_index]
                if output_name not in selected:
                    selected.append(output_name)
                if match_mode == 'first':
                    break
        if selected:
            return selected
        if fallback == 'drop':
            return []
        if fallback == 'error':
            raise ValueError(f'Switch value did not match any rule: {value}')
        return [branch_names[-1]]

    @staticmethod
    def _rule_matches(value: Any, rule: dict[str, Any], case_sensitive: bool) -> bool:
        match_type = str(rule.get('match_type', 'exact') or 'exact').lower()
        pattern = rule.get('pattern', '')
        value_text = str(value)
        pattern_text = str(pattern)
        compare_value = value_text if case_sensitive else value_text.lower()
        compare_pattern = pattern_text if case_sensitive else pattern_text.lower()
        if match_type in {'exact', 'equals', 'string_equal'}:
            return compare_value == compare_pattern
        if match_type == 'contains':
            return compare_pattern in compare_value
        if match_type in {'starts_with', 'startswith'}:
            return compare_value.startswith(compare_pattern)
        if match_type in {'ends_with', 'endswith'}:
            return compare_value.endswith(compare_pattern)
        if match_type == 'regex':
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.search(pattern_text, value_text, flags=flags) is not None
        if match_type in {'numeric_range', 'range'}:
            try:
                numeric_value = _as_float(value)
                lower = rule.get('min', None)
                upper = rule.get('max', None)
                if lower in (None, '') and upper in (None, '') and pattern_text:
                    bounds = [part.strip() for part in pattern_text.split(',', 1)]
                    lower = bounds[0]
                    upper = bounds[1] if len(bounds) > 1 else None
                if lower not in (None, '') and numeric_value < _as_float(lower):
                    return False
                if upper not in (None, '') and numeric_value > _as_float(upper):
                    return False
                return True
            except ValueError:
                return False
        if match_type in {'file_extension', 'extension'}:
            suffixes = ''.join(Path(value_text).suffixes)
            return suffixes == pattern_text or value_text.endswith(pattern_text)
        raise ValueError(f'Unsupported switch match_type: {match_type}')
