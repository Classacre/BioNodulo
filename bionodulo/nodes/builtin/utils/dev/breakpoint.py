"""breakpoint — utils/dev node(s). One tool per file (extracted from utility_dev.py)."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {'', '0', 'false', 'f', 'no', 'n', 'off', 'none', 'null'}:
        return False
    return True


class BreakpointNode(BaseNode):
    """Interactive debugging pause point with safe non-pausing bypass paths."""
    NODE_ID = 'breakpoint'
    DISPLAY_NAME = 'Breakpoint'
    CATEGORY = 'utils/dev'
    DESCRIPTION = 'Pause execution to inspect values - resume, step over, or abort'
    SEARCH_ALIASES = ['breakpoint', 'pause', 'inspect', 'interactive', 'stop', 'halt']
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('value',)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('STRING', {'default': '', 'multiline': True, 'description': 'Value to inspect'})}, 'optional': {'enabled': ('BOOLEAN', {'default': True, 'description': 'Enable this breakpoint'}), 'label': ('STRING', {'default': '', 'description': 'Breakpoint label'}), 'condition': ('STRING', {'default': '', 'description': 'Only break if this string is in the value'}), 'timeout': ('INT', {'default': 300, 'min': 0, 'description': 'Auto-resume after N seconds (0 = never)'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        value = kwargs.get('value', '')
        text = str(value)
        enabled = bool(kwargs.get('enabled', True))
        condition = str(kwargs.get('condition', '') or '')
        if not enabled or (condition and condition not in text):
            return (text,)
        timeout = int(kwargs.get('timeout', 300) or 0)
        label = str(kwargs.get('label', '') or 'default')
        print(f'[BREAKPOINT: {label}] execution paused\n{text}')
        if timeout > 0:
            await asyncio.sleep(timeout)
        return (text,)
