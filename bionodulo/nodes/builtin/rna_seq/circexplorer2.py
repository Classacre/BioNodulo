"""circexplorer2 — rna_seq node(s). One tool per file (extracted from wrapped_sequence_visualization.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CIRCexplorer2Node(CommandNode):
    """Run CIRCexplorer2 circular RNA analysis modules."""
    NODE_ID = 'circexplorer2'
    DISPLAY_NAME = 'CIRCexplorer2'
    REQUIRED_CONDA_PACKAGES = ['circexplorer2']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Circular RNA analysis with CIRCexplorer2 modules.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CIRCexplorer2', 'circexplorer2', 'circular RNA', 'circRNA', 'back-splicing', 'alternative splicing', 'TopHat-Fusion', 'STAR', 'MapSplice']
    RETURN_TYPES = ('TGZ', 'BIGWIG', 'BED', 'TSV', 'TSV', 'TGZ', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('alignment', 'fusion_junction_bw', 'parse', 'annotate', 'annotate_low', 'assemble', 'denovo_combined', 'denovo_circularRNA', 'denovo_annotated', 'denovo_novel', 'denovo_abs5', 'denovo_abs3', 'denovo_all_exon', 'denovo_all_intron', 'denovo_a5ss', 'denovo_a3ss')
    REQUIRED_EXECUTABLES = ['CIRCexplorer2']
    DOCUMENTATION_URL = 'https://circexplorer2.readthedocs.io/en/latest/'
    CITATION_DOIS = [CIRCEXPLORER2_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CIRCEXPLORER2_CITATION_DOI}']
    CITATION_TEXT = CIRCEXPLORER2_CITATION_TEXT
    VERSION = '2.3.8+galaxy0'
    SHELL = True
    MODES = ['align', 'parse', 'annotate', 'assemble', 'denovo']
    ALIGNERS = ['TopHat-Fusion', 'STAR', 'MapSplice', 'BWA', 'segemehl']
    TYPE_MAPPINGS = ['-m', '-n']

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no', 'off'}
        return bool(value)

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('mode', 'align') or 'align')

    @classmethod
    def _out_dir(cls, output_dir: str | Path) -> Path:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return out

    @classmethod
    def _threads_arg(cls, inputs: dict[str, Any]) -> str:
        return f"--thread=${{GALAXY_SLOTS:-{inputs.get('threads', 10)}}}"

    @classmethod
    def _fastq_stage_path(cls, index: int, fastq: str) -> str:
        suffixes = Path(fastq).suffixes
        ext = ''.join(suffixes).lstrip('.') or 'fastq'
        return f'reads/file{index}.{ext}'

    @classmethod
    def _align_command(cls, inputs: dict[str, Any]) -> str:
        commands = [_shell_join(['mkdir', '-p', 'reads'])]
        fastqs = _as_list(inputs.get('fastq'))
        staged: list[str] = []
        for index, fastq in enumerate(fastqs):
            file_path = cls._fastq_stage_path(index, fastq)
            staged.append(file_path)
            commands.append(_shell_join(['ln', '-s', fastq, file_path]))
        cmd = ['CIRCexplorer2', 'align', cls._threads_arg(inputs), '--gtf', str(inputs.get('gtf', '')), '-g', str(inputs.get('genome', '')), '--fastq', ','.join(staged)]
        if cls._bool_flag(inputs.get('bw', False)):
            cmd.append('--bw')
        if cls._bool_flag(inputs.get('scale', False)):
            cmd.append('--scale')
        if cls._bool_flag(inputs.get('skip_tophat', False)):
            cmd.append('--skip-tophat')
        if cls._bool_flag(inputs.get('skip_tophat_fusion', False)):
            cmd.append('--skip-tophat-fusion')
        commands.append(_shell_join(cmd).replace(shlex.quote(cls._threads_arg(inputs)), cls._threads_arg(inputs)))
        commands.append(_shell_join(['tar', '-zcvf', 'alignment.tgz', './alignment']))
        return ' && '.join(commands)

    @classmethod
    def _parse_command(cls, inputs: dict[str, Any]) -> str:
        aligner = str(inputs.get('aligner', 'TopHat-Fusion') or 'TopHat-Fusion')
        cmd = ['CIRCexplorer2', 'parse', '-t', aligner, str(inputs.get('fusion_file', ''))]
        if aligner == 'TopHat-Fusion' and cls._bool_flag(inputs.get('pe', False)):
            cmd.append('--pe')
        if cls._bool_flag(inputs.get('f', False)):
            cmd.append('-f')
        return _shell_join(cmd)

    @classmethod
    def _annotate_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['CIRCexplorer2', 'annotate', '-r', str(inputs.get('ref', '')), '-g', 'reference_genome.fa', '-b', str(inputs.get('bed', ''))]
        if cls._bool_flag(inputs.get('no_fix', False)):
            cmd.append('--no-fix')
        if cls._bool_flag(inputs.get('low_confidence', False)):
            cmd.append('--low-confidence')
        return f"{_shell_join(['ln', '-s', str(inputs.get('genome', '')), 'reference_genome.fa'])} && {_shell_join(cmd)}"

    @classmethod
    def _assemble_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['CIRCexplorer2', 'assemble', cls._threads_arg(inputs), '-r', str(inputs.get('ref', '')), '-m', './alignment']
        if cls._bool_flag(inputs.get('remove_rRNA', False)):
            cmd.append('--remove-rRNA')
        command = _shell_join(cmd).replace(shlex.quote(cls._threads_arg(inputs)), cls._threads_arg(inputs))
        return f"{_shell_join(['tar', '-zxf', str(inputs.get('tophat', ''))])} && {command} && {_shell_join(['tar', '-zcvf', 'assemble.tgz', './assemble'])}"

    @classmethod
    def _denovo_command(cls, inputs: dict[str, Any]) -> str:
        commands = [_shell_join(['ln', '-s', str(inputs.get('genome', '')), 'reference_genome.fa'])]
        assemble_file = str(inputs.get('assemble_file', ''))
        tar_flag = '-zxf' if Path(assemble_file).suffix == '.gz' or assemble_file.endswith('.tgz') else '-xf'
        commands.append(_shell_join(['tar', tar_flag, assemble_file]))
        if str(inputs.get('as_option', 'disabled') or 'disabled') == 'enabled':
            commands.append(_shell_join(['tar', '-zxf', str(inputs.get('tophat', ''))]))
        cmd = ['CIRCexplorer2', 'denovo', '-d', './assemble', '-r', str(inputs.get('ref', '')), '-b', str(inputs.get('bed', '')), '-g', 'reference_genome.fa']
        if cls._bool_flag(inputs.get('abs', False)):
            cmd.extend(['--abs', 'abs'])
        if str(inputs.get('as_option', 'disabled') or 'disabled') == 'enabled':
            cmd.extend(['--as', 'as', str(inputs.get('type_mapping', '-m') or '-m'), './alignment'])
        if cls._bool_flag(inputs.get('no_fix', False)):
            cmd.append('--no-fix')
        if cls._bool_flag(inputs.get('rpkm', False)):
            cmd.append('--rpkm')
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        mode = cls._mode(inputs)
        module_commands = {'align': cls._align_command, 'parse': cls._parse_command, 'annotate': cls._annotate_command, 'assemble': cls._assemble_command, 'denovo': cls._denovo_command}
        command = module_commands.get(mode, cls._align_command)(inputs)
        out = _out(inputs)
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = cls._out_dir(output_dir)
        mode = cls._mode(inputs)
        if mode == 'align':
            outputs = [out / 'alignment.tgz']
            if cls._bool_flag(inputs.get('bw', False)):
                outputs.append(out / 'accepted_hits.bw')
            return outputs
        if mode == 'parse':
            return [out / 'back_spliced_junction.bed']
        if mode == 'annotate':
            outputs = [out / 'circularRNA_known.txt']
            if cls._bool_flag(inputs.get('low_confidence', False)):
                outputs.append(out / 'low_conf_circularRNA_known.txt')
            return outputs
        if mode == 'assemble':
            return [out / 'assemble.tgz']
        outputs = [out / 'combined_ref.txt', out / 'circularRNA_full.txt', out / 'annotated_circ.txt', out / 'novel_circ.txt']
        if cls._bool_flag(inputs.get('abs', False)):
            outputs.extend([out / 'a5bs.txt', out / 'a3bs.txt'])
        if str(inputs.get('as_option', 'disabled') or 'disabled') == 'enabled':
            outputs.extend([out / 'all_exon_info.txt', out / 'all_intron_info.txt', out / 'all_A5SS_info.txt', out / 'all_A3SS_info.txt'])
        return outputs

    @classmethod
    def _require(cls, inputs: dict[str, Any], key: str, mode: str) -> bool | str:
        if not str(inputs.get(key, '')).strip():
            return f'{key} is required when mode is {mode}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode = cls._mode(inputs)
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        if mode == 'align':
            for key in ['gtf', 'genome']:
                result = cls._require(inputs, key, mode)
                if result is not True:
                    return result
            if not _as_list(inputs.get('fastq')):
                return 'at least one fastq value is required when mode is align'
            return True
        if mode == 'parse':
            aligner = str(inputs.get('aligner', 'TopHat-Fusion') or 'TopHat-Fusion')
            if aligner not in cls.ALIGNERS:
                return f"aligner must be one of: {', '.join(cls.ALIGNERS)}"
            return cls._require(inputs, 'fusion_file', mode)
        if mode == 'annotate':
            for key in ['ref', 'genome', 'bed']:
                result = cls._require(inputs, key, mode)
                if result is not True:
                    return result
            return True
        if mode == 'assemble':
            for key in ['ref', 'tophat']:
                result = cls._require(inputs, key, mode)
                if result is not True:
                    return result
            return True
        for key in ['ref', 'bed', 'genome', 'assemble_file']:
            result = cls._require(inputs, key, mode)
            if result is not True:
                return result
        as_option = str(inputs.get('as_option', 'disabled') or 'disabled')
        if as_option not in {'disabled', 'enabled'}:
            return 'as_option must be one of: disabled, enabled'
        if as_option == 'enabled':
            if not str(inputs.get('tophat', '')).strip():
                return 'tophat is required when as_option is enabled'
            type_mapping = str(inputs.get('type_mapping', '-m') or '-m')
            if type_mapping not in cls.TYPE_MAPPINGS:
                return f"type_mapping must be one of: {', '.join(cls.TYPE_MAPPINGS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mode': ('STRING', {'default': 'align', 'options': cls.MODES})}, 'optional': {'gtf': ('GTF', {'default': '', 'description': 'Annotation GTF for align mode'}), 'genome': ('FASTA', {'default': '', 'description': 'Reference genome FASTA'}), 'fastq': ('FASTQ', {'default': [], 'is_list': True, 'description': 'Single-read RNA-seq FASTQ files'}), 'bw': ('BOOLEAN', {'default': False, 'description': 'Create BigWig output in align mode'}), 'scale': ('BOOLEAN', {'default': False, 'description': 'Scale BigWig signal to HPB'}), 'skip_tophat': ('BOOLEAN', {'default': False}), 'skip_tophat_fusion': ('BOOLEAN', {'default': False}), 'aligner': ('STRING', {'default': 'TopHat-Fusion', 'options': cls.ALIGNERS}), 'fusion_file': ('FILE', {'default': '', 'description': 'Fusion junction file for parse mode'}), 'pe': ('BOOLEAN', {'default': False, 'description': 'Parse paired-end TopHat-Fusion alignments'}), 'f': ('BOOLEAN', {'default': False, 'description': 'Count fragments instead of reads in parse mode'}), 'ref': ('TXT', {'default': '', 'description': 'Gene annotation in GenePred/RefSeq format'}), 'bed': ('BED', {'default': '', 'description': 'Back-spliced junction BED file'}), 'no_fix': ('BOOLEAN', {'default': False}), 'low_confidence': ('BOOLEAN', {'default': False}), 'tophat': ('TGZ', {'default': '', 'description': 'TopHat alignment archive from align mode'}), 'remove_rRNA': ('BOOLEAN', {'default': False}), 'assemble_file': ('TGZ', {'default': '', 'description': 'Assemble archive for denovo mode'}), 'abs': ('BOOLEAN', {'default': False, 'description': 'Detect alternative back-splicing'}), 'as_option': ('STRING', {'default': 'disabled', 'options': ['disabled', 'enabled']}), 'type_mapping': ('STRING', {'default': '-m', 'options': cls.TYPE_MAPPINGS}), 'rpkm': ('BOOLEAN', {'default': False}), 'threads': ('INT', {'default': 10, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
