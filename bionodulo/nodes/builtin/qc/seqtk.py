"""seqtk — qc node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class SeqTKFqchkNode(CommandNode):
    """Report FASTQ base composition and quality summaries with seqtk fqchk."""
    NODE_ID = 'seqtk_fqchk'
    DISPLAY_NAME = 'SeqTK FASTQ Check'
    REQUIRED_CONDA_PACKAGES = ['seqtk', 'gawk']
    CATEGORY = 'qc'
    DESCRIPTION = 'Report base-by-base FASTQ composition and quality summaries with seqtk fqchk.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'seqtk', 'seqtk fqchk', 'SeqTK fqchk', 'FASTQ QC', 'base quality summary', 'quality distribution', 'base composition']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('quality_information',)
    REQUIRED_EXECUTABLES = ['seqtk', 'awk']
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = '1.5+galaxy0'
    SHELL = True

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/quality_information.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['seqtk', 'fqchk', '-q', str(inputs.get('q', 20)), str(inputs.get('in_file', ''))]
        return f"""{_shell_join(cmd)} | awk '{{if(NR<4){{print "#"$0}}else{{print $0}}}}' > {shlex.quote(cls._out_path(inputs))}"""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'quality_information.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('FASTQ', {'description': 'Input FASTQ file, optionally gzip-compressed'})}, 'optional': {'q': ('INT', {'default': 20, 'min': 0, 'description': 'Quality threshold; use 0 to report all quality values'})}, 'hidden': {'output': ('STRING', {})}}
