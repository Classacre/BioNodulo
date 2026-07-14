"""argnorm — annotation node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class ArgNormNode(CommandNode):
    """Normalize ARG annotation tables to Antibiotic Resistance Ontology terms."""
    NODE_ID = 'argnorm'
    DISPLAY_NAME = 'argNorm'
    REQUIRED_CONDA_PACKAGES = ['argnorm']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Normalize antibiotic resistance gene annotations by mapping them to the Antibiotic Resistance Ontology.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'argnorm', 'argNorm', 'antibiotic resistance genes', 'ARG normalization', 'Antibiotic Resistance Ontology', 'ARO', 'CARD', 'hAMRonization']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['argnorm']
    DOCUMENTATION_URL = 'https://github.com/BigDataBiology/argNorm'
    CITATION_DOIS = [ARGNORM_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ARGNORM_CITATION_DOI}']
    CITATION_TEXT = ARGNORM_CITATION_TEXT
    VERSION = '1.0.0+galaxy0'
    SHELL = True
    TOOLS = ['deeparg', 'argsoap', 'abricate', 'resfinder', 'amrfinderplus', 'groot', 'hamronization']
    ABRICATE_DBS = ['sarg', 'ncbi', 'resfinder', 'resfinderfg', 'deeparg', 'megares', 'argannot']
    GROOT_DBS = ['groot-resfinder', 'groot-argannot', 'groot-card', 'groot-db', 'groot-core-db']

    @classmethod
    def _tool(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('tool', 'deeparg') or 'deeparg')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/argnorm.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        tool = cls._tool(inputs)
        cmd = ['argnorm', tool]
        if tool == 'abricate':
            cmd.extend(['--db', str(inputs.get('abricate_db', 'sarg') or 'sarg')])
        elif tool == 'groot':
            cmd.extend(['--db', str(inputs.get('groot_db', 'groot-resfinder') or 'groot-resfinder')])
        cmd.extend(['-i', str(inputs.get('input', '')), '-o', cls._output_path(inputs)])
        if tool == 'hamronization' and inputs.get('hamronized'):
            cmd.append('--hamronization_skip_unsupported_tool')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'argnorm.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        tool = cls._tool(inputs)
        if tool not in cls.TOOLS:
            return f"tool must be one of: {', '.join(cls.TOOLS)}"
        abricate_db = str(inputs.get('abricate_db', 'sarg') or 'sarg')
        if tool == 'abricate' and abricate_db not in cls.ABRICATE_DBS:
            return f"abricate_db must be one of: {', '.join(cls.ABRICATE_DBS)}"
        groot_db = str(inputs.get('groot_db', 'groot-resfinder') or 'groot-resfinder')
        if tool == 'groot' and groot_db not in cls.GROOT_DBS:
            return f"groot_db must be one of: {', '.join(cls.GROOT_DBS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'ARG annotation table from a supported tool'})}, 'optional': {'tool': ('STRING', {'default': 'deeparg', 'options': cls.TOOLS, 'description': 'Tool that produced the ARG annotation input'}), 'abricate_db': ('STRING', {'default': 'sarg', 'options': cls.ABRICATE_DBS, 'description': 'ABRicate database used for the input annotations'}), 'groot_db': ('STRING', {'default': 'groot-resfinder', 'options': cls.GROOT_DBS, 'description': 'Groot database used for the input annotations'}), 'hamronized': ('BOOLEAN', {'default': False, 'description': 'Skip unsupported tools in combined hAMRonization results'})}, 'hidden': {'output': ('STRING', {})}}
