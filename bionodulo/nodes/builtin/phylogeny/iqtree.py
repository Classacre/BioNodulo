"""iqtree node(s) — phylogeny category (extracted, one tool per file)."""
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



class IQTREENode(CommandNode):
    """Phylogenetic tree inference with IQ-TREE."""
    NODE_ID = 'iqtree'
    DISPLAY_NAME = 'IQ-TREE'
    REQUIRED_CONDA_PACKAGES = ['iqtree']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Efficient phylogenomic inference with maximum likelihood'
    SEARCH_ALIASES = ['iqtree', 'maximum likelihood', 'tree', 'phylogeny']
    RETURN_TYPES = ('PHYLOGENY_TREE',)
    RETURN_NAMES = ('tree',)
    REQUIRED_EXECUTABLES = ['iqtree']
    DOCUMENTATION_URL = 'http://www.iqtree.org/'
    VERSION = '2.3.4'
    COMMAND = ['iqtree', '-s', '{inputs.alignment}', '-nt', '{inputs.threads}', '-pre', '{output}/tree', '-m', '{inputs.model}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('ALIGNMENT', {'description': 'Multiple sequence alignment'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'model': ('STRING', {'default': 'MFP', 'description': 'Substitution model: MFP, GTR+I+G, LG+I+G, etc.'}), 'bootstrap': ('INT', {'default': 1000, 'min': 0, 'max': 10000, 'step': 100, 'display': 'slider'}), 'alrt': ('INT', {'default': 1000, 'min': 0})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        threads = str(inputs.get('threads', 4))
        cmd = ['iqtree', '-s', str(inputs.get('alignment', '')), '-nt', 'AUTO', '-ntmax', threads, '-pre', f"{inputs.get('output', '.')}/tree", '-m', str(inputs.get('model', 'MFP'))]
        if inputs.get('bootstrap'):
            cmd.extend(['-bb', str(inputs['bootstrap'])])
        if inputs.get('alrt'):
            cmd.extend(['-alrt', str(inputs['alrt'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'tree.treefile']
