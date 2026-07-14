"""mutect2 — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class Mutect2Node(CommandNode):
    """Call somatic variants with GATK Mutect2."""
    NODE_ID = 'mutect2'
    DISPLAY_NAME = 'Mutect2'
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = 'variant'
    DESCRIPTION = 'Call somatic variants from tumor-only or tumor-normal BAM inputs with GATK Mutect2'
    SEARCH_ALIASES = ['mutect2', 'gatk', 'somatic variant', 'tumor normal', 'cancer variant']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['gatk']
    DOCUMENTATION_URL = 'https://gatk.broadinstitute.org/hc/en-us/articles/360037593851-Mutect2'
    VERSION = '4.6.2.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['gatk', 'Mutect2', '-R', str(inputs.get('reference', '')), '-I', str(inputs.get('tumor_bam', ''))]
        if inputs.get('tumor_sample'):
            cmd.extend(['-tumor', str(inputs['tumor_sample'])])
        if inputs.get('normal_bam'):
            cmd.extend(['-I', str(inputs['normal_bam'])])
            if inputs.get('normal_sample'):
                cmd.extend(['-normal', str(inputs['normal_sample'])])
        if inputs.get('germline_resource'):
            cmd.extend(['--germline-resource', str(inputs['germline_resource'])])
        if inputs.get('panel_of_normals'):
            cmd.extend(['--panel-of-normals', str(inputs['panel_of_normals'])])
        if inputs.get('intervals'):
            cmd.extend(['-L', str(inputs['intervals'])])
        cmd.extend(['-O', f"{inputs.get('output', '.')}/vcf.vcf.gz"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'tumor_bam': ('BAM', {'description': 'Tumor BAM (sorted, indexed, with read groups)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'})}, 'optional': {'normal_bam': ('BAM', {'description': 'Matched normal BAM for tumor-normal calling', 'advanced': True}), 'tumor_sample': ('STRING', {'default': '', 'description': 'Tumor sample name in the BAM read groups', 'advanced': True}), 'normal_sample': ('STRING', {'default': '', 'description': 'Normal sample name in the BAM read groups', 'advanced': True}), 'germline_resource': ('VCF_GZ', {'description': 'Population allele frequency resource', 'advanced': True}), 'panel_of_normals': ('VCF_GZ', {'description': 'Panel of normals VCF', 'advanced': True}), 'intervals': ('STRING', {'default': '', 'description': 'Intervals to process (e.g., chr1:1-1000)', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
