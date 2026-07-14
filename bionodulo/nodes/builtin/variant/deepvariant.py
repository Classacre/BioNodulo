"""deepvariant — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class DeepVariantNode(CommandNode):
    """Call small variants with DeepVariant."""
    NODE_ID = 'deepvariant'
    DISPLAY_NAME = 'DeepVariant'
    CATEGORY = 'variant'
    DESCRIPTION = "Call small variants with DeepVariant, Google's deep learning-based variant caller."
    SEARCH_ALIASES = ['deepvariant', 'deep learning', 'small variant', 'snp', 'indel', 'variant caller']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['run_deepvariant']
    REQUIRED_CONDA_PACKAGES = ['deepvariant']
    DOCUMENTATION_URL = 'https://github.com/google/deepvariant'
    VERSION = '1.6.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['run_deepvariant', f"--model_type={inputs.get('model_type', 'WGS')}", f"--ref={inputs.get('reference', '')}", f"--reads={inputs.get('bam', '')}", f"--output_vcf={inputs.get('output', '.')}/vcf.vcf.gz"]
        if inputs.get('num_shards'):
            cmd.append(f"--num_shards={inputs['num_shards']}")
        if inputs.get('regions'):
            cmd.append(f"--regions={inputs['regions']}")
        if inputs.get('sample_name'):
            cmd.append(f"--sample_name={inputs['sample_name']}")
        if inputs.get('intermediate_results_dir'):
            cmd.append(f"--intermediate_results_dir={inputs['intermediate_results_dir']}")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'})}, 'optional': {'model_type': ('STRING', {'default': 'WGS', 'options': ['WGS', 'WES', 'PACBIO', 'ONT_R104']}), 'regions': ('STRING', {'default': '', 'description': 'Optional region string or BED path', 'advanced': True}), 'num_shards': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'}), 'sample_name': ('STRING', {'default': '', 'description': 'Optional sample name override', 'advanced': True}), 'intermediate_results_dir': ('DIRECTORY', {'description': 'Optional DeepVariant intermediate directory', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
