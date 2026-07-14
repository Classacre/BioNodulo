"""provenance — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
from __future__ import annotations
import asyncio
import csv
import difflib
import gzip
import html
import hashlib
import json
import math
import os
import platform
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from bionodulo.execution.pause_state import PauseStateStore
from bionodulo.nodes.base import BaseNode
def _ctx_log(context: Any, level: str, message: str) -> None:
    if context is not None and hasattr(context, 'log'):
        context.log(level, message)
def _ctx_emit(context: Any, event: str, payload: dict[str, Any]) -> None:
    if context is not None and hasattr(context, 'emit'):
        context.emit(event, payload)
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    base.mkdir(parents=True, exist_ok=True)
    return base
def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class ProvenanceNode(BaseNode):
    """Capture reproducibility metadata and pass data through unchanged."""
    NODE_ID = 'provenance'
    DISPLAY_NAME = 'Provenance'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Capture provenance metadata for reproducibility, including tool versions, parameters, inputs, and environment'
    SEARCH_ALIASES = ['provenance', 'metadata', 'reproducibility', 'audit', 'trace', 'lineage', 'cwl']
    RETURN_TYPES = ('ANY', 'JSON', 'FILE')
    RETURN_NAMES = ('passthrough', 'provenance_record', 'provenance_file')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data or artifact reference to pass through and record'})}, 'optional': {'tool_name': ('STRING', {'default': '', 'description': 'Tool or workflow step name'}), 'tool_version': ('STRING', {'default': '', 'description': 'Tool version'}), 'tool_command': ('STRING', {'default': '', 'multiline': True, 'description': 'Command or invocation'}), 'description': ('STRING', {'default': '', 'multiline': True, 'description': 'Human-readable provenance note'}), 'custom_metadata': ('JSON', {'default': '{}', 'multiline': True}), 'include_system_info': ('BOOLEAN', {'default': True}), 'standard': (['w3c', 'cwlprov', 'native'], {'default': 'w3c'})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, str, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        standard = str(kwargs.get('standard', 'w3c') or 'w3c').lower()
        custom = self._parse_custom_metadata(kwargs.get('custom_metadata', '{}'))
        system_info = self._system_info() if bool(kwargs.get('include_system_info', True)) else {}
        params = self._merged_params(kwargs, context, system_info)
        if standard == 'w3c':
            record = self._build_w3c_record(data, params, context, custom)
        elif standard == 'cwlprov':
            record = self._build_cwlprov_record(data, params, context, custom)
        elif standard == 'native':
            record = self._build_native_record(data, params, context, custom, system_info)
        else:
            raise ValueError(f'Unsupported provenance standard: {standard}')
        provenance_file = ''
        if context is not None:
            output_path = _node_output_dir(self, context) / 'provenance.json'
            output_path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding='utf-8')
            provenance_file = str(output_path)
        tool_name = params.get('tool_name') or getattr(context, 'node_id', self.NODE_ID)
        _ctx_log(context, 'info', f'Provenance recorded for {tool_name}')
        return (data, _json_text(record), provenance_file)

    def _merged_params(self, kwargs: dict[str, Any], context: Any, system_info: dict[str, Any]) -> dict[str, Any]:
        context_params = getattr(context, 'params', {}) if context is not None else {}
        merged = dict(context_params) if isinstance(context_params, dict) else {}
        merged.update({'tool_name': str(kwargs.get('tool_name', '') or getattr(context, 'node_type', '') or ''), 'tool_version': str(kwargs.get('tool_version', '') or ''), 'tool_command': str(kwargs.get('tool_command', '') or ''), 'description': str(kwargs.get('description', '') or ''), 'include_system_info': bool(kwargs.get('include_system_info', True)), '_timestamp': system_info.get('timestamp') or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), '_timestamp_unix': system_info.get('timestamp_unix') or time.time()})
        return merged

    @staticmethod
    def _parse_custom_metadata(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value in (None, ''):
            return {}
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return {'parse_error': str(value)}
        return parsed if isinstance(parsed, dict) else {'value': parsed}

    @staticmethod
    def _system_info() -> dict[str, Any]:
        return {'platform': platform.platform(), 'python_version': sys.version, 'processor': platform.processor(), 'machine': platform.machine(), 'hostname': platform.node(), 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'timestamp_unix': time.time()}

    def _build_w3c_record(self, data: Any, params: dict[str, Any], context: Any, custom: dict[str, Any]) -> dict[str, Any]:
        node_id = getattr(context, 'node_id', self.NODE_ID)
        tool_name = params.get('tool_name') or 'unknown'
        return {'@context': 'https://www.w3.org/ns/prov.jsonld', '@type': 'Activity', '@id': f'urn:bionodulo:activity:{node_id}', 'startedAtTime': params.get('_timestamp'), 'endedAtTime': params.get('_timestamp'), 'wasAssociatedWith': {'@type': 'Agent', '@id': f'urn:bionodulo:agent:{tool_name}', 'name': tool_name, 'version': params.get('tool_version', '')}, 'used': {'@type': 'Entity', '@id': f'urn:bionodulo:entity:input:{node_id}', 'value': self._record_value(data, 500)}, 'parameters': self._public_params(params), 'custom_metadata': custom}

    def _build_cwlprov_record(self, data: Any, params: dict[str, Any], context: Any, custom: dict[str, Any]) -> dict[str, Any]:
        return {'class': 'provenance_record', 'run_id': getattr(context, 'run_id', 'unknown'), 'step_id': getattr(context, 'node_id', self.NODE_ID), 'tool': {'name': params.get('tool_name', ''), 'version': params.get('tool_version', ''), 'command': params.get('tool_command', '')}, 'inputs': {'data': self._record_value(data, 1000)}, 'parameters': self._public_params(params), 'timestamp': params.get('_timestamp'), 'custom': custom}

    def _build_native_record(self, data: Any, params: dict[str, Any], context: Any, custom: dict[str, Any], system_info: dict[str, Any]) -> dict[str, Any]:
        return {'bionodulo_provenance': {'version': '1.0', 'run_id': getattr(context, 'run_id', 'unknown'), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'node_type': getattr(context, 'node_type', 'unknown'), 'timestamp': params.get('_timestamp'), 'tool': {'name': params.get('tool_name', ''), 'version': params.get('tool_version', ''), 'command': params.get('tool_command', '')}, 'description': params.get('description', ''), 'inputs': {'data': self._record_value(data, 2000)}, 'parameters': self._public_params(params), 'system': system_info if params.get('include_system_info', True) else {'omitted': True}, 'custom_metadata': custom}}

    @staticmethod
    def _record_value(value: Any, max_length: int) -> Any:
        if isinstance(value, (dict, list)):
            return value
        return str(value)[:max_length]

    @staticmethod
    def _public_params(params: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in params.items() if not key.startswith('_')}
