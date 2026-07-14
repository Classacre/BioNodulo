"""b2btools — proteomics node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class B2BToolsSingleSequenceNode(CommandNode):
    """Run Bio2Byte single-sequence biophysical predictors on protein FASTA."""
    NODE_ID = 'b2btools_single_sequence'
    DISPLAY_NAME = 'b2bTools: Biophysical predictors for single sequences'
    REQUIRED_CONDA_PACKAGES = ['b2btools']
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Predict protein biophysical properties from amino-acid FASTA sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'b2btools', 'Bio2Byte', 'DynaMine', 'DisoMine', 'EFoldMine', 'AgMata', 'protein disorder', 'backbone dynamics', 'early folding', 'beta aggregation', 'biophysical predictors']
    RETURN_TYPES = ('JSON', 'DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('predictions_output', 'split_output', 'split_output_plots')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://bio2byte.be/'
    CITATION_DOIS = B2BTOOLS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in B2BTOOLS_CITATION_DOIS]
    CITATION_TEXT = B2BTOOLS_CITATION_TEXT
    VERSION = '3.0.5+galaxy0'
    SHELL = True
    PREDICTOR_FLAGS = {'dynamine': '--dynamine', 'disomine': '--disomine', 'efoldmine': '--efoldmine', 'agmata': '--agmata'}

    @classmethod
    def _node_output_dir(cls, inputs: dict[str, Any]) -> str:
        return _out(inputs)

    @classmethod
    def _tabular_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{cls._node_output_dir(inputs)}/tabular'

    @classmethod
    def _plots_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{cls._node_output_dir(inputs)}/plots'

    @classmethod
    def _json_path(cls, inputs: dict[str, Any]) -> str:
        return f'{cls._node_output_dir(inputs)}/predictions.json'

    @classmethod
    def _enabled_predictors(cls, inputs: dict[str, Any]) -> list[str]:
        return [key for key in cls.PREDICTOR_FLAGS if inputs.get(key, True)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['mkdir', '-p', cls._tabular_dir(inputs), cls._plots_dir(inputs), '&&', 'python', str(inputs.get('script_path', 'script.py') or 'script.py'), '--file', str(inputs.get('input', '')), '--output', cls._tabular_dir(inputs), '--json', cls._json_path(inputs)]
        for predictor in cls._enabled_predictors(inputs):
            cmd.append(cls.PREDICTOR_FLAGS[predictor])
        if inputs.get('plot') or inputs.get('plot_all'):
            cmd.extend(['--plot-output', cls._plots_dir(inputs)])
        if inputs.get('plot'):
            cmd.append('--plot')
        if inputs.get('plot_all'):
            cmd.append('--plot_all')
        if inputs.get('highlight'):
            cmd.append('--highlight')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        tabular = out / 'tabular'
        plots = out / 'plots'
        tabular.mkdir(parents=True, exist_ok=True)
        plots.mkdir(parents=True, exist_ok=True)
        return [out / 'predictions.json', tabular, plots]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not cls._enabled_predictors(inputs):
            return 'at least one predictor must be selected'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Protein sequences in FASTA format'})}, 'optional': {'dynamine': ('BOOLEAN', {'default': True, 'description': 'Predict backbone dynamics and related properties'}), 'disomine': ('BOOLEAN', {'default': True, 'description': 'Predict protein disorder'}), 'efoldmine': ('BOOLEAN', {'default': True, 'description': 'Predict early folding regions'}), 'agmata': ('BOOLEAN', {'default': True, 'description': 'Predict beta-aggregation-prone regions'}), 'plot': ('BOOLEAN', {'default': False, 'description': 'Plot predicted values for each sequence'}), 'plot_all': ('BOOLEAN', {'default': False, 'description': 'Plot all sequences together for each predicted value'}), 'highlight': ('BOOLEAN', {'default': False, 'description': 'Highlight known biophysical regions on plots'}), 'script_path': ('FILE', {'default': 'script.py', 'advanced': True, 'description': 'Path to the Galaxy b2bTools helper script'})}, 'hidden': {'output': ('STRING', {})}}
