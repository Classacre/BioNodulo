"""busco — assembly node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BUSCONode(CommandNode):
    """Assess genome, transcriptome, or proteome completeness with BUSCO."""
    NODE_ID = 'busco'
    DISPLAY_NAME = 'BUSCO'
    REQUIRED_CONDA_PACKAGES = ['busco']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Assess assembly or annotation completeness using BUSCO lineage orthologs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'busco', 'completeness', 'orthologs', 'assembly qc', 'annotation qc']
    RETURN_TYPES = ('STATS_FILE', 'TSV', 'TSV', 'IMAGE')
    RETURN_NAMES = ('short_summary', 'full_table', 'missing_buscos', 'summary_image')
    REQUIRED_EXECUTABLES = ['busco']
    DOCUMENTATION_URL = 'https://busco.ezlab.org/'
    CITATION_DOIS = ['10.1093/bioinformatics/btv351']
    CITATION_URLS = ['https://doi.org/10.1093/bioinformatics/btv351']
    CITATION_TEXT = 'BUSCO: assessing genome assembly and annotation completeness with single-copy orthologs.'
    VERSION = '5.8.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        mode = str(inputs.get('mode', 'genome'))
        mode_aliases = {'genome': 'genome', 'geno': 'genome', 'transcriptome': 'transcriptome', 'tran': 'transcriptome', 'proteins': 'proteins', 'prot': 'proteins'}
        galaxy_mode = mode_aliases.get(mode, mode)
        cmd = ['busco', '--in', str(inputs.get('input', '')), '--mode', galaxy_mode, '--out', 'busco_galaxy', '--out_path', _out(inputs), '--cpu', str(inputs.get('threads', 4)), '--evalue', str(inputs.get('evalue', 0.001)), '--limit', str(inputs.get('limit', 3)), '--contig_break', str(inputs.get('contig_break', 10))]
        if inputs.get('offline', True):
            cmd.append('--offline')
        _add_if_value(cmd, '--download_path', inputs.get('download_path'))
        lineage_mode = str(inputs.get('lineage_mode', 'select_lineage'))
        if lineage_mode == 'auto_detect':
            cmd.append(str(inputs.get('auto_lineage', '--auto-lineage')))
        else:
            _add_if_value(cmd, '--lineage_dataset', inputs.get('lineage_dataset'))
        predictor = str(inputs.get('gene_predictor', 'miniprot'))
        if galaxy_mode == 'genome' and predictor in {'miniprot', 'augustus', 'metaeuk'}:
            cmd.append(f'--{predictor}')
        _add_if_value(cmd, '--augustus_species', inputs.get('augustus_species'))
        if inputs.get('long'):
            cmd.append('--long')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'short_summary.txt', out / 'full_table.tsv', out / 'missing_buscos.tsv', out / 'summary.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Assembly, transcriptome, or protein FASTA to analyse'}), 'mode': ('STRING', {'default': 'genome', 'options': ['genome', 'transcriptome', 'proteins']}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'optional': {'lineage_mode': ('STRING', {'default': 'select_lineage', 'options': ['select_lineage', 'auto_detect']}), 'lineage_dataset': ('STRING', {'default': 'bacteria_odb10', 'description': 'BUSCO lineage dataset such as bacteria_odb10'}), 'auto_lineage': ('STRING', {'default': '--auto-lineage', 'options': ['--auto-lineage', '--auto-lineage-prok', '--auto-lineage-euk']}), 'gene_predictor': ('STRING', {'default': 'miniprot', 'options': ['miniprot', 'augustus', 'metaeuk'], 'advanced': True}), 'augustus_species': ('STRING', {'default': '', 'advanced': True}), 'download_path': ('DIRECTORY', {'description': 'Cached BUSCO download directory', 'advanced': True}), 'offline': ('BOOLEAN', {'default': True, 'advanced': True}), 'evalue': ('FLOAT', {'default': 0.001, 'min': 0, 'max': 1, 'advanced': True}), 'limit': ('INT', {'default': 3, 'min': 1, 'advanced': True}), 'contig_break': ('INT', {'default': 10, 'min': 1, 'advanced': True}), 'long': ('BOOLEAN', {'default': False, 'description': 'Enable Augustus self-training optimization', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
