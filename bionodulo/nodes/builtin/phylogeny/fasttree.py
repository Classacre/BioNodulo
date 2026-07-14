"""fasttree node(s) — phylogeny category (extracted, one tool per file)."""
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



class FastTreeNode(CommandNode):
    """Fast phylogenetic tree inference with FastTree."""
    NODE_ID = 'fasttree'
    DISPLAY_NAME = 'FastTree'
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Approximately maximum-likelihood phylogenetic tree inference'
    SEARCH_ALIASES = ['fasttree', 'quick tree', 'approximate ml']
    RETURN_TYPES = ('PHYLOGENY_TREE',)
    RETURN_NAMES = ('tree',)
    REQUIRED_EXECUTABLES = ['FastTree']
    REQUIRED_CONDA_PACKAGES = ['fasttree']
    DOCUMENTATION_URL = 'http://www.microbesonline.org/fasttree/'
    VERSION = '2.1.11'
    COMMAND = ['FastTree', '-gamma', '-boot', '100', '{inputs.alignment}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('ALIGNMENT', {'description': 'Multiple sequence alignment (protein or nucleotide)'})}, 'optional': {'nucleotide': ('BOOLEAN', {'default': False, 'description': 'Use nucleotide model instead of protein'}), 'gtr': ('BOOLEAN', {'default': False, 'description': 'Use GTR model for nucleotides'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['FastTree']
        if inputs.get('nucleotide'):
            cmd.append('-nt')
        if inputs.get('gtr'):
            cmd.append('-gtr')
        cmd.extend(['-gamma', '-boot', '100'])
        cmd.append(str(inputs.get('alignment', '')))
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Run FastTree and capture stdout to the output file."""
        import shutil
        from pathlib import Path
        context = kwargs.get('context')
        output_dir = kwargs.get('output_dir')
        if output_dir is None and context is not None:
            output_dir = getattr(context, 'node_dir', '.')
        result = await super().run(**kwargs)
        if output_dir:
            stdout_log = Path(output_dir) / 'stdout.log'
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if stdout_log.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(stdout_log), str(target))
        return result
