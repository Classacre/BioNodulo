"""falco — qc node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class FalcoNode(CommandNode):
    """Run FastQC-compatible read quality control with Falco."""
    NODE_ID = 'falco'
    DISPLAY_NAME = 'Falco'
    REQUIRED_CONDA_PACKAGES = ['falco']
    CATEGORY = 'qc'
    DESCRIPTION = 'Run high-speed FastQC-compatible quality control on FASTQ, SAM, or BAM sequencing reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Falco', 'falco', 'FastQC emulation', 'FASTQ QC', 'read quality control', 'sequencing quality report']
    RETURN_TYPES = ('HTML_REPORT', 'TXT', 'TXT')
    RETURN_NAMES = ('html_file', 'text_file', 'summary_file')
    REQUIRED_EXECUTABLES = ['falco']
    DOCUMENTATION_URL = FALCO_DOCUMENTATION_URL
    CITATION_DOIS = [FALCO_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{FALCO_CITATION_DOI}']
    CITATION_TEXT = FALCO_CITATION_TEXT
    VERSION = '1.3.2+galaxy0'
    SHELL = True
    INPUT_EXT_OPTIONS = ['fastq', 'fastq.gz', 'bam', 'sam']

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get('input_ext', '') or '').strip().lower().lstrip('.')
        if explicit:
            return explicit
        suffixes = [suffix.lower() for suffix in Path(str(inputs.get('input_file', ''))).suffixes]
        if '.bam' in suffixes:
            return 'bam'
        if '.sam' in suffixes:
            return 'sam'
        if '.gz' in suffixes:
            return 'fastq.gz'
        return 'fastq'

    @staticmethod
    def _input_symlink_name(input_file: Any) -> str:
        return sub('[^\\w\\-]', '_', Path(str(input_file or '')).name) or 'input_reads'

    @classmethod
    def _summary_requested(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get('generate_summary'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_file = str(inputs.get('input_file', ''))
        input_name = cls._input_symlink_name(input_file)
        cmd = ['falco', '--outdir', out]
        _add_if_value(cmd, '--contaminants', inputs.get('contaminants'))
        _add_if_value(cmd, '--adapters', inputs.get('adapters'))
        _add_if_value(cmd, '--limits', inputs.get('limits'))
        cmd.extend(['--threads', '${GALAXY_SLOTS:-2}', '--quiet'])
        if inputs.get('nogroup'):
            cmd.append('--nogroup')
        cmd.extend(['-f', cls._input_format(inputs), input_name])
        subsample = inputs.get('subsample', 1)
        if int(subsample) > 1:
            cmd.extend(['-subsample', str(subsample)])
        if inputs.get('bisulfite'):
            cmd.append('-bisulfite')
        if inputs.get('reverse_complement'):
            cmd.append('-reverse-complement')
        if not cls._summary_requested(inputs):
            cmd.append('-skip-summary')
        falco_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-2}'", '${GALAXY_SLOTS:-2}')
        return ' && '.join([_shell_join(['mkdir', '-p', out]), _shell_join(['ln', '-sf', input_file, input_name]), falco_cmd])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'fastqc_report.html', out / 'fastqc_data.txt']
        if cls._summary_requested(inputs):
            outputs.append(out / 'summary.txt')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        input_ext = cls._input_format(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        subsample = inputs.get('subsample', 1)
        try:
            subsample_int = int(subsample)
        except (TypeError, ValueError):
            return 'subsample must be an integer'
        if subsample_int < 1:
            return 'subsample must be greater than or equal to 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTQ', {'description': 'FASTQ, FASTQ.GZ, SAM, or BAM reads to inspect'})}, 'optional': {'input_ext': ('STRING', {'default': 'fastq', 'options': cls.INPUT_EXT_OPTIONS, 'description': 'Input format passed to Falco'}), 'contaminants': ('TSV', {'default': '', 'description': 'Optional contaminant list with name and sequence columns'}), 'adapters': ('TSV', {'default': '', 'description': 'Optional adapter list with name and sequence columns'}), 'limits': ('TXT', {'default': '', 'description': 'Optional custom FastQC limits configuration'}), 'nogroup': ('BOOLEAN', {'default': False, 'description': 'Disable base grouping for reads longer than 50 bp'}), 'subsample': ('INT', {'default': 1, 'min': 1, 'description': 'Process only reads whose index is a multiple of this value'}), 'bisulfite': ('BOOLEAN', {'default': False, 'description': 'Account for whole-genome bisulfite sequencing base composition'}), 'reverse_complement': ('BOOLEAN', {'default': False, 'description': 'Evaluate reads as reverse-complemented'}), 'generate_summary': ('BOOLEAN', {'default': False, 'description': 'Emit Falco summary.txt output'})}, 'hidden': {'output': ('STRING', {})}}
