"""freebayes — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class FreeBayesNode(CommandNode):
    """Call variants with FreeBayes."""
    NODE_ID = 'freebayes'
    DISPLAY_NAME = 'FreeBayes'
    REQUIRED_CONDA_PACKAGES = ['freebayes']
    CATEGORY = 'variant'
    DESCRIPTION = 'Bayesian haplotype-based variant caller'
    SEARCH_ALIASES = ['freebayes', 'variant caller', 'bayesian', 'snp']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['freebayes']
    DOCUMENTATION_URL = 'https://github.com/freebayes/freebayes'
    VERSION = '1.3.10'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['freebayes', '-f', str(inputs.get('reference', ''))]
        if inputs.get('pooled'):
            cmd.append('--pooled-continuous')
        if inputs.get('ploidy'):
            cmd.extend(['-p', str(inputs['ploidy'])])
        if inputs.get('min_mapping_quality') is not None:
            cmd.extend(['--min-mapping-quality', str(inputs['min_mapping_quality'])])
        if inputs.get('min_base_quality') is not None:
            cmd.extend(['--min-base-quality', str(inputs['min_base_quality'])])
        if inputs.get('haplotype_length') is not None:
            cmd.extend(['--haplotype-length', str(inputs['haplotype_length'])])
        cmd.append(str(inputs.get('bam', '')))
        cmd.extend(['>', f"{inputs.get('output', '.')}/vcf.vcf"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file (sorted, indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA'})}, 'optional': {'pooled': ('BOOLEAN', {'default': False, 'description': 'Enable pooled calling'}), 'ploidy': ('INT', {'default': 2, 'min': 1, 'max': 8, 'display': 'slider'}), 'min_mapping_quality': ('INT', {'default': 1, 'min': 0, 'label': 'Min Mapping Quality', 'advanced': True}), 'min_base_quality': ('INT', {'default': 0, 'min': 0, 'label': 'Min Base Quality', 'advanced': True}), 'haplotype_length': ('INT', {'default': 3, 'min': 0, 'label': 'Haplotype Length', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
