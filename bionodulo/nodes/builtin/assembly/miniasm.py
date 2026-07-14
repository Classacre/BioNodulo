"""miniasm — assembly node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MiniasmNode(CommandNode):
    """Assemble noisy long reads into an assembly graph with Miniasm."""
    NODE_ID = 'miniasm'
    DISPLAY_NAME = 'Miniasm'
    REQUIRED_CONDA_PACKAGES = ['miniasm']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assemble noisy long reads into a GFA assembly graph using Miniasm and all-vs-all PAF overlaps.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Miniasm', 'miniasm', 'noisy long reads', 'long-read assembler', 'PAF overlaps', 'GFA assembly graph', 'OLC assembler']
    RETURN_TYPES = ('GFA',)
    RETURN_NAMES = ('assembly_graph',)
    REQUIRED_EXECUTABLES = ['miniasm']
    DOCUMENTATION_URL = 'https://github.com/lh3/miniasm'
    CITATION_DOIS = [MINIASM_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{MINIASM_CITATION_DOI}']
    CITATION_TEXT = MINIASM_CITATION_TEXT
    VERSION = '0.3_r179'
    SHELL = True
    DEFAULTS = {'min_match': 100, 'min_iden': 0.05, 'min_span': 1000, 'min_cov': 3, 'min_ovlp': 1000, 'max_hang': 1000, 'int_thres': 0.08, 'max_gap_diff': 1000, 'max_bub_dist': 50000, 'min_utg_size': 4, 'n_rounds': 3, 'final_drop_ratio': 0.8}
    INTEGER_OPTIONS = {'min_match': 'min_match', 'min_span': 'min_span', 'min_cov': 'min_cov', 'min_ovlp': 'min_ovlp', 'max_hang': 'max_hang', 'max_gap_diff': 'max_gap_diff', 'max_bub_dist': 'max_bub_dist', 'min_utg_size': 'min_utg_size', 'n_rounds': 'n_rounds'}
    FLOAT_OPTIONS = {'min_iden': 'min_iden', 'int_thres': 'int_thres', 'final_drop_ratio': 'final_drop_ratio'}

    @classmethod
    def _option(cls, inputs: dict[str, Any], key: str) -> Any:
        return inputs.get(key, cls.DEFAULTS[key])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output = f'{_out(inputs)}/assembly_graph.gfa'
        cmd = ['miniasm', '-f', str(inputs.get('read_file', '')), '-m', str(cls._option(inputs, 'min_match')), '-i', str(cls._option(inputs, 'min_iden')), '-s', str(cls._option(inputs, 'min_span')), '-c', str(cls._option(inputs, 'min_cov')), '-o', str(cls._option(inputs, 'min_ovlp')), '-h', str(cls._option(inputs, 'max_hang')), '-I', str(cls._option(inputs, 'int_thres')), '-g', str(cls._option(inputs, 'max_gap_diff')), '-d', str(cls._option(inputs, 'max_bub_dist')), '-e', str(cls._option(inputs, 'min_utg_size')), '-n', str(cls._option(inputs, 'n_rounds')), '-F', str(cls._option(inputs, 'final_drop_ratio')), str(inputs.get('paf', ''))]
        return f'{_shell_join(cmd)} > {shlex.quote(output)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'assembly_graph.gfa']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('read_file'):
            return 'sequence reads are required'
        if not inputs.get('paf'):
            return 'PAF overlaps are required'
        for key in cls.INTEGER_OPTIONS:
            try:
                value = int(cls._option(inputs, key))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 0:
                return f'{key} must be >= 0'
        for key in cls.FLOAT_OPTIONS:
            try:
                value = float(cls._option(inputs, key))
            except (TypeError, ValueError):
                return f'{key} must be a number'
            if value < 0:
                return f'{key} must be >= 0'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'read_file': ('FASTQ', {'description': 'Long reads in FASTQ, FASTA, or compressed FASTQ/FASTA format'}), 'paf': ('PAF', {'description': 'All-vs-all read overlaps in Pairwise mApping Format'})}, 'optional': {'min_match': ('INT', {'default': 100, 'min': 0, 'description': 'Drop mappings with fewer matching bases'}), 'min_iden': ('FLOAT', {'default': 0.05, 'min': 0, 'description': 'Ignore mappings below this col10/col11 ratio'}), 'min_span': ('INT', {'default': 1000, 'min': 0, 'description': 'Drop mappings shorter than this many bp'}), 'min_cov': ('INT', {'default': 3, 'min': 0, 'description': 'Minimum coverage by other reads'}), 'min_ovlp': ('INT', {'default': 1000, 'min': 0, 'description': 'Minimum overlap length'}), 'max_hang': ('INT', {'default': 1000, 'min': 0, 'description': 'Maximum overhang length'}), 'int_thres': ('FLOAT', {'default': 0.08, 'min': 0, 'description': 'Containment or overlap internal mapping threshold'}), 'max_gap_diff': ('INT', {'default': 1000, 'min': 0, 'description': 'Maximum gap difference for transitive reduction'}), 'max_bub_dist': ('INT', {'default': 50000, 'min': 0, 'description': 'Maximum probing distance for bubble popping'}), 'min_utg_size': ('INT', {'default': 4, 'min': 0, 'description': 'Small unitig read-count threshold'}), 'n_rounds': ('INT', {'default': 3, 'min': 0, 'description': 'Rounds of short-overlap removal'}), 'final_drop_ratio': ('FLOAT', {'default': 0.8, 'min': 0, 'description': 'Overlap drop ratio threshold after short unitig removal'})}, 'hidden': {'output': ('STRING', {})}}
