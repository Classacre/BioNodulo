"""maftoaxt — genomics node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class MafToAxtNode(CommandNode):
    """Convert UCSC MAF alignments to AXT format."""
    NODE_ID = 'maftoaxt'
    DISPLAY_NAME = 'mafToAxt'
    REQUIRED_CONDA_PACKAGES = ['ucsc-maftoaxt']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Convert a UCSC MAF multiple-alignment file to AXT pairwise alignment format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'maftoaxt', 'mafToAxt', 'MAF to AXT', 'multiple alignment format', 'pairwise alignment']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('out',)
    REQUIRED_EXECUTABLES = ['mafToAxt']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/axt.html'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    TARGET_MODES = ['', 'customTar']

    @classmethod
    def _target_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('tarSeq', '') or '')

    @classmethod
    def _target_sequence(cls, inputs: dict[str, Any]) -> str:
        if cls._target_mode(inputs) == 'customTar':
            return str(inputs.get('targetSeq', ''))
        return 'first'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.axt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['mafToAxt', str(inputs.get('in_maf', '')), cls._target_sequence(inputs), str(inputs.get('querySeq', '')), cls._output_path(inputs)]
        if inputs.get('stripDb'):
            cmd.append('-stripDb')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.axt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_maf', '')).strip():
            return 'in_maf is required'
        if not str(inputs.get('querySeq', '')).strip():
            return 'querySeq is required'
        target_mode = cls._target_mode(inputs)
        if target_mode not in cls.TARGET_MODES:
            return f"tarSeq must be one of: {', '.join(cls.TARGET_MODES)}"
        if target_mode == 'customTar' and (not str(inputs.get('targetSeq', '')).strip()):
            return 'targetSeq is required when tarSeq is customTar'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_maf': ('FILE', {'description': 'UCSC MAF multiple-alignment file to convert'}), 'querySeq': ('STRING', {'description': 'Sequence name to use as the query sequence'})}, 'optional': {'tarSeq': ('STRING', {'default': '', 'options': cls.TARGET_MODES, 'description': 'Use the first MAF block sequence or a custom target sequence name'}), 'targetSeq': ('STRING', {'default': '', 'description': 'Target sequence name used when tarSeq is customTar'}), 'stripDb': ('BOOLEAN', {'default': False, 'description': 'Strip database prefixes up to the first period in sequence names'})}, 'hidden': {'output': ('STRING', {})}}
