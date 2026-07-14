"""raven — assembly node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class RavenNode(CommandNode):
    """Assemble long uncorrected reads with the Galaxy IUC Raven wrapper behavior."""
    NODE_ID = 'raven'
    DISPLAY_NAME = 'Raven'
    REQUIRED_CONDA_PACKAGES = ['raven-assembler']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assemble Oxford Nanopore or other long uncorrected reads with Raven.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Raven', 'raven', 'raven-assembler', 'Oxford Nanopore', 'long-read assembler', 'de novo assembly', 'Graphical Fragment Assembly', 'GFA']
    RETURN_TYPES = ('FASTA', 'GFA')
    RETURN_NAMES = ('out_fasta', 'out_gfa')
    REQUIRED_EXECUTABLES = ['raven']
    DOCUMENTATION_URL = RAVEN_DOCUMENTATION_URL
    CITATION_DOIS = [RAVEN_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{RAVEN_CITATION_DOI}']
    CITATION_TEXT = RAVEN_CITATION_TEXT
    VERSION = '1.8.3+galaxy0'
    SHELL = True
    INPUT_FORMATS = ['fasta', 'fasta.gz', 'fastq', 'fastq.gz']
    STAGED_INPUTS = {'fasta': './input.fa', 'fasta.gz': './input.fa.gz', 'fastq': './input.fq', 'fastq.gz': './input.fq.gz'}

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_format', '') or '').strip()
        if explicit:
            return explicit
        input_path = str(inputs.get('input_reads', '') or '')
        suffixes = [suffix.lower().lstrip('.') for suffix in Path(input_path).suffixes]
        if len(suffixes) >= 2 and suffixes[-2:] == ['fasta', 'gz']:
            return 'fasta.gz'
        if len(suffixes) >= 2 and suffixes[-2:] == ['fastq', 'gz']:
            return 'fastq.gz'
        if suffixes and suffixes[-1] in {'fa', 'fasta', 'fna'}:
            return 'fasta'
        if suffixes and suffixes[-1] in {'fq', 'fastq'}:
            return 'fastq'
        return 'fastq.gz'

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        return cls.STAGED_INPUTS.get(cls._input_format(inputs), './input.fq.gz')

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        value = inputs.get(key, default)
        if value in (None, ''):
            value = default
        return str(int(value))

    @classmethod
    def _format_number(cls, inputs: dict[str, Any], key: str, default: float) -> str:
        value = inputs.get(key, default)
        if value in (None, ''):
            value = default
        parsed = float(value)
        return str(int(parsed)) if parsed.is_integer() else format(parsed, 'g')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input(inputs)
        cmd = ['raven', '--kmer-len', cls._format_int(inputs, 'kmer_len', 15), '--window-len', cls._format_int(inputs, 'window_len', 5), '--frequency', cls._format_number(inputs, 'frequency', 0.001), '--polishing-rounds', cls._format_int(inputs, 'polishing_rounds', 2), '--match', cls._format_int(inputs, 'match', 3), '--mismatch', cls._format_int(inputs, 'mismatch', -5), '--gap', cls._format_int(inputs, 'gap', -4), '--kMaxNumOverlaps', cls._format_int(inputs, 'kMaxNumOverlaps', 32), '--identity', cls._format_number(inputs, 'identity', 0), '--min-unitig-size', cls._format_int(inputs, 'min_unitig_size', 9999)]
        if inputs.get('use_micromizers'):
            cmd.append('--use-micromizers')
        if inputs.get('graphical_fragment_assembly', True):
            cmd.extend(['--graphical-fragment-assembly', cls._output_path(inputs, 'out.gfa')])
        slots = '${GALAXY_SLOTS:-4}'
        cmd.extend(['--disable-checkpoints', '-t', slots, staged, '>', cls._output_path(inputs, 'out.fasta')])
        raven_command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"{_shell_join(['ln', '-s', str(inputs.get('input_reads', '')), staged])} && {raven_command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'out.fasta']
        if inputs.get('graphical_fragment_assembly', True):
            outputs.append(out / 'out.gfa')
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def _validate_float_min(cls, inputs: dict[str, Any], key: str, default: float, minimum: float) -> bool | str:
        try:
            value = float(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if value < minimum:
            return f'{key} must be greater than or equal to {minimum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_reads', '')).strip():
            return 'input_reads is required'
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        for key, default, minimum in (('kmer_len', 15, 1), ('window_len', 5, 1), ('kMaxNumOverlaps', 32, 1), ('min_unitig_size', 9999, 0), ('polishing_rounds', 2, 0)):
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        for key, default in (('frequency', 0.001), ('identity', 0)):
            result = cls._validate_float_min(inputs, key, default, 0)
            if result is not True:
                return result
        try:
            int(inputs.get('match', 3) if inputs.get('match', 3) not in (None, '') else 3)
            int(inputs.get('mismatch', -5) if inputs.get('mismatch', -5) not in (None, '') else -5)
            gap = int(inputs.get('gap', -4) if inputs.get('gap', -4) not in (None, '') else -4)
        except (TypeError, ValueError):
            return 'match, mismatch, and gap must be integers'
        if gap > -1:
            return 'gap must be less than or equal to -1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_reads': ('FILE', {'description': 'FASTA, FASTQ, FASTA.GZ, or FASTQ.GZ long-read data to assemble'})}, 'optional': {'input_format': ('STRING', {'default': 'fastq.gz', 'options': cls.INPUT_FORMATS, 'description': 'Galaxy dataset format used to stage the input file name'}), 'kmer_len': ('INT', {'default': 15, 'min': 1, 'description': 'Length of minimizers used to find overlaps'}), 'window_len': ('INT', {'default': 5, 'min': 1, 'description': 'Length of the sliding window used to sample minimizers'}), 'frequency': ('FLOAT', {'default': 0.001, 'min': 0, 'description': 'Threshold for ignoring the most frequent minimizers'}), 'identity': ('FLOAT', {'default': 0, 'min': 0, 'description': 'Minimum overlap identity; zero disables identity filtering'}), 'kMaxNumOverlaps': ('INT', {'default': 32, 'min': 1, 'description': 'Maximum overlaps kept during pile creation'}), 'min_unitig_size': ('INT', {'default': 9999, 'min': 0, 'description': 'Minimal unitig size'}), 'polishing_rounds': ('INT', {'default': 2, 'min': 0, 'description': 'Number of racon polishing rounds'}), 'match': ('INT', {'default': 3, 'description': 'Racon match score'}), 'mismatch': ('INT', {'default': -5, 'description': 'Racon mismatch penalty'}), 'gap': ('INT', {'default': -4, 'max': -1, 'description': 'Racon gap penalty'}), 'graphical_fragment_assembly': ('BOOLEAN', {'default': True, 'description': 'Emit a Graphical Fragment Assembly output'}), 'use_micromizers': ('BOOLEAN', {'default': False, 'description': 'Use micromizers rather than minimizers for graph construction'})}, 'hidden': {'output': ('STRING', {})}}
