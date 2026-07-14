"""featurecountsnode — rna_seq node(s). One tool per file (extracted from rna_seq.py)."""
from __future__ import annotations
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode


class FeatureCountsNode(CommandNode):
    """Count reads per gene with featureCounts."""
    NODE_ID = ''
    DISPLAY_NAME = 'featureCounts'
    REQUIRED_CONDA_PACKAGES = ['subread']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Count reads mapped to genomic features'
    SEARCH_ALIASES = ['featurecounts', 'counts', 'gene counts', 'subread']
    RETURN_TYPES = ('COUNTS',)
    RETURN_NAMES = ('counts',)
    REQUIRED_EXECUTABLES = ['featureCounts']
    DOCUMENTATION_URL = 'https://subread.sourceforge.net/'
    VERSION = '2.1.1'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        gtf = inputs.get('gtf') or inputs.get('annotation', '')
        cmd = ['featureCounts', '-a', str(gtf), '-o', f"{inputs.get('output', '.')}/counts.counts.tsv", '-T', str(inputs.get('threads', 8))]
        strand = str(inputs.get('strandness', '0'))
        if strand in ('1', '2'):
            cmd.extend(['-s', strand])
        if inputs.get('primary'):
            cmd.append('--primary')
        if inputs.get('count_read_pairs') is not False:
            cmd.extend(['-p', '--countReadPairs'])
        if inputs.get('feature_type'):
            cmd.extend(['-t', str(inputs['feature_type'])])
        if inputs.get('attribute'):
            cmd.extend(['-g', str(inputs['attribute'])])
        cmd.append(str(inputs.get('bam', '')))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Aligned BAM file (sorted, indexed)'}), 'gtf': ('GTF', {'description': 'Gene annotation GTF'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'strandness': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'label': 'Strandness', 'advanced': True}), 'primary': ('BOOLEAN', {'default': True, 'label': 'Primary Only', 'advanced': True}), 'count_read_pairs': ('BOOLEAN', {'default': True, 'label': 'Count Read Pairs', 'advanced': True}), 'feature_type': ('STRING', {'default': 'exon', 'label': 'Feature Type', 'advanced': True}), 'attribute': ('STRING', {'default': 'gene_id', 'label': 'Attribute', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
