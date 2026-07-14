"""qq — visualization node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class QQManhattanNode(CommandNode):
    """Create a GWAS Manhattan plot with qqman."""
    NODE_ID = 'qq_manhattan'
    DISPLAY_NAME = 'Manhattan Plots'
    REQUIRED_CONDA_PACKAGES = ['r-qqman', 'r-optparse']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Create a GWAS Manhattan plot PDF from a tabular association-results file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'qqman', 'qq_manhattan', 'Manhattan Plots', 'GWAS Manhattan plot', 'association results', 'genome-wide association study', 'SNP p-values']
    RETURN_TYPES = ('PDF',)
    RETURN_NAMES = ('manhattan',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://cran.r-project.org/package=qqman'
    CITATION_DOIS = QQMAN_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in QQMAN_CITATION_DOIS]
    CITATION_TEXT = QQMAN_CITATION_TEXT
    VERSION = '0.1.0'
    SHELL = True
    COLUMN_DEFAULTS = {'pval': 'P', 'chr': 'CHR', 'bp': 'BP', 'snp': 'SNP', 'name': 'Manhattan Plot'}

    @classmethod
    def _param(cls, inputs: dict[str, Any], name: str) -> str:
        return str(inputs.get(name, cls.COLUMN_DEFAULTS[name]) or cls.COLUMN_DEFAULTS[name])

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/manhattan.pdf'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['Rscript', str(inputs.get('script_path', 'manhattan.R')), '--file', str(inputs.get('data', '')), '--pval', cls._param(inputs, 'pval'), '--chr', cls._param(inputs, 'chr'), '--bp', cls._param(inputs, 'bp'), '--snp', cls._param(inputs, 'snp'), '--name', cls._param(inputs, 'name')]
        return f"{_shell_join(cmd)} && {_shell_join(['mv', 'manhattan.pdf', cls._output_path(inputs)])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'manhattan.pdf']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('data', '')).strip():
            return 'data is required'
        for name, label in (('pval', 'pval column name'), ('chr', 'chr column name'), ('bp', 'bp column name'), ('snp', 'snp column name'), ('name', 'plot title')):
            if name in inputs and (not str(inputs.get(name, '')).strip()):
                return f'{label} is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data': ('TSV', {'description': 'Tabular GWAS association results with SNP, chromosome, position, and p-value columns'})}, 'optional': {'pval': ('STRING', {'default': 'P', 'description': 'P-value column name in the input file'}), 'chr': ('STRING', {'default': 'CHR', 'description': 'Chromosome column name in the input file'}), 'bp': ('STRING', {'default': 'BP', 'description': 'Base-pair coordinate column name in the input file'}), 'snp': ('STRING', {'default': 'SNP', 'description': 'SNP identifier column name in the input file'}), 'name': ('STRING', {'default': 'Manhattan Plot', 'description': 'Plot title'}), 'script_path': ('FILE', {'default': 'manhattan.R', 'advanced': True, 'description': 'Path to the Galaxy qqman R wrapper script'})}, 'hidden': {'output': ('STRING', {})}}
