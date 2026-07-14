"""seqsero2 — typing node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class SeqSero2Node(CommandNode):
    """Predict Salmonella serotypes with SeqSero2."""
    NODE_ID = 'seqsero2'
    DISPLAY_NAME = 'SeqSero2'
    REQUIRED_CONDA_PACKAGES = ['seqsero2']
    CATEGORY = 'typing'
    DESCRIPTION = 'Predict Salmonella serotypes from raw sequencing reads or genome assemblies.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'SeqSero2', 'seqsero2', 'Salmonella serotype', 'Salmonella typing', 'serotype prediction', 'allele micro-assembly', 'k-mer serotyping']
    RETURN_TYPES = ('TSV', 'TXT')
    RETURN_NAMES = ('results', 'log')
    REQUIRED_EXECUTABLES = ['SeqSero2_package.py']
    DOCUMENTATION_URL = 'https://github.com/denglab/SeqSero2'
    CITATION_DOIS = ['10.1128/AEM.01746-19']
    CITATION_URLS = [f'{DOI_URL}10.1128/AEM.01746-19']
    CITATION_TEXT = 'SeqSero2: rapid and improved Salmonella serotype determination using whole-genome sequencing data.'
    VERSION = '1.3.2+galaxy0'
    SHELL = True
    INPUT_TYPES_OPTIONS = ('paired', 'collection', 'assembly', 'single', 'nanopore')
    WORKFLOW_OPTIONS = ('a', 'k')
    TYPE_VALUES = {'paired': '2', 'collection': '2', 'single': '3', 'assembly': '4', 'nanopore': '5'}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_type', '') or '')

    @classmethod
    def _workflow(cls, inputs: dict[str, Any]) -> str:
        input_type = cls._input_type(inputs)
        if input_type in {'assembly', 'nanopore'}:
            return 'k'
        return str(inputs.get('workflow', 'a') or 'a')

    @staticmethod
    def _extension(path: str, input_type: str) -> str:
        suffixes = ''.join(Path(path).suffixes).lower()
        gz = suffixes.endswith('.gz')
        base = '.fasta' if input_type in {'assembly', 'nanopore'} else '.fastq'
        return f'{base}.gz' if gz else base

    @classmethod
    def _stage_name(cls, path: str, input_type: str, label: str='', suffix: str='') -> str:
        stem = _safe_identifier(label or Path(path).stem or 'input')
        if suffix:
            stem = f'{stem}_{suffix}'
        return f'{stem}{cls._extension(path, input_type)}'

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str, str]:
        collection = inputs.get('input_collection')
        if isinstance(collection, dict):
            forward = str(collection.get('forward', collection.get('read1', collection.get('reads_1', ''))))
            reverse = str(collection.get('reverse', collection.get('read2', collection.get('reads_2', ''))))
            label = str(collection.get('name', collection.get('element_identifier', forward or 'collection')))
            return (forward, reverse, label)
        reads = _as_list(collection)
        return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '', reads[0] if reads else 'collection')

    @classmethod
    def _staged_inputs(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        input_type = cls._input_type(inputs)
        if input_type == 'collection':
            read1, read2, label = cls._collection_reads(inputs)
            return [(read1, cls._stage_name(read1, input_type, label, 'forward')), (read2, cls._stage_name(read2, input_type, label, 'reverse'))]
        read1 = str(inputs.get('read1', ''))
        label1 = str(inputs.get('read1_label', '') or Path(read1).stem or 'input')
        if input_type == 'paired':
            read2 = str(inputs.get('read2', ''))
            label2 = str(inputs.get('read2_label', '') or label1)
            return [(read1, cls._stage_name(read1, input_type, label1, 'forward')), (read2, cls._stage_name(read2, input_type, label2, 'reverse'))]
        return [(read1, cls._stage_name(read1, input_type, label1))]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', out])]
        staged = cls._staged_inputs(inputs)
        commands.extend((_shell_join(['ln', '-s', source, staged_name]) for source, staged_name in staged))
        cmd = ['SeqSero2_package.py', '-m', cls._workflow(inputs), '-t', cls.TYPE_VALUES[cls._input_type(inputs)], '-i', staged[0][1]]
        if cls._input_type(inputs) in {'paired', 'collection'}:
            cmd.append(staged[1][1])
        cmd.extend(['-p', '${GALAXY_SLOTS:-4}', '-d', f'{out}/output'])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-4}'", '${GALAXY_SLOTS:-4}'))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'SeqSero_result.tsv']
        if inputs.get('logfile'):
            outputs.append(out / 'SeqSero_log.txt')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        if input_type == 'collection':
            read1, read2, _ = cls._collection_reads(inputs)
            if not read1 or not read2:
                return 'input_collection with forward and reverse reads is required for collection input'
        else:
            if not str(inputs.get('read1', '')).strip():
                return f'read1 is required for {input_type} input'
            if input_type == 'paired' and (not str(inputs.get('read2', '')).strip()):
                return 'read2 is required for paired input'
        workflow = cls._workflow(inputs)
        if workflow not in cls.WORKFLOW_OPTIONS:
            return f"workflow must be one of: {', '.join(cls.WORKFLOW_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'paired', 'options': list(cls.INPUT_TYPES_OPTIONS), 'description': 'Galaxy SeqSero2 input layout'}), 'read1': ('FILE', {'description': 'Forward, single/interleaved, assembly, or nanopore input'}), 'read2': ('FASTQ', {'description': 'Reverse reads for paired input'})}, 'optional': {'input_collection': ('JSON', {'default': {}, 'description': 'Paired collection with forward and reverse reads'}), 'workflow': ('STRING', {'default': 'a', 'options': list(cls.WORKFLOW_OPTIONS), 'description': 'SeqSero2 workflow for raw reads: allele micro-assembly or k-mer'}), 'logfile': ('BOOLEAN', {'default': False, 'description': 'Return SeqSero2 log output'}), 'read1_label': ('STRING', {'default': '', 'description': 'Optional Galaxy element identifier for read1', 'advanced': True}), 'read2_label': ('STRING', {'default': '', 'description': 'Optional Galaxy element identifier for read2', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
