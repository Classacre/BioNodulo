"""ucsc — wrapped_beacon_ucsc node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class UcscChainSwapNode(_UcscSingleFileUtilityNode):
    """Swap target and query sequences in a UCSC chain file."""
    NODE_ID = 'ucsc_chainswap'
    DISPLAY_NAME = 'chainSwap'
    REQUIRED_CONDA_PACKAGES = ['ucsc-chainswap']
    DESCRIPTION = 'Swap target and query sequences in a UCSC chain alignment file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_chainswap', 'chainSwap', 'chain file', 'UCSC chain', 'swap target query']
    REQUIRED_EXECUTABLES = ['chainSwap']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/chain.html'
    TOOL_NAME = 'chainSwap'
    INPUT_NAME = 'in_chain'
    OUTPUT_FILENAME = 'out.chain'
    INPUT_DESCRIPTION = 'UCSC chain alignment file whose target and query coordinates should be swapped'


class UcscChainSortNode(_UcscSingleFileUtilityNode):
    """Sort records in a UCSC chain file."""
    NODE_ID = 'ucsc_chainsort'
    DISPLAY_NAME = 'chainSort'
    REQUIRED_CONDA_PACKAGES = ['ucsc-chainsort']
    DESCRIPTION = 'Sort UCSC chain alignment records by score, target start, or query start.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_chainsort', 'chainSort', 'chain file', 'UCSC chain', 'sort chains', 'target start', 'query start']
    REQUIRED_EXECUTABLES = ['chainSort']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/chain.html'
    TOOL_NAME = 'chainSort'
    INPUT_NAME = 'in_chain'
    OUTPUT_FILENAME = 'out.chain'
    INPUT_DESCRIPTION = 'UCSC chain alignment file to sort'
    SORT_MODES = ['', '-target', '-query']

    @classmethod
    def _sort_by(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('sort_by', '') or '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, ''))]
        if (sort_by := cls._sort_by(inputs)):
            cmd.append(sort_by)
        cmd.append(cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        required = super().VALIDATE_INPUTS(inputs)
        if required is not True:
            return required
        sort_by = cls._sort_by(inputs)
        if sort_by not in cls.SORT_MODES:
            return f"sort_by must be one of: {', '.join(cls.SORT_MODES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {cls.INPUT_NAME: ('FILE', {'description': cls.INPUT_DESCRIPTION})}, 'optional': {'sort_by': ('STRING', {'default': '', 'options': cls.SORT_MODES, 'description': 'Sort chains by score, target start, or query start'})}, 'hidden': {'output': ('STRING', {})}}


class UcscNetSyntenicNode(_UcscSingleFileUtilityNode):
    """Add synteny annotations to a UCSC net file."""
    NODE_ID = 'ucsc_netsyntenic'
    DISPLAY_NAME = 'netSyntenic'
    REQUIRED_CONDA_PACKAGES = ['ucsc-netsyntenic']
    DESCRIPTION = 'Add synteny information to a UCSC net alignment file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'ucsc_netsyntenic', 'netSyntenic', 'net file', 'UCSC net', 'synteny info']
    REQUIRED_EXECUTABLES = ['netSyntenic']
    DOCUMENTATION_URL = 'https://genome.ucsc.edu/goldenPath/help/net.html'
    TOOL_NAME = 'netSyntenic'
    INPUT_NAME = 'in_net'
    OUTPUT_FILENAME = 'out.ucsc.net'
    INPUT_DESCRIPTION = 'UCSC net alignment file to annotate with synteny information'
