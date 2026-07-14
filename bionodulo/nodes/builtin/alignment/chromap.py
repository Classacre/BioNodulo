"""chromap — alignment node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ChromapNode(CommandNode):
    """Align and preprocess chromatin profiling reads with Chromap."""
    NODE_ID = 'chromap'
    DISPLAY_NAME = 'chromap'
    REQUIRED_CONDA_PACKAGES = ['chromap']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Fast alignment and preprocessing of chromatin profiling reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chromap', 'Chromap', 'chromatin profiles', 'ATAC-seq', 'scATAC-seq', 'ChIP-seq', 'Hi-C', 'TagAlign', '4DN pairs']
    RETURN_TYPES = ('BED', 'TXT')
    RETURN_NAMES = ('mapping_out', 'summary_out')
    REQUIRED_EXECUTABLES = ['chromap']
    DOCUMENTATION_URL = 'https://github.com/haowenz/chromap'
    CITATION_DOIS = [CHROMAP_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHROMAP_CITATION_DOI}']
    CITATION_TEXT = CHROMAP_CITATION_TEXT
    VERSION = '0.3.2+galaxy0'
    SHELL = True
    READ_TYPES = ['single', 'paired']
    PRESETS = ['atac', 'chip', 'hic']
    OUTPUT_FORMATS = {'--SAM': ('SAM', 'sam'), '--BED': ('BED', 'bed'), '--TagAlign': ('TSV', 'tsv'), '--pairs': ('4DN_PAIRS', 'pairs')}

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def _read_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('read_type', 'single') or 'single')

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('out_format', '--BED') or '--BED')

    @classmethod
    def _single_reads(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('single_reads', inputs.get('single_read')))

    @classmethod
    def _paired_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        pair = inputs.get('paired_collection', inputs.get('input_collection', inputs.get('input_pair', {})))
        if isinstance(pair, dict):
            forward = str(pair.get('forward', pair.get('r1', pair.get('left', ''))) or '')
            reverse = str(pair.get('reverse', pair.get('r2', pair.get('right', ''))) or '')
            return (forward, reverse)
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return (str(pair[0]), str(pair[1]))
        return ('', '')

    @classmethod
    def _mapping_filename(cls, inputs: dict[str, Any]) -> str:
        ext = cls.OUTPUT_FORMATS.get(cls._out_format(inputs), cls.OUTPUT_FORMATS['--BED'])[1]
        return f'mapping.{ext}'

    @classmethod
    def _mapping_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._mapping_filename(inputs)}'

    @classmethod
    def _summary_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/summary.txt'

    @classmethod
    def _index_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['chromap', '-i', '-r', str(inputs.get('ref', '')), '-o', 'chromap_index', '-k', str(inputs.get('kmer', 17)), '-w', str(inputs.get('window', 7))]
        _add_if_value(cmd, '--min-frag-length', inputs.get('min_frag_length'))
        return _shell_join(cmd)

    @classmethod
    def _mapping_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['chromap', '--preset', str(inputs.get('preset', 'atac') or 'atac')]
        if cls._read_type(inputs) == 'paired':
            forward, reverse = cls._paired_reads(inputs)
            cmd.extend(['-1', forward, '-2', reverse])
        else:
            cmd.extend(['-1', *cls._single_reads(inputs)])
        cmd.extend(['-r', str(inputs.get('ref', '')), '-x', 'chromap_index'])
        _add_if_value(cmd, '-b', inputs.get('barcode'))
        _add_if_value(cmd, '--barcode-whitelist', inputs.get('barcode_whitelist'))
        _add_if_value(cmd, '--read-format', inputs.get('read_format'))
        _add_if_value(cmd, '--barcode-translate', inputs.get('barcode_translate'))
        if cls._bool_flag(inputs.get('split_alignment', False)):
            cmd.append('--split-alignment')
        cmd.extend(['--error-threshold', str(inputs.get('error_threshold', 8)), '--min-num-seeds', str(inputs.get('min_num_seeds', 2))])
        _add_if_value(cmd, '--max-seed-frequencies', inputs.get('max_seed_frequencies', '500,1000'))
        cmd.extend(['--max-insert-size', str(inputs.get('max_insert_size', 1000)), '--MAPQ-threshold', str(inputs.get('MAPQ_threshold', 30)), '--min-read-length', str(inputs.get('min_read_length', 30))])
        if cls._bool_flag(inputs.get('trim_adapters', False)):
            cmd.append('--trim-adapters')
        if cls._bool_flag(inputs.get('Tn5_shift', False)):
            cmd.append('--Tn5-shift')
        _add_if_value(cmd, '--bc-error-threshold', inputs.get('bc_error_threshold'))
        _add_if_value(cmd, '--bc-probability-threshold', inputs.get('bc_probability_threshold'))
        _add_if_value(cmd, '--chr-order', inputs.get('chr_order'))
        _add_if_value(cmd, '--pairs-natural-chr-order', inputs.get('pairs_natural_chr_order'))
        cmd.append(cls._out_format(inputs))
        if cls._bool_flag(inputs.get('summary', True)):
            cmd.extend(['--summary', cls._summary_path(inputs)])
        threads = f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}"
        cmd.extend(['-t', threads, '-o', cls._mapping_path(inputs)])
        return _shell_join(cmd).replace(shlex.quote(threads), threads)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {cls._index_command(inputs)} && {cls._mapping_command(inputs)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._mapping_filename(inputs)]
        if cls._bool_flag(inputs.get('summary', True)):
            outputs.append(out / 'summary.txt')
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
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum or value > maximum:
            return f'{key} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'{key} must be numeric'
        if value < minimum or value > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('ref', '')).strip():
            return 'ref is required'
        read_type = cls._read_type(inputs)
        if read_type not in cls.READ_TYPES:
            return f"read_type must be one of: {', '.join(cls.READ_TYPES)}"
        if read_type == 'single':
            if not cls._single_reads(inputs):
                return 'at least one single_reads value is required'
        else:
            forward, reverse = cls._paired_reads(inputs)
            if not forward or not reverse:
                return 'paired_collection with forward and reverse reads is required'
        preset = str(inputs.get('preset', 'atac') or 'atac')
        if preset not in cls.PRESETS:
            return f"preset must be one of: {', '.join(cls.PRESETS)}"
        out_format = cls._out_format(inputs)
        if out_format not in cls.OUTPUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        for key, default, minimum in [('kmer', 17, 1), ('window', 7, 1), ('error_threshold', 8, 0), ('min_num_seeds', 2, 1), ('max_insert_size', 1000, 1), ('min_read_length', 30, 1), ('threads', 8, 1)]:
            result = cls._validate_int_min(inputs, key, default, minimum)
            if result is not True:
                return result
        if str(inputs.get('min_frag_length', '')) != '':
            result = cls._validate_int_min(inputs, 'min_frag_length', 30, 1)
            if result is not True:
                return result
        result = cls._validate_int_range(inputs, 'MAPQ_threshold', 30, 0, 60)
        if result is not True:
            return result
        for key in ['bc_error_threshold']:
            if str(inputs.get(key, '')) != '':
                result = cls._validate_int_min(inputs, key, 1, 0)
                if result is not True:
                    return result
        if str(inputs.get('bc_probability_threshold', '')) != '':
            result = cls._validate_float_range(inputs, 'bc_probability_threshold', 0.9, 0.0, 1.0)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'read_type': ('STRING', {'default': 'single', 'options': cls.READ_TYPES}), 'ref': ('FASTA', {'description': 'Reference genome FASTA used to build the Chromap index'})}, 'optional': {'single_reads': ('FASTQ', {'default': [], 'is_list': True, 'description': 'One or more single-end FASTQ reads'}), 'paired_collection': ('JSON', {'default': {}, 'description': 'Paired collection with forward and reverse FASTQ reads'}), 'barcode': ('FASTQ', {'default': '', 'description': 'Optional barcode FASTQ for single-cell assays'}), 'barcode_whitelist': ('TXT', {'default': '', 'description': 'Optional valid barcode whitelist'}), 'read_format': ('STRING', {'default': '', 'description': 'Read/barcode layout such as r1:0:-1,bc:0:-1'}), 'barcode_translate': ('TSV', {'default': '', 'description': 'Optional barcode translation table'}), 'min_frag_length': ('INT', {'default': 30, 'min': 1}), 'kmer': ('INT', {'default': 17, 'min': 1}), 'window': ('INT', {'default': 7, 'min': 1}), 'preset': ('STRING', {'default': 'atac', 'options': cls.PRESETS}), 'split_alignment': ('BOOLEAN', {'default': False}), 'error_threshold': ('INT', {'default': 8, 'min': 0}), 'min_num_seeds': ('INT', {'default': 2, 'min': 1}), 'max_seed_frequencies': ('STRING', {'default': '500,1000'}), 'max_insert_size': ('INT', {'default': 1000, 'min': 1}), 'MAPQ_threshold': ('INT', {'default': 30, 'min': 0, 'max': 60}), 'min_read_length': ('INT', {'default': 30, 'min': 1}), 'trim_adapters': ('BOOLEAN', {'default': False}), 'Tn5_shift': ('BOOLEAN', {'default': False}), 'bc_error_threshold': ('INT', {'default': '', 'min': 0}), 'bc_probability_threshold': ('FLOAT', {'default': '', 'min': 0, 'max': 1}), 'chr_order': ('TSV', {'default': ''}), 'pairs_natural_chr_order': ('TSV', {'default': ''}), 'out_format': ('STRING', {'default': '--BED', 'options': list(cls.OUTPUT_FORMATS)}), 'summary': ('BOOLEAN', {'default': True}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
