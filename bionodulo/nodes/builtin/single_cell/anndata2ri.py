"""anndata2ri — single_cell node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class Anndata2RiNode(CommandNode):
    """Convert between AnnData H5AD and R SingleCellExperiment RDS objects."""
    NODE_ID = 'anndata2ri'
    DISPLAY_NAME = 'anndata2ri'
    REQUIRED_CONDA_PACKAGES = ['anndata2ri', 'anndata', 'bioconductor-singlecellexperiment']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Convert between AnnData and SingleCellExperiment objects.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'anndata2ri', 'AnnData', 'SingleCellExperiment', 'SingleCellexperiment', 'sce2anndata', 'anndata2sce', 'single-cell conversion', 'H5AD', 'RDS']
    RETURN_TYPES = ('H5AD', 'FILE')
    RETURN_NAMES = ('output_anndata', 'output_sce')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = ANNDATA2RI_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ANNDATA2RI_CITATION_URL]
    CITATION_TEXT = ANNDATA2RI_CITATION_TEXT
    VERSION = '1.3.2+galaxy1'
    SHELL = True
    DIRECTIONS = ['sce2anndata', 'anndata2sce']

    @classmethod
    def _direction(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('direction', 'sce2anndata') or 'sce2anndata')

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return 'outfile.rds' if cls._direction(inputs) == 'anndata2sce' else 'outfile.h5ad'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._output_name(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', str(inputs.get('script_path', 'anndata2ri.py')), cls._direction(inputs), str(inputs.get('input_object', '')), cls._output_path(inputs)]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_object', '')).strip():
            return 'input_object is required'
        direction = cls._direction(inputs)
        if direction not in cls.DIRECTIONS:
            return f"direction must be one of: {', '.join(cls.DIRECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_object': ('FILE', {'description': 'AnnData H5AD or SingleCellExperiment RDS object to convert'})}, 'optional': {'direction': ('STRING', {'default': 'sce2anndata', 'options': cls.DIRECTIONS, 'description': 'Conversion direction: SingleCellExperiment to AnnData or AnnData to SingleCellExperiment'}), 'script_path': ('FILE', {'default': 'anndata2ri.py', 'advanced': True, 'description': 'Path to the Galaxy anndata2ri helper script'})}, 'hidden': {'output': ('STRING', {})}}
