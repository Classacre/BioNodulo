"""cache — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class CacheControlNode(BaseNode):
    """Store and retrieve a value through an explicit cache marker."""
    NODE_ID = 'cache_control'
    DISPLAY_NAME = 'Cache Control'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Explicit cache control. Check cache first, execute downstream only on cache miss. Supports TTL and invalidation rules.'
    SEARCH_ALIASES = ['cache', 'ttl', 'invalidate', 'store', 'memo', 'skip']
    RETURN_TYPES = ('ANY', 'BOOLEAN', 'JSON')
    RETURN_NAMES = ('output', 'cache_hit', 'cache_info')
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTOR_CACHE_POLICY = 'always_run'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data to cache and pass through'}), 'cache_key': ('STRING', {'default': '', 'description': 'Explicit cache key; auto-hash when empty'})}, 'optional': {'ttl_seconds': ('INT', {'default': 0, 'min': 0}), 'invalidate_on_change': ('STRING', {'default': ''}), 'force_refresh': ('BOOLEAN', {'default': False}), 'cache_scope': (['run', 'global', 'user'], {'default': 'run'}), 'cache_dir': ('STRING', {'default': '', 'description': 'Custom cache directory'})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        explicit_key = str(kwargs.get('cache_key', '') or '')
        ttl_seconds = max(0, int(kwargs.get('ttl_seconds', 0) or 0))
        invalidate_on_change = str(kwargs.get('invalidate_on_change', '') or '')
        force_refresh = bool(kwargs.get('force_refresh', False))
        cache_scope = str(kwargs.get('cache_scope', 'run') or 'run').lower()
        cache_dir = self._cache_dir(kwargs.get('cache_dir', ''), context, cache_scope)
        invalidation_fingerprint = self._fingerprint(invalidate_on_change)
        cache_key = self._cache_key(data, explicit_key, cache_scope, invalidation_fingerprint)
        now = time.time()
        from bionodulo.execution.cache import CacheStore
        cache = CacheStore(cache_dir)
        try:
            marker = cache.read_marker(cache_key) if cache.is_hit(cache_key) else None
            outputs = marker.get('outputs', {}) if isinstance(marker, dict) else {}
            stored_at = outputs.get('stored_at')
            age_seconds = round(now - float(stored_at), 3) if stored_at is not None else None
            expired = ttl_seconds > 0 and age_seconds is not None and (age_seconds > ttl_seconds)
            cache_hit = bool(marker and (not force_refresh) and (not expired))
            cache_info = {'cache_key': cache_key, 'cache_scope': cache_scope, 'cache_dir': str(cache_dir), 'ttl_seconds': ttl_seconds, 'force_refresh': force_refresh, 'invalidate_on_change': invalidate_on_change, 'invalidation_fingerprint': invalidation_fingerprint, 'age_seconds': age_seconds, 'executor_skip_supported': True}
            if cache_hit:
                output = outputs.get('data', data)
                cache_info.update({'status': 'hit', 'stored_at': stored_at})
                _ctx_log(context, 'info', f'Cache Control hit: {cache_key}')
                return {'outputs': {'output': output, 'cache_hit': True, 'cache_info': _json_text(cache_info)}, 'inactive_outputs': ['output']}
            if force_refresh:
                status = 'refresh'
            elif expired:
                status = 'expired'
            else:
                status = 'miss'
            cache.write_marker(cache_key, outputs={'data': data, 'stored_at': now, 'invalidation_fingerprint': invalidation_fingerprint}, params={'cache_scope': cache_scope, 'ttl_seconds': ttl_seconds, 'invalidate_on_change': invalidate_on_change, 'force_refresh': force_refresh}, inputs={'input': data})
            cache_info.update({'status': status, 'stored_at': now})
            _ctx_log(context, 'info', f'Cache Control {status}: {cache_key}')
            return {'outputs': {'output': data, 'cache_hit': False, 'cache_info': _json_text(cache_info)}, 'inactive_outputs': []}
        finally:
            cache.close()

    def _cache_key(self, data: Any, explicit_key: str, cache_scope: str, invalidation_fingerprint: str) -> str:
        raw_key = explicit_key.strip()
        if not raw_key:
            raw_key = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()[:24]
        safe_key = re.sub('[^A-Za-z0-9_.-]+', '_', raw_key).strip('._') or 'auto'
        payload = json.dumps({'scope': cache_scope, 'key': safe_key, 'invalidate': invalidation_fingerprint}, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]
        return f'cache_control_{safe_key}_{digest}'

    @staticmethod
    def _fingerprint(value: str) -> str:
        if not value:
            return ''
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    @staticmethod
    def _cache_dir(value: Any, context: Any, cache_scope: str) -> Path:
        custom = str(value or '').strip()
        if custom:
            base = Path(custom)
        else:
            workspace_dir = getattr(context, 'workspace_dir', None) if context is not None else None
            root = Path(workspace_dir) / 'cache' if workspace_dir else Path('cache')
            base = root / 'control' / cache_scope
            if cache_scope == 'run':
                run_id = str(getattr(context, 'run_id', '') or 'unknown_run')
                base = base / re.sub('[^A-Za-z0-9_.-]+', '_', run_id).strip('._')
        base.mkdir(parents=True, exist_ok=True)
        return base
