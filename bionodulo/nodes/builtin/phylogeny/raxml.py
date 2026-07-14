"""raxml node(s) — phylogeny category (extracted, one tool per file)."""
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



class RAxMLNode(CommandNode):
    """Phylogenetic tree inference with RAxML."""
    NODE_ID = 'raxml'
    DISPLAY_NAME = 'RAxML'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Maximum likelihood phylogenetic inference with RAxML'
    SEARCH_ALIASES = ['raxml', 'maximum likelihood', 'tree', 'evolution']
    RETURN_TYPES = ('PHYLOGENY_TREE',)
    RETURN_NAMES = ('tree',)
    REQUIRED_EXECUTABLES = ['raxmlHPC']
    REQUIRED_CONDA_PACKAGES = ['raxml']
    DOCUMENTATION_URL = 'https://github.com/stamatak/standard-RAxML'
    VERSION = '8.2.12'
    COMMAND = ['raxmlHPC', '-s', '{inputs.alignment}', '-n', '{inputs.prefix}', '-m', '{inputs.model}', '-p', '12345', '-T', '{inputs.threads}', '-w', '{output}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('ALIGNMENT', {'description': 'Phylip-formatted alignment'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'}), 'model': ('STRING', {'default': 'GTRGAMMA', 'description': 'Substitution model'}), 'prefix': ('STRING', {'default': 'tree'})}, 'optional': {'bootstrap': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['raxmlHPC', '-s', str(inputs.get('alignment', '')), '-n', str(inputs.get('prefix', 'tree')), '-m', str(inputs.get('model', 'GTRGAMMA')), '-p', '12345', '-T', str(inputs.get('threads', 4)), '-w', os.path.abspath(str(inputs.get('output', '.')))]
        if inputs.get('bootstrap'):
            cmd.extend(['-b', '12345', '-#', '100'])
        return cmd


class RAxMLNGNode(CommandNode):
    """Phylogenetic tree inference with RAxML-NG."""
    NODE_ID = 'raxml_ng'
    DISPLAY_NAME = 'RAxML-NG'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Maximum likelihood phylogenetic tree inference with RAxML-NG.'
    SEARCH_ALIASES = ['raxml-ng', 'raxml', 'maximum likelihood', 'phylogeny', 'bootstrap']
    RETURN_TYPES = ('NEWICK', 'FILE')
    RETURN_NAMES = ('tree', 'bootstrap')
    REQUIRED_EXECUTABLES = ['raxml-ng']
    REQUIRED_CONDA_PACKAGES = ['raxml-ng']
    DOCUMENTATION_URL = 'https://github.com/amkozlov/raxml-ng'
    VERSION = '1.2.2'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('FASTA', {'description': 'Multiple sequence alignment'}), 'model': ('STRING', {'default': 'GTR+G', 'description': 'Substitution model, e.g. GTR+G or LG+G'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'seed': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'bootstrap_replicates': ('INT', {'default': 100, 'min': 0, 'max': 10000, 'step': 100}), 'outgroup': ('STRING', {'default': '', 'description': 'Comma-separated outgroup taxa', 'advanced': True}), 'tree_search': ('BOOLEAN', {'default': True, 'description': 'Run ML tree search; disable for evaluation only'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prefix = f"{inputs.get('output', '.')}/raxml_ng"
        cmd = ['raxml-ng', '--msa', str(inputs.get('alignment', '')), '--model', str(inputs.get('model', 'GTR+G')), '--prefix', prefix, '--threads', str(inputs.get('threads', 4))]
        if inputs.get('seed'):
            cmd.extend(['--seed', str(inputs['seed'])])
        if inputs.get('tree_search', True):
            cmd.append('--all')
            if inputs.get('bootstrap_replicates'):
                cmd.extend(['--bs-trees', str(inputs['bootstrap_replicates'])])
        else:
            cmd.append('--evaluate')
        if inputs.get('outgroup'):
            cmd.extend(['--outgroup', str(inputs['outgroup'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prefix = Path(output_dir) / cls.NODE_ID / 'raxml_ng'
        prefix.parent.mkdir(parents=True, exist_ok=True)
        return [Path(f'{prefix}.raxml.bestTree'), Path(f'{prefix}.raxml.bootstraps')]
