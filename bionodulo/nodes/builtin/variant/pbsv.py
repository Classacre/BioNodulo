"""pbsv — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class PBSVNode(CommandNode):
    """Call PacBio HiFi structural variants with pbsv."""
    NODE_ID = 'pbsv'
    DISPLAY_NAME = 'PBSV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'PacBio structural variant caller for HiFi read alignments.'
    SEARCH_ALIASES = ['pbsv', 'pacbio', 'hifi', 'hifi sv', 'structural variant', 'sv caller', 'discover', 'call']
    RETURN_TYPES = ('VCF', 'FILE')
    RETURN_NAMES = ('sv_vcf', 'svsig')
    REQUIRED_EXECUTABLES = ['pbsv']
    REQUIRED_CONDA_PACKAGES = ['pbsv']
    DOCUMENTATION_URL = 'https://github.com/PacificBiosciences/pbsv'
    VERSION = '2.10.0'
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        sample_name = cls._sample_name(inputs)
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f'{sample_name}.pbsv.vcf', node_out / f'{sample_name}.svsig.gz']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not cls._sample_name(inputs):
            return "Input 'sample_name' must not be empty"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get('output', '.'))
        sample_name = cls._sample_name(inputs)
        svsig = f'{out_dir}/{sample_name}.svsig.gz'
        vcf = f'{out_dir}/{sample_name}.pbsv.vcf'
        cmd = ['pbsv', 'discover', str(inputs.get('bam', '')), svsig]
        if inputs.get('tandem_repeats'):
            cmd.extend(['--tandem-repeats', str(inputs['tandem_repeats'])])
        cmd.extend(['&&', 'pbsv', 'call'])
        if inputs.get('ccs'):
            cmd.append('--ccs')
        cmd.extend(['-j', str(inputs.get('threads', 4)), str(inputs.get('reference', '')), svsig, vcf])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'PacBio HiFi BAM aligned to the reference'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'sample_name': ('STRING', {'default': 'sample'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'tandem_repeats': ('BED', {'description': 'Tandem repeat annotations', 'advanced': True}), 'ccs': ('BOOLEAN', {'default': True, 'description': 'Optimize calling for PacBio CCS/HiFi reads'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('sample_name', 'sample')).strip()
