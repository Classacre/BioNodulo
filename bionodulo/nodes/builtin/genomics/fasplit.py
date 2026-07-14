"""fasplit — genomics node(s). One tool per file (extracted from wrapped_beacon_ucsc.py)."""
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


class FaSplitNode(CommandNode):
    """Split a FASTA file into multiple FASTA files."""
    NODE_ID = 'fasplit'
    DISPLAY_NAME = 'faSplit'
    REQUIRED_CONDA_PACKAGES = ['ucsc-fasplit']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Split a FASTA file into multiple FASTA files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'UCSC Genome Browser Utilities', 'fasplit', 'faSplit', 'split FASTA', 'FASTA chunks', 'by sequence name', 'gap boundaries']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('output_list',)
    REQUIRED_EXECUTABLES = ['faSplit']
    DOCUMENTATION_URL = 'https://github.com/ucscGenomeBrowser/kent/blob/master/src/utils/faSplit/faSplit.c'
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{UCSC_UTILS_CITATION_DOI}']
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = '482+galaxy0'
    SPLIT_TYPES = ['sequence', 'base', 'size', 'byname', 'about', 'gap']
    MODES_WITH_COUNT = {'sequence', 'base', 'size', 'about', 'gap'}

    @classmethod
    def _split_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('split_type', 'sequence') or 'sequence')

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_list'

    @classmethod
    def _lift_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/fasplit.lft'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        split_type = cls._split_type(inputs)
        out_dir = cls._output_dir(inputs)
        cmd = ['faSplit']
        if str(inputs.get('maxN', '')) != '' and split_type in {'size', 'gap'}:
            cmd.append(f"-maxN={inputs.get('maxN')}")
        if inputs.get('oneFile') and split_type in {'size', 'gap'}:
            cmd.append('-oneFile')
        if str(inputs.get('extra', '')) != '' and split_type == 'size':
            cmd.append(f"-extra={inputs.get('extra')}")
        if inputs.get('lift') and split_type in {'size', 'gap'}:
            cmd.append(f'-lift={cls._lift_path(inputs)}')
        if str(inputs.get('minGapSize', '')) != '' and split_type == 'gap':
            cmd.append(f"-minGapSize={inputs.get('minGapSize')}")
        if inputs.get('noGapDrops') and split_type == 'gap':
            cmd.append('-noGapDrops')
        if str(inputs.get('outDirDepth', '')) != '':
            cmd.append(f"-outDirDepth={inputs.get('outDirDepth')}")
        if str(inputs.get('prefixLength', '')) != '' and split_type == 'byname':
            cmd.append(f"-prefixLength={inputs.get('prefixLength')}")
        cmd.extend([split_type, str(inputs.get('input', ''))])
        if split_type in cls.MODES_WITH_COUNT:
            cmd.append(str(inputs.get('count', 10)))
        cmd.append(f'{out_dir}/')
        return f'mkdir -p {shlex.quote(out_dir)} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output_list'
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        split_type = cls._split_type(inputs)
        if split_type not in cls.SPLIT_TYPES:
            return f"split_type must be one of: {', '.join(cls.SPLIT_TYPES)}"
        if split_type in cls.MODES_WITH_COUNT and int(inputs.get('count', 10)) < 1:
            return 'count must be greater than or equal to 1'
        minimums = {'maxN': 0, 'extra': 0, 'minGapSize': 1, 'outDirDepth': 0, 'prefixLength': 1}
        for name, minimum in minimums.items():
            value = inputs.get(name, '')
            if str(value) != '' and int(value) < minimum:
                return f'{name} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'FASTA file to split'})}, 'optional': {'split_type': ('STRING', {'default': 'sequence', 'options': cls.SPLIT_TYPES, 'description': 'Split by sequence records, bases, chunk size, sequence name, approximate bytes, or gap boundaries'}), 'count': ('INT', {'default': 10, 'min': 1, 'description': 'Number of chunks or chunk size, depending on split type'}), 'maxN': ('INT', {'default': '', 'min': 0, 'description': 'Suppress size/gap pieces with more than this many Ns'}), 'oneFile': ('BOOLEAN', {'default': False, 'description': 'Write size/gap pieces into one FASTA file'}), 'extra': ('INT', {'default': '', 'min': 0, 'description': 'Add overlapping bases to size-mode pieces'}), 'lift': ('BOOLEAN', {'default': False, 'description': 'Write a lift file describing how pieces reconstruct the input'}), 'minGapSize': ('INT', {'default': '', 'min': 1, 'description': 'Minimum N run length considered a gap in gap mode'}), 'noGapDrops': ('BOOLEAN', {'default': False, 'description': 'Keep gap-only pieces when splitting by gap'}), 'outDirDepth': ('INT', {'default': '', 'min': 0, 'description': 'Create nested numeric output directories'}), 'prefixLength': ('INT', {'default': '', 'min': 1, 'description': 'Group byname output by sequence-name prefix length'})}, 'hidden': {'output': ('STRING', {})}}
