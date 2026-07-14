"""platypus — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class PlatypusNode(CommandNode):
    """Call haplotype-based variants with Platypus."""
    NODE_ID = 'platypus'
    DISPLAY_NAME = 'Platypus'
    CATEGORY = 'variant'
    DESCRIPTION = 'Call haplotype-based variants across SNPs, indels, and complex small variants with Platypus.'
    SEARCH_ALIASES = ['platypus', 'haplotype', 'small variant', 'snp', 'indel', 'variant caller']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['Platypus.py']
    REQUIRED_CONDA_PACKAGES = ['platypus-variant']
    DOCUMENTATION_URL = 'https://github.com/andyrimmer/Platypus'
    VERSION = '0.8.1'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        bams = inputs.get('bam', '')
        if isinstance(bams, (list, tuple)):
            bam_arg = ','.join((str(bam) for bam in bams))
        else:
            bam_arg = str(bams)
        cmd = ['Platypus.py', 'callVariants', f'--bamFiles={bam_arg}', f"--refFile={inputs.get('reference', '')}", f"--output={inputs.get('output', '.')}/vcf.vcf.gz"]
        if inputs.get('regions'):
            cmd.append(f"--regions={inputs['regions']}")
        if inputs.get('threads'):
            cmd.append(f"--nCPU={inputs['threads']}")
        if inputs.get('min_reads') is not None:
            cmd.append(f"--minReads={inputs['min_reads']}")
        if inputs.get('assemble') is not None:
            cmd.append(f"--assemble={(1 if inputs['assemble'] else 0)}")
        if inputs.get('filter_duplicates') is not None:
            cmd.append(f"--filterDuplicates={(1 if inputs['filter_duplicates'] else 0)}")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file or BAM list (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'})}, 'optional': {'regions': ('BED', {'description': 'Optional target regions BED', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'}), 'min_reads': ('INT', {'default': 2, 'min': 1, 'label': 'Minimum Reads', 'advanced': True}), 'assemble': ('BOOLEAN', {'default': True, 'description': 'Enable local assembly', 'advanced': True}), 'filter_duplicates': ('BOOLEAN', {'default': True, 'description': 'Filter duplicate reads', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
