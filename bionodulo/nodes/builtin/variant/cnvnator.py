"""cnvnator — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class CNVnatorNode(CommandNode):
    """Call copy-number variants with CNVnator read-depth analysis."""
    NODE_ID = 'cnvnator'
    DISPLAY_NAME = 'CNVnator'
    CATEGORY = 'variant'
    DESCRIPTION = 'Read-depth based CNV caller using mean-shift partitioning. Multi-step: tree -> hist -> stat -> partition -> call.'
    SEARCH_ALIASES = ['cnvnator', 'cnv', 'read depth', 'mean-shift', 'copy number']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('cnv_calls', 'root_file')
    REQUIRED_EXECUTABLES = ['cnvnator']
    REQUIRED_CONDA_PACKAGES = ['cnvnator']
    DOCUMENTATION_URL = 'https://github.com/abyzovlab/CNVnator'
    VERSION = '0.4.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        bin_size = str(inputs.get('bin_size', 100))
        root_file = f'{out_dir}/cnvnator.root'
        bam = str(inputs.get('bam', ''))
        chrom_dir = str(inputs.get('chrom_dir', ''))
        cmd = ['cnvnator', '-root', root_file, '-tree', bam, '&&']
        cmd.extend(['cnvnator', '-root', root_file, '-his', bin_size])
        if chrom_dir:
            cmd.extend(['-d', chrom_dir])
        cmd.extend(['&&', 'cnvnator', '-root', root_file, '-stat', bin_size, '&&'])
        cmd.extend(['cnvnator', '-root', root_file, '-partition', bin_size, '&&'])
        cmd.extend(['cnvnator', '-root', root_file, '-call', bin_size, '>', f'{out_dir}/cnv_calls.txt'])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input sorted, indexed BAM'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'chrom_dir': ('DIRECTORY', {'description': 'Directory with per-chromosome FASTA files'}), 'bin_size': ('INT', {'default': 100, 'min': 10})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}
