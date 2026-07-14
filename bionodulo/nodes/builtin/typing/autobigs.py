"""autobigs — typing node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class AutoBIGSCliNode(CommandNode):
    """Perform MLST typing or list schemes from BIGSdb sequence definition databases."""
    NODE_ID = 'autobigs-cli'
    DISPLAY_NAME = 'autoBIGS.cli'
    REQUIRED_CONDA_PACKAGES = ['autobigs-cli']
    CATEGORY = 'typing'
    DESCRIPTION = 'Automated MLST typing with BIGSdb sequence definition databases.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'autobigs', 'autobigs-cli', 'autoBIGS', 'autoBIGS.cli', 'MLST', 'BIGSdb', 'PubMLST', 'Institut Pasteur', 'sequence typing', 'scheme']
    RETURN_TYPES = ('CSV', 'CSV')
    RETURN_NAMES = ('mlst_profiles_output', 'info_schemes_out')
    REQUIRED_EXECUTABLES = ['autoBIGS']
    DOCUMENTATION_URL = AUTOBIGS_CLI_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AUTOBIGS_CLI_CITATION_URL]
    CITATION_TEXT = AUTOBIGS_CLI_CITATION_TEXT
    VERSION = '0.6.2+galaxy0'
    SHELL = True
    OPERATIONS = ['st', 'info']
    DATABASE_ORIGINS = ['pubmlst', 'institutpasteur']

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('operation', 'st') or 'st')

    @classmethod
    def _database_origin(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('database_origin', 'pubmlst') or 'pubmlst')

    @classmethod
    def _mlst_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/mlst_profiles_output.csv'

    @classmethod
    def _info_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/info_schemes_out.csv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        bigsdb = str(inputs.get('bigsdb', ''))
        if cls._operation(inputs) == 'info':
            return _shell_join(['autoBIGS', 'info', '--retrieve-bigsdb-schemes', bigsdb, '--csv', cls._info_output_path(inputs)])
        cmd = ['autoBIGS', 'st', '--scheme-name', str(inputs.get('scheme', 'MLST') or 'MLST')]
        cmd.extend(_as_list(inputs.get('fasta')))
        cmd.extend([bigsdb, cls._mlst_output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'mlst_profiles_output.csv', out / 'info_schemes_out.csv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('bigsdb', '')).strip():
            return 'bigsdb is required'
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        database_origin = cls._database_origin(inputs)
        if database_origin not in cls.DATABASE_ORIGINS:
            return f"database_origin must be one of: {', '.join(cls.DATABASE_ORIGINS)}"
        if operation == 'st':
            if not _as_list(inputs.get('fasta')):
                return 'fasta is required for st operation'
            if not str(inputs.get('scheme', 'MLST')).strip():
                return 'scheme is required for st operation'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bigsdb': ('STRING', {'description': 'BIGSdb sequence definition database name, for example pubmlst_bordetella_seqdef'})}, 'optional': {'database_origin': ('STRING', {'default': 'pubmlst', 'options': cls.DATABASE_ORIGINS, 'description': 'Remote BIGSdb source used to choose the sequence definition database'}), 'operation': ('STRING', {'default': 'st', 'options': cls.OPERATIONS, 'description': 'Run sequence typing or list supported schemes'}), 'fasta': ('FASTA', {'default': [], 'is_list': True, 'description': 'FASTA file or files to type in st mode'}), 'scheme': ('STRING', {'default': 'MLST', 'description': 'BIGSdb SeqDef scheme name used for sequence typing'})}, 'hidden': {'output': ('STRING', {})}}
