"""bellerophon — assembly node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BellerophonNode(CommandNode):
    """Filter and merge Arima Genomics chimeric read alignments with Bellerophon."""
    NODE_ID = 'bellerophon'
    DISPLAY_NAME = 'Bellerophon'
    REQUIRED_CONDA_PACKAGES = ['bellerophon', 'samtools']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Filter mapped reads spanning Arima Genomics junctions, keep the 5-prime read, merge mates, and sort the BAM output.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Bellerophon', 'Arima Genomics', 'chimeric reads', 'Hi-C', 'junction-spanning reads', 'qname sorted BAM', 'genome assembly']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('merged_bam',)
    REQUIRED_EXECUTABLES = ['bellerophon', 'samtools']
    DOCUMENTATION_URL = 'https://github.com/ArimaGenomics/bellerophon'
    CITATION_DOIS = ['10.1038/s41586-021-03451-0']
    CITATION_URLS = [f'{DOI_URL}10.1038/s41586-021-03451-0']
    CITATION_TEXT = 'Semi-automated assembly of high-quality diploid human reference genomes.'
    VERSION = '1.0'
    SHELL = True

    @classmethod
    def _format_suffix(cls, inputs: dict[str, Any], key: str, path_key: str) -> str:
        fmt = str(inputs.get(key, '')).strip().lower().lstrip('.')
        if fmt in {'sam', 'bam'}:
            return fmt
        suffix = Path(str(inputs.get(path_key, ''))).suffix.lower().lstrip('.')
        return 'sam' if suffix == 'sam' else 'bam'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        forward_input = f"{out}/forward_input.{cls._format_suffix(inputs, 'forward_format', 'forward')}"
        reverse_input = f"{out}/reverse_input.{cls._format_suffix(inputs, 'reverse_format', 'reverse')}"
        threads = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = ['ln', '-s', str(inputs.get('forward', '')), forward_input, '&&', 'ln', '-s', str(inputs.get('reverse', '')), reverse_input, '&&', 'bellerophon', '--forward', forward_input, '--reverse', reverse_input, '--quality', str(inputs.get('quality', 20)), '--output', f'{out}/merged_out.bam', '--threads', threads, '&&', 'samtools', 'sort', '--no-PG', '-O', 'BAM', '-o', f'{out}/merged.bam', '-@', threads, f'{out}/merged_out.bam']
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'merged.bam']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'forward': ('BAM', {'description': 'First qname-sorted BAM or SAM reads, usually forward reads'}), 'reverse': ('BAM', {'description': 'Second qname-sorted BAM or SAM reads, usually reverse reads'}), 'quality': ('INT', {'default': 20, 'min': 0, 'max': 255, 'description': 'Minimum mapping quality'})}, 'optional': {'forward_format': ('STRING', {'default': 'bam', 'options': ['bam', 'sam'], 'advanced': True, 'description': 'Galaxy input datatype for staging the forward reads'}), 'reverse_format': ('STRING', {'default': 'bam', 'options': ['bam', 'sam'], 'advanced': True, 'description': 'Galaxy input datatype for staging the reverse reads'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
