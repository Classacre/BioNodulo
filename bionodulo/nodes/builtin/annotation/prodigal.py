"""prodigal — annotation node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ProdigalNode(CommandNode):
    """Predict protein-coding genes in microbial genomes with Prodigal."""
    NODE_ID = 'prodigal'
    DISPLAY_NAME = 'Prodigal Gene Predictor'
    REQUIRED_CONDA_PACKAGES = ['prodigal']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Predict protein-coding genes in microbial genomes, draft assemblies, and metagenomic sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Prodigal', 'prodigal', 'gene prediction', 'microbial genomes', 'protein-coding genes', 'translation initiation sites', 'metagenomic gene prediction']
    RETURN_TYPES = ('FILE', 'FASTA', 'FASTA', 'TSV')
    RETURN_NAMES = ('coordinates', 'protein_translations', 'nucleotide_sequences', 'start_sites')
    REQUIRED_EXECUTABLES = ['prodigal']
    DOCUMENTATION_URL = 'https://github.com/hyattpd/Prodigal'
    CITATION_DOIS = [PRODIGAL_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PRODIGAL_CITATION_DOI}']
    CITATION_TEXT = PRODIGAL_CITATION_TEXT
    VERSION = '2.6.3'
    OUTPUT_FORMATS = {'gbk': 'gbk', 'gff': 'gff3', 'sqn': 'sqn', 'sco': 'sco'}

    @classmethod
    def _coordinates_output(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get('out_format', 'gbk') or 'gbk')
        ext = cls.OUTPUT_FORMATS.get(out_format, 'gbk')
        return f'{_out(inputs)}/output.{ext}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['prodigal', '-i', str(inputs.get('input_fa', ''))]
        if inputs.get('input_train'):
            cmd.extend(['-t', str(inputs.get('input_train'))])
        cmd.extend(['-o', cls._coordinates_output(inputs), '-f', str(inputs.get('out_format', 'gbk') or 'gbk'), '-p', str(inputs.get('procedure', 'single') or 'single'), '-g', str(inputs.get('trans_table', '11') or '11'), '-a', f'{_out(inputs)}/output.faa', '-d', f'{_out(inputs)}/output.fnn', '-s', f'{_out(inputs)}/output.start'])
        if inputs.get('closed'):
            cmd.append('-c')
        if inputs.get('force_nonsd'):
            cmd.append('-n')
        if inputs.get('masked_seq'):
            cmd.append('-m')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        ext = cls.OUTPUT_FORMATS.get(str(inputs.get('out_format', 'gbk') or 'gbk'), 'gbk')
        return [out / f'output.{ext}', out / 'output.faa', out / 'output.fnn', out / 'output.start']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input_fa'):
            return 'input FASTA is required'
        out_format = str(inputs.get('out_format', 'gbk') or 'gbk')
        if out_format not in cls.OUTPUT_FORMATS:
            return 'out_format must be one of: gbk, gff, sqn, sco'
        procedure = str(inputs.get('procedure', 'single') or 'single')
        if procedure not in {'single', 'meta'}:
            return 'procedure must be one of: single, meta'
        trans_table = inputs.get('trans_table', '11') or '11'
        try:
            trans_table_int = int(trans_table)
        except (TypeError, ValueError):
            return 'trans_table must be an integer from 1 to 25'
        if not 1 <= trans_table_int <= 25:
            return 'trans_table must be an integer from 1 to 25'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fa': ('FASTA', {'description': 'Input microbial genome, assembly, or metagenomic FASTA'})}, 'optional': {'input_train': ('FASTA', {'default': '', 'description': 'Optional Prodigal training file'}), 'out_format': ('STRING', {'default': 'gbk', 'options': ['gbk', 'gff', 'sqn', 'sco'], 'description': 'Coordinates output format'}), 'procedure': ('STRING', {'default': 'single', 'options': ['single', 'meta'], 'description': 'Single-genome or metagenomic prediction mode'}), 'trans_table': ('STRING', {'default': '11', 'options': [str(value) for value in range(1, 26)], 'description': 'NCBI translation table'}), 'closed': ('BOOLEAN', {'default': False, 'description': 'Do not allow partial genes at sequence edges'}), 'force_nonsd': ('BOOLEAN', {'default': False, 'description': 'Scan for motifs instead of using the Shine-Dalgarno RBS finder'}), 'masked_seq': ('BOOLEAN', {'default': False, 'description': 'Treat runs of N as masked sequence'})}, 'hidden': {'output': ('STRING', {})}}
