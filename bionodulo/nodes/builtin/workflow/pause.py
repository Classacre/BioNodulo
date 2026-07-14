"""pause — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class PauseResumeNode(BaseNode):
    """Record a human review gate and optionally block until a decision."""
    NODE_ID = 'pause_resume'
    DISPLAY_NAME = 'Pause / Resume'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Human review gate. Record review requests and block execution until approval or rejection.'
    SEARCH_ALIASES = ['pause', 'human', 'approval', 'review', 'gate', 'confirm', 'breakpoint']
    RETURN_TYPES = ('ANY', 'BOOLEAN', 'JSON')
    RETURN_NAMES = ('output', 'approved', 'pause_info')
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = 'always_run'
    DEFAULT_ACTIONS = {'wait', 'approve', 'reject'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data to review before proceeding'})}, 'optional': {'message': ('STRING', {'default': 'Please review the intermediate results.', 'multiline': True}), 'timeout_seconds': ('INT', {'default': 0, 'min': 0}), 'default_action': (['wait', 'approve', 'reject'], {'default': 'wait'}), 'show_preview': ('BOOLEAN', {'default': True}), 'reviewers': ('STRING', {'default': ''})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        message = str(kwargs.get('message', 'Please review the intermediate results.') or '')
        timeout_seconds = max(0, int(kwargs.get('timeout_seconds', 0) or 0))
        default_action = str(kwargs.get('default_action', 'wait') or 'wait').lower()
        show_preview = bool(kwargs.get('show_preview', True))
        reviewers = self._reviewers(kwargs.get('reviewers', ''))
        if default_action not in self.DEFAULT_ACTIONS:
            raise ValueError(f'Unsupported default_action: {default_action}')
        status, approved = self._decision(timeout_seconds, default_action)
        pause_info: dict[str, Any] = {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'message': message, 'status': status, 'approved': approved, 'timeout_seconds': timeout_seconds, 'default_action': default_action, 'reviewers': reviewers, 'preview': self._preview(data) if show_preview else None, 'created_at': time.time(), 'review_decision_supported': True, 'engine_pause_supported': True, 'note': 'Review request recorded with persistent approval metadata; executor-level blocking pause/resume is supported.'}
        pause_file = self._write_pause_file(context, pause_info)
        if pause_file:
            pause_info['pause_file'] = pause_file
            self._write_pause_file(context, pause_info)
        _ctx_emit(context, 'pause_requested', {'run_id': pause_info['run_id'], 'node_id': pause_info['node_id'], 'message': message, 'status': status, 'approved': approved, 'timeout_seconds': timeout_seconds, 'reviewers': reviewers, 'pause_file': pause_file, 'preview_data': pause_info['preview'], 'review_decision_supported': True, 'engine_pause_supported': True})
        if status == 'waiting' and pause_file:
            pause_info = await self._wait_for_decision(Path(pause_file), context)
            status = str(pause_info.get('status', status))
            approved = bool(pause_info.get('approved', False))
        _ctx_log(context, 'info' if approved else 'warning', f'Pause / Resume requested: {status}')
        if not approved:
            raise RuntimeError(f"Pause request rejected: {pause_info.get('resolution_comment', '')}")
        return (data, approved, _json_text(pause_info))

    @staticmethod
    def _reviewers(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or '').split(',') if item.strip()]

    @staticmethod
    def _decision(timeout_seconds: int, default_action: str) -> tuple[str, bool]:
        if timeout_seconds > 0 and default_action == 'approve':
            return ('timeout_approved', True)
        if timeout_seconds > 0 and default_action == 'reject':
            return ('timeout_rejected', False)
        return ('waiting', True)

    def _preview(self, data: Any) -> dict[str, Any]:
        if isinstance(data, (str, Path)):
            path = Path(str(data))
            if path.exists():
                size = path.stat().st_size
                preview: dict[str, Any] = {'kind': 'file', 'path': str(path), 'name': path.name, 'size_bytes': size}
                if size <= 1000000:
                    try:
                        preview['text'] = path.read_text(encoding='utf-8', errors='replace')[:5000]
                    except OSError as exc:
                        preview['error'] = str(exc)
                else:
                    preview['text'] = f'File preview omitted: {path.name} is {size} bytes'
                return preview
        if isinstance(data, (dict, list)):
            return {'kind': 'json', 'text': json.dumps(data, indent=2, sort_keys=True, default=str)[:5000]}
        return {'kind': 'text', 'text': str(data)[:5000]}

    @classmethod
    def pause_store(cls, context: Any | None=None, workspace_dir: str | Path | None=None) -> PauseStateStore:
        if workspace_dir is not None:
            base = Path(workspace_dir)
        elif context is not None:
            context_workspace = getattr(context, 'workspace_dir', None)
            base = Path(context_workspace) if context_workspace else _node_output_dir(cls(), context)
        else:
            base = Path('.')
        return PauseStateStore(base / 'pause_requests')

    def _write_pause_file(self, context: Any, pause_info: dict[str, Any]) -> str:
        if context is None:
            return ''
        store = self.pause_store(context)
        return str(store.save(pause_info))

    async def _wait_for_decision(self, pause_file: Path, context: Any) -> dict[str, Any]:
        store = PauseStateStore(pause_file.parent)
        cancel_event = getattr(context, 'cancel_event', None)
        while True:
            if cancel_event is not None and cancel_event.is_set():
                try:
                    return store.cancel(pause_file)
                except (OSError, ValueError):
                    return {'pause_file': str(pause_file), 'status': 'cancelled', 'approved': False, 'resolved_at': time.time(), 'review_decision_supported': True, 'engine_pause_supported': True, 'note': 'Review request cancelled while waiting for approval.'}
            try:
                pause_info = store.load(pause_file)
            except (OSError, ValueError):
                await asyncio.sleep(0.1)
                continue
            status = str(pause_info.get('status', '') or '').lower()
            if status in {'approved', 'rejected', 'cancelled'}:
                pause_info.setdefault('pause_file', str(pause_file))
                return pause_info
            await asyncio.sleep(0.1)

    @staticmethod
    def resolve_pause_request(pause_file: str | Path, action: str, reviewer: str='', comment: str='') -> dict[str, Any]:
        path = Path(pause_file)
        return PauseStateStore(path.parent).resolve(pause_file=path, action=action, reviewer=reviewer, comment=comment)

    @staticmethod
    def resolve_pause_request_by_id(workspace_dir: str | Path, run_id: str, node_id: str, action: str, reviewer: str='', comment: str='') -> dict[str, Any]:
        return PauseStateStore(Path(workspace_dir) / 'pause_requests').resolve(run_id=run_id, node_id=node_id, action=action, reviewer=reviewer, comment=comment)
