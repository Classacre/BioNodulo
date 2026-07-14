"""brew3r — annotation node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class Brew3rRNode(CommandNode):
    """Extend GTF annotations at 3' ends with BREW3R.r."""
    NODE_ID = 'brew3r_r'
    DISPLAY_NAME = 'BREW3R.r'
    REQUIRED_CONDA_PACKAGES = ['bioconductor-brew3r.r', 'bioconductor-rtracklayer', 'r-getopt']
    CATEGORY = 'annotation'
    DESCRIPTION = "Extend GTF annotations at 3' ends with another GTF while preventing new gene overlaps."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BREW3R.r', 'brew3r_r', 'extend GTF', 'GTF extension', '3-prime exon extension', 'StringTie annotation extension']
    RETURN_TYPES = ('GTF', 'TSV')
    RETURN_NAMES = ('output', 'output_table')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = BREW3R_R_CITATION_URL
    CITATION_URLS = [BREW3R_R_CITATION_URL]
    CITATION_TEXT = BREW3R_R_CITATION_TEXT
    VERSION = '1.0.2+galaxy1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.gtf'

    @classmethod
    def _table_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_table.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['Rscript', str(inputs.get('script_path', 'brew3r.r_script.R')), '--gtf_to_extend', str(inputs.get('gtf_to_extend', '')), '--gtf_to_overlap', str(inputs.get('gtf_to_overlap', ''))]
        if inputs.get('sup_output', False):
            cmd.extend(['--sup_output', cls._table_path(inputs)])
        if inputs.get('no_add', False):
            cmd.append('--no_add')
        _add_if_value(cmd, '--exclude_pattern', inputs.get('exclude_pattern'))
        if inputs.get('filter_unstranded', False):
            cmd.append('--filter_unstranded')
        cmd.extend(['-o', cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.gtf']
        if inputs.get('sup_output', False):
            outputs.append(out / 'output_table.tsv')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('gtf_to_extend', '')).strip():
            return 'gtf_to_extend is required'
        if not str(inputs.get('gtf_to_overlap', '')).strip():
            return 'gtf_to_overlap is required'
        for key in ('sup_output', 'no_add', 'filter_unstranded'):
            value = inputs.get(key)
            if value is not None and (not isinstance(value, bool)):
                return f'{key} must be a boolean'
        if any((quote in str(inputs.get('exclude_pattern', '')) for quote in ("'", '"'))):
            return 'exclude_pattern must not contain quotes'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gtf_to_extend': ('GTF', {'description': "Input GTF annotation to extend at 3' ends"}), 'gtf_to_overlap': ('GTF', {'description': 'Template GTF annotation used to extend the input'})}, 'optional': {'sup_output': ('BOOLEAN', {'default': False, 'description': 'Write a supplementary overlap-resolution table'}), 'no_add': ('BOOLEAN', {'default': False, 'description': 'Do not add new exons'}), 'exclude_pattern': ('STRING', {'default': '', 'description': 'Regular-expression pattern for gene names that should not be extended'}), 'filter_unstranded': ('BOOLEAN', {'default': False, 'description': 'Filter unstranded template intervals that overlap genes on both strands'}), 'script_path': ('FILE', {'default': 'brew3r.r_script.R', 'advanced': True, 'description': 'Path to the Galaxy BREW3R.r R wrapper script'})}, 'hidden': {'output': ('STRING', {})}}
