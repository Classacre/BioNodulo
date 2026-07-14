"""chopper — trimming node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ChopperNode(CommandNode):
    """Filter and trim long-read FASTQ files with Chopper."""
    NODE_ID = 'chopper'
    DISPLAY_NAME = 'Chopper'
    REQUIRED_CONDA_PACKAGES = ['chopper']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Filter and trim long-read FASTQ data with Chopper.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Chopper', 'chopper', 'long-read filtering', 'long-read trimming', 'Nanopore', 'PacBio', 'NanoFilt', 'NanoLyse', 'quality filtering']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('fq_filt',)
    REQUIRED_EXECUTABLES = ['chopper', 'gzip']
    DOCUMENTATION_URL = 'https://github.com/wdecoster/chopper'
    CITATION_DOIS = [CHOPPER_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHOPPER_CITATION_DOI}']
    CITATION_TEXT = CHOPPER_CITATION_TEXT
    VERSION = '0.13.0'
    SHELL = True
    TRIM_APPROACHES = ['', 'fixed-crop', 'trim-by-quality', 'best-read-segment', 'split-by-low-quality']

    @classmethod
    def _input_is_gzip(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get('input', '')).lower().endswith('.gz')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = '.fastq.gz' if cls._input_is_gzip(inputs) else '.fastq'
        return f'{_out(inputs)}/fq_filt{suffix}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['chopper', '--input', str(inputs.get('input', '')), '--threads', '${GALAXY_SLOTS:-1}']
        _add_if_value(cmd, '--contam', inputs.get('contam'))
        cmd.extend(['--quality', str(inputs.get('quality', 0))])
        cmd.extend(['--maxqual', str(inputs.get('maxqual', 60))])
        cmd.extend(['--minlength', str(inputs.get('minlength', 1))])
        _add_if_value(cmd, '--maxlength', inputs.get('maxlength'))
        cmd.extend(['--mingc', str(inputs.get('mingc', 0.0))])
        cmd.extend(['--maxgc', str(inputs.get('maxgc', 1.0))])
        trim_approach = str(inputs.get('trim_approach', '') or '')
        if trim_approach:
            cmd.extend(['--trim-approach', trim_approach])
            if trim_approach == 'fixed-crop':
                cmd.extend(['--headcrop', str(inputs.get('headcrop', 0))])
                cmd.extend(['--tailcrop', str(inputs.get('tailcrop', 0))])
            elif trim_approach in {'trim-by-quality', 'best-read-segment'}:
                cmd.extend(['--cutoff', str(inputs.get('cutoff', 10))])
            elif trim_approach == 'split-by-low-quality':
                cmd.extend(['--cutoff', str(inputs.get('cutoff', 10))])
                cmd.extend(['--split-window', str(inputs.get('split_window', 1))])
        if inputs.get('inverse'):
            cmd.append('--inverse')
        chopper_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}')
        output_path = shlex.quote(cls._output_path(inputs))
        if cls._input_is_gzip(inputs):
            return f'{chopper_cmd} | gzip > {output_path}'
        return f'{chopper_cmd} > {output_path}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = '.fastq.gz' if cls._input_is_gzip(inputs) else '.fastq'
        return [out / f'fq_filt{suffix}']

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum or value > maximum:
            return f'{key} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if value < minimum or value > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        for key, default in (('quality', 0), ('maxqual', 60), ('cutoff', 10)):
            validation = cls._validate_int_range(inputs, key, default, 0, 60)
            if validation is not True:
                return validation
        for key, default in (('minlength', 1), ('maxlength', '')):
            if key == 'maxlength' and str(inputs.get(key, '')) == '':
                continue
            validation = cls._validate_int_min(inputs, key, default, 1)
            if validation is not True:
                return validation
        for key, default in (('headcrop', 0), ('tailcrop', 0)):
            validation = cls._validate_int_min(inputs, key, default, 0)
            if validation is not True:
                return validation
        for key, default in (('mingc', 0.0), ('maxgc', 1.0)):
            validation = cls._validate_float_range(inputs, key, default, 0.0, 1.0)
            if validation is not True:
                return validation
        validation = cls._validate_int_min(inputs, 'split_window', 1, 1)
        if validation is not True:
            return validation
        trim_approach = str(inputs.get('trim_approach', '') or '')
        if trim_approach not in cls.TRIM_APPROACHES:
            return f"trim_approach must be one of: {', '.join(cls.TRIM_APPROACHES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTQ', {'description': 'Long-read FASTQ file to filter or trim'})}, 'optional': {'contam': ('FASTA', {'default': '', 'description': 'Optional contaminant reference FASTA for NanoLyse-style filtering'}), 'quality': ('INT', {'default': 0, 'min': 0, 'max': 60, 'description': 'Minimum average Phred quality'}), 'maxqual': ('INT', {'default': 60, 'min': 0, 'max': 60, 'description': 'Maximum average Phred quality'}), 'minlength': ('INT', {'default': 1, 'min': 1, 'description': 'Minimum read length to keep'}), 'maxlength': ('INT', {'default': '', 'min': 1, 'description': 'Maximum read length to keep'}), 'mingc': ('FLOAT', {'default': 0.0, 'min': 0, 'max': 1, 'description': 'Minimum read GC fraction'}), 'maxgc': ('FLOAT', {'default': 1.0, 'min': 0, 'max': 1, 'description': 'Maximum read GC fraction'}), 'trim_approach': ('STRING', {'default': '', 'options': cls.TRIM_APPROACHES, 'description': 'Optional trimming mode applied after filtering'}), 'headcrop': ('INT', {'default': 0, 'min': 0, 'description': 'Bases to crop from read starts'}), 'tailcrop': ('INT', {'default': 0, 'min': 0, 'description': 'Bases to crop from read ends'}), 'cutoff': ('INT', {'default': 10, 'min': 0, 'max': 60, 'description': 'Quality cutoff for trimming modes'}), 'split_window': ('INT', {'default': 1, 'min': 1, 'description': 'Consecutive low-quality bases required before splitting a read'}), 'inverse': ('BOOLEAN', {'default': False, 'description': 'Write reads that fail the normal filters'})}, 'hidden': {'output': ('STRING', {})}}
