"""fasta — qc node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FastaStatsNode(CommandNode):
    """Display summary statistics for FASTA assemblies with Galaxy's fasta-stats helper."""
    NODE_ID = 'fasta-stats'
    DISPLAY_NAME = 'Fasta Statistics'
    REQUIRED_CONDA_PACKAGES = ['python', 'numpy', 'biopython']
    CATEGORY = 'qc'
    DESCRIPTION = 'Display summary statistics for a FASTA or Multi-FASTA file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'fasta-stats', 'Fasta Statistics', 'FASTA statistics', 'Multi-FASTA', 'N50', 'NG50', 'GC content', 'gap stats', 'BED gaps']
    RETURN_TYPES = ('TSV', 'BED')
    RETURN_NAMES = ('stats_output', 'gaps_output')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = FASTA_STATS_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FASTA_STATS_CITATION_URL]
    CITATION_TEXT = FASTA_STATS_CITATION_TEXT
    VERSION = '2.0'
    SHELL = True

    @classmethod
    def _stats_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/stats.tsv'

    @classmethod
    def _gaps_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/gaps.bed'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', str(inputs.get('script_path', 'fasta-stats.py')), '--fasta', str(inputs.get('fasta', '')), '--stats_output', cls._stats_path(inputs)]
        if inputs.get('gaps_option'):
            cmd.extend(['--gaps_output', cls._gaps_path(inputs)])
        if inputs.get('genome_size') is not None and str(inputs.get('genome_size')) != '':
            cmd.extend(['--genome_size', str(inputs.get('genome_size'))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'stats.tsv']
        if inputs.get('gaps_option'):
            outputs.append(out / 'gaps.bed')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('fasta', '')).strip():
            return 'fasta is required'
        genome_size = inputs.get('genome_size')
        if genome_size is not None and str(genome_size) != '':
            if isinstance(genome_size, bool):
                return 'genome_size must be an integer'
            try:
                parsed_genome_size = int(genome_size)
            except (TypeError, ValueError):
                return 'genome_size must be an integer'
            if parsed_genome_size < 0:
                return 'genome_size must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fasta': ('FASTA', {'description': 'FASTA or Multi-FASTA file'})}, 'optional': {'genome_size': ('INT', {'default': '', 'min': 0, 'description': 'Estimated genome size used to calculate NG50'}), 'gaps_option': ('BOOLEAN', {'default': False, 'description': 'Generate an optional BED file describing N-gap ranges'}), 'script_path': ('FILE', {'default': 'fasta-stats.py', 'advanced': True, 'description': 'Path to the Galaxy fasta-stats.py helper script'})}, 'hidden': {'output': ('STRING', {})}}
