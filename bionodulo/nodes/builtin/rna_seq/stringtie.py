"""stringtie — rna_seq node(s). One tool per file (extracted from rna_seq.py)."""
from __future__ import annotations
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode


class StringTieNode(CommandNode):
    """Transcript assembly and quantification with StringTie."""
    NODE_ID = 'stringtie'
    DISPLAY_NAME = 'StringTie'
    REQUIRED_CONDA_PACKAGES = ['stringtie']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Transcript assembly and quantification from RNA-seq alignments'
    SEARCH_ALIASES = ['stringtie', 'assemble', 'transcript', 'expression']
    RETURN_TYPES = ('GTF', 'TSV')
    RETURN_NAMES = ('transcripts', 'gene_abundance')
    REQUIRED_EXECUTABLES = ['stringtie']
    DOCUMENTATION_URL = 'https://ccb.jhu.edu/software/stringtie/'
    VERSION = '3.0.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['stringtie', str(inputs.get('bam', '')), '-G', str(inputs.get('gtf', '')), '-o', f"{inputs.get('output', '.')}/transcripts.gtf", '-A', f"{inputs.get('output', '.')}/gene_abundance.tsv", '-p', str(inputs.get('threads', 8))]
        if inputs.get('fr'):
            cmd.append('--fr')
        elif inputs.get('rf'):
            cmd.append('--rf')
        if inputs.get('min_isoform_fraction') is not None:
            cmd.extend(['-f', str(inputs['min_isoform_fraction'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Aligned BAM file'}), 'gtf': ('GTF', {'description': 'Reference gene annotation GTF'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'fr': ('BOOLEAN', {'default': False, 'label': 'Forward Strand (fr)', 'advanced': True}), 'rf': ('BOOLEAN', {'default': False, 'label': 'Reverse Strand (rf)', 'advanced': True}), 'min_isoform_fraction': ('FLOAT', {'default': 0.01, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'label': 'Min Isoform Fraction', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
