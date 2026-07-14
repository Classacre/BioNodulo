"""chopin2 — ai node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class Chopin2Node(CommandNode):
    """Classify tabular datasets with CHOPIN2 hyperdimensional computing."""
    NODE_ID = 'chopin2'
    DISPLAY_NAME = 'chopin2'
    REQUIRED_CONDA_PACKAGES = ['chopin2']
    CATEGORY = 'ai'
    DESCRIPTION = 'Domain-agnostic supervised learning with hyperdimensional computing.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chopin2', 'CHOPIN2', 'hyperdimensional computing', 'supervised learning', 'feature selection', 'backward variable selection', 'cross-validation', 'DNA methylation classification']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('summary', 'selection')
    REQUIRED_EXECUTABLES = ['chopin2']
    DOCUMENTATION_URL = 'https://github.com/cumbof/chopin2'
    CITATION_DOIS = [CHOPIN2_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHOPIN2_CITATION_DOI}']
    CITATION_TEXT = CHOPIN2_CITATION_TEXT
    VERSION = '1.0.9.post1+galaxy0'
    SHELL = True
    DATASET_EXTENSIONS = ['csv', 'tabular']

    @classmethod
    def _dataset_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('dataset_ext', 'csv') or 'csv')

    @classmethod
    def _dataset_identifier(cls, inputs: dict[str, Any]) -> str:
        identifier = str(inputs.get('dataset_identifier', '') or '')
        if identifier:
            return _safe_element_identifier(identifier)
        return _safe_element_identifier(str(inputs.get('dataset', '')))

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def _threads(cls, inputs: dict[str, Any]) -> str:
        return f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        dataset_identifier = cls._dataset_identifier(inputs)
        tab_token = '__CHOPIN2_TAB__'
        cmd = ['chopin2', '--dataset', dataset_identifier, '--fieldsep', tab_token if cls._dataset_ext(inputs) == 'tabular' else ',', '--dimensionality', str(inputs.get('dimensionality', 10000)), '--levels', str(inputs.get('levels', 1000)), '--retrain', str(inputs.get('retrain', 0)), '--stop', '--crossv_k', str(inputs.get('folds', 2))]
        if cls._bool_flag(inputs.get('enable_fs', False)):
            cmd.extend(['--select_features', '--group_min', str(inputs.get('group_min', 1)), '--accuracy_threshold', str(inputs.get('accuracy_threshold', 60.0)), '--accuracy_uncertainty_perc', str(inputs.get('accuracy_uncertainty_perc', 5.0))])
        threads = cls._threads(inputs)
        cmd.extend(['--dump', '--cleanup', '--nproc', threads, '--verbose'])
        command = _shell_join(cmd).replace(tab_token, "$'\\t'").replace(shlex.quote(threads), threads)
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(['ln', '-s', str(inputs.get('dataset', '')), dataset_identifier])} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'summary.txt']
        if cls._bool_flag(inputs.get('enable_fs', False)):
            outputs.append(out / 'selection.txt')
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be numeric'
        if value < minimum or value > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('dataset', '')).strip():
            return 'dataset is required'
        dataset_ext = cls._dataset_ext(inputs)
        if dataset_ext not in cls.DATASET_EXTENSIONS:
            return f"dataset_ext must be one of: {', '.join(cls.DATASET_EXTENSIONS)}"
        for key, default, minimum in [('dimensionality', 10000, 100), ('levels', 1000, 2), ('retrain', 0, 0), ('folds', 2, 2), ('threads', 4, 1)]:
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        if cls._bool_flag(inputs.get('enable_fs', False)):
            result = cls._validate_int_min(inputs, 'group_min', 1, 1)
            if result is not True:
                return result
            for key, default in {'accuracy_threshold': 60.0, 'accuracy_uncertainty_perc': 5.0}.items():
                result = cls._validate_float_range(inputs, key, default, 0.0, 100.0)
                if result is not True:
                    return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'dataset': ('FILE', {'description': 'CSV or tabular matrix with observation IDs and class labels'})}, 'optional': {'dataset_ext': ('STRING', {'default': 'csv', 'options': cls.DATASET_EXTENSIONS}), 'dataset_identifier': ('STRING', {'default': '', 'description': 'Optional staged dataset filename used by chopin2'}), 'dimensionality': ('INT', {'default': 10000, 'min': 100}), 'levels': ('INT', {'default': 1000, 'min': 2}), 'retrain': ('INT', {'default': 0, 'min': 0}), 'folds': ('INT', {'default': 2, 'min': 2}), 'enable_fs': ('BOOLEAN', {'default': False, 'description': 'Enable feature selection'}), 'group_min': ('INT', {'default': 1, 'min': 1}), 'accuracy_threshold': ('FLOAT', {'default': 60.0, 'min': 0, 'max': 100}), 'accuracy_uncertainty_perc': ('FLOAT', {'default': 5.0, 'min': 0, 'max': 100}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
