"""humann — metagenomics node(s). One tool per file (extracted from metagenomics.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode, _shell_join
DOI_URL = 'https://doi.org/'
METAPHLAN_DOI = '10.1038/s41587-023-01688-w'
METAPHLAN_CITATION_TEXT = 'Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4.'
HUMANN_CITATION_DOIS = ['10.7554/eLife.65088', '10.1371/journal.pcbi.1002358']
HUMANN_CITATION_TEXT = "bioBakery 3: a platform for analyzing meta'omic datasets; HUMAnN: the HMP Unified Metabolic Analysis Network."
KRAKEN2_CITATION_DOI = '10.1186/gb-2014-15-3-r46'
KRAKEN2_CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
BRACKEN_CITATION_DOI = '10.7717/peerj-cs.104'
BRACKEN_CITATION_TEXT = 'Bracken: estimating species abundance in metagenomics data.'
def _as_list(value: Any) -> list[str]:
    if value is None or value == '':
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != '']
    return [str(value)]
def _add_shell_redirect(cmd: list[str], output_path: str) -> None:
    cmd.extend(['>', output_path])
def _shell_join_allow_substitution(cmd: list[str]) -> str:
    parts: list[str] = []
    for token in cmd:
        parts.append(token if token.startswith('$(') else _shell_join([token]))
    return ' '.join(parts)


class HUMAnNNode(CommandNode):
    """Functional profiling with HUMAnN."""
    NODE_ID = 'humann'
    DISPLAY_NAME = 'HUMAnN'
    REQUIRED_CONDA_PACKAGES = ['humann']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Profile microbial pathway and gene-family abundance with HUMAnN 3.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'HUMAnN', 'functional profiling', 'pathway abundance', 'gene families', 'ChocoPhlAn', 'UniRef', 'intermediate output files']
    RETURN_TYPES = ('HUMANN_OUTPUT', 'TSV', 'TSV', 'TSV', 'BIOM', 'BIOM', 'BIOM', 'TXT', 'TSV', 'TSV', 'SAM', 'TSV', 'FASTA', 'FASTA', 'TSV', 'FASTA')
    RETURN_NAMES = ('output_dir', 'genefamilies', 'pathabundance', 'pathcoverage', 'genefamilies_biom', 'pathabundance_biom', 'pathcoverage_biom', 'log', 'metaphlan_bowtie2', 'metaphlan_bugs_list', 'bowtie2_alignment', 'bowtie2_reduced_alignment', 'bowtie2_unaligned', 'custom_chocophlan_database', 'diamond_aligned', 'diamond_unaligned')
    REQUIRED_EXECUTABLES = ['humann']
    DOCUMENTATION_URL = 'https://huttenhower.sph.harvard.edu/humann/'
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = '3.9'
    SHELL = True
    _WORKFLOWS_WITH_PRESCREEN = {'none', 'bypass_translated_search'}
    _WORKFLOWS_WITH_NUCLEOTIDE = {'none', 'bypass_prescreen', 'bypass_taxonomic_profiling', 'bypass_nucleotide_index', 'bypass_translated_search'}
    _WORKFLOWS_WITH_TRANSLATED = {'none', 'bypass_prescreen', 'bypass_taxonomic_profiling', 'bypass_nucleotide_index', 'bypass_nucleotide_search'}

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output', '.'))

    @classmethod
    def _output_basename(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output_basename', 'humann') or 'humann')

    @classmethod
    def _output_dir_path(cls, out: str) -> str:
        return f'{out}/output'

    @classmethod
    def _log_path(cls, out: str) -> str:
        return f'{out}/humann.log'

    @classmethod
    def _customizemetadata_script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('customizemetadata_script', 'customizemetadata.py'))

    @classmethod
    def _first_read(cls, reads: Any) -> str:
        if isinstance(reads, (list, tuple)) and reads:
            return str(reads[0])
        return str(reads or '')

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_selector = str(inputs.get('input_selector', 'raw'))
        input_ext = str(inputs.get('input_ext', '')).lower()
        read = cls._first_read(inputs.get('reads', inputs.get('input', ''))).lower()
        probe = input_ext or read
        if input_selector == 'abundance':
            return 'biom' if 'biom' in probe else 'genetable'
        if input_selector == 'mapping':
            return 'bam' if probe.endswith('bam') else 'sam'
        if probe.endswith(('fastq.gz', 'fq.gz')):
            return 'fastq.gz'
        if probe.endswith(('fasta.gz', 'fa.gz', 'fna.gz')):
            return 'fasta.gz'
        if probe.endswith(('fasta', 'fa', 'fna')):
            return 'fasta'
        return 'fastq'

    @classmethod
    def _safe_humann_label(cls, value: str) -> str:
        return ''.join((char if char.isalnum() or char in {'_', '-', '.'} else '_' for char in value))

    @classmethod
    def _nucleotide_labels(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        names = _as_list(inputs.get('nucleotide_database_names'))
        if len(names) == len(files):
            return [cls._safe_humann_label(name) for name in names]
        labels: list[str] = []
        for file in files:
            name = Path(file).name
            for suffix in ('.fasta.gz', '.fa.gz', '.ffn.gz', '.fasta', '.fa', '.ffn', '.gz'):
                if name.lower().endswith(suffix):
                    name = name[:-len(suffix)]
                    break
            labels.append(cls._safe_humann_label(name))
        return labels

    @classmethod
    def _prepare_prescreen(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if str(inputs.get('metaphlan_db_selector', 'cached')) == 'history':
            setup = [_shell_join(['mkdir', 'metaphlan_db']), shlex.join(['bowtie2-build', '--large-index', str(inputs.get('metaphlan_bowtie2db', '')), 'metaphlan_db/custom_db-v30']), shlex.join(['python', cls._customizemetadata_script(inputs), 'transform_json_to_pkl', '--json', str(inputs.get('metaphlan_mpa_pkl', '')), '--pkl', 'metaphlan_db/custom_db-v30.pkl'])]
            metaphlan_option = '-t rel_ab --bowtie2db metaphlan_db/ --index custom_db-v30'
        else:
            db_path = str(inputs.get('metaphlan_db', inputs.get('metaphlan_cached_db', '')))
            db_index = str(inputs.get('metaphlan_index', inputs.get('metaphlan_dbkey', '')))
            metaphlan_option = f'-t rel_ab --bowtie2db {db_path}'
            if db_index:
                metaphlan_option += f' --index {db_index}'
            setup = []
        args = ['--metaphlan-options', metaphlan_option, '--prescreen-threshold', str(inputs.get('prescreen_threshold', 0.01))]
        return (setup, args)

    @classmethod
    def _prepare_nucleotide(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if str(inputs.get('nucleotide_db_selector', 'cached')) == 'history':
            files = _as_list(inputs.get('nucleotide_database'))
            labels = cls._nucleotide_labels(inputs, files)
            setup = [_shell_join(['mkdir', 'nucleotide_db'])]
            setup.extend((shlex.join(['ln', '-s', file, f'nucleotide_db/{label}.v201901_v31']) for file, label in zip(files, labels, strict=False)))
            db_path = 'nucleotide_db'
        else:
            db_path = str(inputs.get('nuc_db', inputs.get('nucleotide_database', '')))
            setup = []
        args = ['--nucleotide-database', db_path, '--nucleotide-identity-threshold', str(inputs.get('nucleotide_identity_threshold', 0)), '--nucleotide-subject-coverage-threshold', str(inputs.get('nucleotide_subject_coverage_threshold', 50)), '--nucleotide-query-coverage-threshold', str(inputs.get('nucleotide_query_coverage_threshold', 90))]
        return (setup, args)

    @classmethod
    def _search_mode(cls, inputs: dict[str, Any], database: str) -> str:
        if inputs.get('search_mode'):
            return str(inputs['search_mode'])
        return 'uniref50' if 'uniref50' in database.lower() else 'uniref90'

    @classmethod
    def _prepare_translated(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        setup: list[str] = []
        if str(inputs.get('protein_db_selector', 'cached')) == 'history':
            protein_database = str(inputs.get('protein_database', ''))
            setup = [_shell_join(['mkdir', 'protein_db']), shlex.join(['diamond', 'makedb', '--in', protein_database, '--db', 'protein_db/protein-db-201901b', '--threads', str(inputs.get('threads', 4))])]
            db_path = 'protein_db'
        else:
            db_path = str(inputs.get('prot_db', inputs.get('protein_database', '')))
        args = ['--translated-alignment', str(inputs.get('translated_alignment', 'diamond')), '--protein-database', db_path, '--search-mode', cls._search_mode(inputs, db_path), '--evalue', str(inputs.get('evalue', 1))]
        if inputs.get('translated_identity_threshold') not in (None, ''):
            args.extend(['--identity-threshold', str(inputs['translated_identity_threshold'])])
        args.extend(['--translated-subject-coverage-threshold', str(inputs.get('translated_subject_coverage_threshold', 50)), '--translated-query-coverage-threshold', str(inputs.get('translated_query_coverage_threshold', 90))])
        return (setup, args)

    @classmethod
    def _boolean_on_off(cls, inputs: dict[str, Any], name: str, default: bool) -> str:
        return 'on' if bool(inputs.get(name, default)) else 'off'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        reads = cls._first_read(inputs.get('reads', inputs.get('input', '')))
        workflow = str(inputs.get('workflow_selector', 'none'))
        input_selector = str(inputs.get('input_selector', 'raw'))
        out = cls._out(inputs)
        setup_commands: list[str] = []
        workflow_args: list[str] = []
        if input_selector != 'abundance':
            if workflow == 'bypass_prescreen':
                workflow_args.append('--bypass-prescreen')
            elif workflow == 'bypass_taxonomic_profiling':
                workflow_args.extend(['--taxonomic-profile', str(inputs.get('taxonomic_profile', ''))])
            elif workflow == 'bypass_nucleotide_index':
                workflow_args.append('--bypass-nucleotide-index')
            elif workflow == 'bypass_nucleotide_search':
                workflow_args.append('--bypass-nucleotide-search')
            elif workflow == 'bypass_translated_search':
                workflow_args.append('--bypass-translated-search')
            if workflow in cls._WORKFLOWS_WITH_PRESCREEN:
                setup, args = cls._prepare_prescreen(inputs)
                setup_commands.extend(setup)
                workflow_args.extend(args)
            if workflow in cls._WORKFLOWS_WITH_NUCLEOTIDE:
                setup, args = cls._prepare_nucleotide(inputs)
                setup_commands.extend(setup)
                workflow_args.extend(args)
            if workflow in cls._WORKFLOWS_WITH_TRANSLATED:
                setup, args = cls._prepare_translated(inputs)
                setup_commands.extend(setup)
                workflow_args.extend(args)
        cmd = ['humann', '--input', reads, '--input-format', cls._input_format(inputs), '-o', cls._output_dir_path(out)]
        cmd.extend(workflow_args)
        cmd.extend(['--gap-fill', cls._boolean_on_off(inputs, 'gap_fill', True), '--minpath', cls._boolean_on_off(inputs, 'minpath', True), '--pathways', str(inputs.get('pathways', 'metacyc')), '--xipe', cls._boolean_on_off(inputs, 'xipe', False), '--annotation-gene-index', str(inputs.get('annotation_gene_index', 3))])
        if inputs.get('id_mapping'):
            cmd.extend(['--id-mapping', str(inputs['id_mapping'])])
        cmd.extend(['--log-level', 'DEBUG', '--o-log', cls._log_path(out), '--output-basename', cls._output_basename(inputs), '--output-format', str(inputs.get('output_format', 'tsv')), '--output-max-decimals', str(inputs.get('output_max_decimals', 10))])
        if inputs.get('remove_column_description_output'):
            cmd.append('--remove-column-description-output')
        if inputs.get('remove_stratified_output'):
            cmd.append('--remove-stratified-output')
        cmd.extend(['--threads', str(inputs.get('threads', 8)), '--memory-use', str(inputs.get('memory_use', 'minimum'))])
        return ' && '.join([*setup_commands, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        output_path = node_out / 'output'
        output_path.mkdir(parents=True, exist_ok=True)
        basename = cls._output_basename(inputs)
        output_format = str(inputs.get('output_format', 'tsv'))
        suffix = 'biom' if output_format == 'biom' else 'tsv'
        abundance_input = str(inputs.get('input_selector', 'raw')) == 'abundance'
        outputs = [output_path]
        if not abundance_input:
            outputs.append(output_path / f'{basename}_genefamilies.{suffix}')
        outputs.extend([output_path / f'{basename}_pathabundance.{suffix}', output_path / f'{basename}_pathcoverage.{suffix}', node_out / 'humann.log'])
        temp_dir = output_path / f'{basename}_temp'
        intermediate_outputs = {'metaphlan_bowtie2': temp_dir / f'{basename}_metaphlan_bowtie2.txt', 'metaphlan_bugs_list': temp_dir / f'{basename}_metaphlan_bugs_list.tsv', 'bowtie2_alignment': temp_dir / f'{basename}_bowtie2_aligned.sam', 'bowtie2_reduced_alignment': temp_dir / f'{basename}_bowtie2_aligned.tsv', 'bowtie2_unaligned': temp_dir / f'{basename}_bowtie2_unaligned.fa', 'custom_chocophlan_database': temp_dir / f'{basename}_custom_chocophlan_database.ffn', 'diamond_aligned': temp_dir / f'{basename}_diamond_aligned.tsv', 'diamond_unaligned': temp_dir / f'{basename}_diamond_unaligned.fa'}
        for name in _as_list(inputs.get('intermediate_temp')):
            if name in intermediate_outputs:
                outputs.append(intermediate_outputs[name])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reads = cls._first_read(inputs.get('reads', inputs.get('input', '')))
        if not reads:
            return 'reads is required'
        workflow = str(inputs.get('workflow_selector', 'none'))
        input_selector = str(inputs.get('input_selector', 'raw'))
        if input_selector == 'abundance':
            return True
        if workflow in cls._WORKFLOWS_WITH_PRESCREEN and str(inputs.get('metaphlan_db_selector', 'cached')) == 'history':
            if not inputs.get('metaphlan_bowtie2db'):
                return 'metaphlan_bowtie2db is required when metaphlan_db_selector is history'
            if not inputs.get('metaphlan_mpa_pkl'):
                return 'metaphlan_mpa_pkl is required when metaphlan_db_selector is history'
        if workflow in cls._WORKFLOWS_WITH_NUCLEOTIDE:
            if str(inputs.get('nucleotide_db_selector', 'cached')) == 'history':
                if not _as_list(inputs.get('nucleotide_database')):
                    return 'nucleotide_database is required when nucleotide_db_selector is history'
            elif not inputs.get('nuc_db') and (not inputs.get('nucleotide_database')):
                return 'nuc_db is required when nucleotide_db_selector is cached'
        if workflow in cls._WORKFLOWS_WITH_TRANSLATED:
            if str(inputs.get('protein_db_selector', 'cached')) == 'history':
                if not inputs.get('protein_database'):
                    return 'protein_database is required when protein_db_selector is history'
            elif not inputs.get('prot_db') and (not inputs.get('protein_database')):
                return 'prot_db is required when protein_db_selector is cached'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FILE', {'description': 'Raw reads, precomputed mappings, or abundance table'}), 'nuc_db': ('DIRECTORY', {'description': 'Cached ChocoPhlAn nucleotide database'}), 'prot_db': ('DIRECTORY', {'description': 'Cached UniRef protein database'})}, 'optional': {'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'}), 'input_selector': ('STRING', {'default': 'raw', 'options': ['raw', 'mapping', 'abundance'], 'description': 'Galaxy input mode'}), 'input_ext': ('STRING', {'default': 'fastq', 'description': 'Input extension used to set HUMAnN input format'}), 'workflow_selector': ('STRING', {'default': 'none', 'options': ['none', 'bypass_prescreen', 'bypass_taxonomic_profiling', 'bypass_nucleotide_index', 'bypass_nucleotide_search', 'bypass_translated_search'], 'description': 'Galaxy HUMAnN workflow step selection'}), 'taxonomic_profile': ('TSV', {'default': '', 'description': 'Taxonomic profile for bypass_taxonomic_profiling'}), 'metaphlan_db_selector': ('STRING', {'default': 'cached', 'options': ['cached', 'history']}), 'metaphlan_db': ('DIRECTORY', {'default': '', 'description': 'Cached MetaPhlAn marker database'}), 'metaphlan_index': ('STRING', {'default': '', 'description': 'Cached MetaPhlAn index/dbkey'}), 'metaphlan_bowtie2db': ('FASTA', {'default': '', 'description': 'History MetaPhlAn marker FASTA'}), 'metaphlan_mpa_pkl': ('JSON', {'default': '', 'description': 'History MetaPhlAn marker metadata JSON'}), 'prescreen_threshold': ('FLOAT', {'default': 0.01, 'min': 0, 'max': 100}), 'nucleotide_db_selector': ('STRING', {'default': 'cached', 'options': ['cached', 'history']}), 'nucleotide_database': ('FASTA', {'default': [], 'multiple': True, 'description': 'History ChocoPhlAn pangenome FASTA files'}), 'nucleotide_database_names': ('STRING', {'default': [], 'multiple': True, 'description': 'Element identifiers for history nucleotide databases'}), 'nucleotide_identity_threshold': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'nucleotide_subject_coverage_threshold': ('FLOAT', {'default': 50, 'min': 0, 'max': 100}), 'nucleotide_query_coverage_threshold': ('FLOAT', {'default': 90, 'min': 0, 'max': 100}), 'protein_db_selector': ('STRING', {'default': 'cached', 'options': ['cached', 'history']}), 'protein_database': ('FASTA', {'default': '', 'description': 'History UniRef protein FASTA'}), 'search_mode': ('STRING', {'default': '', 'options': ['', 'uniref50', 'uniref90']}), 'evalue': ('FLOAT', {'default': 1}), 'translated_identity_threshold': ('FLOAT', {'default': ''}), 'translated_subject_coverage_threshold': ('FLOAT', {'default': 50, 'min': 0, 'max': 100}), 'translated_query_coverage_threshold': ('FLOAT', {'default': 90, 'min': 0, 'max': 100}), 'gap_fill': ('BOOLEAN', {'default': True}), 'minpath': ('BOOLEAN', {'default': True}), 'pathways': ('STRING', {'default': 'metacyc', 'options': ['metacyc', 'unipathway']}), 'xipe': ('BOOLEAN', {'default': False}), 'annotation_gene_index': ('INT', {'default': 3}), 'id_mapping': ('TSV', {'default': ''}), 'output_basename': ('STRING', {'default': 'humann'}), 'output_format': ('STRING', {'default': 'tsv', 'options': ['tsv', 'biom']}), 'output_max_decimals': ('INT', {'default': 10}), 'remove_column_description_output': ('BOOLEAN', {'default': False}), 'remove_stratified_output': ('BOOLEAN', {'default': False}), 'intermediate_temp': ('STRING', {'default': [], 'multiple': True, 'options': ['metaphlan_bowtie2', 'metaphlan_bugs_list', 'bowtie2_alignment', 'bowtie2_reduced_alignment', 'bowtie2_unaligned', 'custom_chocophlan_database', 'diamond_aligned', 'diamond_unaligned'], 'description': 'Intermediate output files'})}, 'hidden': {'output': ('STRING', {})}}
