"""minia — assembly node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MiniaNode(CommandNode):
    """Assemble short reads with the Minia de Bruijn graph assembler."""
    NODE_ID = 'minia'
    DISPLAY_NAME = 'Minia'
    REQUIRED_CONDA_PACKAGES = ['minia']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assemble short reads into contigs with Minia, a compact de Bruijn graph assembler.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Minia', 'minia', 'short-read assembler', 'de Bruijn graph', 'Bloom filter', 'contig assembly', 'k-mer assembler']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('contigs',)
    REQUIRED_EXECUTABLES = ['minia']
    DOCUMENTATION_URL = 'https://github.com/GATB/minia'
    CITATION_DOIS = [MINIA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{MINIA_CITATION_DOI}']
    CITATION_TEXT = MINIA_CITATION_TEXT
    VERSION = '3.2.6'
    SHELL = True

    @classmethod
    def _staged_input_name(cls, input_path: Any) -> str:
        suffixes = Path(str(input_path or '')).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            return f'infile{suffixes[-2]}{suffixes[-1]}'
        suffix = suffixes[-1] if suffixes else '.fa'
        return f'infile{suffix}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input_name(inputs.get('in'))
        cmd = ['minia', '-in', staged, '-kmer-size', str(inputs.get('kmer_size', 31))]
        if inputs.get('abundance_min') not in (None, ''):
            cmd.extend(['-abundance-min', str(inputs.get('abundance_min'))])
        if inputs.get('abundance_max') not in (None, ''):
            cmd.extend(['-abundance-max', str(inputs.get('abundance_max'))])
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd.extend(['-nb-cores', slots, '-out', f'{_out(inputs)}/output'])
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"ln -s {shlex.quote(str(inputs.get('in', '')))} {staged} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.contigs.fa']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('in'):
            return 'input reads are required'
        for key, message in (('kmer_size', 'kmer_size must be >= 1'), ('threads', 'threads must be >= 1')):
            try:
                value = int(inputs.get(key, 31 if key == 'kmer_size' else 1))
            except (TypeError, ValueError):
                return message.replace('>=', 'must be an integer >=')
            if value < 1:
                return message
        for key in ('abundance_min', 'abundance_max'):
            if inputs.get(key) in (None, ''):
                continue
            try:
                value = int(inputs.get(key))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if value < 0:
                return f'{key} must be >= 0'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in': ('FASTQ', {'description': 'Reads in FASTA, FASTQ, or compressed FASTA/FASTQ format'})}, 'optional': {'kmer_size': ('INT', {'default': 31, 'min': 1, 'description': 'K-mer size'}), 'abundance_min': ('INT', {'default': '', 'min': 0, 'description': 'Minimum abundance threshold for solid k-mers'}), 'abundance_max': ('INT', {'default': '', 'min': 0, 'description': 'Maximum abundance threshold for solid k-mers'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
