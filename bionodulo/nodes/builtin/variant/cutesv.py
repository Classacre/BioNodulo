"""cutesv — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class CuteSVNode(CommandNode):
    """Call long-read structural variants with cuteSV."""
    NODE_ID = 'cutesv'
    DISPLAY_NAME = 'cuteSV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Efficient long-read SV caller for ONT and PacBio HiFi.'
    SEARCH_ALIASES = ['cutesv', 'cuteSV', 'long-read sv', 'nanopore sv', 'pacbio sv', 'structural variant']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('sv_vcf',)
    REQUIRED_EXECUTABLES = ['cuteSV']
    REQUIRED_CONDA_PACKAGES = ['cute-sv']
    DOCUMENTATION_URL = 'https://github.com/tjiangHIT/cuteSV'
    VERSION = '2.1.1'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get('output', '.'))
        cmd = ['cuteSV', '--threads', str(inputs.get('threads', 4)), '--sample', str(inputs.get('sample_name', 'sample'))]
        if inputs.get('max_cluster_bias_ins'):
            cmd.extend(['--max_cluster_bias_INS', str(inputs['max_cluster_bias_ins'])])
        if inputs.get('min_size'):
            cmd.extend(['--min_size', str(inputs['min_size'])])
        if inputs.get('max_size'):
            cmd.extend(['--max_size', str(inputs['max_size'])])
        cmd.extend([str(inputs.get('bam', '')), str(inputs.get('reference', '')), f'{out_dir}/sv_vcf.vcf', out_dir])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input sorted, indexed BAM from a long-read aligner'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'sample_name': ('STRING', {'default': 'sample'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'max_cluster_bias_ins': ('INT', {'default': 1000, 'min': 50, 'label': 'Max Cluster Bias INS'}), 'min_size': ('INT', {'default': 30, 'min': 10, 'label': 'Min SV Size'}), 'max_size': ('INT', {'default': 100000, 'min': 1000, 'label': 'Max SV Size'})}, 'hidden': {'output': ('STRING', {})}}
