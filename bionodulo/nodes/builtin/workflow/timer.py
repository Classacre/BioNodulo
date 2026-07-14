"""timer — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class TimerNode(BaseNode):
    """Record a workflow timestamp and pass data through unchanged."""
    NODE_ID = 'timer'
    DISPLAY_NAME = 'Timer'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Measure execution time and emit timestamp metadata for workflow profiling'
    SEARCH_ALIASES = ['timer', 'time', 'duration', 'benchmark', 'profile', 'elapsed']
    RETURN_TYPES = ('ANY', 'FLOAT', 'JSON', 'JSON')
    RETURN_NAMES = ('passthrough', 'elapsed_seconds', 'start_time', 'end_time')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data to pass through'})}, 'optional': {'label': ('STRING', {'default': '', 'description': 'Timer label'}), 'log_level': (['debug', 'info', 'warning'], {'default': 'info'})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, float, str, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        label = str(kwargs.get('label', '') or getattr(context, 'node_id', self.NODE_ID))
        log_level = str(kwargs.get('log_level', 'info') or 'info')
        start = time.time()
        start_info = {'timestamp': start, 'iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start)), 'label': label, 'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID)}
        end = time.time()
        end_info = {**start_info, 'timestamp': end, 'iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(end))}
        elapsed = max(0.0, end - start)
        if context is not None and hasattr(context, 'run_metadata'):
            timers = context.run_metadata.setdefault('timers', [])
            timers.append({'node_id': getattr(context, 'node_id', self.NODE_ID), 'label': label, 'start': start, 'end': end})
        _ctx_emit(context, 'timer_elapsed', {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'label': label, 'elapsed_ms': round(elapsed * 1000, 3), 'start_time': start_info['iso'], 'end_time': end_info['iso']})
        _ctx_log(context, log_level, f"Timer '{label}' recorded {elapsed:.6f}s")
        return (data, elapsed, _json_text(start_info), _json_text(end_info))
