"""taxpasta — taxonomy node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TaxpastaNode(CommandNode):
    """Standardise and merge taxonomic profiler reports with Taxpasta."""
    NODE_ID = 'taxpasta'
    DISPLAY_NAME = 'Taxpasta'
    REQUIRED_CONDA_PACKAGES = ['taxpasta']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Standardise and merge taxonomic profiles from common metagenomic profilers.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'taxpasta', 'taxonomic profile standardisation', 'taxonomy aggregation', 'BIOM', 'Kraken2 report', 'MetaPhlAn', 'DIAMOND taxonomy']
    RETURN_TYPES = ('TSV', 'BIOM')
    RETURN_NAMES = ('tabular_output', 'biom_output')
    REQUIRED_EXECUTABLES = ['taxpasta']
    DOCUMENTATION_URL = 'https://taxpasta.readthedocs.io/en/latest/'
    CITATION_DOIS = [TAXPASTA_DOI]
    CITATION_URLS = [f'{DOI_URL}{TAXPASTA_DOI}']
    CITATION_TEXT = TAXPASTA_CITATION_TEXT
    VERSION = '0.7.0'
    SHELL = True
    PROFILERS = ['bracken', 'Centrifuge', 'diamond', 'ganon', 'kaiju', 'kraken2', 'krakenuniq', 'megan6', 'metaphlan', 'motus']

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('action', 'standardise')) == 'merge':
            return str(inputs.get('output_format', 'TSV'))
        return 'TSV'

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return 'biom_output.biom' if cls._output_format(inputs) == 'BIOM' else 'tabular_output.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        action = str(inputs.get('action', 'standardise'))
        output_format = cls._output_format(inputs)
        cmd = ['taxpasta', action, '--profiler', str(inputs.get('profiler', '')), '--taxonomy', str(inputs.get('taxonomy', '')), '--output-format', output_format, '--output', f'{out}/{cls._output_filename(inputs)}']
        if action == 'merge' and output_format == 'TSV':
            cmd.append('--wide' if inputs.get('wide', True) else '--long')
        for input_name, flag in (('add_name', '--add-name'), ('add_rank', '--add-rank'), ('add_lineage', '--add-lineage'), ('add_id_lineage', '--add-id-lineage'), ('add_rank_lineage', '--add-rank-lineage')):
            default = input_name == 'add_name'
            if inputs.get(input_name, default):
                cmd.append(flag)
        cmd.extend(_as_list(inputs.get('infile')))
        return shlex.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get('infile')):
            return 'At least one Taxpasta input report is required'
        if not inputs.get('profiler'):
            return 'Taxpasta profiler is required'
        if not inputs.get('taxonomy'):
            return 'NCBI taxonomy directory is required'
        output_format = str(inputs.get('output_format', 'TSV'))
        if output_format not in {'TSV', 'BIOM'}:
            return f'Unsupported Taxpasta output format: {output_format}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'action': ('STRING', {'default': 'standardise', 'options': ['standardise', 'merge'], 'description': 'Taxpasta action matching the Galaxy wrapper'}), 'profiler': ('STRING', {'default': 'kraken2', 'options': cls.PROFILERS, 'description': 'Profiler that produced the input taxonomic report'}), 'infile': ('TSV', {'multiple': True, 'description': 'One or more taxonomic reports from the same profiler'}), 'taxonomy': ('DIRECTORY', {'description': 'NCBI taxonomy directory containing nodes.dmp and names.dmp'})}, 'optional': {'output_format': ('STRING', {'default': 'TSV', 'options': ['TSV', 'BIOM'], 'description': 'Desired output format when merging profiles', 'displayOptions': {'show': {'action': ['merge']}}}), 'wide': ('BOOLEAN', {'default': True, 'description': 'Output merged TSV abundance data in wide format instead of long format', 'displayOptions': {'show': {'action': ['merge'], 'output_format': ['TSV']}}}), 'add_name': ('BOOLEAN', {'default': True, 'description': 'Add taxon names to the output'}), 'add_rank': ('BOOLEAN', {'default': False, 'description': 'Add taxon ranks to the output'}), 'add_lineage': ('BOOLEAN', {'default': False, 'description': 'Add semicolon-separated taxon name lineages'}), 'add_id_lineage': ('BOOLEAN', {'default': False, 'description': 'Add semicolon-separated taxon identifier lineages'}), 'add_rank_lineage': ('BOOLEAN', {'default': False, 'description': 'Add semicolon-separated taxon rank lineages'})}, 'hidden': {'output': ('STRING', {})}}
