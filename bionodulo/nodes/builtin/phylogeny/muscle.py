"""muscle node(s) — phylogeny category (extracted, one tool per file)."""
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



class MUSCLENode(CommandNode):
    """Multiple sequence alignment with MUSCLE."""
    NODE_ID = 'muscle'
    DISPLAY_NAME = 'MUSCLE'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Multiple sequence alignment with MUSCLE, especially for protein sequences.'
    SEARCH_ALIASES = ['muscle', 'align', 'msa', 'multiple alignment', 'protein alignment']
    RETURN_TYPES = ('ALIGNMENT',)
    RETURN_NAMES = ('alignment',)
    REQUIRED_EXECUTABLES = ['muscle']
    REQUIRED_CONDA_PACKAGES = ['muscle']
    DOCUMENTATION_URL = 'https://drive5.com/muscle/'
    VERSION = '5.3'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sequences': ('FASTA', {'description': 'Input sequences FASTA'})}, 'optional': {'maxiters': ('INT', {'default': 0, 'min': 0, 'description': 'Maximum refinement iterations; 0 uses MUSCLE default'}), 'diags': ('BOOLEAN', {'default': False, 'description': 'Use diagonal optimization for similar sequences'}), 'stable': ('BOOLEAN', {'default': False, 'description': 'Preserve input sequence order in output'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['muscle', '-align', str(inputs.get('sequences', '')), '-output', f"{inputs.get('output', '.')}/alignment.aln.fasta"]
        if inputs.get('maxiters'):
            cmd.extend(['-maxiters', str(inputs['maxiters'])])
        if inputs.get('diags'):
            cmd.append('-diags')
        if inputs.get('stable'):
            cmd.append('-stable')
        return cmd
