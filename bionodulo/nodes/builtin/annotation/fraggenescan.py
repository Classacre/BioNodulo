"""fraggenescan — annotation node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FragGeneScanNode(CommandNode):
    """Find complete and fragmented genes in short reads or assemblies."""
    NODE_ID = 'fraggenescan'
    DISPLAY_NAME = 'FragGeneScan'
    REQUIRED_CONDA_PACKAGES = ['fraggenescan']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Find complete and fragmented genes in short reads, incomplete assemblies, or complete genomes.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'FragGeneScan', 'fraggenescan', 'run_FragGeneScan.pl', 'fragmented genes', 'gene prediction', 'short reads', 'prokaryotic genes']
    RETURN_TYPES = ('TSV', 'FASTA', 'FASTA', 'GFF')
    RETURN_NAMES = ('coordinates', 'nucleotide_sequences', 'protein_sequences', 'gff')
    REQUIRED_EXECUTABLES = ['run_FragGeneScan.pl']
    DOCUMENTATION_URL = 'https://omics.informatics.indiana.edu/FragGeneScan/'
    CITATION_DOIS = [FRAGGENESCAN_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{FRAGGENESCAN_CITATION_DOI}']
    CITATION_TEXT = FRAGGENESCAN_CITATION_TEXT
    VERSION = '1.30'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        complete = '1' if inputs.get('complete') else '0'
        return ['run_FragGeneScan.pl', '-genome', str(inputs.get('genome', '')), '-out', f'{_out(inputs)}/output_file_name', '-complete', complete, '-train', str(inputs.get('train', 'complete')), f"-thread=${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output_file_name.out', out / 'output_file_name.ffn', out / 'output_file_name.faa', out / 'output_file_name.gff']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('genome'):
            return 'input FASTA is required'
        threads = inputs.get('threads', 4)
        try:
            if int(threads) < 1:
                return 'threads must be >= 1'
        except (TypeError, ValueError):
            return 'threads must be an integer'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'genome': ('FASTA', {'description': 'Input sequence file'})}, 'optional': {'complete': ('BOOLEAN', {'default': False, 'description': 'Treat input as complete genomic sequences'}), 'train': ('STRING', {'default': 'complete', 'options': ['454_5', '454_10', '454_30', 'complete', 'gene', 'illumina_1', 'illumina_5', 'illumina_10', 'noncoding', 'pwm', 'rgene', 'sanger_5', 'sanger_10', 'start', 'start1', 'stop', 'stop1'], 'description': 'FragGeneScan training model'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
