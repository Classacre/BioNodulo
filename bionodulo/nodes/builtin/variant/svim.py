"""svim — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SVIMNode(CommandNode):
    """Call long-read structural variants with SVIM."""
    NODE_ID = 'svim'
    DISPLAY_NAME = 'SVIM SV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Long-read SV caller optimized for Oxford Nanopore data.'
    SEARCH_ALIASES = ['svim', 'long-read sv', 'nanopore sv', 'structural variant']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('sv_vcf',)
    REQUIRED_EXECUTABLES = ['svim']
    REQUIRED_CONDA_PACKAGES = ['svim']
    DOCUMENTATION_URL = 'https://github.com/eldariont/svim'
    VERSION = '2.0.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get('output', '.'))
        cmd = ['svim', 'alignment', '--sample', str(inputs.get('sample_name', 'sample'))]
        if inputs.get('min_sv_size'):
            cmd.extend(['--min_sv_size', str(inputs['min_sv_size'])])
        if inputs.get('max_sv_size'):
            cmd.extend(['--max_sv_size', str(inputs['max_sv_size'])])
        if inputs.get('sequence_alleles'):
            cmd.append('--sequence_alleles')
        if inputs.get('symbolic_alleles'):
            cmd.append('--symbolic_alleles')
        cmd.extend(['--interspersed_duplications_as_insertions', '--tandem_duplications_as_insertions', out_dir, str(inputs.get('bam', '')), str(inputs.get('reference', ''))])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input sorted, indexed BAM from a long-read aligner'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'}), 'sample_name': ('STRING', {'default': 'sample'})}, 'optional': {'min_sv_size': ('INT', {'default': 50, 'min': 20}), 'max_sv_size': ('INT', {'default': 50000, 'min': 1000}), 'sequence_alleles': ('BOOLEAN', {'default': True}), 'symbolic_alleles': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}
