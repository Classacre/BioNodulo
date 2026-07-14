"""plasflow — metagenomics node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class PlasFlowNode(CommandNode):
    """Predict plasmid-origin contigs with PlasFlow."""
    NODE_ID = 'plasflow'
    DISPLAY_NAME = 'PlasFlow'
    REQUIRED_CONDA_PACKAGES = ['plasflow']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Predict plasmid sequences in metagenomic contigs with PlasFlow genome-signature models.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'PlasFlow', 'plasflow', 'plasmid prediction', 'metagenomic contigs', 'genome signatures', 'chromosome classification']
    RETURN_TYPES = ('TSV', 'FASTA', 'FASTA', 'FASTA')
    RETURN_NAMES = ('probability_table', 'chromosomes', 'plasmids', 'unclassified')
    REQUIRED_EXECUTABLES = ['PlasFlow.py']
    DOCUMENTATION_URL = 'https://github.com/smaegol/PlasFlow'
    CITATION_DOIS = [PLASFLOW_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PLASFLOW_CITATION_DOI}']
    CITATION_TEXT = PLASFLOW_CITATION_TEXT
    VERSION = '1.1.0'
    SHELL = True

    @classmethod
    def _is_gzipped_fasta(cls, input_path: Any) -> bool:
        return Path(str(input_path or '')).suffixes[-2:] == ['.fasta', '.gz']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        read_file = str(inputs.get('read_file', ''))
        if cls._is_gzipped_fasta(read_file):
            stage = f'gunzip -c {shlex.quote(read_file)} > reads.fasta'
        else:
            stage = f'ln -s {shlex.quote(read_file)} reads.fasta'
        cmd = ['PlasFlow.py', '--input', 'reads.fasta', '--output', f'{_out(inputs)}/output', '--threshold', str(inputs.get('threshold', 0.7))]
        return f'{stage} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output', out / 'output_chromosomes.fasta', out / 'output_plasmids.fasta', out / 'output_unclassified.fasta']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('read_file'):
            return 'contig FASTA is required'
        try:
            threshold = float(inputs.get('threshold', 0.7))
        except (TypeError, ValueError):
            return 'threshold must be a number'
        if not 0 <= threshold <= 1:
            return 'threshold must be between 0 and 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'read_file': ('FASTA', {'description': 'Metagenomic contig sequences in FASTA or FASTA.GZ format'})}, 'optional': {'threshold': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1, 'description': 'Probability threshold for classification'})}, 'hidden': {'output': ('STRING', {})}}
