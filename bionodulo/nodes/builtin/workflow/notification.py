"""notification — workflow node(s). One tool per file (extracted from workflow_enhancement.py)."""
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


class NotificationNode(BaseNode):
    """Send or record workflow notifications when this node is reached."""
    NODE_ID = 'notification'
    DISPLAY_NAME = 'Notification'
    CATEGORY = 'workflow'
    DESCRIPTION = 'Send notifications on workflow events. Supports webhook, Slack, Discord. Trigger: on complete, on error, or always.'
    SEARCH_ALIASES = ['notify', 'alert', 'slack', 'discord', 'webhook', 'email', 'message']
    RETURN_TYPES = ('BOOLEAN', 'JSON')
    RETURN_NAMES = ('success', 'delivery_info')
    REQUIRES_EXTERNAL_TOOLS = False
    SUPPORTED_CHANNELS = {'webhook', 'slack', 'discord', 'email', 'log', 'noop'}
    SUPPORTED_TRIGGERS = {'on_complete', 'on_error', 'always'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'trigger': (['on_complete', 'on_error', 'always'], {'default': 'always'}), 'channel': (['webhook', 'slack', 'discord', 'email', 'log', 'noop'], {'default': 'webhook'})}, 'optional': {'webhook_url': ('STRING', {'default': ''}), 'message': ('STRING', {'default': 'Workflow notification', 'multiline': True}), 'include_results': ('BOOLEAN', {'default': False}), 'secret_key': ('STRING', {'default': '', 'description': 'Secret key that resolves to a webhook URL'}), 'timeout_seconds': ('FLOAT', {'default': 10.0, 'min': 0.1}), 'smtp_host': ('STRING', {'default': '', 'description': 'SMTP host for email notifications'}), 'smtp_port': ('INT', {'default': 587, 'min': 1, 'max': 65535}), 'smtp_username': ('STRING', {'default': ''}), 'smtp_password': ('STRING', {'default': '', 'password': True}), 'smtp_from': ('STRING', {'default': ''}), 'smtp_to': ('STRING', {'default': '', 'description': 'Comma-separated email recipients'}), 'smtp_use_tls': ('BOOLEAN', {'default': True})}, 'hidden': {'context': ('CONTEXT', {})}}

    async def run(self, **kwargs: Any) -> tuple[bool, str]:
        context = kwargs.pop('context', None)
        trigger = str(kwargs.get('trigger', 'always') or 'always').lower()
        channel = str(kwargs.get('channel', 'webhook') or 'webhook').lower()
        if trigger not in self.SUPPORTED_TRIGGERS:
            raise ValueError(f'Unsupported notification trigger: {trigger}')
        if channel not in self.SUPPORTED_CHANNELS:
            raise ValueError(f'Unsupported notification channel: {channel}')
        webhook_url = str(kwargs.get('webhook_url', '') or '')
        message = str(kwargs.get('message', 'Workflow notification') or 'Workflow notification')
        include_results = bool(kwargs.get('include_results', False))
        secret_key = str(kwargs.get('secret_key', '') or '')
        timeout = max(0.1, float(kwargs.get('timeout_seconds', 10.0) or 10.0))
        webhook_url = self._resolve_webhook_url(webhook_url, secret_key, context)
        run_info = {'run_id': getattr(context, 'run_id', 'unknown'), 'node_id': getattr(context, 'node_id', self.NODE_ID), 'trigger': trigger, 'status': getattr(context, 'status', '')}
        payload = self._build_payload(channel, message, run_info)
        if include_results and context is not None:
            payload['run_metadata'] = getattr(context, 'run_metadata', {})
        delivery_info: dict[str, Any] = {'channel': channel, 'trigger': trigger, 'status': 'pending', 'message_length': len(message), 'webhook_url_configured': bool(webhook_url), 'payload': payload if channel in {'log', 'noop'} else self._redacted_payload(payload)}
        if channel == 'noop':
            delivery_info['status'] = 'skipped'
            delivery_info['reason'] = 'No-op notification channel'
            _ctx_log(context, 'info', f'Notification [noop]: {message}')
            return (True, _json_text(delivery_info))
        if channel == 'log':
            delivery_info['status'] = 'delivered'
            _ctx_log(context, 'info', f'Notification [log]: {message}')
            return (True, _json_text(delivery_info))
        if channel == 'email':
            settings = self._resolve_email_settings(kwargs)
            delivery_info.update({'smtp_host_configured': bool(settings['host']), 'recipients': settings['to_addresses']})
            if not settings['host'] or not settings['to_addresses']:
                delivery_info['status'] = 'skipped'
                delivery_info['reason'] = 'No SMTP host or recipients configured'
                _ctx_log(context, 'warning', 'Notification [email] skipped: no SMTP host or recipients configured')
                return (False, _json_text(delivery_info))
            try:
                email_result = await self._send_email(settings, payload, timeout)
            except Exception as exc:
                delivery_info.update({'status': 'failed', 'error': str(exc)})
                _ctx_log(context, 'error', f'Notification [email] failed: {exc}')
                return (False, _json_text(delivery_info))
            recipients = [str(item) for item in email_result.get('recipients', settings['to_addresses'])]
            delivery_info.update({'status': 'delivered', 'message_id': email_result.get('message_id', ''), 'recipients': recipients})
            _ctx_log(context, 'info', f'Notification [email] delivered to {len(recipients)} recipient(s)')
            return (True, _json_text(delivery_info))
        if not webhook_url:
            delivery_info['status'] = 'skipped'
            delivery_info['reason'] = 'No webhook URL configured'
            _ctx_log(context, 'warning', f'Notification [{channel}] skipped: no webhook URL configured')
            return (False, _json_text(delivery_info))
        try:
            response = await self._post_json(webhook_url, payload, timeout)
        except Exception as exc:
            delivery_info.update({'status': 'failed', 'error': str(exc)})
            _ctx_log(context, 'error', f'Notification [{channel}] failed: {exc}')
            return (False, _json_text(delivery_info))
        status_code = int(response.get('status_code', 0) or 0)
        success = 200 <= status_code < 300
        delivery_info.update({'status': 'delivered' if success else 'failed', 'http_status': status_code, 'response_body': str(response.get('body', ''))[:500]})
        _ctx_log(context, 'info' if success else 'warning', f'Notification [{channel}] HTTP {status_code}')
        return (success, _json_text(delivery_info))

    def _build_payload(self, channel: str, message: str, run_info: dict[str, Any]) -> dict[str, Any]:
        if channel == 'slack':
            return {'text': message, 'blocks': [{'type': 'section', 'text': {'type': 'mrkdwn', 'text': f"*{run_info.get('run_id', 'unknown')}*"}}, {'type': 'section', 'text': {'type': 'mrkdwn', 'text': message}}]}
        if channel == 'discord':
            color = 2278750 if run_info.get('status') == 'completed' else 15680580
            return {'content': message, 'embeds': [{'title': f"BioNodulo: {run_info.get('run_id', 'unknown')}", 'description': message, 'color': color}]}
        return {'message': message, 'run_id': run_info.get('run_id'), 'node_id': run_info.get('node_id'), 'trigger': run_info.get('trigger'), 'status': run_info.get('status')}

    @staticmethod
    def _resolve_webhook_url(webhook_url: str, secret_key: str, context: Any) -> str:
        if not secret_key or context is None or (not hasattr(context, 'resolve_secret')):
            return webhook_url
        resolved = context.resolve_secret(secret_key)
        return str(resolved or webhook_url)

    @staticmethod
    def _redacted_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(payload, default=str))

    @staticmethod
    def _resolve_email_settings(inputs: dict[str, Any]) -> dict[str, Any]:
        host = str(inputs.get('smtp_host', '') or os.environ.get('BIONODULO_SMTP_HOST', '')).strip()
        port = int(inputs.get('smtp_port', 0) or os.environ.get('BIONODULO_SMTP_PORT', '587') or 587)
        username = str(inputs.get('smtp_username', '') or os.environ.get('BIONODULO_SMTP_USERNAME', '')).strip()
        password = str(inputs.get('smtp_password', '') or os.environ.get('BIONODULO_SMTP_PASSWORD', ''))
        from_address = str(inputs.get('smtp_from', '') or os.environ.get('BIONODULO_SMTP_FROM', '')).strip()
        to_text = str(inputs.get('smtp_to', '') or os.environ.get('BIONODULO_SMTP_TO', '')).strip()
        use_tls_raw = inputs.get('smtp_use_tls', os.environ.get('BIONODULO_SMTP_USE_TLS', 'true'))
        if isinstance(use_tls_raw, str):
            use_tls = use_tls_raw.strip().lower() not in {'0', 'false', 'no', 'off'}
        else:
            use_tls = bool(use_tls_raw)
        to_addresses = [item.strip() for item in re.split('[,;\\n]+', to_text) if item.strip()]
        return {'host': host, 'port': port, 'username': username, 'password': password, 'from_address': from_address or username, 'to_addresses': to_addresses, 'use_tls': use_tls}

    async def _send_email(self, settings: dict[str, Any], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return await asyncio.to_thread(self._send_email_sync, settings, payload, timeout)

    @staticmethod
    def _send_email_sync(settings: dict[str, Any], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        from_address = str(settings.get('from_address', '') or '')
        recipients = [str(item) for item in settings.get('to_addresses', [])]
        if not from_address:
            raise ValueError('SMTP from address is required')
        if not recipients:
            raise ValueError('At least one email recipient is required')
        message = EmailMessage()
        message['Subject'] = f"BioNodulo notification: {payload.get('run_id', 'workflow')}"
        message['From'] = from_address
        message['To'] = ', '.join(recipients)
        message.set_content('\n'.join([str(payload.get('message', 'Workflow notification')), '', f"Run ID: {payload.get('run_id', '')}", f"Node ID: {payload.get('node_id', '')}", f"Trigger: {payload.get('trigger', '')}", f"Status: {payload.get('status', '')}"]))
        with smtplib.SMTP(str(settings['host']), int(settings['port']), timeout=timeout) as smtp:
            if settings.get('use_tls'):
                smtp.starttls()
            username = str(settings.get('username', '') or '')
            password = str(settings.get('password', '') or '')
            if username or password:
                smtp.login(username, password)
            refused = smtp.send_message(message)
        if refused:
            raise RuntimeError(f'SMTP refused recipients: {sorted(refused)}')
        return {'message_id': message.get('Message-ID', ''), 'recipients': recipients}

    async def _post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers={'Content-Type': 'application/json'})
        return {'status_code': response.status_code, 'body': response.text}
