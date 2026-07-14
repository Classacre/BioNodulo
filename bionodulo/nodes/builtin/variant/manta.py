"""manta — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class MantaNode(CommandNode):
    """Call paired-end structural variants with Manta."""
    NODE_ID = 'manta'
    DISPLAY_NAME = 'Manta SV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Call structural variants (DEL, DUP, INS, INV, BND) from paired-end sequencing. Supports germline and somatic modes.'
    SEARCH_ALIASES = ['manta', 'structural variant', 'sv caller', 'illumina sv', 'germline sv', 'somatic sv']
    RETURN_TYPES = ('VCF_GZ', 'VCF_GZ')
    RETURN_NAMES = ('candidate_sv', 'diploid_sv')
    REQUIRED_EXECUTABLES = ['configManta.py', 'runWorkflow.py']
    REQUIRED_CONDA_PACKAGES = ['manta']
    DOCUMENTATION_URL = 'https://github.com/Illumina/manta'
    VERSION = '1.6.0'
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        variants_dir = node_out / 'results' / 'variants'
        variants_dir.mkdir(parents=True, exist_ok=True)
        return [variants_dir / 'candidateSV.vcf.gz', variants_dir / 'diploidSV.vcf.gz']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get('output', '.'))
        cmd = ['configManta.py', '--bam', str(inputs.get('bam', '')), '--referenceFasta', str(inputs.get('reference', '')), '--runDir', out_dir]
        if inputs.get('normal_bam'):
            cmd.extend(['--normalBam', str(inputs['normal_bam'])])
        if inputs.get('exome'):
            cmd.append('--exome')
        if inputs.get('rna'):
            cmd.append('--rna')
        cmd.extend(['&&', f'{out_dir}/runWorkflow.py', '-m', 'local', '-j', str(inputs.get('threads', 4))])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'normal_bam': ('BAM', {'description': 'Normal BAM for somatic mode', 'advanced': True}), 'exome': ('BOOLEAN', {'default': False, 'description': 'Exome/targeted mode', 'advanced': True}), 'rna': ('BOOLEAN', {'default': False, 'description': 'RNA-seq mode', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class MantaCallNode(MantaNode):
    """Workflow-compatible Manta structural variant caller alias."""
    NODE_ID = 'manta_call'
    DISPLAY_NAME = 'Manta Call'
    DESCRIPTION = 'Call paired-end structural variants with Manta for multi-caller SV workflows.'
    SEARCH_ALIASES = ['manta_call', 'manta', 'structural variant', 'sv caller', 'illumina sv', 'germline sv']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('sv_vcf',)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        variants_dir = node_out / 'results' / 'variants'
        variants_dir.mkdir(parents=True, exist_ok=True)
        vcf_name = 'somaticSV.vcf.gz' if inputs.get('normal_bam') else 'diploidSV.vcf.gz'
        return [variants_dir / vcf_name]
