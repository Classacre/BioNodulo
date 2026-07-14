"""mlst — typing node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class MLSTNode(CommandNode):
    """Scan assemblies against PubMLST typing schemes with mlst."""
    NODE_ID = 'mlst'
    DISPLAY_NAME = 'MLST'
    REQUIRED_CONDA_PACKAGES = ['mlst']
    CATEGORY = 'typing'
    DESCRIPTION = "Scan genome assemblies against PubMLST schemes with Torsten Seemann's MLST."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'MLST', 'mlst', 'PubMLST', 'sequence typing', 'scheme typing', 'allele profile', 'novel alleles']
    RETURN_TYPES = ('TSV', 'FASTA')
    RETURN_NAMES = ('report', 'novel_alleles')
    REQUIRED_EXECUTABLES = ['mlst']
    DOCUMENTATION_URL = MLST_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [MLST_CITATION_URL]
    CITATION_TEXT = MLST_CITATION_TEXT
    VERSION = '2.22.0'
    SHELL = True
    ADVANCED_OPTIONS = ['simple', 'advanced']
    SET_SCHEME_OPTIONS = ['auto', 'list', 'manual']

    @staticmethod
    def _label_for(path: str, label: str | None=None) -> str:
        return str(label or Path(path).name or 'input.fasta')

    @classmethod
    def _staged_inputs(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        paths = _as_list(inputs.get('input_files'))
        labels = _as_list(inputs.get('input_labels'))
        return [(path, cls._label_for(path, labels[index] if index < len(labels) else None)) for index, path in enumerate(paths)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_inputs = cls._staged_inputs(inputs)
        parts = [_shell_join(['ln', '-s', path, label]) for path, label in staged_inputs]
        cmd = ['mlst', '--nopath', '--threads', '${GALAXY_SLOTS:-1}']
        if str(inputs.get('advanced', 'simple')) == 'advanced':
            if inputs.get('minid') not in (None, ''):
                cmd.append(f"--minid={inputs['minid']}")
            if inputs.get('mincov') not in (None, ''):
                cmd.append(f"--mincov={inputs['mincov']}")
            if inputs.get('novel'):
                cmd.extend(['--novel', f'{_out(inputs)}/novel_alleles.fasta'])
            set_scheme = str(inputs.get('set_scheme', 'auto'))
            if set_scheme == 'auto':
                if inputs.get('minscore') not in (None, ''):
                    cmd.append(f"--minscore={inputs['minscore']}")
                if str(inputs.get('exclude', '')).strip():
                    cmd.extend(['--exclude', str(inputs.get('exclude'))])
            elif set_scheme in {'list', 'manual'}:
                if str(inputs.get('scheme', '')).strip():
                    cmd.append(f"--scheme={inputs['scheme']}")
                if inputs.get('legacy', True):
                    cmd.append('--legacy')
        cmd.extend((label for _, label in staged_inputs))
        cmd.extend(['>', f'{_out(inputs)}/report.tsv'])
        parts.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}'))
        return ' && '.join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'report.tsv']
        if inputs.get('novel'):
            outputs.append(out / 'novel_alleles.fasta')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get('input_files')):
            return 'at least one input_files value is required'
        advanced = str(inputs.get('advanced', 'simple'))
        if advanced not in cls.ADVANCED_OPTIONS:
            return f"advanced must be one of: {', '.join(cls.ADVANCED_OPTIONS)}"
        if advanced == 'advanced':
            for key in ('minid', 'mincov', 'minscore'):
                if inputs.get(key) in (None, ''):
                    continue
                value = int(inputs[key])
                if value < 0 or value > 100:
                    return f'{key} must be between 0 and 100'
            set_scheme = str(inputs.get('set_scheme', 'auto'))
            if set_scheme not in cls.SET_SCHEME_OPTIONS:
                return f"set_scheme must be one of: {', '.join(cls.SET_SCHEME_OPTIONS)}"
            if set_scheme in {'list', 'manual'} and (not str(inputs.get('scheme', '')).strip()):
                return 'scheme is required when set_scheme is list or manual'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_files': ('FASTA', {'multiple': True, 'description': 'FASTA or GenBank genome assembly files to scan with mlst'})}, 'optional': {'advanced': ('STRING', {'default': 'simple', 'options': cls.ADVANCED_OPTIONS, 'description': 'Use default or advanced mlst parameters'}), 'minid': ('INT', {'default': 95, 'min': 0, 'max': 100, 'advanced': True}), 'mincov': ('INT', {'default': 10, 'min': 0, 'max': 100, 'advanced': True}), 'novel': ('BOOLEAN', {'default': False, 'description': 'Write novel alleles to FASTA', 'advanced': True}), 'set_scheme': ('STRING', {'default': 'auto', 'options': cls.SET_SCHEME_OPTIONS, 'description': 'Auto-detect, select, or manually set scheme'}), 'minscore': ('INT', {'default': 50, 'min': 0, 'max': 100, 'advanced': True}), 'exclude': ('STRING', {'default': '', 'description': 'Comma-separated schemes to ignore in auto mode', 'advanced': True}), 'scheme': ('STRING', {'default': '', 'description': 'PubMLST scheme for list/manual modes'}), 'legacy': ('BOOLEAN', {'default': True, 'description': 'Include allele header row when scheme is set'}), 'input_labels': ('STRING', {'default': [], 'is_list': True, 'description': 'Optional Galaxy element identifiers used as readable output names', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class MLSTListNode(CommandNode):
    """List MLST schemes and optional allele details."""
    NODE_ID = 'mlst_list'
    DISPLAY_NAME = 'MLST List'
    REQUIRED_CONDA_PACKAGES = ['mlst']
    CATEGORY = 'typing'
    DESCRIPTION = 'List available PubMLST schemes and optional allele details from the MLST database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'MLST List', 'mlst --list', 'mlst --longlist', 'PubMLST schemes', 'allele list']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('report',)
    REQUIRED_EXECUTABLES = ['mlst']
    DOCUMENTATION_URL = MLST_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [MLST_CITATION_URL]
    CITATION_TEXT = MLST_CITATION_TEXT
    VERSION = '2.22.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(['mlst', '--longlist' if inputs.get('list_type') else '--list', '>', f'{_out(inputs)}/report.txt'])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'report.txt']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'optional': {'list_type': ('BOOLEAN', {'default': False, 'description': 'Include allele columns with mlst --longlist'})}, 'hidden': {'output': ('STRING', {})}}
