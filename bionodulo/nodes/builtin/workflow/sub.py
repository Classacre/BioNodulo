"""sub — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class SubWorkflowNode(BaseNode):
    """Prepare or execute another workflow as a nested routine."""
    NODE_ID = 'sub_workflow'
    DISPLAY_NAME = 'Sub-Workflow'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Execute another workflow as a sub-routine. Pass inputs, run the sub-workflow, receive outputs.'
    SEARCH_ALIASES = ['subworkflow', 'sub', 'nested', 'call', 'routine', 'module']
    RETURN_TYPES = ('JSON', 'FILE')
    RETURN_NAMES = ('outputs', 'run_metadata')
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = 'always_run'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'workflow_path': ('STRING', {'description': 'Path to workflow JSON file or template name'})}, 'optional': {'inputs': ('JSON', {'default': '{}', 'description': 'JSON dict of inputs'}), 'target_nodes': ('STRING', {'default': '', 'description': 'Comma-separated output node IDs'}), 'timeout_seconds': ('INT', {'default': 3600, 'min': 1}), 'inherit_secrets': ('BOOLEAN', {'default': True})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop('context', None)
        workflow_ref = str(kwargs.get('workflow_path', '') or '')
        inputs = self._parse_inputs(kwargs.get('inputs', {}))
        target_nodes = self._target_nodes(kwargs.get('target_nodes', ''))
        timeout_seconds = max(1, int(kwargs.get('timeout_seconds', 3600) or 3600))
        inherit_secrets = bool(kwargs.get('inherit_secrets', True))
        workflow_path = self._resolve_workflow_path(workflow_ref, context)
        workflow = json.loads(workflow_path.read_text(encoding='utf-8'))
        prepared_workflow = BatchSubmitterNode._fill_template(workflow, inputs)
        node_dir = _node_output_dir(self, context)
        prepared_file = node_dir / 'sub_workflow_prepared.json'
        prepared_file.write_text(json.dumps(prepared_workflow, indent=2, sort_keys=True, default=str), encoding='utf-8')
        executor = getattr(context, 'executor', None) if context is not None else None
        sub_run_id = f"{getattr(context, 'run_id', 'run')}_sub_{getattr(context, 'node_id', self.NODE_ID)}"
        if executor is None or not hasattr(executor, 'execute'):
            outputs = {'status': 'planned', 'execution_supported': False, 'workflow_path': str(workflow_path), 'prepared_workflow_file': str(prepared_file), 'inputs': inputs, 'target_nodes': target_nodes, 'note': 'Sub-workflow prepared; context.executor is not available for nested execution.'}
            metadata = {'status': 'planned', 'executor_available': False, 'execution_supported': False, 'sub_run_id': sub_run_id, 'workflow_path': str(workflow_path), 'workflow_name': prepared_workflow.get('name', workflow_path.stem), 'prepared_workflow_file': str(prepared_file), 'inputs': inputs, 'target_nodes': target_nodes}
            metadata_file = self._write_metadata(node_dir, metadata)
            _ctx_emit(context, 'sub_workflow_planned', metadata)
            _ctx_log(context, 'info', f"Sub-workflow planned: {metadata['workflow_name']}")
            return (json.dumps(outputs, sort_keys=True, default=str), metadata_file)
        options: dict[str, Any] = {'target_nodes': target_nodes}
        if inherit_secrets and context is not None and hasattr(context, 'api_secrets'):
            options['api_secrets'] = getattr(context, 'api_secrets')
        _ctx_emit(context, 'sub_workflow_started', {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'sub_run_id': sub_run_id, 'workflow_path': str(workflow_path), 'target_nodes': target_nodes})
        try:
            result = await asyncio.wait_for(executor.execute(run_id=sub_run_id, workflow=prepared_workflow, options=options, cancel_event=getattr(context, 'cancel_event', None), emit=getattr(context, 'emit', None)), timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f'Sub-workflow timed out after {timeout_seconds}s') from exc
        outputs = result.get('outputs', {})
        metadata = {'status': result.get('status', 'unknown'), 'executor_available': True, 'execution_supported': True, 'sub_run_id': sub_run_id, 'workflow_path': str(workflow_path), 'workflow_name': prepared_workflow.get('name', workflow_path.stem), 'prepared_workflow_file': str(prepared_file), 'inputs': inputs, 'target_nodes': target_nodes, 'executor_metadata': result.get('metadata', {})}
        metadata_file = self._write_metadata(node_dir, metadata)
        _ctx_emit(context, 'sub_workflow_completed', metadata)
        _ctx_log(context, 'info', f"Sub-workflow completed: {metadata['status']}")
        return (json.dumps(outputs, sort_keys=True, default=str), metadata_file)

    @staticmethod
    def _parse_inputs(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value or '{}')
            except json.JSONDecodeError as exc:
                raise ValueError(f'inputs must be valid JSON: {exc}') from exc
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError('inputs must be a JSON object')
        return value

    @staticmethod
    def _target_nodes(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or '').split(',') if item.strip()]

    @staticmethod
    def _resolve_workflow_path(workflow_ref: str, context: Any) -> Path:
        candidates: list[Path] = []
        ref_path = Path(workflow_ref)
        candidates.append(ref_path)
        workspace_dir = getattr(context, 'workspace_dir', None) if context is not None else None
        if workspace_dir is not None and (not ref_path.is_absolute()):
            workspace = Path(workspace_dir)
            candidates.append(workspace / workflow_ref)
            candidates.append(workspace / 'workflows' / workflow_ref)
            if not workflow_ref.endswith('.json'):
                candidates.append(workspace / 'workflows' / f'{workflow_ref}.json')
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f'Sub-workflow not found: {workflow_ref}')

    @staticmethod
    def _write_metadata(node_dir: Path, metadata: dict[str, Any]) -> str:
        metadata_file = node_dir / 'sub_workflow_metadata.json'
        metadata_file.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str), encoding='utf-8')
        return str(metadata_file)
