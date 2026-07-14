"""cite — single_cell node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CiteSeqCountNode(CommandNode):
    """Count CITE-seq and cell-hashing tags from paired FASTQ reads."""
    NODE_ID = 'cite_seq_count'
    DISPLAY_NAME = 'CITE-seq-Count'
    REQUIRED_CONDA_PACKAGES = ['cite-seq-count', 'python', 'umi_tools', 'python-levenshtein', 'levenshtein', 'pandas', 'bzip2', 'expat', 'multiprocess', 'numpy', 'pysam', 'scipy']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Count CMO/HTO tags from raw CITE-seq or cell-hashing FASTQ reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CITE-seq-Count', 'cite_seq_count', 'CITE-seq', 'cell hashing', 'CMO', 'HTO', 'hashtag oligo', 'cell multiplexing oligo', 'UMI and read counts', 'raw FASTQ CITE-seq']
    RETURN_TYPES = ('YAML', 'TSV', 'TSV', 'FILE', 'TSV', 'TSV', 'FILE', 'TSV')
    RETURN_NAMES = ('report', 'output_features', 'output_barcodes', 'output_matrix', 'output_features_filtered', 'output_barcodes_filtered', 'output_matrix_filtered', 'dense_output_matrix')
    REQUIRED_EXECUTABLES = ['CITE-seq-Count', 'gunzip']
    DOCUMENTATION_URL = 'https://hoohm.github.io/CITE-seq-Count/'
    CITATION_DOIS = [CITE_SEQ_COUNT_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CITE_SEQ_COUNT_CITATION_DOI}']
    CITATION_TEXT = CITE_SEQ_COUNT_CITATION_TEXT
    VERSION = '1.4.4+galaxy0'
    SHELL = True
    INPUT_TYPES_OPTIONS = ['repeat', 'list_paired']
    CHEMISTRY_OPTIONS = ['v2', 'v3', 'custom']
    OUTPUT_MOVES = [('Results/run_report.yaml', 'run_report.yaml'), ('Results/read_count/features.tsv', 'read_count_features.tsv'), ('Results/read_count/barcodes.tsv', 'read_count_barcodes.tsv'), ('Results/read_count/matrix.mtx', 'read_count_matrix.mtx'), ('Results/umi_count/features.tsv', 'umi_count_features.tsv'), ('Results/umi_count/barcodes.tsv', 'umi_count_barcodes.tsv'), ('Results/umi_count/matrix.mtx', 'umi_count_matrix.mtx')]

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def _threads(cls, inputs: dict[str, Any]) -> str:
        return f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_type', 'repeat') or 'repeat')

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get('input_collection')
        if isinstance(collection, dict):
            return (str(collection.get('forward', collection.get('read1', collection.get('reads_1', '')))), str(collection.get('reverse', collection.get('read2', collection.get('reads_2', '')))))
        reads = _as_list(collection)
        return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '')

    @staticmethod
    def _repeat_reads(value: Any) -> list[str]:
        if isinstance(value, str):
            return [item for item in value.split(',') if item]
        return _as_list(value)

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if cls._input_type(inputs) == 'list_paired':
            read1, read2 = cls._paired_collection_reads(inputs)
            return ([read1] if read1 else [], [read2] if read2 else [])
        return (cls._repeat_reads(inputs.get('input1')), cls._repeat_reads(inputs.get('input2')))

    @classmethod
    def _chemistry_bases(cls, inputs: dict[str, Any]) -> tuple[int, int, int, int]:
        chemistry = str(inputs.get('chemistry', 'v2') or 'v2')
        if chemistry == 'v3':
            return (1, 16, 17, 28)
        if chemistry == 'custom':
            return (int(inputs.get('cell_barcode_first_base', 1)), int(inputs.get('cell_barcode_last_base', 16)), int(inputs.get('umi_first_base', 17)), int(inputs.get('umi_last_base', 26)))
        return (1, 16, 17, 26)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reads1, reads2 = cls._reads(inputs)
        cell_first, cell_last, umi_first, umi_last = cls._chemistry_bases(inputs)
        threads = cls._threads(inputs)
        cmd = ['CITE-seq-Count', '--threads', threads, '--read1', ','.join(reads1), '--read2', ','.join(reads2), '--tags', str(inputs.get('tags', '')), '--cell_barcode_first_base', str(cell_first), '--cell_barcode_last_base', str(cell_last), '--umi_first_base', str(umi_first), '--umi_last_base', str(umi_last), '--bc_collapsing_dist', str(inputs.get('bc_collapsing_dist', 1)), '--umi_collapsing_dist', str(inputs.get('umi_collapsing_dist', 2))]
        if cls._bool_flag(inputs.get('no_umi_correction', False)):
            cmd.append('--no_umi_correction')
        cmd.extend(['--expected_cells', str(inputs.get('expected_cells', 3000))])
        if str(inputs.get('whitelist', '')).strip():
            cmd.extend(['--whitelist', str(inputs.get('whitelist', ''))])
        cmd.extend(['--max-error', str(inputs.get('max_error', 2))])
        if int(inputs.get('start_trim', 0)) != 0:
            cmd.extend(['--start-trim', str(inputs.get('start_trim', 0))])
        if cls._bool_flag(inputs.get('sliding_window', False)):
            cmd.append('--sliding-window')
        if cls._bool_flag(inputs.get('dense', False)):
            cmd.append('--dense')
        if int(inputs.get('first_n', 0)) != 0:
            cmd.extend(['--first_n', str(inputs.get('first_n', 0))])
        if cls._bool_flag(inputs.get('unknown_tags_output', False)):
            cmd.extend(['--unknown-top-tags', str(inputs.get('unknown_top_tags', 100))])
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}']
        cite_command = _shell_join(cmd).replace(shlex.quote(threads), threads)
        commands.append(cite_command)
        commands.extend((_shell_join(['gunzip', path]) for path in ['Results/read_count/barcodes.tsv.gz', 'Results/read_count/features.tsv.gz', 'Results/read_count/matrix.mtx.gz', 'Results/umi_count/barcodes.tsv.gz', 'Results/umi_count/features.tsv.gz', 'Results/umi_count/matrix.mtx.gz']))
        commands.extend((_shell_join(['mv', source, target]) for source, target in cls.OUTPUT_MOVES))
        if cls._bool_flag(inputs.get('dense', False)):
            commands.append(_shell_join(['mv', 'Results/dense_umis.tsv', 'dense_umis.tsv']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / target for _, target in cls.OUTPUT_MOVES]
        if cls._bool_flag(inputs.get('dense', False)):
            outputs.append(out / 'dense_umis.tsv')
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('tags', '')).strip():
            return 'tags is required'
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        reads1, reads2 = cls._reads(inputs)
        if input_type == 'list_paired':
            if not reads1 or not reads2:
                return 'input_collection with forward and reverse reads is required for list_paired input'
        else:
            if not reads1 or not reads2:
                return 'input1 and input2 are required for repeat input'
            if len(reads1) != len(reads2):
                return 'input1 and input2 must contain the same number of FASTQ files'
        chemistry = str(inputs.get('chemistry', 'v2') or 'v2')
        if chemistry not in cls.CHEMISTRY_OPTIONS:
            return f"chemistry must be one of: {', '.join(cls.CHEMISTRY_OPTIONS)}"
        if chemistry == 'custom':
            for key, default in [('cell_barcode_first_base', 1), ('cell_barcode_last_base', 16), ('umi_first_base', 17), ('umi_last_base', 26)]:
                result = cls._validate_int_min(inputs, key, default, 1)
                if result is not True:
                    return result
        for key, default, minimum in [('bc_collapsing_dist', 1, 0), ('umi_collapsing_dist', 2, 0), ('expected_cells', 3000, 1), ('max_error', 2, 0), ('start_trim', 0, 0), ('first_n', 0, 0), ('threads', 4, 1)]:
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        if cls._bool_flag(inputs.get('unknown_tags_output', False)):
            result = cls._validate_int_min(inputs, 'unknown_top_tags', 100, 1)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'repeat', 'options': cls.INPUT_TYPES_OPTIONS, 'description': 'Use separate repeated barcode/HTO reads or a paired read collection'}), 'tags': ('CSV', {'description': 'CMO/HTO barcode table with sequence in the first column and tag name in the second'})}, 'optional': {'input1': ('FASTQ', {'default': [], 'is_list': True, 'description': 'Barcode read 1 FASTQ files for repeat input'}), 'input2': ('FASTQ', {'default': [], 'is_list': True, 'description': 'HTO/CMO read 2 FASTQ files for repeat input'}), 'input_collection': ('JSON', {'default': {}, 'description': 'Paired collection with forward/read1 and reverse/read2 FASTQ entries'}), 'chemistry': ('STRING', {'default': 'v2', 'options': cls.CHEMISTRY_OPTIONS}), 'cell_barcode_first_base': ('INT', {'default': 1, 'min': 1, 'advanced': True}), 'cell_barcode_last_base': ('INT', {'default': 16, 'min': 1, 'advanced': True}), 'umi_first_base': ('INT', {'default': 17, 'min': 1, 'advanced': True}), 'umi_last_base': ('INT', {'default': 26, 'min': 1, 'advanced': True}), 'bc_collapsing_dist': ('INT', {'default': 1, 'min': 0}), 'umi_collapsing_dist': ('INT', {'default': 2, 'min': 0}), 'no_umi_correction': ('BOOLEAN', {'default': False, 'description': 'Deactivate UMI correction'}), 'expected_cells': ('INT', {'default': 3000, 'min': 1}), 'whitelist': ('FILE', {'default': '', 'description': 'Optional whitelist of cell barcodes'}), 'max_error': ('INT', {'default': 2, 'min': 0}), 'start_trim': ('INT', {'default': 0, 'min': 0}), 'sliding_window': ('BOOLEAN', {'default': False}), 'dense': ('BOOLEAN', {'default': False, 'description': 'Also emit dense UMI-count TSV output'}), 'first_n': ('INT', {'default': 0, 'min': 0}), 'unknown_tags_output': ('BOOLEAN', {'default': False, 'description': 'Write top unmapped tags'}), 'unknown_top_tags': ('INT', {'default': 100, 'min': 1}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
