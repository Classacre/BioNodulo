"""megahit — assembly node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MegahitContig2FastgNode(CommandNode):
    """Convert MEGAHIT contigs into FASTG assembly graph format."""
    NODE_ID = 'megahit_contig2fastg'
    DISPLAY_NAME = 'megahit contig2fastg'
    REQUIRED_CONDA_PACKAGES = ['megahit']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Convert MEGAHIT contigs into FASTG assembly graph format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'MEGAHIT', 'megahit_contig2fastg', 'megahit_toolkit', 'contig2fastg', 'FASTG', 'assembly graph', 'metagenomics assembly']
    RETURN_TYPES = ('GFA',)
    RETURN_NAMES = ('fastg',)
    REQUIRED_EXECUTABLES = ['megahit_toolkit']
    DOCUMENTATION_URL = 'https://github.com/voutcn/megahit'
    CITATION_DOIS = [MEGAHIT_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{MEGAHIT_CITATION_DOI}']
    CITATION_TEXT = MEGAHIT_CITATION_TEXT
    VERSION = '1.1.3+galaxy1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/contigs.fastg'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['megahit_toolkit', 'contig2fastg', str(inputs.get('kmer', 99)), str(inputs.get('contigs', ''))]
        return f'{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'contigs.fastg']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('contigs', '')).strip():
            return 'contigs is required'
        try:
            kmer = int(inputs.get('kmer', 99))
        except (TypeError, ValueError):
            return 'kmer must be an integer'
        if kmer <= 0:
            return 'kmer must be greater than 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'contigs': ('FASTA', {'description': 'MEGAHIT contig FASTA file, such as k99.contigs.fa'})}, 'optional': {'kmer': ('INT', {'default': 99, 'min': 1, 'description': 'K-mer length used by MEGAHIT for the input contigs'})}, 'hidden': {'output': ('STRING', {})}}
