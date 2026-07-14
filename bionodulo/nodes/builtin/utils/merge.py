"""merge — utils node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class MergeVCFNode(CommandNode):
    """Merge multiple VCF files with bcftools."""
    NODE_ID = 'merge_vcf'
    DISPLAY_NAME = 'Merge VCF'
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    CATEGORY = 'utils'
    DESCRIPTION = 'Merge multiple VCF/BCF files into one'
    SEARCH_ALIASES = ['merge', 'vcf', 'combine', 'bcftools merge']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('merged_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/bcftools.html'
    VERSION = '1.20'
    COMMAND = ['bcftools', 'merge', '-Oz', '-o', '{output}/merged.vcf.gz']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcfs': ('VCF_GZ', {'description': 'List of VCF.gz files to merge'})}, 'optional': {'force_samples': ('BOOLEAN', {'default': True}), 'merge': ('STRING', {'default': 'both', 'description': 'snps, indels, both, all, none'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        vcfs = inputs.get('vcfs', [])
        if isinstance(vcfs, str):
            vcfs = [vcfs]
        cmd = ['bcftools', 'merge', '-Oz', '-o', f"{inputs.get('output', '.')}/merged.vcf.gz"]
        if inputs.get('force_samples'):
            cmd.append('--force-samples')
        if inputs.get('merge'):
            cmd.extend(['-m', str(inputs['merge'])])
        cmd.extend(list(vcfs))
        return cmd
