"""survivor — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SURVIVORMergeNode(CommandNode):
    """Merge structural variant callsets into a consensus VCF with SURVIVOR."""
    NODE_ID = 'survivor_merge'
    DISPLAY_NAME = 'SURVIVOR Merge'
    CATEGORY = 'variant'
    DESCRIPTION = 'Merge SV calls from multiple VCFs into a consensus callset for multi-caller pipelines.'
    SEARCH_ALIASES = ['survivor', 'merge sv', 'consensus sv', 'multi-caller', 'structural variant merge']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('merged_sv',)
    REQUIRED_EXECUTABLES = ['SURVIVOR']
    REQUIRED_CONDA_PACKAGES = ['survivor']
    DOCUMENTATION_URL = 'https://github.com/fritzsedlazeck/SURVIVOR'
    VERSION = '1.0.7'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        vcf_files = inputs.get('vcf_files', [])
        if isinstance(vcf_files, str):
            vcf_files = [vcf_files]
        sample_list = out_dir / 'sample_files.txt'
        sample_list.write_text(''.join((f'{vcf}\n' for vcf in vcf_files)), encoding='utf-8')
        return ['SURVIVOR', 'merge', str(sample_list), str(inputs.get('max_distance', 1000)), str(inputs.get('min_callers', 1)), str(inputs.get('use_type', 1)), str(inputs.get('use_strand', 1)), str(inputs.get('min_sv_size', 30)), str(out_dir / 'merged_sv.vcf')]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf_files': ('VCF_GZ', {'description': 'List of VCF files to merge'}), 'max_distance': ('INT', {'default': 1000, 'min': 0, 'label': 'Max Breakpoint Distance (bp)'}), 'min_callers': ('INT', {'default': 1, 'min': 1, 'label': 'Min Supporting Callers'})}, 'optional': {'use_type': ('INT', {'default': 1, 'min': 0, 'max': 1}), 'use_strand': ('INT', {'default': 1, 'min': 0, 'max': 1}), 'min_sv_size': ('INT', {'default': 30, 'min': 10})}, 'hidden': {'output': ('STRING', {})}}
