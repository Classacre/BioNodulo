"""taxonomy — taxonomy node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TaxonomyKronaChartNode(CommandNode):
    """Render taxonomy or tabular profiles as an interactive Krona chart."""
    NODE_ID = 'taxonomy_krona_chart'
    DISPLAY_NAME = 'Krona pie chart'
    REQUIRED_CONDA_PACKAGES = ['krona']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Render taxonomic profiles as an interactive Krona HTML pie chart.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Krona', 'taxonomy_krona_chart', 'ktImportGalaxy', 'ktImportText', 'taxonomy sunburst', 'metagenomic visualization', 'taxonomic profile']
    RETURN_TYPES = ('HTML_REPORT',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['ktImportGalaxy', 'ktImportText']
    DOCUMENTATION_URL = 'https://github.com/marbl/Krona/wiki'
    CITATION_DOIS = KRONA_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in KRONA_CITATION_DOIS]
    CITATION_TEXT = KRONA_CITATION_TEXT
    VERSION = '2.7.1+galaxy0'
    SHELL = True
    TYPE_OPTIONS = ['taxonomy', 'text']
    MAX_RANK_OPTIONS = ['8', '0', '1', '2', '3', '4', '5', '6', '7', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21']

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('input'))

    @classmethod
    def _input_labels(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        labels = _as_list(inputs.get('element_identifiers'))
        result: list[str] = []
        for index, input_file in enumerate(input_files):
            label = labels[index] if index < len(labels) and labels[index] else Path(input_file).stem
            result.append(_safe_identifier(label))
        return result

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/krona.html'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = str(inputs.get('type_of_data_selector', 'taxonomy') or 'taxonomy')
        cmd = ['ktImportGalaxy' if input_type == 'taxonomy' else 'ktImportText']
        if input_type == 'taxonomy':
            cmd.extend(['-d', str(inputs.get('max_rank', '8') or '8')])
        cmd.extend(['-n', str(inputs.get('root_name', 'Root') or 'Root'), '-o', cls._output_path(inputs)])
        if inputs.get('combine_inputs', False):
            cmd.append('-c')
        input_files = cls._input_files(inputs)
        labels = cls._input_labels(inputs, input_files)
        for input_file, label in zip(input_files, labels, strict=False):
            cmd.append(f'{input_file},{label}')
        return ' && '.join([f'mkdir -p {shlex.quote(out)}', _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'krona.html']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one input file is required'
        input_type = str(inputs.get('type_of_data_selector', 'taxonomy') or 'taxonomy')
        if input_type not in cls.TYPE_OPTIONS:
            return f"type_of_data_selector must be one of: {', '.join(cls.TYPE_OPTIONS)}"
        max_rank = str(inputs.get('max_rank', '8') or '8')
        if max_rank not in cls.MAX_RANK_OPTIONS:
            return f"max_rank must be one of: {', '.join(cls.MAX_RANK_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'multiple': True, 'description': 'One or more taxonomy or tabular profile files'})}, 'optional': {'type_of_data_selector': ('STRING', {'default': 'taxonomy', 'options': cls.TYPE_OPTIONS, 'description': 'Galaxy taxonomy input or generic tabular profile input'}), 'max_rank': ('STRING', {'default': '8', 'options': cls.MAX_RANK_OPTIONS, 'description': 'Maximum taxonomy rank depth for Galaxy taxonomy input'}), 'root_name': ('STRING', {'default': 'Root', 'description': 'Name for the basal rank'}), 'combine_inputs': ('BOOLEAN', {'default': False, 'description': 'Combine multiple datasets into one Krona chart'}), 'element_identifiers': ('STRING', {'default': [], 'multiple': True, 'description': 'Optional labels for the input datasets'})}, 'hidden': {'output': ('STRING', {})}}
