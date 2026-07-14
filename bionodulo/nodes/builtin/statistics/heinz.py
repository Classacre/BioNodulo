"""heinz — statistics node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _Beacon2MultiInputBaseNode(CommandNode):
    """Shared command rendering for Beacon2 converters that symlink multi-input collections."""
    REQUIRED_CONDA_PACKAGES = ['beacon2-ri-tools', 'gzip']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2'
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f'{DOI_URL}{BEACON2_DOI}']
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = '2.0.0+galaxy0'
    SHELL = True
    INPUT_NAME = ''

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get(cls.INPUT_NAME))

    @classmethod
    def _staged_paths(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        labels = _as_list(inputs.get('element_identifiers'))
        staged: list[str] = []
        for index, input_file in enumerate(cls._input_files(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_file
            staged.append(f'{out}/{_safe_element_identifier(label)}')
        return staged

    @classmethod
    def _symlink_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return [_shell_join(['ln', '-s', input_file, staged_path]) for input_file, staged_path in zip(cls._input_files(inputs), cls._staged_paths(inputs), strict=False)]
class _UcscSingleFileUtilityNode(CommandNode):
    """Shared behavior for single-input UCSC Genome Browser utilities."""
    CATEGORY = 'genomics'
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    DOCUMENTATION_URL = ''
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    TOOL_NAME = ''
    INPUT_NAME = ''
    OUTPUT_FILENAME = ''
    INPUT_DESCRIPTION = ''

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls.OUTPUT_FILENAME}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, '')), cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get(cls.INPUT_NAME, '')).strip():
            return f'{cls.INPUT_NAME} is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {cls.INPUT_NAME: ('FILE', {'description': cls.INPUT_DESCRIPTION})}, 'hidden': {'output': ('STRING', {})}}


class HeinzNode(CommandNode):
    """Identify an optimal scoring subnetwork with Heinz."""
    NODE_ID = 'heinz'
    DISPLAY_NAME = 'Identify optimal scoring subnetwork'
    REQUIRED_CONDA_PACKAGES = ['heinz']
    CATEGORY = 'statistics'
    DESCRIPTION = 'Identify an optimal scoring subnetwork from Heinz score and edge files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Heinz', 'heinz', 'optimal scoring subnetwork', 'protein-protein interaction networks', 'functional modules', 'score file', 'edge file']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('subnetwork',)
    REQUIRED_EXECUTABLES = ['heinz']
    DOCUMENTATION_URL = 'https://github.com/ls-cwi/heinz'
    CITATION_DOIS = [HEINZ_CITATION_DOIS[0]]
    CITATION_URLS = [f'{DOI_URL}{HEINZ_CITATION_DOIS[0]}']
    CITATION_TEXT = 'Heinz identifies optimal scoring subnetworks in protein-protein interaction networks.'
    VERSION = '1.0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/subnetwork.txt'

    @classmethod
    def _threads_arg(cls, inputs: dict[str, Any]) -> str:
        if 'threads' not in inputs or inputs.get('threads') in (None, ''):
            return '${GALAXY_SLOTS:-2}'
        return str(inputs.get('threads'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        threads = cls._threads_arg(inputs)
        cmd = ['heinz', '-m']
        if threads == '${GALAXY_SLOTS:-2}':
            cmd_text = f'{_shell_join(cmd)} {threads}'
        else:
            cmd_text = _shell_join([*cmd, threads])
        cmd_text = ' '.join([cmd_text, _shell_join(['-n', str(inputs.get('score', '')), '-e', str(inputs.get('edge', ''))])])
        return f'{cmd_text} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'subnetwork.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('score', '')).strip():
            return 'score is required'
        if not str(inputs.get('edge', '')).strip():
            return 'edge is required'
        if 'threads' in inputs and inputs.get('threads') not in (None, ''):
            try:
                threads = int(inputs['threads'])
            except (TypeError, ValueError):
                return 'threads must be an integer'
            if threads <= 0:
                return 'threads must be greater than 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'score': ('TXT', {'description': 'Two-column Heinz score file with node identifier and score'}), 'edge': ('TXT', {'description': 'Two-column edge list defining the background network'})}, 'optional': {'threads': ('INT', {'default': 2, 'min': 1, 'description': 'Worker count passed to heinz -m'})}, 'hidden': {'output': ('STRING', {})}}


class HeinzScoringNode(CommandNode):
    """Calculate per-node Heinz scores from p-values and BUM parameters."""
    NODE_ID = 'heinz_scoring'
    DISPLAY_NAME = 'Calculate a Heinz score'
    REQUIRED_CONDA_PACKAGES = ['pandas', 'numpy']
    CATEGORY = 'statistics'
    DESCRIPTION = 'Calculate Heinz node scores from p-values and BUM model parameters.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Heinz', 'heinz_scoring', 'Calculate a Heinz score', 'Heinz score', 'BUM model', 'Beta-Uniform Mixture', 'p-value scoring', 'node p-values']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('score',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/heinz'
    CITATION_DOIS = HEINZ_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HEINZ_CITATION_DOIS]
    CITATION_TEXT = HEINZ_CITATION_TEXT
    VERSION = '1.0'
    SHELL = True
    INPUT_TYPE_OPTIONS = ['bum_output', 'bum_type']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/score.txt'

    @staticmethod
    def _format_float(value: Any, default: float) -> str:
        if value in (None, ''):
            value = default
        return f'{float(value):g}'

    @staticmethod
    def _validate_float(value: Any, name: str, default: float) -> tuple[float, str] | str:
        if value in (None, ''):
            value = default
        try:
            return (float(value), f'{float(value):g}')
        except (TypeError, ValueError):
            return f'{name} must be a number'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['python', str(inputs.get('script_path', 'heinz_scoring.py')), '-n', str(inputs.get('node', '')), '-f', cls._format_float(inputs.get('FDR'), 0.5), '-o', cls._output_path(inputs)]
        if str(inputs.get('input_type_selector', 'bum_output')) == 'bum_type':
            cmd.extend(['-l', cls._format_float(inputs.get('lambda_param'), 0.5), '-a', cls._format_float(inputs.get('alpha'), 0.5)])
        else:
            cmd.extend(['-m', str(inputs.get('input_bum', ''))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'score.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('node', '')).strip():
            return 'node is required'
        fdr = cls._validate_float(inputs.get('FDR'), 'FDR', 0.5)
        if isinstance(fdr, str):
            return fdr
        if fdr[0] <= 0 or fdr[0] >= 1:
            return 'FDR must be greater than 0 and less than 1'
        input_type_selector = str(inputs.get('input_type_selector', 'bum_output') or 'bum_output')
        if input_type_selector not in cls.INPUT_TYPE_OPTIONS:
            return f"input_type_selector must be one of: {', '.join(cls.INPUT_TYPE_OPTIONS)}"
        if input_type_selector == 'bum_output':
            if not str(inputs.get('input_bum', '')).strip():
                return 'input_bum is required when input_type_selector is bum_output'
            return True
        lam = cls._validate_float(inputs.get('lambda_param'), 'lambda_param', 0.5)
        if isinstance(lam, str):
            return lam
        if lam[0] < 0 or lam[0] > 1:
            return 'lambda_param must be between 0 and 1'
        alpha = cls._validate_float(inputs.get('alpha'), 'alpha', 0.5)
        if isinstance(alpha, str):
            return alpha
        if alpha[0] < 0 or alpha[0] >= 1:
            return 'alpha must be greater than or equal to 0 and less than 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'node': ('TXT', {'description': 'Two-column text file containing node identifiers and p-values'})}, 'optional': {'FDR': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'False discovery rate used to calculate the score threshold'}), 'input_type_selector': ('STRING', {'default': 'bum_output', 'options': cls.INPUT_TYPE_OPTIONS, 'description': 'Choose whether BUM parameters come from a BUM output file or manual values'}), 'input_bum': ('TXT', {'default': '', 'description': 'BUM model output with lambda on the first line and alpha on the second'}), 'lambda_param': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Manual BUM lambda parameter'}), 'alpha': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Manual BUM alpha parameter'}), 'script_path': ('FILE', {'default': 'heinz_scoring.py', 'advanced': True, 'description': 'Path to the Galaxy Heinz scoring Python wrapper script'})}, 'hidden': {'output': ('STRING', {})}}


class HeinzBumNode(CommandNode):
    """Fit a Beta-Uniform Mixture model to p-values with BioNet."""
    NODE_ID = 'heinz_bum'
    DISPLAY_NAME = 'Fit a BUM model'
    REQUIRED_CONDA_PACKAGES = ['bioconductor-bionet', 'r-getopt']
    CATEGORY = 'statistics'
    DESCRIPTION = 'Fit a Beta-Uniform Mixture model to a one-column p-value distribution.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Heinz', 'BioNet', 'heinz_bum', 'BUM model', 'Beta-Uniform Mixture', 'p-value distribution', 'fitBumModel']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('dist_params',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/BioNet'
    CITATION_DOIS = HEINZ_BUM_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HEINZ_BUM_CITATION_DOIS]
    CITATION_TEXT = HEINZ_BUM_CITATION_TEXT
    VERSION = '1.0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/dist_params.txt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['Rscript', str(inputs.get('script_path', 'bum.R')), '--input', str(inputs.get('p_values', '')), '--output', cls._output_path(inputs)]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'dist_params.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('p_values', '')).strip():
            return 'p_values is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'p_values': ('FILE', {'description': 'Text file containing one p-value per line'})}, 'optional': {'script_path': ('FILE', {'default': 'bum.R', 'advanced': True, 'description': 'Path to the Galaxy Heinz BUM R wrapper script'})}, 'hidden': {'output': ('STRING', {})}}
