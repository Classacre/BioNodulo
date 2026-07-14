"""flash — trimming node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FLASHNode(CommandNode):
    """Merge overlapping paired-end reads with FLASH."""
    NODE_ID = 'flash'
    DISPLAY_NAME = 'FLASH'
    REQUIRED_CONDA_PACKAGES = ['flash']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Merge paired-end reads with FLASH and emit merged, unmerged, log, and histogram outputs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'FLASH', 'flash', 'read merging', 'paired-end merge', 'overlap', 'Fast Length Adjustment of SHort reads']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'FASTQ', 'TSV', 'STATS_FILE', 'STATS_FILE', 'TSV', 'TSV', 'STATS_FILE', 'STATS_FILE')
    RETURN_NAMES = ('merged_reads', 'unmerged_forward_reads', 'unmerged_reverse_reads', 'histogram_table', 'raw_log', 'histogram_text', 'innie_histogram_table', 'outie_histogram_table', 'innie_histogram_text', 'outie_histogram_text')
    REQUIRED_EXECUTABLES = ['flash']
    DOCUMENTATION_URL = 'https://ccb.jhu.edu/software/FLASH/'
    CITATION_DOIS = [FLASH_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{FLASH_CITATION_DOI}']
    CITATION_TEXT = FLASH_CITATION_TEXT
    VERSION = '1.2.11'
    SHELL = True

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if str(inputs.get('layout', 'individual') or 'individual') == 'collection':
            reads = inputs.get('reads')
            if isinstance(reads, dict):
                return (str(reads.get('forward', '')), str(reads.get('reverse', '')))
            read_list = _as_list(reads)
            return (read_list[0] if read_list else '', read_list[1] if len(read_list) > 1 else '')
        return (str(inputs.get('forward', '')), str(inputs.get('reverse', '')))

    @classmethod
    def _fastq_suffix(cls, inputs: dict[str, Any]) -> str:
        return '.fastq.gz' if bool(inputs.get('gzip', False)) else '.fastq'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        forward, reverse = cls._read_pair(inputs)
        cmd = ['flash', f"--threads=${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}", '-m', str(inputs.get('min_overlap', 10)), '-M', str(inputs.get('max_overlap', 65)), '-x', str(inputs.get('max_mismatch_density', 0.25))]
        if inputs.get('allow_outies'):
            cmd.append('--allow-outies')
        cmd.extend([forward, reverse, '-p', str(inputs.get('phred_offset', 33))])
        if inputs.get('gzip'):
            cmd.append('-z')
        cmd.extend(['--output-prefix', f'{_out(inputs)}/out', '--output-suffix='])
        if inputs.get('save_log'):
            _add_shell_redirect(cmd, f'{_out(inputs)}/flash.log')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = cls._fastq_suffix(inputs)
        outputs = [out / f'out.extendedFrags{suffix}', out / f'out.notCombined_1{suffix}', out / f'out.notCombined_2{suffix}', out / 'out.hist']
        if inputs.get('save_log'):
            outputs.append(out / 'flash.log')
        if inputs.get('generate_histogram'):
            outputs.append(out / 'out.histogram')
        if inputs.get('allow_outies'):
            outputs.extend([out / 'out.hist.innie', out / 'out.hist.outie'])
            if inputs.get('generate_histogram'):
                outputs.extend([out / 'out.histogram.innie', out / 'out.histogram.outie'])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        forward, reverse = cls._read_pair(inputs)
        if str(inputs.get('layout', 'individual') or 'individual') == 'collection':
            if not forward or not reverse:
                return 'paired collection requires forward and reverse reads'
        elif not forward or not reverse:
            return 'forward and reverse reads are required'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'layout': ('STRING', {'default': 'individual', 'options': ['individual', 'collection'], 'description': 'Use individual forward/reverse datasets or a paired collection'}), 'forward': ('FASTQ', {'description': 'Forward reads for individual dataset mode'}), 'reverse': ('FASTQ', {'description': 'Reverse reads for individual dataset mode'})}, 'optional': {'reads': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection [forward, reverse] or mapping'}), 'min_overlap': ('INT', {'default': 10, 'min': 1, 'description': 'Minimum required overlap length'}), 'max_overlap': ('INT', {'default': 65, 'min': 1, 'description': 'Maximum expected overlap length'}), 'max_mismatch_density': ('FLOAT', {'default': 0.25, 'min': 0, 'description': 'Maximum mismatch-to-overlap ratio'}), 'allow_outies': ('BOOLEAN', {'default': False, 'description': 'Try combining read pairs in both orientations'}), 'generate_histogram': ('BOOLEAN', {'default': False, 'description': 'Emit text histogram outputs'}), 'save_log': ('BOOLEAN', {'default': False, 'description': 'Save FLASH console log'}), 'phred_offset': ('INT', {'default': 33, 'options': [33, 64], 'description': 'FASTQ quality score offset'}), 'gzip': ('BOOLEAN', {'default': False, 'description': 'Write gzip-compressed FASTQ outputs'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
