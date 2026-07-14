"""workflow — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class WorkflowTriggerNode(BaseNode):
    """Trigger a webhook immediately or record a deferred trigger intent."""
    NODE_ID = 'workflow_trigger'
    DISPLAY_NAME = 'Workflow Trigger'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Trigger workflows via webhook, schedule, or file watch. HTTP POST, cron-like scheduling, or filesystem events.'
    SEARCH_ALIASES = ['trigger', 'webhook', 'cron', 'schedule', 'filewatch', 'event', 'http']
    RETURN_TYPES = ('JSON', 'BOOLEAN')
    RETURN_NAMES = ('trigger_info', 'triggered')
    REQUIRES_EXTERNAL_TOOLS = False
    SUPPORTED_TRIGGER_TYPES = {'webhook', 'schedule', 'file_watch'}
    SUPPORTED_WATCH_EVENTS = {'create', 'modify', 'delete', 'move'}
    CRON_FIELD_SPECS = {'minute': (0, 59), 'hour': (0, 23), 'day_of_month': (1, 31), 'month': (1, 12), 'day_of_week': (0, 7)}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'trigger_type': (['webhook', 'schedule', 'file_watch'], {'default': 'webhook'})}, 'optional': {'webhook_url': ('STRING', {'default': ''}), 'payload': ('JSON', {'default': '{}'}), 'cron_expression': ('STRING', {'default': '0 2 * * *'}), 'timezone': ('STRING', {'default': 'UTC'}), 'watch_path': ('STRING', {'default': ''}), 'watch_event': (['create', 'modify', 'delete', 'move'], {'default': 'create'}), 'target_workflow': ('STRING', {'default': ''}), 'timeout_seconds': ('FLOAT', {'default': 30.0, 'min': 0.1})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[str, bool]:
        context = kwargs.pop('context', None)
        trigger_type = str(kwargs.get('trigger_type', 'webhook') or 'webhook').lower()
        if trigger_type not in self.SUPPORTED_TRIGGER_TYPES:
            raise ValueError(f'Unsupported trigger_type: {trigger_type}')
        target_workflow = str(kwargs.get('target_workflow', '') or '')
        timestamp = time.time()
        payload = self._parse_payload(kwargs.get('payload', '{}'))
        timeout = max(0.1, float(kwargs.get('timeout_seconds', 30.0) or 30.0))
        if trigger_type == 'webhook':
            info, triggered = await self._trigger_webhook(webhook_url=str(kwargs.get('webhook_url', '') or ''), payload=payload, timeout=timeout)
        elif trigger_type == 'schedule':
            info, triggered = self._record_schedule(context=context, cron_expression=str(kwargs.get('cron_expression', '0 2 * * *') or '0 2 * * *'), timezone=str(kwargs.get('timezone', 'UTC') or 'UTC'))
        else:
            info, triggered = self._record_file_watch(context=context, watch_path=str(kwargs.get('watch_path', '') or ''), watch_event=str(kwargs.get('watch_event', 'create') or 'create'))
        info.update({'trigger_type': trigger_type, 'target_workflow': target_workflow, 'payload': payload, 'timestamp': timestamp})
        trigger_file = ''
        if trigger_type in {'schedule', 'file_watch'} and triggered:
            trigger_file = self._write_trigger_file(context, trigger_type, info)
            if trigger_file:
                info['schedule_file' if trigger_type == 'schedule' else 'watch_file'] = trigger_file
                self._write_trigger_file(context, trigger_type, info)
        event_payload = {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'trigger_type': trigger_type, 'status': info.get('status', 'unknown'), 'triggered': triggered, 'target_workflow': target_workflow}
        _ctx_emit(context, 'workflow_trigger', event_payload)
        _ctx_log(context, 'info' if triggered else 'warning', f"Workflow Trigger [{trigger_type}]: {info.get('status')}")
        return (_json_text(info), triggered)

    @staticmethod
    def _parse_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value or '{}')
            except json.JSONDecodeError as exc:
                raise ValueError(f'payload must be valid JSON: {exc}') from exc
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError('payload must be a JSON object')
        return value

    async def _trigger_webhook(self, webhook_url: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], bool]:
        if not webhook_url:
            return ({'status': 'skipped', 'reason': 'No webhook URL configured', 'webhook_url_configured': False}, False)
        try:
            response = await self._post_json(webhook_url, payload, timeout)
        except Exception as exc:
            return ({'status': 'failed', 'error': str(exc), 'webhook_url_configured': True}, False)
        status_code = int(response.get('status_code', 0) or 0)
        success = 200 <= status_code < 300
        return ({'status': 'triggered' if success else 'failed', 'http_status': status_code, 'response_body': str(response.get('body', ''))[:1000], 'webhook_url_configured': True}, success)

    def _record_schedule(self, context: Any, cron_expression: str, timezone: str) -> tuple[dict[str, Any], bool]:
        cron_fields, allowed = self._parse_cron_expression(cron_expression)
        try:
            zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f'Unsupported timezone: {timezone}') from exc
        now = datetime.fromtimestamp(time.time(), tz=zone)
        next_run = self._next_cron_run(now, allowed)
        next_run_utc = next_run.astimezone(dt_timezone.utc)
        info = {'status': 'registered', 'cron_expression': cron_expression, 'cron_fields': cron_fields, 'timezone': timezone, 'next_run_at': next_run.isoformat(), 'next_run_at_utc': next_run_utc.isoformat(), 'seconds_until_next_run': int((next_run_utc - now.astimezone(dt_timezone.utc)).total_seconds()), 'scheduler_runner_contract_supported': True, 'durable_scheduler_supported': True, 'note': 'Schedule registration written with pollable due-run metadata and durable runner support.'}
        return (info, True)

    def _parse_cron_expression(self, cron_expression: str) -> tuple[dict[str, str], dict[str, set[int]]]:
        fields = cron_expression.split()
        if len(fields) != 5:
            raise ValueError('cron_expression must have exactly 5 fields')
        names = ['minute', 'hour', 'day_of_month', 'month', 'day_of_week']
        cron_fields = dict(zip(names, fields, strict=True))
        allowed = {name: self._parse_cron_field(name, cron_fields[name], *self.CRON_FIELD_SPECS[name]) for name in names}
        if 7 in allowed['day_of_week']:
            allowed['day_of_week'].add(0)
            allowed['day_of_week'].discard(7)
        return (cron_fields, allowed)

    def _parse_cron_field(self, name: str, value: str, minimum: int, maximum: int) -> set[int]:
        allowed: set[int] = set()
        for part in value.split(','):
            part = part.strip()
            if not part:
                raise ValueError(f'Invalid {name} field: {value}')
            step = 1
            base = part
            if '/' in part:
                base, step_text = part.split('/', 1)
                if not step_text.isdigit() or int(step_text) <= 0:
                    raise ValueError(f'Invalid {name} field: {value}')
                step = int(step_text)
            if base == '*':
                start, end = (minimum, maximum)
            elif '-' in base:
                start_text, end_text = base.split('-', 1)
                if not start_text.isdigit() or not end_text.isdigit():
                    raise ValueError(f'Invalid {name} field: {value}')
                start, end = (int(start_text), int(end_text))
                if start > end:
                    raise ValueError(f'Invalid {name} field: {value}')
            else:
                if not base.isdigit():
                    raise ValueError(f'Invalid {name} field: {value}')
                start = end = int(base)
            if start < minimum or end > maximum:
                raise ValueError(f'Invalid {name} field: {value}')
            allowed.update(range(start, end + 1, step))
        return allowed

    def _next_cron_run(self, now: datetime, allowed: dict[str, set[int]]) -> datetime:
        candidate = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        deadline = candidate + timedelta(days=366 * 5)
        while candidate <= deadline:
            cron_weekday = (candidate.weekday() + 1) % 7
            if candidate.minute in allowed['minute'] and candidate.hour in allowed['hour'] and (candidate.month in allowed['month']) and self._cron_day_matches(candidate.day, cron_weekday, allowed):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError('cron_expression did not produce a next run within 5 years')

    def _cron_day_matches(self, day_of_month: int, day_of_week: int, allowed: dict[str, set[int]]) -> bool:
        all_days = set(range(1, 32))
        all_weekdays = set(range(0, 7))
        dom_allowed = allowed['day_of_month']
        dow_allowed = allowed['day_of_week']
        dom_is_wildcard = dom_allowed == all_days
        dow_is_wildcard = dow_allowed == all_weekdays
        dom_matches = day_of_month in dom_allowed
        dow_matches = day_of_week in dow_allowed
        if dom_is_wildcard and dow_is_wildcard:
            return True
        if dom_is_wildcard:
            return dow_matches
        if dow_is_wildcard:
            return dom_matches
        return dom_matches or dow_matches

    def _record_file_watch(self, context: Any, watch_path: str, watch_event: str) -> tuple[dict[str, Any], bool]:
        watch_event = watch_event.lower()
        if watch_event not in self.SUPPORTED_WATCH_EVENTS:
            raise ValueError(f'Unsupported watch_event: {watch_event}')
        path = Path(watch_path) if watch_path else None
        exists = bool(path and path.exists())
        info = {'status': 'registered' if exists else 'failed', 'watch_path': watch_path, 'watch_event': watch_event, 'path_exists': exists, 'path_type': 'directory' if path and path.is_dir() else 'file' if path and path.is_file() else 'missing', 'baseline_snapshot': self._file_watch_snapshot(path) if exists and path is not None else {}, 'file_watch_runner_contract_supported': exists, 'active_file_watcher_supported': False, 'durable_trigger_runner_supported': exists, 'note': 'File-watch registration written with pollable baseline metadata; durable polling runner evaluation can submit embedded workflows, while native filesystem watcher execution is not implemented yet.'}
        if not exists:
            info['error'] = f'Watch path does not exist: {watch_path}'
            return (info, False)
        return (info, True)

    def _write_trigger_file(self, context: Any, trigger_type: str, info: dict[str, Any]) -> str:
        if context is None:
            return ''
        workspace_dir = getattr(context, 'workspace_dir', None)
        base = Path(workspace_dir) if workspace_dir else _node_output_dir(self, context)
        trigger_dir = base / 'workflow_triggers'
        trigger_dir.mkdir(parents=True, exist_ok=True)
        node_id = getattr(context, 'node_id', self.NODE_ID)
        trigger_file = trigger_dir / f'{trigger_type}_{node_id}.json'
        trigger_file.write_text(json.dumps(info, indent=2, sort_keys=True, default=str), encoding='utf-8')
        return str(trigger_file)

    @classmethod
    def due_schedule_triggers(cls, trigger_dir: str | Path, now: str | datetime | None=None) -> list[dict[str, Any]]:
        base = Path(trigger_dir)
        if not base.exists():
            return []
        now_utc = cls._coerce_utc_datetime(now)
        due: list[dict[str, Any]] = []
        for trigger_file in sorted(base.glob('schedule_*.json')):
            try:
                info = json.loads(trigger_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                raise ValueError(f'schedule trigger file is not valid JSON: {trigger_file}') from exc
            if not isinstance(info, dict) or info.get('trigger_type') != 'schedule':
                continue
            next_run = cls._coerce_utc_datetime(info.get('next_run_at_utc'))
            if next_run <= now_utc:
                due_info = dict(info)
                due_info['trigger_file'] = str(trigger_file)
                due.append(due_info)
        return due

    @classmethod
    def due_file_watch_triggers(cls, trigger_dir: str | Path) -> list[dict[str, Any]]:
        base = Path(trigger_dir)
        if not base.exists():
            return []
        due: list[dict[str, Any]] = []
        for trigger_file in sorted(base.glob('file_watch_*.json')):
            try:
                info = json.loads(trigger_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                raise ValueError(f'file-watch trigger file is not valid JSON: {trigger_file}') from exc
            if not isinstance(info, dict) or info.get('trigger_type') != 'file_watch':
                continue
            events = cls._file_watch_events(info)
            if events:
                due_info = dict(info)
                due_info['trigger_file'] = str(trigger_file)
                due_info['events'] = events
                due.append(due_info)
        return due

    @classmethod
    def _file_watch_events(cls, info: dict[str, Any]) -> list[dict[str, str]]:
        path = Path(str(info.get('watch_path', '') or ''))
        watch_event = str(info.get('watch_event', 'create') or 'create')
        if not path.exists() and watch_event != 'delete':
            return []
        baseline = info.get('baseline_snapshot', {})
        if not isinstance(baseline, dict):
            baseline = {}
        current = cls._file_watch_snapshot(path) if path.exists() else {}
        events: list[dict[str, str]] = []
        if watch_event == 'create':
            for relative_path in sorted(set(current) - set(baseline)):
                events.append({'event': 'create', 'path': current[relative_path]['path'], 'relative_path': relative_path})
        elif watch_event == 'modify':
            for relative_path in sorted(set(current) & set(baseline)):
                if cls._file_watch_signature(current[relative_path]) != cls._file_watch_signature(baseline[relative_path]):
                    events.append({'event': 'modify', 'path': current[relative_path]['path'], 'relative_path': relative_path})
        elif watch_event == 'delete':
            for relative_path in sorted(set(baseline) - set(current)):
                events.append({'event': 'delete', 'path': baseline[relative_path]['path'], 'relative_path': relative_path})
        elif watch_event == 'move':
            created_paths = sorted(set(current) - set(baseline))
            deleted_paths = sorted(set(baseline) - set(current))
            unmatched_created = list(created_paths)
            for deleted_path in deleted_paths:
                deleted_signature = cls._file_watch_signature(baseline[deleted_path])
                match = next((created_path for created_path in unmatched_created if cls._file_watch_signature(current[created_path]) == deleted_signature), None)
                if match is None:
                    continue
                unmatched_created.remove(match)
                events.append({'event': 'move', 'path': current[match]['path'], 'relative_path': match, 'previous_path': baseline[deleted_path]['path'], 'previous_relative_path': deleted_path})
        return events

    @staticmethod
    def _file_watch_signature(entry: dict[str, Any]) -> tuple[Any, Any]:
        return (entry.get('size_bytes'), entry.get('mtime_ns'))

    @staticmethod
    def _file_watch_snapshot(path: Path) -> dict[str, dict[str, Any]]:
        if path.is_file():
            paths = [path]
            root = path.parent
        else:
            paths = [entry for entry in path.rglob('*') if entry.is_file()]
            root = path
        snapshot: dict[str, dict[str, Any]] = {}
        for entry in sorted(paths):
            try:
                stat = entry.stat()
            except OSError:
                continue
            snapshot[entry.relative_to(root).as_posix()] = {'path': str(entry), 'size_bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        return snapshot

    @staticmethod
    def _coerce_utc_datetime(value: str | datetime | None) -> datetime:
        if value is None:
            return datetime.fromtimestamp(time.time(), tz=dt_timezone.utc)
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_timezone.utc)
        return parsed.astimezone(dt_timezone.utc)

    async def _post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers={'Content-Type': 'application/json'})
        return {'status_code': response.status_code, 'body': response.text}
