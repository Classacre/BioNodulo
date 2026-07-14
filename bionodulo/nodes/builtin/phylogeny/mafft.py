"""mafft node(s) — phylogeny category (extracted, one tool per file)."""
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



class MAFFTNode(CommandNode):
    """Multiple sequence alignment with MAFFT."""
    NODE_ID = 'mafft'
    DISPLAY_NAME = 'MAFFT'
    REQUIRED_CONDA_PACKAGES = ['mafft']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Multiple sequence alignment with MAFFT (fast FFT-based)'
    SEARCH_ALIASES = ['mafft', 'align', 'msa', 'multiple alignment']
    RETURN_TYPES = ('ALIGNMENT',)
    RETURN_NAMES = ('alignment',)
    REQUIRED_EXECUTABLES = ['mafft']
    DOCUMENTATION_URL = 'https://mafft.cbrc.jp/alignment/software/'
    VERSION = '7.520'
    COMMAND = ['mafft', '--thread', '{inputs.threads}', '{inputs.input}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Input sequences FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'strategy': ('STRING', {'default': 'auto', 'description': 'Alignment strategy: auto, linsi, ginsi, einsi'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        strategy = str(inputs.get('strategy', 'auto')).strip().lower()
        strategy_flags = {'auto': ['--auto'], 'linsi': ['--localpair', '--maxiterate', '1000'], 'ginsi': ['--globalpair', '--maxiterate', '1000'], 'einsi': ['--genafpair', '--maxiterate', '1000'], '': ['--auto']}
        if strategy.startswith('--'):
            flags = [strategy]
        else:
            flags = strategy_flags.get(strategy, ['--auto'])
        out_dir = str(inputs.get('output', '.'))
        out_file = f'{out_dir}/alignment.aln.fasta'
        parts = ['mafft', '--thread', str(inputs.get('threads', 4)), *flags, shlex.quote(str(inputs.get('input', ''))), '>', shlex.quote(out_file)]
        return ' '.join(parts)
