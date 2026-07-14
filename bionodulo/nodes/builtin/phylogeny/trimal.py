"""trimal node(s) — phylogeny category (extracted, one tool per file)."""
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



class TrimAlNode(CommandNode):
    """Automated multiple sequence alignment trimming with trimAl."""
    NODE_ID = 'trimal'
    DISPLAY_NAME = 'trimAl'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Automated trimming of multiple sequence alignments before tree inference.'
    SEARCH_ALIASES = ['trimal', 'trimAl', 'alignment trimming', 'msa trim', 'phylogeny']
    RETURN_TYPES = ('FASTA', 'STATS_FILE')
    RETURN_NAMES = ('trimmed', 'stats')
    REQUIRED_EXECUTABLES = ['trimal']
    REQUIRED_CONDA_PACKAGES = ['trimal']
    DOCUMENTATION_URL = 'http://trimal.cgenomics.org/'
    VERSION = '1.4.1'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('ALIGNMENT', {'description': 'Input multiple sequence alignment'})}, 'optional': {'automated': ('STRING', {'default': 'automated1', 'options': ['automated1', 'strict', 'strictplus', 'gappyout'], 'description': 'trimAl automated trimming strategy'}), 'fasta_output': ('BOOLEAN', {'default': True, 'description': 'Write FASTA-formatted trimmed alignment'}), 'htmlout': ('BOOLEAN', {'default': False, 'description': 'Also write an HTML trimming report'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get('output', '.'))
        automated = str(inputs.get('automated', 'automated1') or 'automated1')
        if automated not in {'automated1', 'strict', 'strictplus', 'gappyout'}:
            raise ValueError(f'Unsupported trimAl automated mode: {automated}')
        cmd = ['trimal', '-in', str(inputs.get('alignment', '')), '-out', f'{out_dir}/trimmed.fasta', f'-{automated}']
        if inputs.get('fasta_output', True):
            cmd.append('-fasta')
        if inputs.get('htmlout'):
            cmd.extend(['-htmlout', f'{out_dir}/stats.html'])
        return cmd
