"""memoize — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class MemoizeNode(BaseNode):
    """Hash inputs and persist a reusable memoization marker."""
    NODE_ID = 'memoize'
    DISPLAY_NAME = 'Memoize'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Function memoization for expensive operations. Hash inputs, cache results, auto-invalidate on parameter changes.'
    SEARCH_ALIASES = ['memoize', 'memo', 'hash', 'fingerprint', 'dedup']
    RETURN_TYPES = ('ANY', 'STRING', 'JSON')
    RETURN_NAMES = ('output', 'hash', 'memo_info')
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = 'always_run'
    SUPPORTED_ALGORITHMS = {'sha256', 'md5', 'blake2b'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Input data to memoize'})}, 'optional': {'salt': ('STRING', {'default': '', 'description': 'Extra salt for hash, such as tool version or database version'}), 'hash_algorithm': (['sha256', 'md5', 'blake2b'], {'default': 'sha256'}), 'cache_dir': ('STRING', {'default': '', 'description': 'Custom cache directory'})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, str, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        salt = str(kwargs.get('salt', '') or '')
        algorithm = str(kwargs.get('hash_algorithm', 'sha256') or 'sha256').lower()
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f'Unsupported hash algorithm: {algorithm}')
        input_hash = self._compute_hash(data, salt, algorithm)
        cache_key = f'memoize_{input_hash[:24]}'
        cache_dir = self._cache_dir(kwargs.get('cache_dir', ''), context)
        from bionodulo.execution.cache import CacheStore
        cache = CacheStore(cache_dir)
        try:
            memo_info = {'input_hash': input_hash, 'algorithm': algorithm, 'salt': salt, 'cache_key': cache_key, 'cache_dir': str(cache_dir), 'executor_skip_supported': False}
            cached_output = data
            if cache.is_hit(cache_key):
                marker = cache.read_marker(cache_key) or {}
                outputs = marker.get('outputs', {}) if isinstance(marker, dict) else {}
                cached_output = outputs.get('data', data)
                memo_info.update({'status': 'hit', 'cached_at': marker.get('cached_at'), 'cache_marker_found': True})
                _ctx_log(context, 'info', f'Memoize hit: hash={input_hash[:16]}...')
            else:
                cache.write_marker(cache_key, outputs={'data': data, 'hash': input_hash})
                memo_info.update({'status': 'miss', 'cached_at': None})
                _ctx_log(context, 'info', f'Memoize miss: stored hash={input_hash[:16]}...')
        finally:
            cache.close()
        return (cached_output, input_hash, _json_text(memo_info))

    def _compute_hash(self, data: Any, salt: str, algorithm: str) -> str:
        payload = {'input': data, 'salt': salt}
        serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
        hasher = hashlib.new(algorithm)
        hasher.update(serialized.encode('utf-8'))
        return hasher.hexdigest()

    @staticmethod
    def _cache_dir(value: Any, context: Any) -> Path:
        custom = str(value or '').strip()
        if custom:
            base = Path(custom)
        else:
            workspace_dir = getattr(context, 'workspace_dir', None) if context is not None else None
            base = Path(workspace_dir) / 'cache' if workspace_dir else Path('cache')
        base.mkdir(parents=True, exist_ok=True)
        return base
