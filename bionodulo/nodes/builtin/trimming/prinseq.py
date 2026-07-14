"""prinseq — trimming node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class PrinseqNode(CommandNode):
    """Filter and trim FASTQ reads with PRINSEQ."""
    NODE_ID = 'prinseq'
    DISPLAY_NAME = 'PRINSEQ'
    REQUIRED_CONDA_PACKAGES = ['prinseq']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Filter and trim single-end or paired-end FASTQ reads with PRINSEQ.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'PRINSEQ', 'prinseq-lite', 'quality control', 'quality filter', 'metagenomic preprocessing', 'read trimming', 'N filtering']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'FASTQ', 'FASTQ', 'FASTQ', 'FASTQ')
    RETURN_NAMES = ('good_sequences', 'rejected_sequences', 'good_sequences_1', 'good_sequences_1_singletons', 'good_sequences_2', 'rejected_sequences_2')
    REQUIRED_EXECUTABLES = ['prinseq-lite.pl']
    DOCUMENTATION_URL = 'http://prinseq.sourceforge.net/manual.html'
    CITATION_DOIS = [PRINSEQ_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PRINSEQ_CITATION_DOI}']
    CITATION_TEXT = PRINSEQ_CITATION_TEXT
    VERSION = '0.20.4'
    SHELL = True

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get('paired', False))

    @classmethod
    def _compress_output(cls, inputs: dict[str, Any]) -> bool:
        if 'compress_output' in inputs:
            return bool(inputs.get('compress_output'))
        if not any((key in inputs for key in ('input_singles', 'input_mate1', 'input_mate2'))):
            return True
        reads = [str(inputs.get('input_singles', '')), str(inputs.get('input_mate1', '')), str(inputs.get('input_mate2', ''))]
        return any((path.endswith('.gz') for path in reads if path))

    @classmethod
    def _planned_names(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._is_paired(inputs):
            names = ['good_sequences_1.fastq', 'good_sequences_1_singletons.fastq', 'rejected_sequences_1.fastq', 'good_sequences_2.fastq', 'good_sequences_2_singletons.fastq', 'rejected_sequences_2.fastq']
        else:
            names = ['good_sequences.fastq', 'rejected_sequences.fastq']
        if cls._compress_output(inputs):
            names = [f'{name}.gz' for name in names]
        return names

    @classmethod
    def _stage_fastq(cls, source: str, target: str) -> str:
        if source.endswith('.gz'):
            return f'gunzip -c {shlex.quote(source)} > {target}'
        return f'ln -sf {shlex.quote(source)} {target}'

    @classmethod
    def _add_value_flag(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str) -> None:
        value = inputs.get(key)
        if value is not None and str(value) != '':
            cmd.extend([flag, str(value)])

    @classmethod
    def _prinseq_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['prinseq-lite.pl', '-fastq', 'fwd.fastq']
        if cls._is_paired(inputs):
            cmd.extend(['-fastq2', 'rev.fastq'])
        if inputs.get('phred64'):
            cmd.append('-phred64')
        cmd.extend(['-out_good', f'{_out(inputs)}/tmp/good_sequences', '-out_bad', f'{_out(inputs)}/tmp/rejected_sequences'])
        for key, flag in (('min_len', '-min_len'), ('max_len', '-max_len'), ('min_qual_score', '-min_qual_score'), ('max_qual_score', '-max_qual_score'), ('min_qual_mean', '-min_qual_mean'), ('max_qual_mean', '-max_qual_mean'), ('min_gc', '-min_gc'), ('max_gc', '-max_gc'), ('ns_max_n', '-ns_max_n'), ('ns_max_p', '-ns_max_p'), ('trim_to_len', '-trim_to_len'), ('trim_left', '-trim_left'), ('trim_right', '-trim_right'), ('trim_left_p', '-trim_left_p'), ('trim_right_p', '-trim_right_p'), ('trim_tail_left', '-trim_tail_left'), ('trim_tail_right', '-trim_tail_right'), ('trim_ns_left', '-trim_ns_left'), ('trim_ns_right', '-trim_ns_right'), ('trim_qual_left', '-trim_qual_left'), ('trim_qual_right', '-trim_qual_right'), ('trim_qual_type', '-trim_qual_type'), ('trim_qual_rule', '-trim_qual_rule'), ('trim_qual_window', '-trim_qual_window'), ('trim_qual_step', '-trim_qual_step'), ('lc_method', '-lc_method'), ('lc_threshold', '-lc_threshold')):
            cls._add_value_flag(cmd, inputs, key, flag)
        return ' '.join((shlex.quote(part) for part in cmd))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tmp = f'{out}/tmp'
        parts = ['set -eu', f'mkdir -p {shlex.quote(tmp)}']
        if cls._is_paired(inputs):
            parts.extend([cls._stage_fastq(str(inputs.get('input_mate1', '')), 'fwd.fastq'), cls._stage_fastq(str(inputs.get('input_mate2', '')), 'rev.fastq'), f'touch {shlex.quote(tmp)}/good_sequences_1.fastq {shlex.quote(tmp)}/good_sequences_1_singletons.fastq {shlex.quote(tmp)}/rejected_sequences_1.fastq {shlex.quote(tmp)}/good_sequences_2.fastq {shlex.quote(tmp)}/good_sequences_2_singletons.fastq {shlex.quote(tmp)}/rejected_sequences_2.fastq'])
        else:
            parts.extend([cls._stage_fastq(str(inputs.get('input_singles', '')), 'fwd.fastq'), f'touch {shlex.quote(tmp)}/good_sequences.fastq {shlex.quote(tmp)}/rejected_sequences.fastq'])
        parts.append(cls._prinseq_command(inputs))
        names = cls._planned_names(inputs)
        for name in names:
            source = name.removesuffix('.gz')
            source_path = f'{tmp}/{source}'
            target_path = f'{out}/{name}'
            if name.endswith('.gz'):
                parts.append(f'gzip -c {shlex.quote(source_path)} > {shlex.quote(target_path)}')
            else:
                parts.append(f'cp {shlex.quote(source_path)} {shlex.quote(target_path)}')
        return ' && '.join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / name for name in cls._planned_names(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'paired': ('BOOLEAN', {'default': False, 'description': 'Run paired-end PRINSEQ processing'}), 'input_singles': ('FASTQ', {'default': '', 'description': 'Single-end FASTQ input'}), 'input_mate1': ('FASTQ', {'default': '', 'description': 'Paired-end mate 1 FASTQ'}), 'input_mate2': ('FASTQ', {'default': '', 'description': 'Paired-end mate 2 FASTQ'})}, 'optional': {'compress_output': ('BOOLEAN', {'default': True, 'description': 'Write gzip-compressed FASTQ outputs'}), 'phred64': ('BOOLEAN', {'default': False, 'description': 'Treat input qualities as Illumina/Phred+64'}), 'min_len': ('INT', {'default': 60, 'min': 0, 'description': 'Minimum sequence length to keep'}), 'max_len': ('INT', {'default': '', 'min': 0, 'advanced': True, 'description': 'Maximum sequence length to keep'}), 'min_qual_score': ('INT', {'default': '', 'min': 0, 'max': 40, 'advanced': True}), 'max_qual_score': ('INT', {'default': '', 'min': 0, 'max': 40, 'advanced': True}), 'min_qual_mean': ('INT', {'default': 15, 'min': 0, 'max': 40, 'description': 'Minimum mean quality to keep'}), 'max_qual_mean': ('INT', {'default': '', 'min': 0, 'max': 40, 'advanced': True}), 'min_gc': ('INT', {'default': '', 'min': 0, 'max': 100, 'advanced': True}), 'max_gc': ('INT', {'default': '', 'min': 0, 'max': 100, 'advanced': True}), 'ns_max_n': ('INT', {'default': '', 'min': 0, 'advanced': True, 'description': 'Maximum number of N bases'}), 'ns_max_p': ('INT', {'default': 2, 'min': 0, 'max': 100, 'description': 'Maximum percentage of N bases'}), 'trim_to_len': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_left': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_right': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_left_p': ('INT', {'default': '', 'min': 0, 'max': 100, 'advanced': True}), 'trim_right_p': ('INT', {'default': '', 'min': 0, 'max': 100, 'advanced': True}), 'trim_tail_left': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_tail_right': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_ns_left': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_ns_right': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'trim_qual_left': ('INT', {'default': '', 'min': 0, 'max': 40, 'advanced': True}), 'trim_qual_right': ('INT', {'default': 20, 'min': 0, 'max': 40, 'description': 'Right-end quality trimming threshold'}), 'trim_qual_type': ('STRING', {'default': 'min', 'options': ['min', 'mean', 'max', 'sum'], 'advanced': True}), 'trim_qual_rule': ('STRING', {'default': 'lt', 'options': ['lt', 'gt', 'et'], 'advanced': True}), 'trim_qual_window': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'trim_qual_step': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'lc_method': ('STRING', {'default': '', 'options': ['', 'dust', 'entropy'], 'advanced': True}), 'lc_threshold': ('INT', {'default': '', 'min': 0, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
