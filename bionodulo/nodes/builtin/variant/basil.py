"""basil — variant node(s). One tool per file (extracted from wrapped_core_data.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _DatamashBaseNode(CommandNode):
    """Shared metadata and helpers for GNU Datamash Galaxy wrappers."""
    REQUIRED_CONDA_PACKAGES = ['datamash']
    CATEGORY = 'data_transform'
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('out_file',)
    DOCUMENTATION_URL = DATAMASH_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [DATAMASH_CITATION_URL]
    CITATION_TEXT = DATAMASH_CITATION_TEXT
    VERSION = '1.9'
    SHELL = True
    INPUT_EXT_OPTIONS = ['tabular', 'tsv', 'csv']

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_ext', 'tabular') or 'tabular')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_file.tsv'

    @classmethod
    def _separator_args(cls, inputs: dict[str, Any]) -> list[str]:
        return ['-t', ','] if cls._input_ext(inputs) == 'csv' else []

    @classmethod
    def _redirect_stdin_stdout(cls, cmd: list[str], inputs: dict[str, Any]) -> str:
        cmd.extend(['>', cls._output_path(inputs)])
        input_file = shlex.quote(str(inputs.get('in_file', '')))
        return _shell_join(cmd).replace(' > ', f' < {input_file} > ')

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out_file.tsv']

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_file', '')).strip():
            return 'in_file is required'
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('TSV', {'description': 'Input tabular, TSV, or CSV dataset'})}, 'optional': {'input_ext': ('STRING', {'default': 'tabular', 'options': cls.INPUT_EXT_OPTIONS, 'description': 'Input file format'})}, 'hidden': {'output': ('STRING', {})}}


class BasilNode(CommandNode):
    """Detect structural-variant breakpoints with BASIL."""
    NODE_ID = 'basil'
    DISPLAY_NAME = 'basil'
    REQUIRED_CONDA_PACKAGES = ['anise_basil']
    CATEGORY = 'variant'
    DESCRIPTION = 'Detect structural-variant breakpoints, including large insertions, from BAM reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'basil', 'BASIL', 'anise_basil', 'breakpoint detection', 'structural variants', 'large insertions', 'insertion breakpoints', 'one-end-anchor reads', 'OEA']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['basil']
    DOCUMENTATION_URL = f'{DOI_URL}{BASIL_CITATION_DOI}'
    CITATION_DOIS = [BASIL_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BASIL_CITATION_DOI}']
    CITATION_TEXT = BASIL_CITATION_TEXT
    VERSION = '1.2.0+galaxy2'
    SHELL = True
    REFERENCE_SOURCE_OPTIONS = ['cached', 'history']

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference_source_selector', inputs.get('reference_source', 'history')) or 'history')

    @classmethod
    def _support_threshold(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get('min_oea_each_side', 2)
        if value is None or str(value) == '':
            return 2
        return int(value)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.vcf'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['ln', '-f', '-s', str(inputs.get('ref', '')), 'ref.fa', '&&', 'ln', '-s', str(inputs.get('bam', '')), 'in.bam', '&&', 'basil', '--input-reference', 'ref.fa', '--input-mapping', 'in.bam', '--out-vcf', cls._output_path(inputs), '--oea-min-support-each-side', str(cls._support_threshold(inputs))]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.vcf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('ref', '')).strip():
            return 'ref is required'
        if not str(inputs.get('bam', '')).strip():
            return 'bam is required'
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        try:
            min_oea_each_side = cls._support_threshold(inputs)
        except (TypeError, ValueError):
            return 'min_oea_each_side must be an integer'
        if min_oea_each_side < 1:
            return 'min_oea_each_side must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'ref': ('FASTA', {'description': 'Reference genome FASTA from history or a built-in cached reference'}), 'bam': ('BAM', {'description': 'SAM/BAM alignments to scan for breakpoints'})}, 'optional': {'reference_source_selector': ('STRING', {'default': 'history', 'options': cls.REFERENCE_SOURCE_OPTIONS, 'description': 'Use a reference FASTA from history or a built-in cached reference'}), 'min_oea_each_side': ('INT', {'default': 2, 'min': 1, 'description': 'Minimum OEA supporting reads on each side of an insertion breakpoint'})}, 'hidden': {'output': ('STRING', {})}}
