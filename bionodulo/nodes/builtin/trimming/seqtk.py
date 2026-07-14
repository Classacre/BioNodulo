"""seqtk — trimming node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class SeqTKTrimFQNode(CommandNode):
    """Trim FASTQ reads with seqtk trimfq."""
    NODE_ID = 'seqtk_trimfq'
    DISPLAY_NAME = 'SeqTK Trim FASTQ'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'pigz']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Trim FASTQ reads by Phred quality or fixed end positions.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk trimfq', 'SeqTK trimfq', 'FASTQ trimming', 'Phred trimming', 'quality trimming', 'trim reads', 'fixed position trim']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('trimmed_reads',)
    REQUIRED_EXECUTABLES = ['seqtk', 'pigz']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lstrip('.')
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get('in_file', ''))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip('.')
        return 'fastq'

    @classmethod
    def _output_ext(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {'fq', 'fastqsanger'}:
            return 'fastq'
        if ext in {'fq.gz', 'fastqsanger.gz'}:
            return 'fastq.gz'
        return ext or 'fastq'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return f'trimmed.{cls._output_ext(inputs)}'

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        mode = str(inputs.get('mode_select', 'quality') or 'quality')
        cmd = ['seqtk', 'trimfq']
        if mode == 'position':
            cmd.extend(['-b', str(inputs.get('b', 0)), '-e', str(inputs.get('e', 0))])
        else:
            cmd.extend(['-q', str(inputs.get('q', 0.05)), '-l', str(inputs.get('l', 30))])
        cmd.append(str(inputs.get('in_file', '')))
        if cls._output_ext(inputs).endswith('.gz'):
            return f'{_shell_join(cmd)} | pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time > {shlex.quote(cls._out_path(inputs))}'
        return f'{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base = super().VALIDATE_INPUTS(inputs)
        if base is not True:
            return base
        mode = str(inputs.get('mode_select', 'quality') or 'quality')
        if mode not in {'quality', 'position'}:
            return f'Unsupported trim mode: {mode}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ_LIST', {'description': 'Input FASTQ file, optionally gzip-compressed'})}, 'optional': {'mode_select': ('STRING', {'default': 'quality', 'options': ['quality', 'position'], 'description': 'Trim by quality thresholds or fixed end positions'}), 'q': ('FLOAT', {'default': 0.05, 'description': 'Error rate threshold for quality trimming'}), 'l': ('INT', {'default': 30, 'description': 'Maximally trim down to this read length'}), 'b': ('INT', {'default': 0, 'description': 'Trim this many bases from the left end'}), 'e': ('INT', {'default': 0, 'description': 'Trim this many bases from the right end'}), 'input_ext': ('STRING', {'default': 'fastq', 'options': ['fastq', 'fastq.gz', 'fastqsanger', 'fastqsanger.gz'], 'description': 'Input/output FASTQ format used to mirror Galaxy format_source metadata', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
