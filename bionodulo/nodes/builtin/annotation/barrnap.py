"""barrnap — annotation node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BarrnapNode(CommandNode):
    """Locate ribosomal RNA genes in FASTA assemblies with barrnap."""
    NODE_ID = 'barrnap'
    DISPLAY_NAME = 'barrnap'
    REQUIRED_CONDA_PACKAGES = ['barrnap']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Locate 5S, 16S, and 23S ribosomal RNA genes in FASTA sequences and emit GFF3 annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'barrnap', 'BActerial Ribosomal RNA Predictor', 'rRNA prediction', 'ribosomal RNA', '5S 16S 23S', 'GFF3 rRNA', 'NHMMER']
    RETURN_TYPES = ('GFF', 'FASTA')
    RETURN_NAMES = ('rrna_gff', 'rrna_sequences')
    REQUIRED_EXECUTABLES = ['barrnap']
    DOCUMENTATION_URL = BARRNAP_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BARRNAP_CITATION_URL]
    CITATION_TEXT = BARRNAP_CITATION_TEXT
    VERSION = '1.2.2'
    SHELL = True
    KINGDOM_OPTIONS = ['bac', 'euk', 'mito', 'arc']

    @classmethod
    def _gff_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/rrna.gff3'

    @classmethod
    def _fasta_out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/rrna_sequences.fasta'

    @classmethod
    def _query_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/query.fa'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['barrnap', '--quiet', '--threads', '${GALAXY_SLOTS:-1}', '--reject', str(inputs.get('reject', 0.5)), '--lencutoff', str(inputs.get('lencutoff', 0.8)), '--evalue', str(inputs.get('evalue', '1e-06'))]
        if inputs.get('incseq'):
            cmd.append('--incseq')
        if inputs.get('outseq'):
            cmd.extend(['--outseq', cls._fasta_out_path(inputs)])
        cmd.extend(['--kingdom', str(inputs.get('kingdom', 'bac') or 'bac'), cls._query_path(inputs)])
        barrnap_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}')
        return f"ln -s {shlex.quote(str(inputs.get('fasta_file', '')))} {shlex.quote(cls._query_path(inputs))} && {barrnap_cmd} > {shlex.quote(cls._gff_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'rrna.gff3']
        if inputs.get('outseq'):
            outputs.append(out / 'rrna_sequences.fasta')
        return outputs

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if value < 0 or value > 1:
            return f'{key} must be between 0 and 1'
        return True

    @classmethod
    def _validate_float(cls, inputs: dict[str, Any], key: str, default: str) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if value <= 0:
            return f'{key} must be greater than 0'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('fasta_file', '')).strip():
            return 'fasta_file is required'
        kingdom = str(inputs.get('kingdom', 'bac') or 'bac')
        if kingdom not in cls.KINGDOM_OPTIONS:
            return f"kingdom must be one of: {', '.join(cls.KINGDOM_OPTIONS)}"
        for key, default in (('reject', 0.5), ('lencutoff', 0.8)):
            validation = cls._validate_float_range(inputs, key, default)
            if validation is not True:
                return validation
        validation = cls._validate_float(inputs, 'evalue', '1e-06')
        if validation is not True:
            return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fasta_file': ('FASTA', {'description': 'FASTA file to scan for ribosomal RNA genes'})}, 'optional': {'kingdom': ('STRING', {'default': 'bac', 'options': cls.KINGDOM_OPTIONS, 'description': 'Barrnap kingdom model: bacteria, eukaryote, mitochondria, or archaea'}), 'reject': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Proportional length threshold below which predictions are rejected'}), 'lencutoff': ('FLOAT', {'default': 0.8, 'min': 0, 'max': 1, 'description': 'Proportional length threshold below which predictions are tagged as pseudo'}), 'evalue': ('FLOAT', {'default': 1e-06, 'min': 0, 'description': 'Similarity e-value cutoff'}), 'incseq': ('BOOLEAN', {'default': False, 'description': 'Include original FASTA sequences after a #FASTA tag in the GFF3 output'}), 'outseq': ('BOOLEAN', {'default': False, 'description': 'Write predicted rRNA sequences to a FASTA output'})}, 'hidden': {'output': ('STRING', {})}}
