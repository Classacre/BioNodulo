"""fasta — sequence node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class FastaRegexFinderNode(CommandNode):
    """Search FASTA sequences for regular-expression matches and emit BED coordinates."""
    NODE_ID = 'fasta_regex_finder'
    DISPLAY_NAME = 'Fasta regular expression finder'
    REQUIRED_CONDA_PACKAGES = ['python']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Search FASTA sequences for regular-expression matches and report BED coordinates.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'fasta_regex_finder', 'fastaRegexFinder', 'FASTA regex', 'regular expression finder', 'motif search', 'G-quadruplex', 'BED coordinates', 'reverse complement']
    RETURN_TYPES = ('BED',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = FASTA_REGEX_FINDER_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FASTA_REGEX_FINDER_CITATION_URL]
    CITATION_TEXT = FASTA_REGEX_FINDER_CITATION_TEXT
    VERSION = '0.1.0'
    SHELL = True
    ADVANCED_MODES = ['simple', 'advanced']
    DEFAULT_REGEX = '([gG]{3,}\\w{1,7}){3,}[gG]{3,}'

    @classmethod
    def _advanced(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('advanced', 'simple') or 'simple')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.bed'

    @classmethod
    def _maxstr(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get('maxstr', 10000)
        if value is None or str(value) == '':
            return 10000
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', str(inputs.get('script_path', 'fastaregexfinder.py') or 'fastaregexfinder.py'), '--fasta', str(inputs.get('input', '')), '--regex', str(inputs.get('regex', cls.DEFAULT_REGEX) or cls.DEFAULT_REGEX)]
        if cls._advanced(inputs) == 'advanced':
            if inputs.get('matchcase'):
                cmd.append('--matchcase')
            if inputs.get('noreverse'):
                cmd.append('--noreverse')
            cmd.extend(['--maxstr', str(cls._maxstr(inputs))])
            _add_if_value(cmd, '--seqnames', inputs.get('seqnames'))
        cmd.extend(['--quiet', '>', cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.bed']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not str(inputs.get('regex', cls.DEFAULT_REGEX)).strip():
            return 'regex is required'
        advanced = cls._advanced(inputs)
        if advanced not in cls.ADVANCED_MODES:
            return f"advanced must be one of: {', '.join(cls.ADVANCED_MODES)}"
        if advanced == 'advanced':
            try:
                maxstr = cls._maxstr(inputs)
            except (TypeError, ValueError):
                return 'maxstr must be an integer'
            if maxstr < 1:
                return 'maxstr must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'FASTA sequences to search'})}, 'optional': {'regex': ('STRING', {'default': cls.DEFAULT_REGEX, 'description': 'Regular expression searched in the FASTA input'}), 'advanced': ('STRING', {'default': 'simple', 'options': cls.ADVANCED_MODES, 'description': 'Expose advanced search controls'}), 'matchcase': ('BOOLEAN', {'default': False, 'description': 'Match case instead of ignoring case'}), 'noreverse': ('BOOLEAN', {'default': False, 'description': 'Do not search the reverse complement'}), 'maxstr': ('INT', {'default': 10000, 'min': 1, 'description': 'Maximum length of matched sequence to report'}), 'seqnames': ('STRING', {'default': '', 'description': 'Space-separated FASTA sequence names to search in advanced mode'}), 'script_path': ('FILE', {'default': 'fastaregexfinder.py', 'advanced': True, 'description': 'Path to the fastaRegexFinder script'})}, 'hidden': {'output': ('STRING', {})}}
