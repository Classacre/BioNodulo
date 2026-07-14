"""bamleftalign — variant node(s). One tool per file (extracted from wrapped_bcftools.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BamLeftAlignNode(CommandNode):
    """Left-realign indels in BAM alignments with FreeBayes bamleftalign."""
    NODE_ID = 'bamleftalign'
    DISPLAY_NAME = 'BamLeftAlign'
    REQUIRED_CONDA_PACKAGES = ['freebayes', 'samtools', 'coreutils']
    CATEGORY = 'variant'
    DESCRIPTION = 'Left-realign indels in BAM alignments using the FreeBayes bamleftalign utility.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'FreeBayes', 'bamleftalign', 'left realignment', 'left-align BAM indels', 'indel normalization']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('realigned_bam',)
    REQUIRED_EXECUTABLES = ['bamleftalign', 'samtools']
    DOCUMENTATION_URL = 'https://github.com/freebayes/freebayes#citation'
    CITATION_DOIS = FREEBAYES_CITATION_DOIS
    CITATION_URLS = FREEBAYES_CITATION_URLS
    CITATION_TEXT = FREEBAYES_CITATION_TEXT
    VERSION = '1.3.10+galaxy0'
    SHELL = True
    REFERENCE_SOURCE_OPTIONS = ['history', 'cached']

    @classmethod
    def _input_bam(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_bam', inputs.get('bam', '')) or '')

    @classmethod
    def _reference(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference', inputs.get('ref_file', inputs.get('fasta_ref', ''))) or '')

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source', inputs.get('reference_source_selector', 'history')) or 'history')

    @classmethod
    def _iterations(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get('iterations', 5)
        return 5 if value is None or value == '' else int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reference = cls._reference(inputs)
        cmd: list[str] = []
        if cls._reference_source(inputs) == 'history':
            cmd.extend(['samtools', 'faidx', reference, '&&'])
        cmd.extend(['cat', cls._input_bam(inputs), '|', 'bamleftalign', '--fasta-reference', reference, '-c', '--max-iterations', str(cls._iterations(inputs))])
        _add_shell_redirect(cmd, f'{_out(inputs)}/realigned.bam')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bcftools_common_output(cls.NODE_ID, 'realigned.bam', output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_bam(inputs).strip():
            return 'input_bam is required'
        if not cls._reference(inputs).strip():
            return 'reference is required'
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        try:
            iterations = cls._iterations(inputs)
        except (TypeError, ValueError):
            return 'iterations must be an integer'
        if iterations < 1:
            return 'iterations must be at least 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_bam': ('BAM', {'description': 'BAM dataset to left-realign'}), 'reference': ('FASTA', {'description': 'Reference FASTA used by bamleftalign'})}, 'optional': {'reference_source': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Reference source matching the Galaxy wrapper selector'}), 'iterations': ('INT', {'default': 5, 'min': 1, 'description': 'Maximum number of left-realignment iterations'}), 'bam': ('BAM', {'description': 'Compatibility alias for input_bam', 'advanced': True}), 'ref_file': ('FASTA', {'description': 'Compatibility alias for reference', 'advanced': True}), 'fasta_ref': ('FASTA', {'description': 'Compatibility alias for reference', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
