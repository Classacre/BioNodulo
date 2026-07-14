"""shovill — assembly node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ShovillNode(CommandNode):
    """Assemble bacterial isolate genomes with the Galaxy IUC Shovill wrapper behavior."""
    NODE_ID = 'shovill'
    DISPLAY_NAME = 'Shovill'
    REQUIRED_CONDA_PACKAGES = ['shovill']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assemble bacterial isolate genomes from Illumina paired-end reads with Shovill.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Shovill', 'shovill', 'SPAdes', 'Faster SPAdes assembly', 'Illumina paired-end', 'bacterial isolate assembly', 'skesa', 'megahit', 'velvet', 'contigs.fa']
    RETURN_TYPES = ('TXT', 'FASTA', 'TXT', 'BAM', 'GFA')
    RETURN_NAMES = ('shovill_std_log', 'contigs', 'contigs_graph', 'bamfiles', 'skesa_gfa')
    REQUIRED_EXECUTABLES = ['shovill']
    DOCUMENTATION_URL = SHOVILL_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SHOVILL_CITATION_URL]
    CITATION_TEXT = SHOVILL_CITATION_TEXT
    VERSION = '1.4.2+galaxy1'
    SHELL = True
    LIB_TYPES = ['paired', 'collection']
    FASTQ_FORMATS = ['fastq', 'fastq.gz', 'fastqsanger', 'fastqsanger.gz', 'fastqsanger.bz2']
    COPY_FORMATS = {'fastqsanger.gz', 'fastqsanger.bz2'}
    ASSEMBLERS = ['skesa', 'megahit', 'velvet', 'spades']
    NOCORR_OPTIONS = ['no_correction', 'yes_correction']

    @classmethod
    def _format_value(cls, inputs: dict[str, Any], key: str, default: str) -> str:
        value = inputs.get(key, default)
        if value in (None, ''):
            value = default
        return str(value)

    @classmethod
    def _single_quote(cls, value: Any) -> str:
        return "'" + str(value).replace("'", '\'"\'"\'') + "'"

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get('input_collection')
        if isinstance(collection, dict):
            return (str(collection.get('forward', '') or ''), str(collection.get('reverse', '') or ''))
        if isinstance(collection, (list, tuple)) and len(collection) >= 2:
            return (str(collection[0]), str(collection[1]))
        return ('', '')

    @classmethod
    def _read_paths(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._format_value(inputs, 'lib_type', 'paired') == 'collection':
            return cls._collection_reads(inputs)
        return (str(inputs.get('R1', '') or ''), str(inputs.get('R2', '') or ''))

    @classmethod
    def _read_format(cls, inputs: dict[str, Any], key: str, path: str) -> str:
        explicit = str(inputs.get(key, '') or '').strip()
        if explicit:
            return explicit
        suffixes = [suffix.lower().lstrip('.') for suffix in Path(path).suffixes]
        if len(suffixes) >= 2 and suffixes[-2:] in (['fastq', 'gz'], ['fq', 'gz']):
            return 'fastq.gz'
        if len(suffixes) >= 2 and suffixes[-2:] in (['fastq', 'bz2'], ['fq', 'bz2']):
            return 'fastqsanger.bz2'
        return 'fastqsanger'

    @classmethod
    def _stage_command(cls, source: str, staged: str, fastq_format: str) -> str:
        operation = 'cp' if fastq_format in cls.COPY_FORMATS else 'ln -s'
        return f'{operation} {shlex.quote(source)} {shlex.quote(staged)}'

    @classmethod
    def _outdir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        r1, r2 = cls._read_paths(inputs)
        r1_format = cls._read_format(inputs, 'R1_format', r1)
        r2_format = cls._read_format(inputs, 'R2_format', r2)
        r1_staged = f'fastq_r1.{r1_format}'
        r2_staged = f'fastq_r2.{r2_format}'
        commands = [cls._stage_command(r1, r1_staged, r1_format), cls._stage_command(r2, r2_staged, r2_format), 'GALAXY_MEMORY_GB=$((${GALAXY_MEMORY_MB:-8192}/1024))', 'SHOVILL_RAM=${SHOVILL_RAM:-${GALAXY_MEMORY_GB}}']
        slots = '${GALAXY_SLOTS:-1}'
        ram = '${SHOVILL_RAM:-8}'
        cmd = ['shovill', '--outdir', cls._outdir(inputs), '--cpus', slots, '--ram', ram, '--R1', r1_staged, '--R2', r2_staged]
        if inputs.get('trim'):
            cmd.append('--trim')
        cmd.extend(['--namefmt', cls._single_quote(inputs.get('namefmt', 'contig%05d') or 'contig%05d'), '--depth', cls._format_value(inputs, 'depth', '100')])
        if str(inputs.get('gsize', '') or '').strip():
            cmd.extend(['--gsize', str(inputs.get('gsize'))])
        if str(inputs.get('kmers', '') or '').strip():
            cmd.extend(['--kmers', str(inputs.get('kmers'))])
        if str(inputs.get('opts', '') or '').strip():
            cmd.extend(['--opts', cls._single_quote(inputs.get('opts'))])
        assembler = cls._format_value(inputs, 'assembler', 'spades')
        cmd.extend(['--minlen', cls._format_value(inputs, 'minlen', '0'), '--mincov', cls._format_value(inputs, 'mincov', '2'), '--assembler', assembler])
        if assembler == 'spades' and inputs.get('plasmid'):
            cmd.append('--plasmid')
        if cls._format_value(inputs, 'nocorr', 'no_correction') == 'no_correction':
            cmd.append('--nocorr')
        elif inputs.get('keepfiles'):
            cmd.append('--keepfiles')
        shovill_command = _shell_join(cmd).replace(shlex.quote(slots), slots).replace(shlex.quote(ram), ram)
        shovill_command = shovill_command.replace(shlex.quote(cls._single_quote(inputs.get('namefmt', 'contig%05d'))), cls._single_quote(inputs.get('namefmt', 'contig%05d') or 'contig%05d'))
        if str(inputs.get('opts', '') or '').strip():
            shovill_command = shovill_command.replace(shlex.quote(cls._single_quote(inputs.get('opts'))), cls._single_quote(inputs.get('opts')))
        commands.append(shovill_command)
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'out'
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if inputs.get('log', True):
            outputs.append(out / 'shovill.log')
        outputs.append(out / 'contigs.fa')
        assembler = cls._format_value(inputs, 'assembler', 'spades')
        if assembler == 'skesa':
            outputs.append(out / 'skesa.gfa')
        else:
            outputs.append(out / 'spades.gfa')
        if cls._format_value(inputs, 'nocorr', 'no_correction') == 'yes_correction' and inputs.get('keepfiles'):
            outputs.append(out / 'shovill.bam')
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, '') else default)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if value < minimum:
            return f'{key} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        lib_type = cls._format_value(inputs, 'lib_type', 'paired')
        if lib_type not in cls.LIB_TYPES:
            return f"lib_type must be one of: {', '.join(cls.LIB_TYPES)}"
        r1, r2 = cls._read_paths(inputs)
        if lib_type == 'collection':
            if not r1 or not r2:
                return 'input_collection with forward and reverse reads is required for collection input'
        else:
            if not r1:
                return 'R1 is required for paired input'
            if not r2:
                return 'R2 is required for paired input'
        r1_format = cls._read_format(inputs, 'R1_format', r1)
        r2_format = cls._read_format(inputs, 'R2_format', r2)
        if r1_format not in cls.FASTQ_FORMATS:
            return f"R1_format must be one of: {', '.join(cls.FASTQ_FORMATS)}"
        if r2_format not in cls.FASTQ_FORMATS:
            return f"R2_format must be one of: {', '.join(cls.FASTQ_FORMATS)}"
        assembler = cls._format_value(inputs, 'assembler', 'spades')
        if assembler not in cls.ASSEMBLERS:
            return f"assembler must be one of: {', '.join(cls.ASSEMBLERS)}"
        if inputs.get('plasmid') and assembler != 'spades':
            return 'plasmid mode is only available with the spades assembler'
        nocorr = cls._format_value(inputs, 'nocorr', 'no_correction')
        if nocorr not in cls.NOCORR_OPTIONS:
            return f"nocorr must be one of: {', '.join(cls.NOCORR_OPTIONS)}"
        for key, default in (('depth', 100), ('minlen', 0), ('mincov', 2)):
            result = cls._validate_int_min(inputs, key, default, 0)
            if result is not True:
                return result
        if not str(inputs.get('namefmt', 'contig%05d') or '').strip():
            return 'namefmt is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'lib_type': ('STRING', {'default': 'paired', 'options': cls.LIB_TYPES, 'description': 'Galaxy input layout: paired FASTQ datasets or a paired collection'}), 'R1': ('FASTQ', {'description': 'Forward reads for paired input'}), 'R2': ('FASTQ', {'description': 'Reverse reads for paired input'})}, 'optional': {'input_collection': ('FILE', {'default': '', 'description': 'Paired collection object with forward and reverse reads'}), 'R1_format': ('STRING', {'default': 'fastqsanger', 'options': cls.FASTQ_FORMATS, 'description': 'Galaxy extension for R1'}), 'R2_format': ('STRING', {'default': 'fastqsanger', 'options': cls.FASTQ_FORMATS, 'description': 'Galaxy extension for R2'}), 'trim': ('BOOLEAN', {'default': False, 'description': 'Use Trimmomatic to remove common adapters first'}), 'assembler': ('STRING', {'default': 'spades', 'options': cls.ASSEMBLERS, 'description': 'Assembler backend used by Shovill'}), 'plasmid': ('BOOLEAN', {'default': False, 'description': 'Enable SPAdes plasmid mode'}), 'namefmt': ('STRING', {'default': 'contig%05d', 'description': 'printf-style contig FASTA ID format'}), 'depth': ('INT', {'default': 100, 'min': 0, 'description': 'Subsample R1/R2 to this depth; 0 disables subsampling'}), 'gsize': ('STRING', {'default': '', 'description': 'Estimated genome size, for example 4.8M; blank autodetects'}), 'kmers': ('STRING', {'default': '', 'description': 'Comma-separated k-mer sizes; blank selects AUTO'}), 'opts': ('STRING', {'default': '', 'description': 'Extra assembler options passed through Shovill'}), 'nocorr': ('STRING', {'default': 'no_correction', 'options': cls.NOCORR_OPTIONS, 'description': 'Galaxy correction selector; no_correction adds --nocorr'}), 'keepfiles': ('BOOLEAN', {'default': False, 'description': 'Keep BAM files when post-assembly correction is enabled'}), 'minlen': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum output contig length'}), 'mincov': ('INT', {'default': 2, 'min': 0, 'description': 'Minimum contig coverage'}), 'log': ('BOOLEAN', {'default': True, 'description': 'Return shovill.log as an output'})}, 'hidden': {'output': ('STRING', {})}}
