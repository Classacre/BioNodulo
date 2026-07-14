"""batch — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class BatchSubmitterNode(BaseNode):
    """Create or queue one workflow run for each parameter set."""
    NODE_ID = 'batch_submitter'
    DISPLAY_NAME = 'Batch Submitter'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Submit array jobs to batch systems. Monitor completion and collect results. Extends HPC integration.'
    SEARCH_ALIASES = ['batch', 'array', 'slurm', 'hpc', 'submit', 'queue', 'cluster', 'parallel']
    RETURN_TYPES = ('JSON', 'JSON', 'FILE')
    RETURN_NAMES = ('job_ids', 'status_summary', 'batch_log')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'workflow_template': ('STRING', {'multiline': True}), 'param_matrix': ('JSON', {})}, 'optional': {'scheduler': ('STRING', {'default': 'slurm'}), 'array_size': ('INT', {'default': 0, 'min': 0}), 'poll_interval_seconds': ('INT', {'default': 60, 'min': 5}), 'max_wait_seconds': ('INT', {'default': 86400, 'min': 0}), 'partition': ('STRING', {'default': ''}), 'memory_per_job': ('STRING', {'default': '8G'}), 'walltime': ('STRING', {'default': '04:00:00'})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        context = kwargs.pop('context', None)
        scheduler = str(kwargs.get('scheduler', 'slurm') or 'slurm')
        array_size = max(0, int(kwargs.get('array_size', 0) or 0))
        partition = str(kwargs.get('partition', '') or '')
        memory_per_job = str(kwargs.get('memory_per_job', '8G') or '8G')
        walltime = str(kwargs.get('walltime', '04:00:00') or '04:00:00')
        workflow_template = self._parse_workflow_template(kwargs.get('workflow_template', '{}'))
        param_sets = self._parse_param_matrix(kwargs.get('param_matrix', []))
        output_dir = _node_output_dir(self, context)
        queue = getattr(context, 'queue', None) if context is not None else None
        hpc_backend = getattr(context, 'hpc_backend', None) if context is not None else None
        queue_submission_supported = queue is not None and hasattr(queue, 'submit')
        hpc_submission_supported = not queue_submission_supported and hpc_backend is not None and hasattr(hpc_backend, 'submit_workflow')
        jobs: list[dict[str, Any]] = []
        for index, params in enumerate(param_sets):
            workflow = self._fill_template(workflow_template, params)
            if queue_submission_supported:
                job = await self._submit_to_queue(queue, workflow, params, index, scheduler, context)
            elif hpc_submission_supported:
                job = await self._submit_to_hpc_backend(hpc_backend, workflow, params, index, scheduler, memory_per_job, walltime)
            else:
                job = self._write_planned_workflow(output_dir, workflow, params, index, context)
            jobs.append(job)
        summary = self._summary(jobs=jobs, scheduler=scheduler, array_size=array_size, partition=partition, memory_per_job=memory_per_job, walltime=walltime, queue_submission_supported=queue_submission_supported, hpc_submission_supported=hpc_submission_supported)
        log_path = output_dir / 'batch_submitter_log.json'
        log_payload = {'summary': summary, 'jobs': jobs}
        log_path.write_text(json.dumps(log_payload, indent=2, sort_keys=True, default=str), encoding='utf-8')
        event_payload = {'run_id': getattr(context, 'run_id', ''), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'scheduler': scheduler, 'total': summary['total'], 'queued': summary['queued'], 'planned': summary['planned'], 'failed': summary['failed'], 'batch_log': str(log_path)}
        _ctx_emit(context, 'batch_submitted', event_payload)
        action = 'queued' if queue_submission_supported else 'submitted' if hpc_submission_supported else 'planned'
        _ctx_log(context, 'info', f"Batch Submitter {action} {summary['total']} jobs via {scheduler}")
        return (json.dumps(jobs, sort_keys=True, default=str), _json_text(summary), str(log_path))

    @staticmethod
    def _parse_workflow_template(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value or '{}')
            except json.JSONDecodeError as exc:
                raise ValueError(f'workflow_template must be valid JSON: {exc}') from exc
        if not isinstance(value, dict):
            raise ValueError('workflow_template must be a JSON object')
        return value

    @staticmethod
    def _parse_param_matrix(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, str):
            try:
                value = json.loads(value or '[]')
            except json.JSONDecodeError as exc:
                raise ValueError(f'param_matrix must be valid JSON: {exc}') from exc
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            raise ValueError('param_matrix must be a JSON array or object')
        param_sets: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f'param_matrix entry {index} must be a JSON object')
            param_sets.append(item)
        return param_sets

    async def _submit_to_queue(self, queue: Any, workflow: dict[str, Any], params: dict[str, Any], index: int, scheduler: str, context: Any) -> dict[str, Any]:
        metadata = {'source': self.NODE_ID, 'parent_run_id': getattr(context, 'run_id', ''), 'parent_node_id': getattr(context, 'node_id', self.NODE_ID), 'batch_index': index, 'scheduler': scheduler, 'params': params}
        try:
            job_id = await queue.submit(workflow=workflow, metadata=metadata)
        except Exception as exc:
            return {'index': index, 'job_id': None, 'status': 'failed', 'error': str(exc), 'params': params}
        return {'index': index, 'job_id': str(job_id), 'status': 'queued', 'params': params}

    async def _submit_to_hpc_backend(self, hpc_backend: Any, workflow: dict[str, Any], params: dict[str, Any], index: int, scheduler: str, memory_per_job: str, walltime: str) -> dict[str, Any]:
        try:
            job_id = await hpc_backend.submit_workflow(workflow=workflow, name=str(workflow.get('name') or f'batch_job_{index}'), cpus=None, memory=memory_per_job, walltime=walltime, dependency_jobs=[], parameters=params)
        except Exception as exc:
            return {'index': index, 'job_id': None, 'status': 'failed', 'error': str(exc), 'scheduler': scheduler, 'params': params}
        return {'index': index, 'job_id': str(job_id), 'status': 'submitted', 'scheduler': scheduler, 'params': params}

    def _write_planned_workflow(self, output_dir: Path, workflow: dict[str, Any], params: dict[str, Any], index: int, context: Any) -> dict[str, Any]:
        workflow_file = output_dir / f'batch_job_{index}.json'
        workflow_file.write_text(json.dumps(workflow, indent=2, sort_keys=True, default=str), encoding='utf-8')
        node_id = getattr(context, 'node_id', self.NODE_ID)
        return {'index': index, 'job_id': f'planned:{node_id}:{index}', 'status': 'planned', 'workflow_file': str(workflow_file), 'params': params}

    @classmethod
    def _fill_template(cls, value: Any, params: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: cls._fill_template(item, params) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._fill_template(item, params) for item in value]
        if isinstance(value, str):
            return cls._replace_placeholders(value, params)
        return value

    @staticmethod
    def _replace_placeholders(value: str, params: dict[str, Any]) -> str:
        rendered = value
        for key in sorted(params):
            rendered = rendered.replace(f'{{{{{key}}}}}', str(params[key]))
        return rendered

    @staticmethod
    def _summary(*, jobs: list[dict[str, Any]], scheduler: str, array_size: int, partition: str, memory_per_job: str, walltime: str, queue_submission_supported: bool, hpc_submission_supported: bool=False) -> dict[str, Any]:
        return {'total': len(jobs), 'queued': sum((1 for job in jobs if job.get('status') == 'queued')), 'submitted': sum((1 for job in jobs if job.get('status') == 'submitted')), 'planned': sum((1 for job in jobs if job.get('status') == 'planned')), 'completed': sum((1 for job in jobs if job.get('status') == 'completed')), 'failed': sum((1 for job in jobs if job.get('status') == 'failed')), 'scheduler': scheduler, 'array_size': array_size, 'partition': partition, 'memory_per_job': memory_per_job, 'walltime': walltime, 'queue_submission_supported': queue_submission_supported, 'hpc_submission_supported': hpc_submission_supported}
