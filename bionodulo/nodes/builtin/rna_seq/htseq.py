"""htseq — rna_seq node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class HTSeqCountNode(CommandNode):
    """Count reads overlapping genomic features with HTSeq-count."""
    NODE_ID = 'htseq_count'
    DISPLAY_NAME = 'HTSeq-count'
    REQUIRED_CONDA_PACKAGES = ['htseq', 'samtools']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Count aligned reads in SAM/BAM files that overlap GFF/GTF features.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'htseq-count', 'htseq', 'gene counts', 'rna-seq counts']
    RETURN_TYPES = ('COUNTS',)
    RETURN_NAMES = ('counts',)
    REQUIRED_EXECUTABLES = ['htseq-count', 'samtools']
    DOCUMENTATION_URL = 'https://htseq.readthedocs.io/en/latest/htseqcount.html'
    CITATION_DOIS = ['10.1093/bioinformatics/btu638']
    CITATION_URLS = ['https://doi.org/10.1093/bioinformatics/btu638']
    CITATION_TEXT = 'HTSeq: a Python framework to work with high-throughput sequencing data.'
    VERSION = '2.1.2'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        samfile = str(inputs.get('samfile', ''))
        if inputs.get('sort_bam'):
            samfile = f'{_out(inputs)}/name_sorted.bam'
            cmd = ['samtools', 'sort', '-n', '-o', samfile, str(inputs.get('samfile', '')), '&&']
        else:
            cmd = []
        cmd.extend(['htseq-count', '--format=bam' if str(inputs.get('samfile', '')).lower().endswith('.bam') else '--format=sam', f"--mode={inputs.get('mode', 'union')}", f"--stranded={inputs.get('stranded', 'yes')}", f"--minaqual={inputs.get('minaqual', 0)}", f"--type={inputs.get('featuretype', 'exon')}", f"--idattr={inputs.get('idattr', 'gene_id')}", f"--nonunique={inputs.get('nonunique', 'none')}", f"--secondary-alignments={inputs.get('secondary_alignments', 'score')}", f"--supplementary-alignments={inputs.get('supplementary_alignments', 'score')}", f"--order={inputs.get('order', 'pos')}", samfile, str(inputs.get('gfffile', ''))])
        _add_shell_redirect(cmd, f'{_out(inputs)}/counts.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'counts.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'samfile': ('BAM', {'description': 'Aligned SAM/BAM file'}), 'gfffile': ('GFF_GTF', {'description': 'GFF/GTF feature annotation'})}, 'optional': {'mode': ('STRING', {'default': 'union', 'options': ['union', 'intersection-strict', 'intersection-nonempty']}), 'stranded': ('STRING', {'default': 'yes', 'options': ['yes', 'no', 'reverse']}), 'minaqual': ('INT', {'default': 0, 'min': 0}), 'featuretype': ('STRING', {'default': 'exon'}), 'idattr': ('STRING', {'default': 'gene_id'}), 'nonunique': ('STRING', {'default': 'none', 'options': ['none', 'all', 'fraction', 'random']}), 'secondary_alignments': ('STRING', {'default': 'score', 'options': ['score', 'ignore'], 'advanced': True}), 'supplementary_alignments': ('STRING', {'default': 'score', 'options': ['score', 'ignore'], 'advanced': True}), 'order': ('STRING', {'default': 'pos', 'options': ['pos', 'name'], 'advanced': True}), 'sort_bam': ('BOOLEAN', {'default': False, 'description': 'Name-sort BAM with samtools before counting', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
