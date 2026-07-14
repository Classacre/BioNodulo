"""Shared helpers/constants for the phylogeny node category."""
from __future__ import annotations

from __future__ import annotations
import asyncio
import json
import os
import re
import shlex
import time
from pathlib import Path
from io import StringIO
from typing import Any
from xml.etree import ElementTree as ET
import httpx
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
from bionodulo.nodes.command_node import CommandNode


MAX_RETRIES = 3

RETRY_DELAY_S = 1.0

REQUEST_TIMEOUT_S = 60.0

def _phylogeny_node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def _split_text_list(value: Any) -> list[str]:
    items: list[str] = []
    for chunk in str(value or '').replace(',', '\n').splitlines():
        stripped = chunk.strip()
        if stripped:
            items.append(stripped)
    return items

def _safe_filename(value: str, default: str) -> str:
    name = re.sub('[^A-Za-z0-9._-]+', '_', value).strip('._')
    return name or default

def _html_to_text(value: str) -> str:
    text = re.sub('(?is)<(script|style).*?</\\1>', ' ', value)
    text = re.sub('(?s)<[^>]+>', ' ', text)
    return re.sub('\\s+', ' ', text).strip()
