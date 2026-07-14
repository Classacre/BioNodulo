"""add — data_transform node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class AddInputNameAsColumnNode(CommandNode):
    """Add the input dataset name as an appended or prepended tabular column."""
    NODE_ID = 'add_input_name_as_column'
    DISPLAY_NAME = 'Add input name as column'
    REQUIRED_CONDA_PACKAGES = ['python']
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Add the input dataset name as an appended or prepended tabular column.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Add input name as column', 'add_input_name_as_column', 'dataset collection labels', 'history dataset name', 'sample label column', 'tabular label column']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = ADD_INPUT_NAME_AS_COLUMN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ADD_INPUT_NAME_AS_COLUMN_CITATION_URL]
    CITATION_TEXT = ADD_INPUT_NAME_AS_COLUMN_CITATION_TEXT
    VERSION = '0.3.0'
    SHELL = True
    HEADER_OPTIONS = ['yes', 'no']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', str(inputs.get('script_path', 'add_input_name_as_column.py')), '--input', str(inputs.get('input', '')), '--label', str(inputs.get('label', '')), '--output', cls._output_path(inputs)]
        if str(inputs.get('contains_header', 'yes') or 'yes') == 'yes':
            cmd.extend(['--header', str(inputs.get('colname', 'sample') or 'sample')])
        if inputs.get('prepend'):
            cmd.append('--prepend')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not str(inputs.get('label', '')).strip():
            return 'label is required'
        contains_header = str(inputs.get('contains_header', 'yes') or 'yes')
        if contains_header not in cls.HEADER_OPTIONS:
            return f"contains_header must be one of: {', '.join(cls.HEADER_OPTIONS)}"
        if contains_header == 'yes' and (not str(inputs.get('colname', 'sample') or '').strip()):
            return 'colname is required when contains_header is yes'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TXT', {'description': 'Text or tabular dataset to annotate with its input label'}), 'label': ('STRING', {'description': "Dataset label to add, matching Galaxy's input element identifier"})}, 'optional': {'contains_header': ('STRING', {'default': 'yes', 'options': cls.HEADER_OPTIONS, 'description': 'Whether the first line should receive a column header instead of the dataset label'}), 'colname': ('STRING', {'default': 'sample', 'description': 'Column name added to the first line when the input has a header'}), 'prepend': ('BOOLEAN', {'default': False, 'description': 'Prepend the label column instead of appending it'}), 'script_path': ('FILE', {'default': 'add_input_name_as_column.py', 'advanced': True, 'description': 'Path to the Galaxy add_input_name_as_column.py helper script'})}, 'hidden': {'output': ('STRING', {})}}
