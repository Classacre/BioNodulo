"""seqkit — qc node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class SeqKitStatsNode(CommandNode):
    """Compute FASTA/Q summary statistics with SeqKit."""
    NODE_ID = 'seqkit_stats'
    DISPLAY_NAME = 'SeqKit Stats'
    REQUIRED_CONDA_PACKAGES = ['seqkit']
    CATEGORY = 'qc'
    DESCRIPTION = 'Compute sequence counts, length summaries, N50, and FASTQ quality statistics.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqkit', 'stats', 'fasta statistics', 'fastq statistics', 'n50']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('stats',)
    REQUIRED_EXECUTABLES = ['seqkit']
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/usage/#stats'
    CITATION_DOIS = ['10.1371/journal.pone.0163962']
    CITATION_URLS = ['https://doi.org/10.1371/journal.pone.0163962']
    CITATION_TEXT = 'SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation.'
    VERSION = '2.13.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['seqkit', 'stats', str(inputs.get('input', ''))]
        if inputs.get('all'):
            cmd.append('--all')
        if inputs.get('basename'):
            cmd.append('--basename')
        if inputs.get('skip_err'):
            cmd.append('--skip-err')
        if inputs.get('tabular', True):
            cmd.append('--tabular')
        _add_shell_redirect(cmd, f'{_out(inputs)}/stats.tsv')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'stats.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ_LIST', {'description': 'FASTA or FASTQ file'})}, 'optional': {'all': ('BOOLEAN', {'default': False, 'description': 'Output all statistics'}), 'basename': ('BOOLEAN', {'default': False, 'description': 'Report input basename only'}), 'skip_err': ('BOOLEAN', {'default': False, 'description': 'Skip errors and show warnings'}), 'tabular': ('BOOLEAN', {'default': True, 'description': 'Output tabular format'})}, 'hidden': {'output': ('STRING', {})}}
