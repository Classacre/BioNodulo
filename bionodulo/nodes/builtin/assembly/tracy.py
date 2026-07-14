"""tracy — assembly node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TracyAssembleNode(CommandNode):
    """Assemble overlapping Sanger chromatogram trace files with Tracy."""
    NODE_ID = 'tracy_assemble'
    DISPLAY_NAME = 'tracy Assemble'
    REQUIRED_CONDA_PACKAGES = ['tracy']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assemble overlapping Sanger chromatogram trace files into a consensus sequence with Tracy.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Tracy', 'tracy Assemble', 'tracy trace assembly', 'Sanger chromatogram assembly', 'overlapping Sanger traces', 'consensus sequence']
    RETURN_TYPES = ('FASTA', 'FASTA', 'JSON')
    RETURN_NAMES = ('consensus', 'alignment', 'json')
    REQUIRED_EXECUTABLES = ['tracy']
    DOCUMENTATION_URL = 'https://www.gear-genomics.com/docs/tracy/cli/#trace-assembly'
    CITATION_DOIS = ['10.1186/s12864-020-6635-8']
    CITATION_URLS = [f'{DOI_URL}10.1186/s12864-020-6635-8']
    CITATION_TEXT = 'Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files.'
    VERSION = '0.7.8'
    SHELL = True
    FORMATS = ['fasta', 'fastq']
    INT_MIN_OPTIONS = {'trim': 1, 'match': 0}
    INT_MAX_OPTIONS = {'gapopen': 0, 'gapext': 0, 'mismatch': 0}

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('format', 'fasta') or 'fasta')

    @classmethod
    def _consensus_filename(cls, inputs: dict[str, Any]) -> str:
        return 'out.cons.fq' if cls._format(inputs) == 'fastq' else 'out.cons.fa'

    @classmethod
    def _tracefiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('tracefiles'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['tracy', 'assemble']
        if str(inputs.get('useref', 'no') or 'no') == 'yes':
            cmd.extend(['--reference', str(inputs.get('reference', ''))])
            if inputs.get('incref'):
                cmd.append('--incref')
        cmd.extend(['--pratio', str(inputs.get('pratio', 0.33)), '--trim', str(inputs.get('trim', 4)), '--fracmatch', str(inputs.get('fracmatch', 0.5)), '--called', str(inputs.get('called', 0.1)), '--format', cls._format(inputs)])
        if inputs.get('inccons'):
            cmd.append('--inccons')
        cmd.extend(['--gapopen', str(inputs.get('gapopen', -10)), '--gapext', str(inputs.get('gapext', -4)), '--match', str(inputs.get('match', 3)), '--mismatch', str(inputs.get('mismatch', -5))])
        cmd.extend(cls._tracefiles(inputs))
        move_cmd = ['mv', cls._consensus_filename(inputs), f'{out}/{cls._consensus_filename(inputs)}']
        return f'{_shell_join(cmd)} && {_shell_join(move_cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._consensus_filename(inputs), out / 'out.align.fa']
        if inputs.get('json_output'):
            outputs.append(out / 'out.json')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._tracefiles(inputs):
            return 'at least one tracefile is required'
        useref = str(inputs.get('useref', 'no') or 'no')
        if useref not in {'yes', 'no'}:
            return 'useref must be one of: yes, no'
        if useref == 'yes' and (not str(inputs.get('reference', '')).strip()):
            return 'reference is required when useref is yes'
        output_format = cls._format(inputs)
        if output_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        try:
            pratio = float(inputs.get('pratio', 0.33))
        except (TypeError, ValueError):
            return 'pratio must be a number'
        if pratio < 0:
            return 'pratio must be >= 0'
        try:
            fracmatch = float(inputs.get('fracmatch', 0.5))
        except (TypeError, ValueError):
            return 'fracmatch must be a number'
        if fracmatch < 0 or fracmatch > 1:
            return 'fracmatch must be between 0 and 1'
        try:
            called = float(inputs.get('called', 0.1))
        except (TypeError, ValueError):
            return 'called must be a number'
        if called < 0:
            return 'called must be >= 0'
        for name, minimum in cls.INT_MIN_OPTIONS.items():
            try:
                value = int(inputs.get(name, {'trim': 4, 'match': 3}[name]))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
        for name, maximum in cls.INT_MAX_OPTIONS.items():
            try:
                value = int(inputs.get(name, {'gapopen': -10, 'gapext': -4, 'mismatch': -5}[name]))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value > maximum:
                return f'{name} must be <= {maximum}'
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'tracefiles': ('FILE', {'multiple': True, 'description': 'Sanger chromatogram trace files in AB1 or SCF format'})}, 'optional': {'pratio': ('FLOAT', {'default': 0.33, 'min': 0, 'description': 'Peak ratio threshold for calling a base'}), 'trim': ('INT', {'default': 4, 'min': 1, 'description': 'Automatic trimming stringency'}), 'fracmatch': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Minimum fraction of matching positions'}), 'called': ('FLOAT', {'default': 0.1, 'min': 0, 'description': 'Fraction of traces required for consensus'}), 'format': ('STRING', {'default': 'fasta', 'options': cls.FORMATS, 'description': 'Consensus output format'}), 'inccons': ('BOOLEAN', {'default': False, 'description': 'Include consensus in the FASTA alignment'}), 'useref': ('STRING', {'default': 'no', 'options': ['yes', 'no'], 'description': 'Use a reference to guide assembly'}), 'reference': ('FASTA', {'default': '', 'description': 'Optional FASTA reference for guided assembly'}), 'incref': ('BOOLEAN', {'default': False, 'description': 'Include reference in the consensus'}), 'gapopen': ('INT', {'default': -10, 'max': 0, 'description': 'Gap open penalty'}), 'gapext': ('INT', {'default': -4, 'max': 0, 'description': 'Gap extension penalty'}), 'match': ('INT', {'default': 3, 'min': 0, 'description': 'Nucleotide match score'}), 'mismatch': ('INT', {'default': -5, 'max': 0, 'description': 'Mismatch penalty'}), 'json_output': ('BOOLEAN', {'default': False, 'description': 'Produce Tracy JSON output'})}, 'hidden': {'output': ('STRING', {})}}
