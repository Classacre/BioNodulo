"""astral node(s) — phylogeny category (extracted, one tool per file)."""
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



class ASTRALNode(CommandNode):
    """Estimate species trees from gene trees with ASTRAL-III."""
    NODE_ID = 'astral'
    DISPLAY_NAME = 'ASTRAL-III'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Estimate an unrooted species tree from unrooted gene trees with ASTRAL-III.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'ASTRAL', 'ASTRAL-III', 'astral', 'species tree', 'gene tree', 'quartet support', 'coalescent', 'incomplete lineage sorting', 'phylogenomics']
    RETURN_TYPES = ('PHYLOGENY_TREE', 'TXT', 'TSV')
    RETURN_NAMES = ('output', 'log_output', 'branch_annotations')
    REQUIRED_EXECUTABLES = ['astral']
    REQUIRED_CONDA_PACKAGES = ['astral-tree']
    DOCUMENTATION_URL = 'https://github.com/smirarab/ASTRAL'
    CITATION_DOIS = ['10.1186/s12859-018-2129-y']
    CITATION_URLS = ['https://doi.org/10.1186/s12859-018-2129-y']
    CITATION_TEXT = 'ASTRAL-III: polynomial time species tree reconstruction from partially resolved gene trees.'
    VERSION = '5.7.8+galaxy0'
    SHELL = True
    BRANCH_ANNOTATE_OPTIONS = ['0', '1', '2', '3', '4', '8', '16', '32', '10']

    @classmethod
    def _branch_annotate(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('branch_annotate', '3') or '3')

    @classmethod
    def _lambda_value(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('lambda', 0.5)

    @classmethod
    def _export_branch_annotations(cls, inputs: dict[str, Any]) -> bool:
        return cls._branch_annotate(inputs) in {'16', '32'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('PHYLOGENY_TREE', {'description': 'Newick gene tree file'})}, 'optional': {'branch_annotate': ('STRING', {'default': '3', 'options': cls.BRANCH_ANNOTATE_OPTIONS, 'description': 'ASTRAL -t branch annotation mode'}), 'lambda': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 10, 'description': 'Yule prior lambda parameter for branch lengths and posterior probabilities'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input tree file is required'
        branch_annotate = cls._branch_annotate(inputs)
        if branch_annotate not in cls.BRANCH_ANNOTATE_OPTIONS:
            return f"branch_annotate must be one of: {', '.join(cls.BRANCH_ANNOTATE_OPTIONS)}"
        try:
            lambda_value = float(cls._lambda_value(inputs))
        except (TypeError, ValueError):
            return 'lambda must be numeric'
        if lambda_value < 0 or lambda_value > 10:
            return 'lambda must be between 0 and 10'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = str(inputs.get('output', '.'))
        cmd = ['astral', '--input', str(inputs.get('input', '')), '--branch-annotate', cls._branch_annotate(inputs), '--output', './output.tre', '--lambda', str(cls._lambda_value(inputs)), '2>&1', '|', 'tee', f'{out_dir}/log_output.txt']
        commands = [f'mkdir -p {shlex.quote(out_dir)}', f'cd {shlex.quote(out_dir)}', ' '.join((shlex.quote(part) for part in cmd)).replace("'2>&1'", '2>&1').replace("'|'", '|'), f"mv ./output.tre {shlex.quote(f'{out_dir}/output.tre')}"]
        if cls._export_branch_annotations(inputs):
            commands.append(f"mv freqQuad.csv {shlex.quote(f'{out_dir}/branch_annotations.tsv')}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / 'output.tre', node_out / 'log_output.txt']
        if cls._export_branch_annotations(inputs):
            outputs.append(node_out / 'branch_annotations.tsv')
        return outputs
