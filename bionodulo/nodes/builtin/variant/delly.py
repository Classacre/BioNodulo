"""delly — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class DellyNode(CommandNode):
    """Call structural variants with DELLY."""
    NODE_ID = 'delly'
    DISPLAY_NAME = 'DELLY SV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Paired-end + split-read SV caller. Supports germline, somatic, and long-read modes.'
    SEARCH_ALIASES = ['delly', 'structural variant', 'sv caller', 'somatic sv', 'long-read sv']
    RETURN_TYPES = ('BCF',)
    RETURN_NAMES = ('sv_calls',)
    REQUIRED_EXECUTABLES = ['delly']
    REQUIRED_CONDA_PACKAGES = ['delly']
    DOCUMENTATION_URL = 'https://github.com/dellytools/delly'
    VERSION = '1.2.6'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        mode = inputs.get('mode', 'call')
        cmd = ['delly', 'lr' if mode == 'lr' else 'call', '-g', str(inputs.get('reference', '')), '-o', f"{inputs.get('output', '.')}/sv_calls.bcf"]
        if inputs.get('exclude_regions'):
            cmd.extend(['-x', str(inputs['exclude_regions'])])
        if inputs.get('map_qual') is not None:
            cmd.extend(['-q', str(inputs['map_qual'])])
        cmd.append(str(inputs.get('bam', '')))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'mode': ('STRING', {'default': 'call', 'options': ['call', 'lr']})}, 'optional': {'exclude_regions': ('BED', {'description': 'Exclude regions BED', 'advanced': True}), 'map_qual': ('INT', {'default': 1, 'min': 0, 'label': 'Min MapQ', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class DellyCallNode(DellyNode):
    """Workflow-compatible DELLY caller that emits an indexed VCF."""
    NODE_ID = 'delly_call'
    DISPLAY_NAME = 'DELLY Call'
    DESCRIPTION = 'Call structural variants with DELLY and convert BCF output to indexed VCF.'
    SEARCH_ALIASES = ['delly_call', 'delly', 'structural variant', 'sv caller', 'somatic sv', 'long-read sv']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('sv_vcf',)
    REQUIRED_EXECUTABLES = ['delly', 'bcftools', 'tabix']
    REQUIRED_CONDA_PACKAGES = ['delly', 'bcftools', 'htslib']
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'sv_vcf.vcf.gz']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        bcf = out_dir / 'sv_calls.bcf'
        sv_vcf = out_dir / 'sv_vcf.vcf.gz'
        mode = inputs.get('mode', 'call')
        cmd = ['delly', 'lr' if mode == 'lr' else 'call', '-g', str(inputs.get('reference', '')), '-o', str(bcf)]
        if inputs.get('exclude_regions'):
            cmd.extend(['-x', str(inputs['exclude_regions'])])
        if inputs.get('map_qual') is not None:
            cmd.extend(['-q', str(inputs['map_qual'])])
        cmd.extend([str(inputs.get('bam', '')), '&&', 'bcftools', 'view', '-Oz', '-o', str(sv_vcf), str(bcf), '&&', 'tabix', '-f', '-p', 'vcf', str(sv_vcf)])
        return cmd
