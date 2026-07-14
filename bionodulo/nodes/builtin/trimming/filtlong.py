"""filtlong — trimming node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FiltlongNode(CommandNode):
    """Filter long reads by quality, length, and optional references with Filtlong."""
    NODE_ID = 'filtlong'
    DISPLAY_NAME = 'filtlong'
    REQUIRED_CONDA_PACKAGES = ['filtlong']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Filter long reads by quality, length, and optional external references with Filtlong.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'filtlong', 'Filtlong', 'long-read filtering', 'long-read quality', 'Nanopore', 'PacBio', 'target bases', 'read identity']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('outfile',)
    REQUIRED_EXECUTABLES = ['filtlong']
    DOCUMENTATION_URL = FILTLONG_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FILTLONG_CITATION_URL]
    CITATION_TEXT = FILTLONG_CITATION_TEXT
    VERSION = '0.3.1'
    SHELL = True
    LENGTH_PATTERN = re.compile('^[0-9]+(?:[KMG](?:B)?)?$', re.IGNORECASE)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.fastq'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['filtlong']
        for key in ('target_bases', 'keep_percent', 'min_length', 'min_mean_q', 'min_window_q', 'max_length'):
            _add_if_value(cmd, f'--{key}', inputs.get(key))
        for key in ('assembly', 'short_1', 'short_2'):
            _add_if_value(cmd, f'--{key}', inputs.get(key))
        cmd.extend(['--length_weight', str(inputs.get('length_weight', 1))])
        cmd.extend(['--mean_q_weight', str(inputs.get('mean_q_weight', 1))])
        cmd.extend(['--window_q_weight', str(inputs.get('window_q_weight', 1))])
        if inputs.get('trim'):
            cmd.append('--trim')
        _add_if_value(cmd, '--split', inputs.get('split'))
        cmd.extend(['--window_size', str(inputs.get('window_size', 250))])
        cmd.append(str(inputs.get('input_file', '')))
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.fastq']

    @classmethod
    def _validate_float_min(cls, inputs: dict[str, Any], key: str, default: float | str, minimum: float) -> bool | str:
        value = inputs.get(key, default)
        if value is None or str(value) == '':
            return True
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if parsed < minimum:
            return f'{key} must be greater than or equal to {minimum:g}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float | str, minimum: float, maximum: float) -> bool | str:
        value = inputs.get(key, default)
        if value is None or str(value) == '':
            return True
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if parsed < minimum or parsed > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def _validate_length_value(cls, inputs: dict[str, Any], key: str) -> bool | str:
        value = inputs.get(key)
        if value is None or str(value) == '':
            return True
        if not cls.LENGTH_PATTERN.fullmatch(str(value)):
            return f'{key} must be a positive integer with optional k/kb/m/mb/g/gb suffix'
        return True

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        value = inputs.get(key, default)
        if value is None or str(value) == '':
            return True
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if parsed < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        for key in ('target_bases', 'min_length', 'max_length', 'split'):
            validation = cls._validate_length_value(inputs, key)
            if validation is not True:
                return validation
        validation = cls._validate_float_range(inputs, 'keep_percent', '', 0, 100)
        if validation is not True:
            return validation
        for key in ('min_mean_q', 'min_window_q', 'length_weight', 'mean_q_weight', 'window_q_weight'):
            validation = cls._validate_float_min(inputs, key, 1 if key.endswith('_weight') else '', 0)
            if validation is not True:
                return validation
        validation = cls._validate_int_min(inputs, 'window_size', 250, 0)
        if validation is not True:
            return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTQ', {'description': 'Long-read FASTQ input reads'})}, 'optional': {'target_bases': ('STRING', {'default': '', 'description': 'Keep the best reads up to this total bases threshold'}), 'keep_percent': ('FLOAT', {'default': '', 'min': 0, 'max': 100, 'description': 'Keep this percentage of best read bases'}), 'min_length': ('STRING', {'default': '', 'description': 'Minimum read length, with optional k/kb/m/mb/g/gb suffix'}), 'max_length': ('STRING', {'default': '', 'description': 'Maximum read length, with optional k/kb/m/mb/g/gb suffix'}), 'min_mean_q': ('FLOAT', {'default': '', 'min': 0, 'description': 'Minimum mean read quality'}), 'min_window_q': ('FLOAT', {'default': '', 'min': 0, 'description': 'Minimum sliding-window quality'}), 'assembly': ('FASTA', {'default': '', 'description': 'Optional reference assembly for identity-based scoring'}), 'short_1': ('FASTQ', {'default': '', 'description': 'Optional first Illumina reference read set'}), 'short_2': ('FASTQ', {'default': '', 'description': 'Optional second Illumina reference read set'}), 'length_weight': ('FLOAT', {'default': 1.0, 'min': 0, 'description': 'Weight assigned to read length'}), 'mean_q_weight': ('FLOAT', {'default': 1.0, 'min': 0, 'description': 'Weight assigned to mean quality'}), 'window_q_weight': ('FLOAT', {'default': 1.0, 'min': 0, 'description': 'Weight assigned to window quality'}), 'trim': ('BOOLEAN', {'default': False, 'description': 'Trim non-k-mer-matching bases from read ends'}), 'split': ('STRING', {'default': '', 'description': 'Split reads at this many consecutive non-k-mer-matching bases'}), 'window_size': ('INT', {'default': 250, 'min': 0, 'description': 'Sliding window size'})}, 'hidden': {'output': ('STRING', {})}}
