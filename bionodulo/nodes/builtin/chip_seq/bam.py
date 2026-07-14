"""bam — chip_seq node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class BamToScidxNode(CommandNode):
    """Convert BAM data to Strand-specific coordinate count ScIdx files."""
    NODE_ID = 'bam_to_scidx'
    DISPLAY_NAME = 'Convert BAM to ScIdx'
    REQUIRED_CONDA_PACKAGES = ['openjdk']
    CATEGORY = 'chip_seq'
    DESCRIPTION = 'Convert BAM alignments to Strand-specific coordinate count ScIdx format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bam_to_scidx', 'BAM to ScIdx', 'ScIdx', 'strand-specific coordinate count', 'ChIP-exo', 'GeneTrack', 'MultiGPS', 'BAMtoscIDX']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['java']
    DOCUMENTATION_URL = BAM_TO_SCIDX_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BAM_TO_SCIDX_CITATION_URL]
    CITATION_TEXT = BAM_TO_SCIDX_CITATION_TEXT
    VERSION = '1.0.1'
    SHELL = True
    PROPER_MATE_PAIRING = ['1', '0']
    READS = ['0', '1', '2']

    @classmethod
    def _proper_mate_pairing(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('require_proper_mate_pairing', '1') or '1')

    @classmethod
    def _read(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('read', '0') or '0')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.scidx'

    @classmethod
    def _optional_int(cls, inputs: dict[str, Any], key: str) -> int | None:
        value = inputs.get(key)
        if value is None or str(value) == '':
            return None
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['ln', '-s', str(inputs.get('input_bam', '')), 'localbam.bam', '&&', 'ln', '-f', '-s', str(inputs.get('bam_index', '')), 'localbam.bam.bai', '&&', 'java', '-jar', str(inputs.get('jar_path', 'BAMtoscIDX.jar') or 'BAMtoscIDX.jar'), '-b', 'localbam.bam', '-i', 'localbam.bam.bai', '-p', cls._proper_mate_pairing(inputs), '-r', cls._read(inputs)]
        min_insert_size = cls._optional_int(inputs, 'min_insert_size')
        if min_insert_size is not None:
            cmd.extend(['-m', str(min_insert_size)])
        max_insert_size = cls._optional_int(inputs, 'max_insert_size')
        if max_insert_size is not None:
            cmd.extend(['-M', str(max_insert_size)])
        cmd.extend(['-o', cls._output_path(inputs), '1>/dev/null'])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.scidx']

    @classmethod
    def _validate_insert_size(cls, inputs: dict[str, Any], key: str) -> bool | str:
        try:
            value = cls._optional_int(inputs, key)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value is not None and value < 0:
            return f'{key} must be greater than or equal to 0'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_bam', '')).strip():
            return 'input_bam is required'
        if not str(inputs.get('bam_index', '')).strip():
            return 'bam_index is required'
        read = cls._read(inputs)
        if read not in cls.READS:
            return f"read must be one of: {', '.join(cls.READS)}"
        proper_mate_pairing = cls._proper_mate_pairing(inputs)
        if proper_mate_pairing not in cls.PROPER_MATE_PAIRING:
            return f"require_proper_mate_pairing must be one of: {', '.join(cls.PROPER_MATE_PAIRING)}"
        for key in ('min_insert_size', 'max_insert_size'):
            validation = cls._validate_insert_size(inputs, key)
            if validation is not True:
                return validation
        min_insert_size = cls._optional_int(inputs, 'min_insert_size')
        max_insert_size = cls._optional_int(inputs, 'max_insert_size')
        if min_insert_size is not None and max_insert_size is not None and (max_insert_size < min_insert_size):
            return 'max_insert_size must be greater than or equal to min_insert_size'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_bam': ('BAM', {'description': 'Input BAM file'}), 'bam_index': ('BAI', {'description': 'BAM index file for the input BAM'})}, 'optional': {'require_proper_mate_pairing': ('STRING', {'default': '1', 'options': cls.PROPER_MATE_PAIRING, 'description': 'Require proper mate-pairing when filtering by insert size'}), 'read': ('STRING', {'default': '0', 'options': cls.READS, 'description': 'Read to output: 0 Read1, 1 Read2, or 2 combined'}), 'min_insert_size': ('INT', {'default': '', 'min': 0, 'description': 'Minimum insert size to output'}), 'max_insert_size': ('INT', {'default': '', 'min': 0, 'description': 'Maximum insert size to output'}), 'jar_path': ('FILE', {'default': 'BAMtoscIDX.jar', 'advanced': True, 'description': 'Path to BAMtoscIDX.jar'})}, 'hidden': {'output': ('STRING', {})}}
