"""bmtagger — metagenomics node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BMTaggerNode(CommandNode):
    """Remove contaminant reads with BMTagger."""
    NODE_ID = 'bmtagger'
    DISPLAY_NAME = 'bmtagger'
    REQUIRED_CONDA_PACKAGES = ['bmtagger']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Filter contaminant sequences from input FASTA or FASTQ reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BMTagger', 'bmtagger', 'contaminant reads', 'host read removal', 'human read filtering', 'metagenomics contamination', 'Best Match Tagger']
    RETURN_TYPES = ('FASTQ', 'FASTQ')
    RETURN_NAMES = ('out_single', 'out_pair')
    REQUIRED_EXECUTABLES = ['bmtagger.sh', 'extract_fullseq', 'bmtool', 'srprism', 'makeblastdb', 'gunzip']
    DOCUMENTATION_URL = BMTAGGER_CITATION_URL
    CITATION_URLS = [BMTAGGER_CITATION_URL]
    CITATION_TEXT = BMTAGGER_CITATION_TEXT
    VERSION = '3.101+galaxy0'
    SHELL = True
    SEQUENCE_TYPES = ['single', 'paired']
    HOST_SOURCES = ['cached', 'history']
    READ_FORMATS = ['', 'fasta', 'fasta.gz', 'fastqsanger', 'fastqsanger.gz', 'fastqillumina', 'fastqillumina.gz']
    HOST_FORMATS = ['', 'fasta', 'fasta.gz']

    @classmethod
    def _sequence_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('sequence_type', inputs.get('type', 'single')) or 'single')

    @classmethod
    def _host_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('host_source', inputs.get('source', 'cached')) or 'cached')

    @classmethod
    def _reads_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reads_ext', '') or '')

    @classmethod
    def _host_sequence_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('host_sequence_ext', '') or '')

    @classmethod
    def _is_gzip(cls, path: Any, explicit_type: Any='') -> bool:
        value = str(explicit_type or path or '').lower()
        return value.endswith('.gz') or value in {'fasta.gz', 'fastqsanger.gz', 'fastqillumina.gz'}

    @classmethod
    def _is_fasta(cls, path: Any, explicit_type: Any='') -> bool:
        value = str(explicit_type or path or '').lower()
        return value.startswith('fasta') or value.endswith(('.fa', '.fasta', '.fa.gz', '.fasta.gz'))

    @classmethod
    def _is_test(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get('test', '')
        if isinstance(value, str):
            return value.lower() in {'true', '1', 'yes'}
        return bool(value)

    @classmethod
    def _stage_file_command(cls, source: str, target: str, *, compressed: bool) -> str:
        quoted_source = shlex.quote(source)
        quoted_target = shlex.quote(target)
        if compressed:
            return f'gunzip -c {quoted_source} > {quoted_target}'
        return f'ln -s {quoted_source} {quoted_target}'

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return '.fastq.gz' if cls._is_gzip(inputs.get('reads'), cls._reads_ext(inputs)) else '.fastq'

    @classmethod
    def _single_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_single{cls._output_suffix(inputs)}'

    @classmethod
    def _forward_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/forward{cls._output_suffix(inputs)}'

    @classmethod
    def _reverse_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/reverse{cls._output_suffix(inputs)}'

    @classmethod
    def _reference_prefix(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('reference', inputs.get('host_reference', '')) or '')

    @classmethod
    def _host_sequence(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('host_sequence', inputs.get('sequence', '')) or '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = cls._sequence_type(inputs)
        reads = str(inputs.get('reads', '') or '')
        reads_reverse = str(inputs.get('reads_reverse', inputs.get('reverse', '')) or '')
        reads_ext = cls._reads_ext(inputs)
        gzipped_reads = cls._is_gzip(reads, reads_ext)
        fasta_reads = cls._is_fasta(reads, reads_ext)
        commands = []
        commands.append(cls._stage_file_command(reads, 'forward', compressed=gzipped_reads))
        if sequence_type == 'paired':
            commands.append(cls._stage_file_command(reads_reverse, 'reverse', compressed=gzipped_reads))
        host_source = cls._host_source(inputs)
        if host_source == 'cached':
            reference = cls._reference_prefix(inputs)
            if cls._is_test(inputs):
                commands.append(f"srprism mkindex -i {shlex.quote(reference + '.fa')} -o reference.srprism")
            bitmask = f'{reference}.bitmask'
            srprism = 'reference.srprism' if cls._is_test(inputs) else f'{reference}.srprism'
            database = reference
        else:
            host_sequence = cls._host_sequence(inputs)
            commands.append(cls._stage_file_command(host_sequence, 'reference.fa', compressed=cls._is_gzip(host_sequence, cls._host_sequence_ext(inputs))))
            word_size = 10 if cls._is_test(inputs) else 18
            commands.extend([f'bmtool -d reference.fa -o reference.bitmask -w {word_size}', 'srprism mkindex -i reference.fa -o reference.srprism', 'makeblastdb -in reference.fa -dbtype nucl'])
            bitmask = 'reference.bitmask'
            srprism = 'reference.srprism'
            database = 'reference'
        tagger_cmd = ['bmtagger.sh', '-q', '0' if fasta_reads else '1', '-1', 'forward']
        if sequence_type == 'paired':
            tagger_cmd.extend(['-2', 'reverse'])
        tagger_cmd.extend(['-b', bitmask, '-x', srprism, '-d', database, '-o', 'host_ids'])
        commands.append(_shell_join(tagger_cmd))
        gzip_pipe = ' | gzip -c' if gzipped_reads else ''
        if sequence_type == 'single':
            commands.append(f'extract_fullseq host_ids -keep -fastq -single forward{gzip_pipe} > {shlex.quote(cls._single_output_path(inputs))}')
        else:
            commands.extend([f'extract_fullseq host_ids -keep -fastq -mate1 forward{gzip_pipe} > {shlex.quote(cls._forward_output_path(inputs))}', f'extract_fullseq host_ids -keep -fastq -mate2 reverse{gzip_pipe} > {shlex.quote(cls._reverse_output_path(inputs))}'])
        return 'set -eo pipefail; ' + ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = cls._output_suffix(inputs)
        if cls._sequence_type(inputs) == 'paired':
            return [out / f'forward{suffix}', out / f'reverse{suffix}']
        return [out / f'out_single{suffix}']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('reads', '')).strip():
            return 'reads is required'
        sequence_type = cls._sequence_type(inputs)
        if sequence_type not in cls.SEQUENCE_TYPES:
            return f"sequence_type must be one of: {', '.join(cls.SEQUENCE_TYPES)}"
        if sequence_type == 'paired' and (not str(inputs.get('reads_reverse', inputs.get('reverse', ''))).strip()):
            return 'reads_reverse is required for paired sequence_type'
        reads_ext = cls._reads_ext(inputs)
        if reads_ext and reads_ext not in cls.READ_FORMATS:
            return f"reads_ext must be one of: {', '.join(cls.READ_FORMATS)}"
        host_source = cls._host_source(inputs)
        if host_source not in cls.HOST_SOURCES:
            return f"host_source must be one of: {', '.join(cls.HOST_SOURCES)}"
        if host_source == 'cached' and (not cls._reference_prefix(inputs).strip()):
            return 'reference is required when host_source is cached'
        if host_source == 'history' and (not cls._host_sequence(inputs).strip()):
            return 'host_sequence is required when host_source is history'
        host_ext = cls._host_sequence_ext(inputs)
        if host_ext and host_ext not in cls.HOST_FORMATS:
            return f"host_sequence_ext must be one of: {', '.join(cls.HOST_FORMATS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Single-end reads or forward reads for paired-end filtering'})}, 'optional': {'sequence_type': ('STRING', {'default': 'single', 'options': cls.SEQUENCE_TYPES}), 'reads_reverse': ('FASTQ', {'default': '', 'description': 'Reverse reads for paired-end filtering'}), 'reads_ext': ('STRING', {'default': '', 'options': cls.READ_FORMATS, 'description': 'Galaxy datatype extension for input reads', 'advanced': True}), 'host_source': ('STRING', {'default': 'cached', 'options': cls.HOST_SOURCES}), 'reference': ('FILE', {'default': '', 'description': 'Prefix for a precomputed BMTagger reference'}), 'host_sequence': ('FASTA', {'default': '', 'description': 'Host FASTA sequence for on-the-fly indexing'}), 'host_sequence_ext': ('STRING', {'default': '', 'options': cls.HOST_FORMATS, 'description': 'Galaxy datatype extension for the host sequence', 'advanced': True}), 'test': ('BOOLEAN', {'default': False, 'advanced': True, 'description': "Use the Galaxy wrapper's small-index test mode"})}, 'hidden': {'output': ('STRING', {})}}
