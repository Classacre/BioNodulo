"""try — flow_control node(s). One tool per file (extracted from flow_control.py)."""
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


class TryCatchNode(BaseNode):
    """Route work through try, retry, and catch phases for error recovery."""
    NODE_ID = 'try_catch'
    DISPLAY_NAME = 'Try / Catch'
    CATEGORY = 'flow_control'
    DESCRIPTION = 'Route execution through try and catch branches with retry metadata for recoverable failures.'
    SEARCH_ALIASES = ['try', 'catch', 'error', 'fallback', 'retry', 'recover', 'rescue']
    RETURN_TYPES = ('ANY', 'ANY', 'ANY', 'BOOLEAN', 'STRING', 'INT')
    RETURN_NAMES = ('try', 'catch', 'output', 'succeeded', 'error_info', 'retry_count')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_TRY_CATCH_BRANCHES = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'try_input': ('ANY', {'description': 'Data to pass to the try branch'})}, 'optional': {'max_retries': ('INT', {'default': 0, 'min': 0, 'max': 10}), 'catch_errors': ('STRING', {'default': '', 'description': 'Comma-separated error types to catch; empty catches all'}), 'retry_delay': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 300.0}), 'pass_input_to_catch': ('BOOLEAN', {'default': True}), 'pass_error_to_catch': ('BOOLEAN', {'default': True})}, 'hidden': {'_phase': ('STRING', {'default': 'init'}), '_try_result': ('ANY', {}), '_try_error': ('STRING', {}), '_catch_result': ('ANY', {}), '_retry_count': ('INT', {'default': 0})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop('context', None)
        try_input = kwargs.get('try_input')
        max_retries = int(kwargs.get('max_retries', 0) or 0)
        retry_delay = float(kwargs.get('retry_delay', 1.0) or 0.0)
        catch_errors = kwargs.get('catch_errors', '')
        pass_input_to_catch = bool(kwargs.get('pass_input_to_catch', True))
        pass_error_to_catch = bool(kwargs.get('pass_error_to_catch', True))
        phase = str(kwargs.get('_phase', 'init') or 'init')
        try_result = kwargs.get('_try_result')
        try_error = str(kwargs.get('_try_error', '') or '')
        retry_count = int(kwargs.get('_retry_count', 0) or 0)
        if phase == 'init':
            return self._result(try_value=try_input, catch_value=None, output=None, succeeded=False, error_info='', retry_count=0, inactive=['catch', 'output', 'succeeded', 'error_info', 'retry_count'], flow_phase='trying')
        if phase == 'try_result':
            if try_result is not None and (not try_error):
                return self._result(try_value=None, catch_value=None, output=try_result, succeeded=True, error_info='', retry_count=retry_count, inactive=['try', 'catch', 'error_info'], flow_phase='completed')
            if try_error and (not _is_catchable(try_error, catch_errors)):
                return self._result(try_value=None, catch_value=None, output=None, succeeded=False, error_info=try_error, retry_count=retry_count, inactive=['try', 'catch', 'output', 'succeeded', 'retry_count'], flow_phase='uncaught_error', error_type=_error_type(try_error))
            if retry_count < max_retries:
                if retry_delay > 0:
                    await asyncio.sleep(retry_delay)
                next_retry = retry_count + 1
                return self._result(try_value=try_input, catch_value=None, output=None, succeeded=False, error_info=try_error, retry_count=next_retry, inactive=['catch', 'output', 'succeeded'], flow_phase='retrying')
            catch_inputs: dict[str, Any] = {}
            if pass_input_to_catch:
                catch_inputs['input'] = try_input
            if pass_error_to_catch:
                catch_inputs['error'] = try_error
            catch_value: Any = catch_inputs if catch_inputs else None
            return self._result(try_value=None, catch_value=catch_value, output=None, succeeded=False, error_info=try_error, retry_count=retry_count, inactive=['try', 'output', 'succeeded', 'retry_count'], flow_phase='catching', error_type=_error_type(try_error))
        if phase == 'catch_result':
            return self._result(try_value=None, catch_value=None, output=kwargs.get('_catch_result'), succeeded=False, error_info=try_error, retry_count=retry_count, inactive=['try', 'catch', 'succeeded'], flow_phase='completed_with_catch')
        return self._result(try_value=None, catch_value=None, output=None, succeeded=False, error_info=f'Unknown try/catch phase: {phase}', retry_count=retry_count, inactive=['try', 'catch', 'output', 'succeeded', 'retry_count'], flow_phase='error')

    @staticmethod
    def _result(*, try_value: Any, catch_value: Any, output: Any, succeeded: bool, error_info: str, retry_count: int, inactive: list[str], flow_phase: str, error_type: str | None=None) -> dict[str, Any]:
        flow_control: dict[str, Any] = {'type': 'try_catch', 'phase': flow_phase, 'retry_count': retry_count}
        if error_type:
            flow_control['error_type'] = error_type
        return {'outputs': {'try': try_value, 'catch': catch_value, 'output': output, 'succeeded': succeeded, 'error_info': error_info, 'retry_count': retry_count}, 'inactive_outputs': inactive, 'flow_control': flow_control}
