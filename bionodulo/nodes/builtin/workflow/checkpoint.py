"""checkpoint — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class CheckpointNode(BaseNode):
    """Persist a workflow value to a checkpoint artifact."""
    NODE_ID = 'checkpoint'
    DISPLAY_NAME = 'Checkpoint'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Save workflow state snapshot. Persist intermediate results for resumable workflows.'
    SEARCH_ALIASES = ['checkpoint', 'snapshot', 'save', 'resume', 'persist', 'state']
    RETURN_TYPES = ('ANY', 'FILE', 'JSON')
    RETURN_NAMES = ('passthrough', 'checkpoint_file', 'checkpoint_info')
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = 'always_run'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('ANY', {'description': 'Data to checkpoint'})}, 'optional': {'checkpoint_name': ('STRING', {'default': '', 'description': 'Checkpoint name; generated from node and time when empty'}), 'include_upstream_metadata': ('BOOLEAN', {'default': True}), 'compression': ('BOOLEAN', {'default': True})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[Any, str, str]:
        context = kwargs.pop('context', None)
        data = kwargs.get('input')
        include_metadata = bool(kwargs.get('include_upstream_metadata', True))
        compress = bool(kwargs.get('compression', True))
        checkpoint_name = self._checkpoint_name(kwargs.get('checkpoint_name', ''), context)
        checkpoint_dir = self._checkpoint_dir(context)
        timestamp = time.time()
        payload: dict[str, Any] = {'version': '1.0', 'checkpoint_name': checkpoint_name, 'timestamp': timestamp, 'timestamp_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp)), 'data': data}
        if include_metadata and context is not None:
            payload['run_metadata'] = self._context_metadata(context)
        suffix = '.json.gz' if compress else '.json'
        checkpoint_path = (checkpoint_dir / f'{checkpoint_name}{suffix}').resolve()
        json_bytes = json.dumps(payload, indent=2, sort_keys=True, default=str).encode('utf-8')
        if compress:
            checkpoint_path.write_bytes(gzip.compress(json_bytes))
        else:
            checkpoint_path.write_bytes(json_bytes)
        checkpoint_info = {'checkpoint_name': checkpoint_name, 'checkpoint_path': str(checkpoint_path), 'timestamp': timestamp, 'timestamp_iso': payload['timestamp_iso'], 'compressed': compress, 'size_bytes': checkpoint_path.stat().st_size, 'resume_manifest_supported': True, 'resume_supported': True, 'note': 'Checkpoint artifact and resume manifest written; downstream executor resume is supported for checkpoint nodes.'}
        manifest_path = self._update_checkpoint_manifest(checkpoint_dir, checkpoint_info, context)
        checkpoint_info['manifest_path'] = str(manifest_path)
        _ctx_log(context, 'info', f'Checkpoint saved: {checkpoint_path}')
        _ctx_emit(context, 'checkpoint_saved', {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'checkpoint_path': str(checkpoint_path), 'compressed': compress, 'manifest_path': str(manifest_path)})
        return (data, str(checkpoint_path), _json_text(checkpoint_info))

    def _checkpoint_dir(self, context: Any) -> Path:
        workspace_dir = getattr(context, 'workspace_dir', None) if context is not None else None
        if workspace_dir:
            base = Path(workspace_dir) / 'checkpoints'
        elif context is not None:
            base = _node_output_dir(self, context) / 'checkpoints'
        else:
            base = Path('checkpoints')
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _checkpoint_name(self, value: Any, context: Any) -> str:
        raw = str(value or '').strip()
        if not raw:
            node_id = getattr(context, 'node_id', self.NODE_ID)
            raw = f'{node_id}_{int(time.time())}'
        sanitized = re.sub('[^A-Za-z0-9_.-]+', '_', raw).strip('._')
        return sanitized or f'{self.NODE_ID}_{int(time.time())}'

    @staticmethod
    def _context_metadata(context: Any) -> dict[str, Any]:
        params = getattr(context, 'params', {})
        public_params = {key: value for key, value in params.items() if not str(key).startswith('_')} if isinstance(params, dict) else {}
        metadata = {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', ''), 'node_type': getattr(context, 'node_type', ''), 'params': public_params}
        workflow_metadata = getattr(context, 'run_metadata', None)
        if isinstance(workflow_metadata, dict) and workflow_metadata:
            metadata['workflow'] = json.loads(json.dumps(workflow_metadata, sort_keys=True, default=str))
        return metadata

    def _update_checkpoint_manifest(self, checkpoint_dir: Path, checkpoint_info: dict[str, Any], context: Any) -> Path:
        manifest_path = checkpoint_dir / 'checkpoint_manifest.json'
        manifest = self._read_checkpoint_manifest(manifest_path)
        entry = {'checkpoint_name': checkpoint_info['checkpoint_name'], 'checkpoint_path': checkpoint_info['checkpoint_path'], 'timestamp': checkpoint_info['timestamp'], 'timestamp_iso': checkpoint_info['timestamp_iso'], 'compressed': checkpoint_info['compressed'], 'size_bytes': checkpoint_info['size_bytes'], 'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'node_type': getattr(context, 'node_type', '')}
        for key in ('resume_manifest_supported', 'resume_supported', 'note'):
            if key in checkpoint_info:
                entry[key] = checkpoint_info[key]
        manifest['updated_at'] = checkpoint_info['timestamp']
        manifest['updated_at_iso'] = checkpoint_info['timestamp_iso']
        manifest.setdefault('checkpoints', {})[entry['checkpoint_path']] = entry
        manifest.setdefault('latest_by_name', {})[entry['checkpoint_name']] = entry
        manifest.setdefault('latest_by_run_node', {})[self._run_node_key(entry['run_id'], entry['node_id'])] = entry
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding='utf-8')
        return manifest_path

    @staticmethod
    def _read_checkpoint_manifest(manifest_path: Path) -> dict[str, Any]:
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                raise ValueError(f'checkpoint manifest is not valid JSON: {manifest_path}') from exc
            if not isinstance(manifest, dict):
                raise ValueError(f'checkpoint manifest must be a JSON object: {manifest_path}')
            manifest.setdefault('version', '1.0')
            manifest.setdefault('checkpoints', {})
            manifest.setdefault('latest_by_name', {})
            manifest.setdefault('latest_by_run_node', {})
            return manifest
        return {'version': '1.0', 'checkpoints': {}, 'latest_by_name': {}, 'latest_by_run_node': {}}

    @classmethod
    def resolve_checkpoint(cls, manifest_path: str | Path, run_id: str='', node_id: str='', checkpoint_name: str='') -> dict[str, Any]:
        manifest = cls._read_checkpoint_manifest(Path(manifest_path))
        if run_id or node_id:
            entry = manifest.get('latest_by_run_node', {}).get(cls._run_node_key(run_id, node_id))
            if entry:
                return dict(entry)
        if checkpoint_name:
            entry = manifest.get('latest_by_name', {}).get(checkpoint_name)
            if entry:
                return dict(entry)
        return {}

    @staticmethod
    def _run_node_key(run_id: Any, node_id: Any) -> str:
        return f'{run_id}:{node_id}'
