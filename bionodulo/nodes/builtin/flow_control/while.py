"""while — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class WhileLoopNode(BaseNode):
    """Track conditional loop state for iterative workflow sections."""
    NODE_ID = 'while_loop'
    DISPLAY_NAME = 'While Loop'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Repeat a loop body while a condition remains true, with a mandatory max-iteration limit.'
    SEARCH_ALIASES = ['while', 'until', 'repeat', 'convergence', 'iterate']
    RETURN_TYPES = ('ANY', 'INT', 'BOOLEAN')
    RETURN_NAMES = ('results', 'iterations', 'converged')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_LOOP_BODY = True
    _CONDITION_MODES = ['file_exists', 'file_not_exists', 'numeric_equals', 'numeric_not_equals', 'numeric_greater', 'numeric_less', 'numeric_greater_equal', 'numeric_less_equal', 'boolean_is_true', 'boolean_is_false']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'condition_mode': ('STRING', {'default': 'file_not_exists', 'options': cls._CONDITION_MODES})}, 'optional': {'value': ('ANY', {}), 'compare_to': ('STRING', {'default': ''}), 'max_iterations': ('INT', {'default': 100, 'min': 1, 'max': 10000}), 'check_frequency': ('INT', {'default': 1, 'min': 1, 'max': 100})}, 'hidden': {'_loop_state': ('LOOP_STATE', {}), '_is_loop_iteration': ('BOOLEAN', {'default': False}), '_body_result': ('ANY', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        condition_mode = str(kwargs.get('condition_mode', 'file_not_exists') or 'file_not_exists')
        value = kwargs.get('value')
        compare_to = kwargs.get('compare_to', '')
        max_iterations = max(1, min(10000, int(kwargs.get('max_iterations', 100) or 100)))
        check_frequency = max(1, min(100, int(kwargs.get('check_frequency', 1) or 1)))
        is_loop_iteration = bool(kwargs.get('_is_loop_iteration', False))
        if not is_loop_iteration:
            loop_state = {'iteration': 0, 'max_iterations': max_iterations, 'check_frequency': check_frequency, 'condition_mode': condition_mode, 'compare_to': compare_to, 'processed': [], 'is_complete': False}
            if not self._evaluate_condition(value, condition_mode, compare_to):
                loop_state['is_complete'] = True
                return self._result([], 0, True, 'completed', loop_state, inactive=[])
            return self._result([], 0, False, 'iterating', loop_state, inactive=['results', 'iterations', 'converged'])
        loop_state = self._normalise_loop_state(kwargs.get('_loop_state'), condition_mode, compare_to, max_iterations)
        processed = list(loop_state.get('processed', []))
        body_result = kwargs.get('_body_result')
        if body_result is not None:
            processed.append(body_result)
        iteration = int(loop_state.get('iteration', 0) or 0) + 1
        loop_state['iteration'] = iteration
        loop_state['processed'] = processed
        if iteration >= int(loop_state.get('max_iterations', max_iterations) or max_iterations):
            loop_state['is_complete'] = True
            return self._result(processed, iteration, False, 'max_iterations', loop_state, inactive=[])
        check_frequency = max(1, min(100, int(loop_state.get('check_frequency', check_frequency) or check_frequency)))
        if iteration % check_frequency != 0:
            return self._result(processed, iteration, False, 'iterating', loop_state, inactive=['results', 'iterations', 'converged'])
        mode = str(loop_state.get('condition_mode', condition_mode) or condition_mode)
        compare = loop_state.get('compare_to', compare_to)
        if not self._evaluate_condition(value, mode, compare):
            loop_state['is_complete'] = True
            return self._result(processed, iteration, True, 'completed', loop_state, inactive=[])
        return self._result(processed, iteration, False, 'iterating', loop_state, inactive=['results', 'iterations', 'converged'])

    @classmethod
    def _evaluate_condition(cls, value: Any, mode: str, compare_to: Any) -> bool:
        if mode == 'file_exists':
            return bool(value) and Path(str(value)).exists()
        if mode == 'file_not_exists':
            return not (bool(value) and Path(str(value)).exists())
        if mode == 'boolean_is_true':
            return _bool_value(value) is True
        if mode == 'boolean_is_false':
            return _bool_value(value) is False
        if mode.startswith('numeric_'):
            left = _as_float(value)
            right = _as_float(compare_to)
            if mode == 'numeric_equals':
                return left == right
            if mode == 'numeric_not_equals':
                return left != right
            if mode == 'numeric_greater':
                return left > right
            if mode == 'numeric_less':
                return left < right
            if mode == 'numeric_greater_equal':
                return left >= right
            if mode == 'numeric_less_equal':
                return left <= right
        raise ValueError(f'Unsupported while loop condition mode: {mode}')

    @staticmethod
    def _normalise_loop_state(loop_state: Any, condition_mode: str, compare_to: Any, max_iterations: int) -> dict[str, Any]:
        if isinstance(loop_state, dict):
            state = dict(loop_state)
        else:
            state = {}
            for key in ('iteration', 'max_iterations', 'processed', 'is_complete'):
                if hasattr(loop_state, key):
                    state[key] = getattr(loop_state, key)
            context = getattr(loop_state, 'context', None)
            if isinstance(context, dict):
                state.update(context)
        state.setdefault('iteration', 0)
        state.setdefault('max_iterations', max_iterations)
        state.setdefault('check_frequency', 1)
        state.setdefault('condition_mode', condition_mode)
        state.setdefault('compare_to', compare_to)
        state.setdefault('processed', [])
        state.setdefault('is_complete', False)
        return state

    @staticmethod
    def _result(results: list[Any], iterations: int, converged: bool, phase: str, loop_state: dict[str, Any], inactive: list[str]) -> dict[str, Any]:
        return {'outputs': {'results': results, 'iterations': iterations, 'converged': converged}, 'inactive_outputs': inactive, 'flow_control': {'type': 'while_loop', 'phase': phase, 'is_complete': bool(loop_state.get('is_complete', phase != 'iterating')), 'loop_state': dict(loop_state)}}
