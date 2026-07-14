"""bbtools — assembly node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BBToolsTadpoleNode(CommandNode):
    """Assemble, extend, or correct reads with BBTools Tadpole."""
    NODE_ID = 'bbtools_tadpole'
    DISPLAY_NAME = 'BBTools Tadpole'
    REQUIRED_CONDA_PACKAGES = ['bbmap', 'samtools']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assemble, extend, or correct reads with Tadpole k-mer processing from BBTools.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BBTools', 'Tadpole', 'tadpole', 'bbtools_tadpole', 'kmer assembler', 'error correction', 'read extension', 'contig mode', 'fastadump']
    RETURN_TYPES = ('FASTQ', 'FASTQ', 'FASTA')
    RETURN_NAMES = ('output', 'reverse_output', 'fastadump')
    REQUIRED_EXECUTABLES = ['tadpole.sh']
    DOCUMENTATION_URL = 'https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/tadpole-guide/'
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BBTOOLS_CITATION_DOI}']
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = '39.08'
    SHELL = True
    VALID_MODES = {'contig', 'extend', 'correct'}
    VALID_INPUT_TYPES = {'single', 'pair', 'paired'}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_type', 'single') or 'single')

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == 'paired':
            collection = inputs.get('reads_collection')
            if isinstance(collection, dict):
                return (str(collection.get('forward', '')), str(collection.get('reverse', '')))
            reads = _as_list(collection or inputs.get('reads'))
            return (reads[0] if reads else '', reads[1] if len(reads) > 1 else '')
        return (str(inputs.get('read1', '')), str(inputs.get('read2', '')))

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return '.fastq.gz' if str(path).endswith('.gz') else '.fastq'

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            if value in {'t', 'f'}:
                return value
            return 't' if value.lower() in {'true', 'yes', '1'} else 'f'
        return 't' if bool(value) else 'f'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f'{out}/forward{cls._fastq_ext(read1)}'
        setup = [f'ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}']
        if input_type in {'pair', 'paired'}:
            read2_file = f'{out}/reverse{cls._fastq_ext(read1)}'
            setup.append(f'ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}')
        else:
            read2_file = ''
        mode = str(inputs.get('mode', 'contig') or 'contig')
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        cmd = ['tadpole.sh', f'in={read1_file}']
        if input_type in {'pair', 'paired'}:
            cmd.append(f'in2={read2_file}')
        cmd.extend([f"fastadump={cls._bool_value(inputs, 'fastadump', True)}", f"mincounttodump={inputs.get('mincounttodump', 1)}"])
        if inputs.get('fastadump', True):
            cmd.append(f'dump={out}/fastadump.fasta')
        cmd.append(f'out={out}/output.fastq')
        if input_type in {'pair', 'paired'} and mode != 'contig':
            cmd.append(f'out2={out}/reverse_output.fastq')
        cmd.extend([f'mode={mode}', f'threads={slots}', 'overwrite=true'])
        command = _shell_join(cmd).replace(shlex.quote(f'threads={slots}'), f'threads={slots}')
        return ' && '.join(setup + [command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        input_type = cls._input_type(inputs)
        mode = str(inputs.get('mode', 'contig') or 'contig')
        outputs = [out / 'output.fastq']
        if input_type in {'pair', 'paired'} and mode != 'contig':
            outputs.append(out / 'reverse_output.fastq')
        if inputs.get('fastadump', True):
            outputs.append(out / 'fastadump.fasta')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.VALID_INPUT_TYPES:
            return 'input_type must be one of: single, pair, paired'
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return 'read1 FASTQ is required'
        if input_type in {'pair', 'paired'} and (not read2):
            return 'read2 FASTQ is required for paired input'
        mode = str(inputs.get('mode', 'contig') or 'contig')
        if mode not in cls.VALID_MODES:
            return 'mode must be one of: contig, extend, correct'
        for key, default in (('mincounttodump', 1), ('threads', 4)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 1:
                return f'{key} must be >= 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'pair', 'paired'], 'description': 'Galaxy input mode'}), 'read1': ('FASTQ', {'description': 'Single, forward, or paired-collection forward FASTQ'})}, 'optional': {'read2': ('FASTQ', {'default': '', 'description': 'Reverse FASTQ reads for paired input'}), 'reads_collection': ('FASTQ_LIST', {'default': '', 'description': 'Paired collection mapping or [forward, reverse]'}), 'mode': ('STRING', {'default': 'contig', 'options': ['contig', 'extend', 'correct'], 'description': 'Tadpole processing mode'}), 'fastadump': ('BOOLEAN', {'default': True, 'description': 'Write k-mers and counts as FASTA'}), 'mincounttodump': ('INT', {'default': 1, 'min': 1, 'description': 'Minimum k-mer depth to dump'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}
