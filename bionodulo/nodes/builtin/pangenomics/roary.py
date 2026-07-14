"""roary — pangenomics node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class RoaryNode(CommandNode):
    """Calculate prokaryotic pan-genomes and core gene alignments from GFF3 annotations."""
    NODE_ID = 'roary'
    DISPLAY_NAME = 'Roary'
    REQUIRED_CONDA_PACKAGES = ['roary']
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Quickly generate prokaryotic pan-genome gene clusters and core gene alignments from GFF3 annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Roary', 'roary', 'pan genome', 'pangenome', 'core gene alignment', 'gene presence absence', 'Prokka GFF3']
    RETURN_TYPES = ('TSV', 'FASTA', 'CSV', 'FASTA', 'FILE', 'FILE', 'FILE', 'TSV', 'TXT', 'TXT', 'FILE', 'FILE', 'TSV', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'FASTA')
    RETURN_NAMES = ('summary_statistics', 'core_gene_alignment', 'gene_presence_absence', 'accessory_binary_genes', 'accessory_binary_genes_newick', 'accessory_graph', 'accessory_header_embl', 'accessory_table', 'blast_identity_frequency', 'clustered_proteins', 'core_accessory_graph', 'core_accessory_embl', 'core_accessory_table', 'gene_presence_absence_rtab', 'number_of_conserved_genes', 'number_of_genes_in_pan_genome', 'number_of_new_genes', 'number_of_unique_genes', 'pan_genome_reference')
    REQUIRED_EXECUTABLES = ['roary']
    DOCUMENTATION_URL = f'{DOI_URL}{ROARY_CITATION_DOI}'
    CITATION_DOIS = [ROARY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ROARY_CITATION_DOI}']
    CITATION_TEXT = ROARY_CITATION_TEXT
    VERSION = '3.13.0+galaxy3'
    SHELL = True
    GFF_INPUT_OPTIONS = ['individual', 'collection']
    OUTPUT_OPTIONS = ['abg_nw', 'abg_fa', 'accgraph', 'acchead_embl', 'acctab', 'blastfreq', 'clust', 'coreaccgraph', 'coreaccembl', 'coreacctab', 'genepa_rtab', 'numcons_rtab', 'numpangene_rtab', 'numnew_rtab', 'numuniq_rtab', 'pangenomeref']
    OUTPUT_FILE_ORDER = ['abg_fa', 'abg_nw', 'accgraph', 'acchead_embl', 'acctab', 'blastfreq', 'clust', 'coreaccgraph', 'coreaccembl', 'coreacctab', 'genepa_rtab', 'numcons_rtab', 'numpangene_rtab', 'numnew_rtab', 'numuniq_rtab', 'pangenomeref']
    TRANS_TAB_OPTIONS = [1, 4, 11]
    OPTIONAL_OUTPUT_PATHS = {'abg_fa': 'accessory_binary_genes.fa', 'abg_nw': 'accessory_binary_genes.fa.newick', 'accgraph': 'accessory_graph.dot', 'acchead_embl': 'accessory.header.embl', 'acctab': 'accessory.tab', 'blastfreq': 'blast_identity_frequency.Rtab', 'clust': 'clustered_proteins', 'coreaccgraph': 'core_accessory_graph.dot', 'coreaccembl': 'core_accessory.header.embl', 'coreacctab': 'core_accessory.tab', 'genepa_rtab': 'gene_presence_absence.Rtab', 'numcons_rtab': 'number_of_conserved_genes.Rtab', 'numpangene_rtab': 'number_of_genes_in_pan_genome.Rtab', 'numnew_rtab': 'number_of_new_genes.Rtab', 'numuniq_rtab': 'number_of_unique_genes.Rtab', 'pangenomeref': 'pan_genome_reference.fa'}

    @staticmethod
    def _staged_gff_name(path: str) -> str:
        stem = Path(path).stem or 'input'
        sanitized = sub('[^\\w_-]', '_', stem)
        return f'{sanitized}.gff'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_names: list[str] = []
        commands: list[str] = []
        for gff in _as_list(inputs.get('gffs')):
            staged_name = cls._staged_gff_name(gff)
            commands.append(_shell_join(['cp', gff, staged_name]))
            staged_names.append(staged_name)
        roary_cmd = ['roary', '-f', f'{_out(inputs)}/out', '-p', '${GALAXY_SLOTS:-1}', '-e', '-z', '-n', '-i', str(inputs.get('percent_ident', 95)), '-cd', str(inputs.get('core_diff', 99.0)), '-g', str(inputs.get('maxclust', 50000))]
        if inputs.get('split_para'):
            roary_cmd.append('-s')
        roary_cmd.extend(['-t', str(inputs.get('trans_tab', 11)), '-iv', str(inputs.get('mcl', 1.5)), *staged_names])
        commands.append(_shell_join(roary_cmd).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}'))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'summary_statistics.txt', out / 'core_gene_alignment.aln', out / 'gene_presence_absence.csv']
        requested_outputs = _as_list(inputs.get('outputs'))
        for option in cls.OUTPUT_FILE_ORDER:
            if option in requested_outputs:
                outputs.append(out / cls.OPTIONAL_OUTPUT_PATHS[option])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if len(_as_list(inputs.get('gffs'))) < 2:
            return 'at least two gffs are required'
        gff_input_selector = str(inputs.get('gff_input_selector', 'individual'))
        if gff_input_selector not in cls.GFF_INPUT_OPTIONS:
            return f"gff_input_selector must be one of: {', '.join(cls.GFF_INPUT_OPTIONS)}"
        unsupported_outputs = [value for value in _as_list(inputs.get('outputs')) if value not in cls.OUTPUT_OPTIONS]
        if unsupported_outputs:
            return f"outputs contains unsupported values: {', '.join(unsupported_outputs)}"
        percent_ident = int(inputs.get('percent_ident', 95))
        if percent_ident < 1 or percent_ident > 100:
            return 'percent_ident must be between 1 and 100'
        core_diff = float(inputs.get('core_diff', 99.0))
        if core_diff < 0 or core_diff > 100:
            return 'core_diff must be between 0 and 100'
        maxclust = int(inputs.get('maxclust', 50000))
        if maxclust < 1:
            return 'maxclust must be >= 1'
        trans_tab = int(inputs.get('trans_tab', 11))
        if trans_tab not in cls.TRANS_TAB_OPTIONS:
            return 'trans_tab must be one of: 1, 4, 11'
        mcl = float(inputs.get('mcl', 1.5))
        if mcl <= 0:
            return 'mcl must be > 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gffs': ('GFF', {'multiple': True, 'min_items': 2, 'description': 'Two or more Prokka-style GFF3 annotation files for Roary'})}, 'optional': {'gff_input_selector': ('STRING', {'default': 'individual', 'options': cls.GFF_INPUT_OPTIONS}), 'percent_ident': ('INT', {'default': 95, 'min': 1, 'max': 100, 'description': 'Minimum blastp percent identity'}), 'core_diff': ('FLOAT', {'default': 99.0, 'min': 0, 'max': 100, 'description': 'Percentage of isolates required for a gene to be core'}), 'outputs': ('STRING', {'default': [], 'multiple': True, 'options': cls.OUTPUT_OPTIONS, 'description': 'Additional Roary output files to collect'}), 'maxclust': ('INT', {'default': 50000, 'min': 1, 'advanced': True}), 'split_para': ('BOOLEAN', {'default': False, 'description': 'Do not split paralogs', 'advanced': True}), 'trans_tab': ('INT', {'default': 11, 'options': cls.TRANS_TAB_OPTIONS, 'advanced': True}), 'mcl': ('FLOAT', {'default': 1.5, 'min': 0, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
