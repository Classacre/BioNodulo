"""clustalo node(s) — phylogeny category (extracted, one tool per file)."""
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



class ClustalONode(CommandNode):
    """Multiple sequence alignment with Clustal Omega."""
    NODE_ID = 'clustalo'
    DISPLAY_NAME = 'Clustal Omega'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Scalable multiple protein sequence alignment'
    SEARCH_ALIASES = ['clustal', 'clustalo', 'clustal omega', 'msa']
    RETURN_TYPES = ('ALIGNMENT',)
    RETURN_NAMES = ('alignment',)
    REQUIRED_EXECUTABLES = ['clustalo']
    REQUIRED_CONDA_PACKAGES = ['clustal-omega']
    DOCUMENTATION_URL = 'http://www.clustal.org/omega/'
    VERSION = '1.2.4'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['clustalo', '-i', str(inputs.get('input', '')), '-o', f"{inputs.get('output', '.')}/alignment.fasta", '--threads', str(inputs.get('threads', 4)), '--force']
        if inputs.get('outfmt'):
            cmd.extend(['--outfmt', str(inputs['outfmt'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Input sequences FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'outfmt': ('STRING', {'default': 'fasta'})}, 'hidden': {'output': ('STRING', {})}}
