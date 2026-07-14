"""datamash — wrapped_core_data node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class DatamashOpsNode(_DatamashBaseNode):
    """Perform GNU Datamash statistical operations on tabular data."""
    NODE_ID = 'datamash_ops'
    DISPLAY_NAME = 'Datamash'
    DESCRIPTION = 'Perform statistical and text operations on tabular data, optionally grouped by fields.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Datamash', 'GNU Datamash', 'datamash_ops', 'group by fields', 'tabular statistics', 'column operations', 'sum mean median']
    REQUIRED_EXECUTABLES = ['datamash']
    OPERATIONS = ['count', 'sum', 'min', 'max', 'absmin', 'absmax', 'mean', 'pstdev', 'sstdev', 'median', 'q1', 'q3', 'iqr', 'mad', 'pvar', 'svar', 'sskew', 'pskew', 'skurt', 'pkurt', 'jarque', 'dpo', 'mode', 'antimode', 'rand', 'unique', 'collapse', 'countunique']

    @classmethod
    def _operations(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        raw = inputs.get('operations')
        if raw is None or raw == '':
            return [{'op_name': str(inputs.get('op_name', 'count') or 'count'), 'op_column': inputs.get('op_column', 1)}]
        if isinstance(raw, list):
            return [op for op in raw if isinstance(op, dict)]
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['datamash']
        for key, flag in (('header_in', '--header-in'), ('header_out', '--header-out'), ('need_sort', '--sort'), ('print_full_line', '--full'), ('ignore_case', '--ignore-case'), ('narm', '--narm')):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(cls._separator_args(inputs))
        grouping = str(inputs.get('grouping', '') or '').replace(' ', '')
        if grouping:
            cmd.extend(['--group', grouping])
        for operation in cls._operations(inputs):
            cmd.extend([str(operation.get('op_name', '')), str(operation.get('op_column', ''))])
        return cls._redirect_stdin_stdout(cmd, inputs)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        common = cls._validate_common(inputs)
        if common is not True:
            return common
        grouping = str(inputs.get('grouping', '') or '').replace(' ', '')
        if grouping and (not re.fullmatch('\\d+(,\\d+)*', grouping)):
            return 'grouping must be a comma-separated list of integer fields'
        operations = cls._operations(inputs)
        if not operations:
            return 'at least one operation is required'
        for operation in operations:
            op_name = str(operation.get('op_name', '') or '')
            if op_name not in cls.OPERATIONS:
                return f"op_name must be one of: {', '.join(cls.OPERATIONS)}"
            try:
                column = int(operation.get('op_column', ''))
            except (TypeError, ValueError):
                return 'op_column must be an integer'
            if column < 1:
                return 'op_column must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        spec = super().INPUT_TYPES()
        spec['optional'].update({'grouping': ('STRING', {'default': '', 'description': 'Comma-separated field numbers used to group consecutive rows'}), 'need_sort': ('BOOLEAN', {'default': False, 'description': 'Sort input by grouping fields before operation'}), 'header_in': ('BOOLEAN', {'default': False, 'description': 'Input file has a header line'}), 'header_out': ('BOOLEAN', {'default': False, 'description': 'Print a header line'}), 'print_full_line': ('BOOLEAN', {'default': False, 'description': 'Print all fields from input file'}), 'ignore_case': ('BOOLEAN', {'default': False, 'description': 'Ignore case while grouping'}), 'narm': ('BOOLEAN', {'default': False, 'description': 'Skip NA and NaN values'}), 'operations': ('JSON', {'default': [{'op_name': 'count', 'op_column': 1}], 'is_list': True, 'description': 'Datamash operation objects with op_name and op_column'}), 'op_name': ('STRING', {'default': 'count', 'options': cls.OPERATIONS, 'description': 'Operation type for simple forms'}), 'op_column': ('INT', {'default': 1, 'min': 1, 'description': 'Column number for simple forms'})})
        return spec


class DatamashTransposeNode(_DatamashBaseNode):
    """Transpose rows and columns with GNU Datamash."""
    NODE_ID = 'datamash_transpose'
    DISPLAY_NAME = 'Transpose'
    REQUIRED_CONDA_PACKAGES = ['datamash', 'coreutils']
    DESCRIPTION = 'Transpose rows and columns in a tabular or CSV file with GNU Datamash.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Datamash', 'GNU Datamash', 'datamash_transpose', 'transpose rows columns', 'matrix transpose']
    REQUIRED_EXECUTABLES = ['datamash', 'split', 'paste']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get('in_file', ''))
        output = cls._output_path(inputs)
        if inputs.get('large_file_mode'):
            chunk_count = str(inputs.get('chunk_count', 2) or 2)
            transpose_cmd = _shell_join(['datamash', 'transpose', *cls._separator_args(inputs)])
            return f"{_shell_join(['split', '-n', f'l/{chunk_count}', input_file, 'split_input_'])} && for chunk in $(ls split_input*); do {transpose_cmd} < $chunk > ${{chunk}}_transposed; done && paste split_input_*_transposed > {shlex.quote(output)}"
        cmd = ['datamash', 'transpose', *cls._separator_args(inputs)]
        return cls._redirect_stdin_stdout(cmd, inputs)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        common = cls._validate_common(inputs)
        if common is not True:
            return common
        chunk_count = inputs.get('chunk_count', 2)
        if str(chunk_count) != '':
            try:
                value = int(chunk_count)
            except (TypeError, ValueError):
                return 'chunk_count must be an integer'
            if value < 1:
                return 'chunk_count must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        spec = super().INPUT_TYPES()
        spec['optional'].update({'large_file_mode': ('BOOLEAN', {'default': False, 'description': 'Use split and paste chunking for very large matrices'}), 'chunk_count': ('INT', {'default': 2, 'min': 1, 'description': 'Number of chunks for large-file transpose'})})
        return spec


class DatamashReverseNode(_DatamashBaseNode):
    """Reverse column order with GNU Datamash."""
    NODE_ID = 'datamash_reverse'
    DISPLAY_NAME = 'Reverse'
    DESCRIPTION = 'Reverse column order in a tabular or CSV file with GNU Datamash.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Datamash', 'GNU Datamash', 'datamash_reverse', 'reverse columns', 'column order']
    REQUIRED_EXECUTABLES = ['datamash']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['datamash', 'reverse', *cls._separator_args(inputs)]
        return cls._redirect_stdin_stdout(cmd, inputs)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return cls._validate_common(inputs)
