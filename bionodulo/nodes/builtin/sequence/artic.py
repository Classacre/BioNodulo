"""artic — sequence node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ArticGuppyplexNode(CommandNode):
    """Filter and combine Nanopore FASTQ reads with ARTIC guppyplex."""
    NODE_ID = 'artic_guppyplex'
    DISPLAY_NAME = 'ARTIC guppyplex'
    REQUIRED_CONDA_PACKAGES = ['artic']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Filter Nanopore reads by read length and optionally quality with ARTIC guppyplex.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ARTIC guppyplex', 'artic_guppyplex', 'guppyplex', 'Nanopore read length filter', 'amplicon sequencing', 'ARTIC amplicon scheme']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['artic', 'bash', 'gzip']
    DOCUMENTATION_URL = ARTIC_DOCUMENTATION_URL
    CITATION_DOIS = []
    CITATION_URLS = [ARTIC_CITATION_URL]
    CITATION_TEXT = ARTIC_CITATION_TEXT
    VERSION = '1.7.3+galaxy1'
    SHELL = True
    STRUCTURES = ['one_to_one', 'one_to_many']
    FASTQ_FORMATS = ['fastq', 'fastq.gz', 'fastqsanger', 'fastqsanger.gz']

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit_ext = str(inputs.get('input_ext', '') or '')
        if explicit_ext:
            return explicit_ext
        first_read = _as_list(inputs.get('reads'))[0] if _as_list(inputs.get('reads')) else ''
        suffixes = [suffix.lstrip('.') for suffix in Path(first_read).suffixes]
        if len(suffixes) >= 2 and suffixes[-1] == 'gz':
            return f'{suffixes[-2]}.gz'
        return suffixes[-1] if suffixes else 'fastq'

    @classmethod
    def _compressed(cls, inputs: dict[str, Any]) -> bool:
        return cls._input_ext(inputs) in {'fastq.gz', 'fastqsanger.gz'}

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return 'guppyplex_out.fastq.gz' if cls._compressed(inputs) else 'guppyplex_out.fastq'

    @classmethod
    def _inputs_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/inputs'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        reads = _as_list(inputs.get('reads'))
        input_ext = cls._input_ext(inputs)
        commands = [_shell_join(['mkdir', '-p', cls._inputs_dir(inputs)])]
        if str(inputs.get('structure', 'one_to_one') or 'one_to_one') == 'one_to_one':
            if reads:
                commands.append(_shell_join(['ln', '-s', reads[0], f'{cls._inputs_dir(inputs)}/1.{input_ext}']))
        else:
            for idx, read in enumerate(reads):
                commands.append(_shell_join(['ln', '-s', read, f'{cls._inputs_dir(inputs)}/{idx}.{input_ext}']))
        cmd = ['artic', 'guppyplex', '--min-length', str(inputs.get('min_length', 400)), '--max-length', str(inputs.get('max_length', 700))]
        min_quality = int(inputs.get('min_quality', 7))
        if min_quality == 0:
            cmd.append('--skip-quality-check')
        else:
            cmd.extend(['--quality', str(min_quality)])
        cmd.extend(['--directory', f'{cls._inputs_dir(inputs)}/', '--output', f'{_out(inputs)}/guppyplex_out.fastq'])
        commands.append(_shell_join(cmd))
        if cls._compressed(inputs):
            commands.append(_shell_join(['gzip', f'{_out(inputs)}/guppyplex_out.fastq']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get('reads')):
            return 'reads is required'
        structure = str(inputs.get('structure', 'one_to_one') or 'one_to_one')
        if structure not in cls.STRUCTURES:
            return f"structure must be one of: {', '.join(cls.STRUCTURES)}"
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.FASTQ_FORMATS:
            return f"input_ext must be one of: {', '.join(cls.FASTQ_FORMATS)}"
        try:
            min_length = int(inputs.get('min_length', 400))
            max_length = int(inputs.get('max_length', 700))
            min_quality = int(inputs.get('min_quality', 7))
        except (TypeError, ValueError):
            return 'min_length, max_length, and min_quality must be integers'
        if min_length < 1:
            return 'min_length must be greater than or equal to 1'
        if max_length < 1:
            return 'max_length must be greater than or equal to 1'
        if min_quality < 0:
            return 'min_quality must be greater than or equal to 0'
        if max_length < min_length:
            return 'max_length must be greater than or equal to min_length'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Nanopore FASTQ reads to filter'})}, 'optional': {'structure': ('STRING', {'default': 'one_to_one', 'options': cls.STRUCTURES, 'description': 'One or multiple input datasets'}), 'input_ext': ('STRING', {'default': 'fastq', 'options': cls.FASTQ_FORMATS}), 'max_length': ('INT', {'default': 700, 'min': 1, 'description': 'Remove reads greater than this number of base pairs'}), 'min_length': ('INT', {'default': 400, 'min': 1, 'description': 'Remove reads less than this number of base pairs'}), 'min_quality': ('INT', {'default': 7, 'min': 0, 'description': 'Set to 0 to skip the average-quality check'})}, 'hidden': {'output': ('STRING', {})}}
