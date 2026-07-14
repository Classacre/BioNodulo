"""tracy — sequence node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TracyBasecallNode(CommandNode):
    """Basecall Sanger chromatogram trace files with Tracy."""
    NODE_ID = 'tracy_basecall'
    DISPLAY_NAME = 'tracy Basecall'
    REQUIRED_CONDA_PACKAGES = ['tracy']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Basecall a Sanger chromatogram trace file with Tracy.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Tracy', 'tracy Basecall', 'tracy Sanger basecalling', 'Sanger chromatogram', 'AB1 trace', 'SCF trace']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('basecalls',)
    REQUIRED_EXECUTABLES = ['tracy']
    DOCUMENTATION_URL = 'https://www.gear-genomics.com/docs/tracy/cli/#basecalling-a-chromatogram-trace-file'
    CITATION_DOIS = ['10.1186/s12864-020-6635-8']
    CITATION_URLS = [f'{DOI_URL}10.1186/s12864-020-6635-8']
    CITATION_TEXT = 'Tracy: basecalling, alignment, assembly and deconvolution of Sanger chromatogram trace files.'
    VERSION = '0.7.8'
    FORMATS = ['fasta', 'fastq', 'tsv', 'json']

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('format', 'fasta') or 'fasta')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/basecalls.{cls._format(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ['tracy', 'basecall', '--pratio', str(inputs.get('pratio', 0.33)), '--format', cls._format(inputs), '--output', cls._output_path(inputs), str(inputs.get('tracefile', ''))]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'basecalls.{cls._format(inputs)}']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('tracefile', '')).strip():
            return 'tracefile is required'
        raw_pratio = inputs.get('pratio', 0.33)
        try:
            pratio = float(raw_pratio)
        except (TypeError, ValueError):
            return 'pratio must be a number'
        if pratio < 0:
            return 'pratio must be >= 0'
        output_format = cls._format(inputs)
        if output_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'tracefile': ('FILE', {'description': 'Chromatogram trace file in AB1 or SCF format'})}, 'optional': {'pratio': ('FLOAT', {'default': 0.33, 'min': 0, 'description': 'Peak ratio threshold for calling a base'}), 'format': ('STRING', {'default': 'fasta', 'options': cls.FORMATS, 'description': 'Output format'})}, 'hidden': {'output': ('STRING', {})}}
