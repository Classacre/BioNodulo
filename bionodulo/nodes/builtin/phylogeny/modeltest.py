"""modeltest node(s) — phylogeny category (extracted, one tool per file)."""
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



class ModelTestNGNode(CommandNode):
    """Substitution model selection with ModelTest-NG."""
    NODE_ID = 'modeltest_ng'
    DISPLAY_NAME = 'ModelTest-NG'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Select best-fit substitution model for phylogenetic analysis.'
    SEARCH_ALIASES = ['modeltest-ng', 'modeltest', 'substitution model', 'model selection', 'phylogeny']
    RETURN_TYPES = ('STRING', 'JSON')
    RETURN_NAMES = ('best_model', 'model_stats')
    REQUIRED_EXECUTABLES = ['modeltest-ng']
    REQUIRED_CONDA_PACKAGES = ['modeltest-ng']
    DOCUMENTATION_URL = 'https://github.com/ddarriba/modeltest'
    VERSION = '0.1.7'
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('FASTA', {'description': 'Multiple sequence alignment'}), 'datatype': ('STRING', {'default': 'nt', 'options': ['nt', 'aa']}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'template': ('STRING', {'default': '', 'options': ['', 'raxml', 'phyml', 'mrbayes', 'paup']}), 'models': ('STRING', {'default': '', 'description': 'Optional comma-separated model subset'}), 'schemes': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'ascertainment_bias': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get('output', '.'))
        output_prefix = f'{out_dir}/modeltest'
        best_model = f'{out_dir}/best_model.txt'
        model_stats = f'{out_dir}/model_stats.json'
        cmd = ['modeltest-ng', '-i', str(inputs.get('alignment', '')), '-d', str(inputs.get('datatype', 'nt')), '-p', str(inputs.get('threads', 4)), '-o', output_prefix]
        if inputs.get('template'):
            cmd.extend(['-T', str(inputs['template'])])
        if inputs.get('models'):
            cmd.extend(['-m', str(inputs['models'])])
        if inputs.get('schemes'):
            cmd.extend(['-s', str(inputs['schemes'])])
        if inputs.get('ascertainment_bias'):
            cmd.append('--asc-bias')
        best_model_payload = f"'best_model\\tSee {output_prefix}.out\\n'"
        model_stats_payload = f"""'{{\\n  "modeltest_output": "{output_prefix}.out",\\n  "ranking": "{output_prefix}.ranking"\\n}}\\n'"""
        cmd.extend(['&&', 'printf', best_model_payload, '>', best_model])
        cmd.extend(['&&', 'printf', model_stats_payload, '>', model_stats])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'best_model.txt', node_out / 'model_stats.json']
