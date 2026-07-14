"""charts — visualization node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class ChartsNode(CommandNode):
    """Generate tabular chart data with Galaxy Charts R modules."""
    NODE_ID = 'charts'
    DISPLAY_NAME = 'Charts'
    REQUIRED_CONDA_PACKAGES = ['r-getopt', 'r-matrix']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Generate tabular chart data from tabular inputs with Galaxy Charts R modules.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Charts', 'charts', 'Chart Utilities', 'boxplot', 'heatmap', 'histogram', 'histogramdiscrete', 'R chart modules', 'tabular visualization']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = CHARTS_CITATION_URL
    CITATION_URLS = [CHARTS_CITATION_URL]
    CITATION_TEXT = CHARTS_CITATION_TEXT
    VERSION = '1.0.1'
    SHELL = True
    MODULES = ['boxplot', 'heatmap', 'histogram', 'histogramdiscrete']

    @classmethod
    def _module(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('module', 'boxplot') or 'boxplot')

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('charts_script', 'charts.r') or 'charts.r')

    @classmethod
    def _workdir(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('charts_workdir', './') or './')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['Rscript', cls._script(inputs), '-w', cls._workdir(inputs), '-m', cls._module(inputs), '-i', str(inputs.get('input', '')), '-c', str(inputs.get('columns', '')), '-s', str(inputs.get('settings', '')), '-o', cls._output_path(inputs)]
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if cls._module(inputs) not in cls.MODULES:
            return f"module must be one of: {', '.join(cls.MODULES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Input tabular dataset'})}, 'optional': {'module': ('STRING', {'default': 'boxplot', 'options': cls.MODULES}), 'columns': ('STRING', {'default': '', 'description': 'Column mapping string, such as key1: 2, key2: 3'}), 'settings': ('STRING', {'default': '', 'description': 'Options string, such as key1: value, key2: value'}), 'charts_script': ('FILE', {'default': 'charts.r', 'advanced': True}), 'charts_workdir': ('STRING', {'default': './', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
