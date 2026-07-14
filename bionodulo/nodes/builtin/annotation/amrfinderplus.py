"""amrfinderplus — annotation node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AMRFinderPlusNode(CommandNode):
    """Find AMR genes, point mutations, and plus genes with NCBI AMRFinderPlus."""
    NODE_ID = 'amrfinderplus'
    DISPLAY_NAME = 'AMRFinderPlus'
    REQUIRED_CONDA_PACKAGES = ['ncbi-amrfinderplus']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Find acquired antimicrobial resistance genes, point mutations, stress response, biocide, and virulence genes in nucleotide and/or protein sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'amrfinder', 'amrfinderplus', 'NCBI AMRFinderPlus', 'antimicrobial resistance', 'AMR genes', 'point mutations', 'virulence genes']
    RETURN_TYPES = ('TSV', 'TSV', 'FASTA', 'FASTA', 'FASTA')
    RETURN_NAMES = ('amrfinderplus_report', 'mutation_all_report', 'protein_output', 'nucleotide_output', 'nucleotide_flank5_output')
    REQUIRED_EXECUTABLES = ['amrfinder']
    DOCUMENTATION_URL = 'https://github.com/ncbi/amr/wiki'
    CITATION_DOIS = ['10.1038/s41598-021-91456-0']
    CITATION_URLS = ['https://doi.org/10.1038/s41598-021-91456-0']
    CITATION_TEXT = 'AMRFinderPlus and the Reference Gene Catalog facilitate examination of the genomic links among antimicrobial resistance, stress response, and virulence.'
    VERSION = '4.2.7'
    SHELL = True

    @classmethod
    def _report_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _has_organism(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get('organism_select', '')) == 'add_organism' or bool(inputs.get('organism'))

    @classmethod
    def _flank5_size(cls, inputs: dict[str, Any]) -> int:
        try:
            return int(inputs.get('nucleotide_flank5_size', 0) or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _add_nucleotide_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--nucleotide', str(inputs.get('nucleotide_input', ''))])
        if cls._flank5_size(inputs) > 0:
            cmd.extend(['--nucleotide_flank5_size', str(cls._flank5_size(inputs)), '--nucleotide_flank5_output', cls._report_path(inputs, 'amrfinderplus_flanking_sequence_output.fasta')])
        cmd.extend(['--nucleotide_output', cls._report_path(inputs, 'amrfinderplus_nucleotide_output.fasta')])

    @classmethod
    def _add_protein_inputs(cls, cmd: list[str], inputs: dict[str, Any], *, require_annotation: bool=False) -> None:
        cmd.extend(['--protein', str(inputs.get('protein_input', ''))])
        gff = inputs.get('gff_annotation')
        if require_annotation or gff:
            cmd.extend(['--gff', str(gff or '')])
        annotation_format = inputs.get('annotation_format')
        if require_annotation or annotation_format:
            cmd.extend(['--annotation_format', str(annotation_format or 'genbank')])
        cmd.extend(['--protein_output', cls._report_path(inputs, 'amrfinderplus_protein_output.fasta')])

    @classmethod
    def _add_version_columns_command(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        database = str(inputs.get('database', ''))
        database_name = str(inputs.get('database_name', Path(database).name or 'amrfinderplus_database'))
        report_path = cls._report_path(inputs, 'amrfinderplus_report.tsv')
        mutation_path = cls._report_path(inputs, 'mutation_all_report.tsv')
        script = f"from pathlib import Path\ntool_version = '{cls.VERSION}'\ndatabase = Path('{database}')\ndatabase_version = (database / 'version.txt').read_text().strip() if (database / 'version.txt').is_file() else '{database_name}'\nfor report in [Path('{report_path}'), Path('{mutation_path}')]:\n    if not report.is_file() or report.stat().st_size == 0:\n        continue\n    lines = report.read_text().splitlines()\n    if not lines:\n        continue\n    updated = [lines[0] + '\\tDatabase version\\tTool version']\n    updated.extend(line + '\\t' + database_version + '\\t' + tool_version for line in lines[1:])\n    report.write_text('\\n'.join(updated) + '\\n')\n"
        cmd.extend(['&&', 'python', '-c', script])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['amrfinder', '--threads', str(inputs.get('threads', 1)), '--database', str(inputs.get('database', ''))]
        input_select = str(inputs.get('input_select', 'nucleotide'))
        if input_select == 'protein':
            cls._add_protein_inputs(cmd, inputs)
        elif input_select == 'nucl_prot':
            cmd.extend(['--nucleotide', str(inputs.get('nucleotide_input', ''))])
            if cls._flank5_size(inputs) > 0:
                cmd.extend(['--nucleotide_flank5_size', str(cls._flank5_size(inputs)), '--nucleotide_flank5_output', cls._report_path(inputs, 'amrfinderplus_flanking_sequence_output.fasta')])
            cmd.extend(['--protein', str(inputs.get('protein_input', '')), '--gff', str(inputs.get('gff_annotation', '')), '--annotation_format', str(inputs.get('annotation_format', 'genbank')), '--nucleotide_output', cls._report_path(inputs, 'amrfinderplus_nucleotide_output.fasta'), '--protein_output', cls._report_path(inputs, 'amrfinderplus_protein_output.fasta')])
        else:
            cls._add_nucleotide_inputs(cmd, inputs)
        if cls._has_organism(inputs):
            cmd.extend(['--organism', str(inputs.get('organism', ''))])
            if inputs.get('mutation_all'):
                cmd.extend(['--mutation_all', cls._report_path(inputs, 'mutation_all_report.tsv')])
            if inputs.get('plus') and inputs.get('report_common'):
                cmd.append('--report_common')
        cmd.extend(['--ident_min', str(inputs.get('ident_min', -1))])
        cmd.extend(['--coverage_min', str(inputs.get('coverage_min', 0.5))])
        _add_if_value(cmd, '--translation_table', inputs.get('translation_table'))
        _add_if_value(cmd, '--name', inputs.get('name'))
        for key, flag in (('plus', '--plus'), ('report_all_equal', '--report_all_equal'), ('print_node', '--print_node')):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(['--output', cls._report_path(inputs, 'amrfinderplus_report.tsv')])
        if inputs.get('add_version_columns'):
            cls._add_version_columns_command(cmd, inputs)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        input_select = str(inputs.get('input_select', 'nucleotide'))
        outputs = [_amrfinderplus_out(output_dir, 'amrfinderplus_report.tsv')]
        if cls._has_organism(inputs) and inputs.get('mutation_all'):
            outputs.append(_amrfinderplus_out(output_dir, 'mutation_all_report.tsv'))
        if input_select in {'protein', 'nucl_prot'}:
            outputs.append(_amrfinderplus_out(output_dir, 'amrfinderplus_protein_output.fasta'))
        if input_select in {'nucleotide', 'nucl_prot'}:
            outputs.append(_amrfinderplus_out(output_dir, 'amrfinderplus_nucleotide_output.fasta'))
        if input_select in {'nucleotide', 'nucl_prot'} and cls._flank5_size(inputs) > 0:
            outputs.append(_amrfinderplus_out(output_dir, 'amrfinderplus_flanking_sequence_output.fasta'))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'database': ('DIRECTORY', {'description': "AMRFinderPlus database directory, matching Galaxy's amrfinderplus versioned database"}), 'input_select': ('STRING', {'default': 'nucleotide', 'options': ['nucleotide', 'protein', 'nucl_prot'], 'description': 'Analyze nucleotide, protein, or paired nucleotide and protein files'})}, 'optional': {'nucleotide_input': ('FASTA', {'default': '', 'description': 'Input nucleotide sequence file'}), 'protein_input': ('FASTA', {'default': '', 'description': 'Input protein sequence file'}), 'gff_annotation': ('GFF', {'default': '', 'description': 'GFF3 annotation file for protein locations'}), 'annotation_format': ('STRING', {'default': 'genbank', 'options': AMRFINDERPLUS_ANNOTATION_FORMATS, 'description': 'Annotation format such as bakta, prokka, rast, or genbank'}), 'nucleotide_flank5_size': ('INT', {'default': 0, 'min': 0, 'description': "5' flanking sequence size added to nucleotide matches"}), 'organism_select': ('STRING', {'default': '', 'options': ['', 'add_organism'], 'description': 'Enable organism-specific point mutation screening'}), 'organism': ('STRING', {'default': '', 'options': AMRFINDERPLUS_ORGANISMS, 'description': 'Taxonomic group for point mutation screening'}), 'mutation_all': ('BOOLEAN', {'default': False, 'description': 'Report genotypes at all screened point mutation locations'}), 'report_common': ('BOOLEAN', {'default': False, 'description': 'Report proteins common to the taxonomy group when plus and organism options are enabled'}), 'ident_min': ('FLOAT', {'default': -1, 'min': -1, 'max': 1, 'description': 'Minimum amino acid identity; -1 uses curated thresholds'}), 'coverage_min': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Minimum coverage of the reference protein'}), 'translation_table': ('STRING', {'default': '11', 'options': AMRFINDERPLUS_TRANSLATION_TABLES, 'description': 'NCBI genetic code for translated BLAST'}), 'plus': ('BOOLEAN', {'default': False, 'description': 'Include stress response, biocide, virulence, and other plus genes'}), 'report_all_equal': ('BOOLEAN', {'default': False, 'description': 'Report all equally scoring BLAST and HMM matches'}), 'print_node': ('BOOLEAN', {'default': False, 'description': 'Print hierarchy node or family'}), 'name': ('STRING', {'default': '', 'description': "Value to add as the report's first-column sample name"}), 'add_version_columns': ('BOOLEAN', {'default': False, 'description': 'Append database and tool version columns to tabular reports'}), 'database_name': ('STRING', {'default': '', 'description': 'Fallback database label when database/version.txt is unavailable', 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
