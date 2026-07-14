"""iuc — trimming node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class PEARNode(CommandNode):
    """Merge paired-end reads with the Galaxy IUC PEAR wrapper behavior."""
    NODE_ID = 'iuc_pear'
    DISPLAY_NAME = 'Pear'
    REQUIRED_CONDA_PACKAGES = ['pear']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Merge paired-end reads with PEAR and emit selected assembled, unassembled, or discarded reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'PEAR', 'Pear', 'iuc_pear', 'PEAR paired-end read merger', 'paired-end read merger', 'read merging', 'Illumina paired-end merge']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'FASTQ', 'FASTQ')
    RETURN_NAMES = ('assembled_reads', 'unassembled_forward_reads', 'unassembled_reverse_reads', 'discarded_reads')
    REQUIRED_EXECUTABLES = ['pear']
    DOCUMENTATION_URL = 'https://sco.h-its.org/exelixis/web/software/pear/doc.html'
    CITATION_DOIS = [PEAR_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PEAR_CITATION_DOI}']
    CITATION_TEXT = PEAR_CITATION_TEXT
    VERSION = '0.9.6.4'
    SHELL = True
    OUTPUT_CHOICES = ['assembled', 'unassembled_forward', 'unassembled_reverse', 'discarded']
    OUTPUT_FILES = {'assembled': 'pear.assembled.fastq', 'unassembled_forward': 'pear.unassembled.forward.fastq', 'unassembled_reverse': 'pear.unassembled.reverse.fastq', 'discarded': 'pear.discarded.fastq'}
    TEST_METHODS = ['1', '2']
    SCORE_METHODS = ['1', '2', '3']

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if str(inputs.get('library_type', 'paired') or 'paired') == 'paired_collection':
            collection = inputs.get('input_collection')
            if isinstance(collection, dict):
                return (str(collection.get('forward', '')), str(collection.get('reverse', '')))
            reads = _as_list(collection)
            return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '')
        return (str(inputs.get('forward', '')), str(inputs.get('reverse', '')))

    @classmethod
    def _outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get('outputs'))
        return outputs if outputs else ['assembled']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        forward, reverse = cls._read_pair(inputs)
        cmd = ['pear', '-f', forward, '-r', reverse, '--phred-base', str(inputs.get('phred_base', '33')), '--output', f'{_out(inputs)}/pear', '--p-value', str(inputs.get('pvalue', 0.01)), '--min-overlap', str(inputs.get('min_overlap', 10))]
        max_assembly_length = int(inputs.get('max_assembly_length', 0) or 0)
        if max_assembly_length > 0:
            cmd.extend(['--max-asm-length', str(max_assembly_length)])
        cmd.extend(['--min-asm-length', str(inputs.get('min_assembly_length', 50)), '--min-trim-length', str(inputs.get('min_trim_length', 1)), '--quality-theshold', str(inputs.get('quality_threshold', 0)), '--max-uncalled-base', str(inputs.get('max_uncalled_base', 1.0)), '--test-method', str(inputs.get('test_method', '1')), '--threads', f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}", '--score-method', str(inputs.get('score_method', '2')), '--cap', str(inputs.get('cap', 40))])
        if inputs.get('empirical_freqs'):
            cmd.append('--empirical-freqs')
        if inputs.get('nbase'):
            cmd.append('--nbase')
        command = _shell_join(cmd)
        slot_token = f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}"
        return command.replace(shlex.quote(slot_token), slot_token)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[output] for output in cls._outputs(inputs) if output in cls.OUTPUT_FILES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        library_type = str(inputs.get('library_type', 'paired') or 'paired')
        if library_type not in {'paired', 'paired_collection'}:
            return 'library_type must be one of: paired, paired_collection'
        forward, reverse = cls._read_pair(inputs)
        if library_type == 'paired_collection':
            if not forward or not reverse:
                return 'paired collection requires forward and reverse reads'
        elif not forward or not reverse:
            return 'forward and reverse reads are required'
        if str(inputs.get('phred_base', '33')) not in {'33', '64'}:
            return 'phred_base must be one of: 33, 64'
        if str(inputs.get('test_method', '1')) not in cls.TEST_METHODS:
            return 'test_method must be one of: 1, 2'
        if str(inputs.get('score_method', '2')) not in cls.SCORE_METHODS:
            return 'score_method must be one of: 1, 2, 3'
        for name in ('pvalue', 'max_uncalled_base'):
            try:
                value = float(inputs.get(name, {'pvalue': 0.01, 'max_uncalled_base': 1.0}[name]))
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < 0 or value > 1:
                return f'{name} must be between 0 and 1'
        for name, default in (('min_overlap', 10), ('max_assembly_length', 0), ('min_assembly_length', 50), ('min_trim_length', 1), ('quality_threshold', 0), ('cap', 40)):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 0:
                return f'{name} must be >= 0'
        unsupported_outputs = [output for output in cls._outputs(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"outputs contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'library_type': ('STRING', {'default': 'paired', 'options': ['paired', 'paired_collection'], 'description': 'Use individual forward/reverse datasets or a paired collection'})}, 'optional': {'forward': ('FASTQ', {'default': '', 'description': 'Forward reads for paired dataset mode'}), 'reverse': ('FASTQ', {'default': '', 'description': 'Reverse reads for paired dataset mode'}), 'input_collection': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection [forward, reverse] or mapping'}), 'phred_base': ('STRING', {'default': '33', 'options': ['33', '64'], 'description': 'FASTQ PHRED quality score base'}), 'pvalue': ('FLOAT', {'default': 0.01, 'min': 0, 'max': 1, 'description': 'P-value threshold for accepting an assembly overlap'}), 'min_overlap': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum overlap size'}), 'max_assembly_length': ('INT', {'default': 0, 'min': 0, 'description': 'Maximum assembled sequence length; 0 disables the cap'}), 'min_assembly_length': ('INT', {'default': 50, 'min': 0, 'description': 'Minimum assembled sequence length'}), 'min_trim_length': ('INT', {'default': 1, 'min': 0, 'description': 'Minimum read length after low-quality trimming'}), 'quality_threshold': ('INT', {'default': 0, 'description': 'Quality threshold for trimming low-quality read tails'}), 'max_uncalled_base': ('FLOAT', {'default': 1.0, 'min': 0, 'max': 1, 'description': 'Maximum proportion of uncalled bases'}), 'cap': ('INT', {'default': 40, 'min': 0, 'description': 'Upper bound for resulting quality scores'}), 'test_method': ('STRING', {'default': '1', 'options': cls.TEST_METHODS, 'description': 'Statistical test method'}), 'empirical_freqs': ('BOOLEAN', {'default': False, 'description': 'Disable empirical base frequencies'}), 'nbase': ('BOOLEAN', {'default': False, 'description': 'Use N when a merged base is uncertain'}), 'score_method': ('STRING', {'default': '2', 'options': cls.SCORE_METHODS, 'description': 'PEAR scoring method'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 128, 'display': 'slider'}), 'outputs': ('STRING', {'default': ['assembled'], 'multiple': True, 'options': cls.OUTPUT_CHOICES, 'description': 'Selected PEAR FASTQ outputs'})}, 'hidden': {'output': ('STRING', {})}}
