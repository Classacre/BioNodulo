"""retry — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class RetryNode(BaseNode):
    """Record a retry policy and pass data through unchanged."""
    NODE_ID = 'retry'
    DISPLAY_NAME = 'Retry'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Configure retry policy for downstream nodes. Attach upstream of a branch to enable automatic retry on failure.'
    SEARCH_ALIASES = ['retry', 'reexecute', 'attempt', 'failure', 'recover']
    RETURN_TYPES = ('ANY', 'JSON')
    RETURN_NAMES = ('passthrough', 'retry_log')
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = 'always_run'
    RETRY_ON_OPTIONS = {'all', 'timeout', 'memory', 'exit_code'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data to pass through to downstream nodes'})}, 'optional': {'max_retries': ('INT', {'default': 3, 'min': 0, 'max': 10}), 'delay_seconds': ('FLOAT', {'default': 5.0, 'min': 0.0}), 'backoff_multiplier': ('FLOAT', {'default': 2.0, 'min': 1.0}), 'max_delay': ('INT', {'default': 300, 'min': 1}), 'retry_on': (['all', 'timeout', 'memory', 'exit_code'], {'default': 'all'}), 'only_retry_specific_nodes': ('STRING', {'default': ''})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        max_retries = int(kwargs.get('max_retries', 3) or 0)
        delay_seconds = max(0.0, float(kwargs.get('delay_seconds', 5.0) or 0.0))
        backoff_multiplier = max(1.0, float(kwargs.get('backoff_multiplier', 2.0) or 1.0))
        max_delay = max(1.0, float(kwargs.get('max_delay', 300) or 300))
        retry_on = str(kwargs.get('retry_on', 'all') or 'all').lower()
        target_nodes = self._target_nodes(kwargs.get('only_retry_specific_nodes', ''))
        if max_retries < 0 or max_retries > 10:
            raise ValueError('max_retries must be between 0 and 10')
        if retry_on not in self.RETRY_ON_OPTIONS:
            raise ValueError(f'Unsupported retry_on value: {retry_on}')
        policy = {'node_id': getattr(context, 'node_id', self.NODE_ID), 'run_id': getattr(context, 'run_id', ''), 'max_retries': max_retries, 'delay_seconds': delay_seconds, 'backoff_multiplier': backoff_multiplier, 'max_delay': max_delay, 'retry_on': retry_on, 'target_nodes': target_nodes, 'delays_seconds': self._delays(max_retries, delay_seconds, backoff_multiplier, max_delay), 'timestamp': time.time(), 'executor_retry_supported': True, 'note': 'Retry policy recorded; the executor applies it to downstream matching nodes.'}
        if context is not None and hasattr(context, 'run_metadata'):
            context.run_metadata.setdefault('retry_policies', []).append(policy)
        policy_file = ''
        if context is not None:
            policy_path = _node_output_dir(self, context) / 'retry_policy.json'
            policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True, default=str), encoding='utf-8')
            policy_file = str(policy_path)
            policy['policy_file'] = policy_file
        _ctx_emit(context, 'retry_policy_registered', {'run_id': policy['run_id'], 'node_id': policy['node_id'], 'max_retries': max_retries, 'retry_on': retry_on, 'target_nodes': target_nodes, 'policy_file': policy_file})
        _ctx_log(context, 'info', f'Retry policy registered: {max_retries} retries, retry_on={retry_on}')
        return (data, _json_text(policy))

    @staticmethod
    def _target_nodes(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or '').split(',') if item.strip()]

    @staticmethod
    def _delays(max_retries: int, delay_seconds: float, backoff_multiplier: float, max_delay: float) -> list[float]:
        delays: list[float] = []
        current = delay_seconds
        for _ in range(max_retries):
            delays.append(round(min(current, max_delay), 6))
            current *= backoff_multiplier
        return delays
