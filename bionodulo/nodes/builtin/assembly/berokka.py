"""berokka — assembly node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class BerokkaNode(CommandNode):
    """Trim, circularise, orient, and filter long-read bacterial assemblies."""
    NODE_ID = 'berokka'
    DISPLAY_NAME = 'Berokka'
    REQUIRED_CONDA_PACKAGES = ['berokka']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Trim, circularise, orient and filter long read bacterial genome assemblies.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'berokka', 'Berokka', 'trim circularise orient', 'long read bacterial genome assemblies', 'completed assemblies', 'CANU', 'HGAP', 'Circlator', 'PacBio control sequence']
    RETURN_TYPES = ('FASTA', 'TSV')
    RETURN_NAMES = ('trimmed', 'results')
    REQUIRED_EXECUTABLES = ['berokka']
    DOCUMENTATION_URL = BEROKKA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BEROKKA_CITATION_URL]
    CITATION_TEXT = BEROKKA_CITATION_TEXT
    VERSION = '0.2.3'
    SHELL = True

    @classmethod
    def _read_length(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get('read_length', 60000) or 60000)

    @classmethod
    def _fuzz(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get('fuzz', 5) or 5)

    @classmethod
    def _work_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/default'

    @classmethod
    def _trimmed_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/trimmed.fasta'

    @classmethod
    def _results_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/results.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['berokka', '--outdir', cls._work_dir(inputs), str(inputs.get('input_file', ''))]
        _add_if_value(cmd, '--filter', inputs.get('filter_fasta'))
        cmd.extend(['--readlen', str(cls._read_length(inputs)), '--fuzz', str(cls._fuzz(inputs))])
        if inputs.get('anno', True) is False:
            cmd.append('--noanno')
        cmd.extend(['&&', 'cp', f'{cls._work_dir(inputs)}/02.trimmed.fa', cls._trimmed_path(inputs), '&&', 'cp', f'{cls._work_dir(inputs)}/03.results.tab', cls._results_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'trimmed.fasta', out / 'results.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        try:
            read_length = cls._read_length(inputs)
        except (TypeError, ValueError):
            return 'read_length must be an integer'
        if read_length < 28:
            return 'read_length must be at least 28'
        try:
            cls._fuzz(inputs)
        except (TypeError, ValueError):
            return 'fuzz must be an integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Completed long-read assembly FASTA, such as CANU or HGAP contigs'})}, 'optional': {'filter_fasta': ('FASTA', {'default': '', 'description': 'Optional FASTA whose matching contigs are filtered out'}), 'read_length': ('INT', {'default': 60000, 'min': 28, 'description': 'Approximate maximum read length used for circularisation matching'}), 'fuzz': ('INT', {'default': 5, 'description': 'Accept local alignment within this many bp of global alignment'}), 'anno': ('BOOLEAN', {'default': True, 'description': 'Annotate trimmed FASTA descriptions'})}, 'hidden': {'output': ('STRING', {})}}
