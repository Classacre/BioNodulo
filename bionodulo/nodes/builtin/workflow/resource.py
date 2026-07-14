"""resource — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class ResourceMonitorNode(BaseNode):
    """Check local CPU, memory, and disk availability before continuing."""
    NODE_ID = 'resource_monitor'
    DISPLAY_NAME = 'Resource Monitor'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Monitor system resources and gate execution based on CPU, memory, and disk thresholds'
    SEARCH_ALIASES = ['resource', 'monitor', 'cpu', 'memory', 'disk', 'gate', 'threshold']
    RETURN_TYPES = ('ANY', 'BOOLEAN', 'JSON')
    RETURN_NAMES = ('passthrough', 'resources_ok', 'resource_stats')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data to pass through when resources are checked'})}, 'optional': {'min_free_memory_gb': ('FLOAT', {'default': 4.0, 'min': 0.0}), 'min_free_disk_gb': ('FLOAT', {'default': 10.0, 'min': 0.0}), 'max_cpu_percent': ('FLOAT', {'default': 95.0, 'min': 0.0, 'max': 100.0}), 'fail_on_insufficient': ('BOOLEAN', {'default': False}), 'check_interval_seconds': ('INT', {'default': 0, 'min': 0}), 'max_wait_seconds': ('INT', {'default': 0, 'min': 0})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        min_mem = float(kwargs.get('min_free_memory_gb', 4.0) or 0.0)
        min_disk = float(kwargs.get('min_free_disk_gb', 10.0) or 0.0)
        max_cpu = float(kwargs.get('max_cpu_percent', 95.0) or 100.0)
        fail_on_insufficient = bool(kwargs.get('fail_on_insufficient', False))
        check_interval = max(0, int(kwargs.get('check_interval_seconds', 0) or 0))
        max_wait = max(0, int(kwargs.get('max_wait_seconds', 0) or 0))
        started = time.time()
        stats = self._get_resource_stats()
        resources_ok = self._check_resources(stats, min_mem, min_disk, max_cpu)
        while not resources_ok and check_interval > 0 and (max_wait > 0) and (time.time() - started < max_wait):
            cancel_event = getattr(context, 'cancel_event', None)
            if cancel_event is not None and cancel_event.is_set():
                break
            await asyncio.sleep(min(check_interval, max_wait))
            stats = self._get_resource_stats()
            resources_ok = self._check_resources(stats, min_mem, min_disk, max_cpu)
        stats = {**stats, 'thresholds': {'min_free_memory_gb': min_mem, 'min_free_disk_gb': min_disk, 'max_cpu_percent': max_cpu}, 'resources_ok': resources_ok, 'waited_seconds': round(time.time() - started, 3)}
        _ctx_emit(context, 'resource_check', {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'passed': resources_ok, 'stats': stats})
        if not resources_ok:
            message = f"Insufficient resources: mem={stats.get('free_memory_gb')}GB (need {min_mem}GB), disk={stats.get('free_disk_gb')}GB (need {min_disk}GB), cpu={stats.get('cpu_percent')}% (max {max_cpu}%)"
            _ctx_log(context, 'warning', message)
            if fail_on_insufficient:
                raise RuntimeError(message)
        else:
            _ctx_log(context, 'info', 'Resources OK')
        return (data, resources_ok, _json_text(stats))

    def _get_resource_stats(self) -> dict[str, Any]:
        try:
            import psutil
        except ImportError:
            return {'free_memory_gb': 1000000.0, 'free_disk_gb': 1000000.0, 'cpu_percent': 0.0, 'note': 'psutil is not installed; resource check used permissive fallback'}
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return {'free_memory_gb': round(mem.available / 1024 ** 3, 3), 'total_memory_gb': round(mem.total / 1024 ** 3, 3), 'memory_percent': mem.percent, 'free_disk_gb': round(disk.free / 1024 ** 3, 3), 'total_disk_gb': round(disk.total / 1024 ** 3, 3), 'disk_percent': disk.percent, 'cpu_percent': psutil.cpu_percent(interval=0.0), 'cpu_count': psutil.cpu_count()}

    @staticmethod
    def _check_resources(stats: dict[str, Any], min_mem: float, min_disk: float, max_cpu: float) -> bool:
        return float(stats.get('free_memory_gb', 0.0)) >= min_mem and float(stats.get('free_disk_gb', 0.0)) >= min_disk and (float(stats.get('cpu_percent', 100.0)) <= max_cpu)
