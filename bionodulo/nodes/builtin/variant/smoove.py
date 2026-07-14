"""smoove — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SmooveNode(CommandNode):
    """Call and genotype structural variants with smoove."""
    NODE_ID = 'smoove'
    DISPLAY_NAME = 'Smoove SV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Automated SV calling with smoove (LUMPY wrapper), genotyping, and quality filtering.'
    SEARCH_ALIASES = ['smoove', 'lumpy', 'structural variant', 'sv caller', 'genotyped sv']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('genotyped_sv',)
    REQUIRED_EXECUTABLES = ['smoove']
    REQUIRED_CONDA_PACKAGES = ['smoove', 'lumpy-sv', 'svtyper']
    DOCUMENTATION_URL = 'https://github.com/brentp/smoove'
    VERSION = '0.2.8'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['smoove', 'call', '--name', str(inputs.get('sample_name', 'sample')), '--fasta', str(inputs.get('reference', '')), '-p', str(inputs.get('threads', 4)), '--outdir', str(inputs.get('output', '.'))]
        if inputs.get('genotype'):
            cmd.append('--genotype')
        if inputs.get('exclude'):
            cmd.extend(['--exclude', str(inputs['exclude'])])
        cmd.append(str(inputs.get('bam', '')))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'}), 'sample_name': ('STRING', {'default': 'sample'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'exclude': ('BED', {'description': 'Exclude regions BED', 'advanced': True}), 'genotype': ('BOOLEAN', {'default': True, 'description': 'Run svtyper genotyping'})}, 'hidden': {'output': ('STRING', {})}}
