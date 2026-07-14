"""cat — wrapped_alignment_taxonomy node(s). One tool per file (extracted from wrapped_alignment_taxonomy.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _BctoolsBaseNode(CommandNode):
    """Shared metadata for bctools Galaxy wrappers."""
    REQUIRED_CONDA_PACKAGES = ['bctools']
    CATEGORY = 'sequence'
    REQUIRED_EXECUTABLES: list[str] = []
    DOCUMENTATION_URL = BCTOOLS_CITATION_URL
    CITATION_DOIS = [BCTOOLS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BCTOOLS_CITATION_DOI}', BCTOOLS_CITATION_URL]
    CITATION_TEXT = BCTOOLS_CITATION_TEXT
    VERSION = '0.2.2+galaxy2'
    SHELL = True

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('script_path', cls.REQUIRED_EXECUTABLES[0]) or cls.REQUIRED_EXECUTABLES[0])

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _plan_paths(cls, output_dir: str | Path, *filenames: str) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / filename for filename in filenames]

    @classmethod
    def _script_input(cls) -> tuple[str, dict[str, Any]]:
        return ('FILE', {'default': cls.REQUIRED_EXECUTABLES[0], 'advanced': True, 'description': f'Path to the bctools {cls.REQUIRED_EXECUTABLES[0]} executable'})

    @classmethod
    def _base_aliases(cls, *aliases: str) -> list[str]:
        return [BIONODULO_BUILTIN_ALIAS, 'bctools', *aliases, 'UMI', 'barcodes']
class _CatBaseNode(CommandNode):
    """Shared metadata for CAT/BAT Galaxy wrappers."""
    REQUIRED_CONDA_PACKAGES = ['cat']
    CATEGORY = 'taxonomy'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CAT', 'BAT', 'Contig Annotation Tool', 'Bin Annotation Tool', 'taxonomic classification', 'metagenomics']
    REQUIRED_EXECUTABLES = ['CAT', 'tabpad.py']
    DOCUMENTATION_URL = CAT_CITATION_URL
    CITATION_DOIS = CAT_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CAT_CITATION_DOIS]
    CITATION_TEXT = CAT_CITATION_TEXT
    VERSION = '5.2.3+galaxy0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output.tsv'

    @classmethod
    def _tabpad_path(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('tabpad_path', 'tabpad.py') or 'tabpad.py')

    @classmethod
    def _tabpad_command(cls, inputs: dict[str, Any], input_txt: str) -> list[str]:
        return [cls._tabpad_path(inputs), '-i', input_txt, '-o', cls._output_path(inputs)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.tsv']

    @classmethod
    def _tabpad_input(cls) -> tuple[str, dict[str, Any]]:
        return ('FILE', {'default': 'tabpad.py', 'advanced': True, 'description': 'Path to the Galaxy CAT tabpad.py helper script'})
class _CatClassifyBaseNode(_CatBaseNode):
    """Shared command rendering for CAT contigs and BAT bins workflows."""
    DB_SRC_OPTIONS = ['cached', 'history']
    USE_PREVIOUS_OPTIONS = ['no', 'yes']
    DIAMOND_OPTIONS = ['no', 'yes']
    ADD_NAMES_OPTIONS = ['no', 'orf2lca', 'classification', 'both']
    SUMMARISE_OPTIONS = ['no', 'classification']
    CLASSIFICATION_OUTPUT_NAME = 'contig2classification'
    CLASSIFICATION_SOURCE = 'cat_output.contig2classification.tsv'
    CLASSIFICATION_TXT = 'cat_output.contig2classification.txt'
    CLASSIFICATION_DESTINATION = 'contig2classification.tsv'
    DEFAULT_RANGE = 10
    DEFAULT_FRACTION = 0.5
    DEFAULT_SELECT_OUTPUTS = ['log', 'predicted_proteins_faa', 'orf2lca', 'contig2classification']
    SELECTABLE_OUTPUTS = ['log', 'predicted_proteins_faa', 'predicted_proteins_gff', 'alignment_diamond', 'orf2lca', 'contig2classification']
    BASE_OUTPUT_FILES = {'log': ('cat_output.log', 'log.txt'), 'predicted_proteins_faa': ('cat_output.predicted_proteins.faa', 'predicted_proteins.faa'), 'predicted_proteins_gff': ('cat_output.predicted_proteins.gff', 'predicted_proteins.gff'), 'alignment_diamond': ('cat_output.alignment.diamond', 'alignment.diamond.tsv'), 'orf2lca': ('cat_output.ORF2LCA.tsv', 'ORF2LCA.tsv'), 'contig2classification': ('cat_output.contig2classification.tsv', 'contig2classification.tsv')}
    DERIVED_OUTPUT_FILES = {'orf2lca_names': 'ORF2LCA.names.tsv', 'classification_names': 'classification_names.tsv', 'classification_summary': 'classification_summary.tsv'}

    @classmethod
    def _bool_input(cls, value: Any, default: bool=False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        if 'select_outputs' not in inputs or inputs.get('select_outputs') is None:
            return list(cls.DEFAULT_SELECT_OUTPUTS)
        value = inputs.get('select_outputs')
        if isinstance(value, str) and ',' in value:
            return [part.strip() for part in value.split(',') if part.strip()]
        return _as_list(value)

    @classmethod
    def _db_src(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('db_src', 'cached') or 'cached')

    @classmethod
    def _use_previous(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('use_previous', 'no') or 'no')

    @classmethod
    def _database_paths(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._db_src(inputs) == 'history':
            catdb = str(inputs.get('cat_db_extra_files_path', '') or '')
            return (f'{catdb}/CAT_database', f'{catdb}/taxonomy')
        return (str(inputs.get('database_folder', '') or ''), str(inputs.get('taxonomy_folder', '') or ''))

    @classmethod
    def _range_value(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('range', cls.DEFAULT_RANGE)

    @classmethod
    def _fraction_value(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('fraction', cls.DEFAULT_FRACTION)

    @classmethod
    def _set_diamond_opts(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('set_diamond_opts', 'no') or 'no')

    @classmethod
    def _add_names(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('add_names', 'no') or 'no')

    @classmethod
    def _summarise(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('summarise', 'no') or 'no')

    @classmethod
    def _out_file(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _base_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        selected = set(cls._selected_outputs(inputs))
        outputs = []
        if 'log' in selected:
            outputs.append('log')
        if cls._use_previous(inputs) != 'yes':
            for name in ('predicted_proteins_faa', 'predicted_proteins_gff', 'alignment_diamond'):
                if name in selected:
                    outputs.append(name)
        for name in ('orf2lca', cls.CLASSIFICATION_OUTPUT_NAME):
            if name in selected:
                outputs.append(name)
        return outputs

    @classmethod
    def _derived_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = []
        add_names = cls._add_names(inputs)
        if add_names in {'orf2lca', 'both'}:
            outputs.append('orf2lca_names')
        if add_names in {'classification', 'both'}:
            outputs.append('classification_names')
        if cls._summarise(inputs) == 'classification':
            outputs.append('classification_summary')
        return outputs

    @classmethod
    def _planned_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        return [*cls._base_output_names(inputs), *cls._derived_output_names(inputs)]

    @classmethod
    def _names_options(cls, inputs: dict[str, Any]) -> list[str]:
        options = []
        if cls._bool_input(inputs.get('only_official'), True):
            options.append('--only_official')
        if cls._bool_input(inputs.get('exclude_scores'), False):
            options.append('--exclude_scores')
        return options

    @classmethod
    def _add_names_command(cls, inputs: dict[str, Any], input_file: str, output_file: str, extra_options: list[str] | None=None) -> str:
        _database_folder, taxonomy_folder = cls._database_paths(inputs)
        cmd = ['CAT', 'add_names', *(extra_options if extra_options is not None else cls._names_options(inputs)), '--taxonomy_folder', taxonomy_folder, '-i', input_file, '-o', output_file]
        return _shell_join(cmd)

    @classmethod
    def _tabpad_to_output(cls, inputs: dict[str, Any], input_file: str, output_filename: str) -> str:
        return _shell_join([cls._tabpad_path(inputs), '-i', input_file, '-o', cls._out_file(inputs, output_filename)])

    @classmethod
    def _workflow_setup_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return []

    @classmethod
    def _workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        raise NotImplementedError

    @classmethod
    def _after_tabpad_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return []

    @classmethod
    def _tabpad_classification_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls._tabpad_path(inputs), 'cat_output.ORF2LCA.txt', cls.CLASSIFICATION_TXT])

    @classmethod
    def _summarise_command(cls, inputs: dict[str, Any], summary_input: str) -> str:
        return _shell_join(['CAT', 'summarise', '-c', str(inputs.get('contigs_fasta', '')), '-i', summary_input, '-o', 'classification_summary.txt'])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = cls._workflow_command(inputs)
        cmd.extend(['--out_prefix', 'cat_output', '--range', str(cls._range_value(inputs)), '--fraction', str(cls._fraction_value(inputs))])
        if cls._set_diamond_opts(inputs) == 'yes':
            if cls._bool_input(inputs.get('sensitive'), False):
                cmd.append('--sensitive')
            block_size = inputs.get('block_size', 2.0)
            index_chunks = inputs.get('index_chunks', 4)
            top = inputs.get('top', 50)
            cmd.extend(['--block_size', str(block_size), '--index_chunks', str(index_chunks)])
            if float(top) < 50:
                cmd.extend(['--I_know_what_Im_doing', '--top', str(top)])
        commands = [*cls._workflow_setup_commands(inputs), _shell_join(cmd), cls._tabpad_classification_command(inputs), *cls._after_tabpad_commands(inputs)]
        add_names = cls._add_names(inputs)
        if add_names in {'classification', 'both'}:
            commands.append(cls._add_names_command(inputs, cls.CLASSIFICATION_SOURCE, 'classification_names.txt'))
            commands.append(cls._tabpad_to_output(inputs, 'classification_names.txt', 'classification_names.tsv'))
        if add_names in {'orf2lca', 'both'}:
            commands.append(cls._add_names_command(inputs, 'cat_output.ORF2LCA.tsv', 'orf2lca_names.txt'))
            commands.append(cls._tabpad_to_output(inputs, 'orf2lca_names.txt', 'ORF2LCA.names.tsv'))
        if cls._summarise(inputs) == 'classification':
            if add_names in {'classification', 'both'} and cls._bool_input(inputs.get('only_official'), True):
                summary_input = cls._out_file(inputs, 'classification_names.tsv')
            else:
                summary_input = 'classification_offical_names'
                commands.append(cls._add_names_command(inputs, cls.CLASSIFICATION_SOURCE, summary_input, extra_options=['--only_official']))
            commands.append(cls._summarise_command(inputs, summary_input))
            commands.append(cls._tabpad_to_output(inputs, 'classification_summary.txt', 'classification_summary.tsv'))
        for output_name in cls._base_output_names(inputs):
            source, destination = cls.BASE_OUTPUT_FILES[output_name]
            commands.append(_shell_join(['cp', source, cls._out_file(inputs, destination)]))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        for output_name in cls._planned_output_names(inputs):
            if output_name in cls.BASE_OUTPUT_FILES:
                outputs.append(out / cls.BASE_OUTPUT_FILES[output_name][1])
            else:
                outputs.append(out / cls.DERIVED_OUTPUT_FILES[output_name])
        return outputs

    @classmethod
    def _validate_choice(cls, value: str, name: str, options: list[str]) -> bool | str:
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if parsed < minimum or parsed > maximum:
            return f'{key} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> bool | str:
        value = inputs.get(key, default)
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return f'{key} must be a number'
        if parsed < minimum or parsed > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def _validate_required_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('contigs_fasta', '')).strip():
            return 'contigs_fasta is required'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        required = cls._validate_required_inputs(inputs)
        if required is not True:
            return required
        db_src = cls._db_src(inputs)
        choice = cls._validate_choice(db_src, 'db_src', cls.DB_SRC_OPTIONS)
        if choice is not True:
            return choice
        if db_src == 'history':
            if not str(inputs.get('cat_db_extra_files_path', '')).strip():
                return 'cat_db_extra_files_path is required when db_src is history'
        else:
            if not str(inputs.get('database_folder', '')).strip():
                return 'database_folder is required'
            if not str(inputs.get('taxonomy_folder', '')).strip():
                return 'taxonomy_folder is required'
        use_previous = cls._use_previous(inputs)
        choice = cls._validate_choice(use_previous, 'use_previous', cls.USE_PREVIOUS_OPTIONS)
        if choice is not True:
            return choice
        if use_previous == 'yes':
            if not str(inputs.get('proteins_fasta', '')).strip():
                return 'proteins_fasta is required when use_previous is yes'
            if not str(inputs.get('diamond_alignment', '')).strip():
                return 'diamond_alignment is required when use_previous is yes'
        for validation in (cls._validate_int_range(inputs, 'range', cls.DEFAULT_RANGE, 0, 49), cls._validate_float_range(inputs, 'fraction', cls.DEFAULT_FRACTION, 0, 0.99)):
            if validation is not True:
                return validation
        set_diamond_opts = cls._set_diamond_opts(inputs)
        choice = cls._validate_choice(set_diamond_opts, 'set_diamond_opts', cls.DIAMOND_OPTIONS)
        if choice is not True:
            return choice
        if set_diamond_opts == 'yes':
            for validation in (cls._validate_float_range(inputs, 'block_size', 2.0, 1, 10), cls._validate_int_range(inputs, 'index_chunks', 4, 1, 10), cls._validate_int_range(inputs, 'top', 50, 1, 50)):
                if validation is not True:
                    return validation
        choice = cls._validate_choice(cls._add_names(inputs), 'add_names', cls.ADD_NAMES_OPTIONS)
        if choice is not True:
            return choice
        choice = cls._validate_choice(cls._summarise(inputs), 'summarise', cls.SUMMARISE_OPTIONS)
        if choice is not True:
            return choice
        if not cls._planned_output_names(inputs):
            return 'at least one selected output is required'
        return True

    @classmethod
    def _common_optional_inputs(cls) -> dict[str, Any]:
        return {'db_src': ('STRING', {'default': 'cached', 'options': cls.DB_SRC_OPTIONS}), 'cat_db': ('TXT', {'default': '', 'description': 'CAT prepare history dataset marker'}), 'cat_db_extra_files_path': ('DIRECTORY', {'default': '', 'description': 'Extra files path from a CAT prepare history dataset'}), 'use_previous': ('STRING', {'default': 'no', 'options': cls.USE_PREVIOUS_OPTIONS}), 'proteins_fasta': ('FASTA', {'default': '', 'description': 'Previous Prodigal predicted proteins FASTA'}), 'diamond_alignment': ('TSV', {'default': '', 'description': 'Previous DIAMOND alignment table'}), 'range': ('INT', {'default': cls.DEFAULT_RANGE, 'min': 0, 'max': 49, 'description': 'CAT/BAT range cutoff'}), 'fraction': ('FLOAT', {'default': cls.DEFAULT_FRACTION, 'min': 0, 'max': 0.99, 'description': 'Bit-score support fraction'}), 'set_diamond_opts': ('STRING', {'default': 'no', 'options': cls.DIAMOND_OPTIONS}), 'sensitive': ('BOOLEAN', {'default': False, 'description': 'Run DIAMOND in sensitive mode'}), 'block_size': ('FLOAT', {'default': 2.0, 'min': 1, 'max': 10}), 'index_chunks': ('INT', {'default': 4, 'min': 1, 'max': 10}), 'top': ('INT', {'default': 50, 'min': 1, 'max': 50}), 'add_names': ('STRING', {'default': 'no', 'options': cls.ADD_NAMES_OPTIONS}), 'only_official': ('BOOLEAN', {'default': True, 'description': 'Only output official taxonomic rank names'}), 'exclude_scores': ('BOOLEAN', {'default': False, 'description': 'Exclude bit-score support scores in lineage columns'}), 'summarise': ('STRING', {'default': 'no', 'options': cls.SUMMARISE_OPTIONS}), 'select_outputs': ('STRING', {'default': cls.DEFAULT_SELECT_OUTPUTS, 'options': cls.SELECTABLE_OUTPUTS, 'multiple': True}), 'tabpad_path': cls._tabpad_input()}


class CatPrepareNode(_CatBaseNode):
    """Prepare CAT reference data for CAT/BAT classification workflows."""
    NODE_ID = 'cat_prepare'
    DISPLAY_NAME = 'CAT prepare'
    DESCRIPTION = 'Prepare CAT reference data for classifying metagenomic contigs or genome assemblies.'
    SEARCH_ALIASES = [*_CatBaseNode.SEARCH_ALIASES, 'cat_prepare', 'CAT prepare', 'CAT database', 'CAT reference data', 'CAT prepare database', 'NCBI taxonomy']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('cat_db',)
    REQUIRED_EXECUTABLES = ['CAT']

    @classmethod
    def _database_folder_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs['database_folder']) if 'database_folder' in inputs else 'CAT_database'

    @classmethod
    def _taxonomy_folder_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs['taxonomy_folder']) if 'taxonomy_folder' in inputs else 'taxonomy'

    @classmethod
    def _database_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._database_folder_name(inputs)}'

    @classmethod
    def _taxonomy_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._taxonomy_folder_name(inputs)}'

    @classmethod
    def _cat_db_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/cat_db.txt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        database_name = cls._database_folder_name(inputs)
        taxonomy_name = cls._taxonomy_folder_name(inputs)
        database_path = cls._database_path(inputs)
        taxonomy_path = cls._taxonomy_path(inputs)
        setup = _shell_join(['mkdir', '-p', database_path, taxonomy_path])
        marker = f"echo CAT_DB $(date '+%Y-%m-%d') {shlex.quote(database_name)} {shlex.quote(taxonomy_name)} > {shlex.quote(cls._cat_db_path(inputs))}"
        cmd = ['CAT', 'prepare', '--fresh', '--database_folder', database_path, '--taxonomy_folder', taxonomy_path]
        return f'{setup} && {marker} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'cat_db.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._database_folder_name(inputs).strip():
            return 'database_folder is required'
        if not cls._taxonomy_folder_name(inputs).strip():
            return 'taxonomy_folder is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {}, 'optional': {'database_folder': ('STRING', {'default': 'CAT_database', 'description': 'Prepared CAT database folder name'}), 'taxonomy_folder': ('STRING', {'default': 'taxonomy', 'description': 'Prepared CAT taxonomy folder name'})}, 'hidden': {'output': ('STRING', {})}}


class CatContigsNode(_CatClassifyBaseNode):
    """Classify metagenomic contigs with CAT taxonomic assignments."""
    NODE_ID = 'cat_contigs'
    DISPLAY_NAME = 'CAT contigs'
    DESCRIPTION = 'Classify metagenomic contigs with CAT taxonomic assignments.'
    SEARCH_ALIASES = [*_CatBaseNode.SEARCH_ALIASES, 'cat_contigs', 'CAT contigs', 'contig classification', 'contig2classification', 'ORF2LCA', 'predicted_proteins', 'classification.summary.txt']
    RETURN_TYPES = ('TXT', 'FASTA', 'GFF', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('log', 'predicted_proteins_faa', 'predicted_proteins_gff', 'alignment_diamond', 'orf2lca', 'contig2classification', 'orf2lca_names', 'classification_names', 'classification_summary')

    @classmethod
    def _workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        database_folder, taxonomy_folder = cls._database_paths(inputs)
        cmd = ['CAT', 'contigs', '-c', str(inputs.get('contigs_fasta', '')), '--database_folder', database_folder, '--taxonomy_folder', taxonomy_folder]
        if cls._use_previous(inputs) == 'yes':
            cmd.extend(['--proteins_fasta', str(inputs.get('proteins_fasta', '')), '--diamond_alignment', str(inputs.get('diamond_alignment', ''))])
        return cmd

    @classmethod
    def _validate_required_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('contigs_fasta', '')).strip():
            return 'contigs_fasta is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'contigs_fasta': ('FASTA', {'description': 'Contigs fasta file'}), 'database_folder': ('DIRECTORY', {'description': 'CAT database folder for cached database mode'}), 'taxonomy_folder': ('DIRECTORY', {'description': 'CAT taxonomy folder for cached database mode'})}, 'optional': {**cls._common_optional_inputs()}, 'hidden': {'output': ('STRING', {})}}


class CatBinsNode(_CatClassifyBaseNode):
    """Classify genome bins with BAT taxonomic assignments."""
    NODE_ID = 'cat_bins'
    DISPLAY_NAME = 'CAT bins'
    DESCRIPTION = 'Classify metagenome-assembled genome bins with BAT taxonomic assignments.'
    SEARCH_ALIASES = [*_CatBaseNode.SEARCH_ALIASES, 'cat_bins', 'CAT bins', 'CAT bin', 'BAT', 'Bin Annotation Tool', 'bin classification', 'bin2classification', 'metagenome assembled genomes', 'MAGs']
    RETURN_TYPES = CatContigsNode.RETURN_TYPES
    RETURN_NAMES = ('log', 'predicted_proteins_faa', 'predicted_proteins_gff', 'alignment_diamond', 'orf2lca', 'bin2classification', 'orf2lca_names', 'classification_names', 'classification_summary')
    CLASSIFICATION_OUTPUT_NAME = 'bin2classification'
    CLASSIFICATION_SOURCE = 'cat_output.bin2classification.tsv'
    CLASSIFICATION_TXT = 'cat_output.bin2classification.txt'
    CLASSIFICATION_DESTINATION = 'bin2classification.tsv'
    DEFAULT_RANGE = 5
    DEFAULT_FRACTION = 0.3
    DEFAULT_SELECT_OUTPUTS = ['log', 'predicted_proteins_faa', 'orf2lca', 'bin2classification']
    SELECTABLE_OUTPUTS = ['log', 'predicted_proteins_faa', 'predicted_proteins_gff', 'alignment_diamond', 'orf2lca', 'bin2classification']
    BASE_OUTPUT_FILES = {**{key: value for key, value in _CatClassifyBaseNode.BASE_OUTPUT_FILES.items() if key != 'contig2classification'}, 'bin2classification': ('cat_output.bin2classification.tsv', 'bin2classification.tsv')}

    @classmethod
    def _mag_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('mags'))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], mag_files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get('element_identifiers'))
        return [identifiers[index] if index < len(identifiers) and identifiers[index] else Path(path).name for index, path in enumerate(mag_files)]

    @staticmethod
    def _galaxy_bin_identifier(value: str) -> str:
        return re.sub('[^\\s\\w\\-]', '_', value)

    @classmethod
    def _workflow_setup_commands(cls, inputs: dict[str, Any]) -> list[str]:
        mag_files = cls._mag_files(inputs)
        identifiers = cls._element_identifiers(inputs, mag_files)
        if len(mag_files) > 1:
            commands = [_shell_join(['mkdir', '-p', 'inputs'])]
            for mag_file, identifier in zip(mag_files, identifiers, strict=True):
                commands.append(_shell_join(['ln', '-s', mag_file, f'inputs/{cls._galaxy_bin_identifier(identifier)}.FASTA']))
            return commands
        if not mag_files:
            return []
        return [_shell_join(['ln', '-s', mag_files[0], cls._galaxy_bin_identifier(identifiers[0])])]

    @classmethod
    def _workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        database_folder, taxonomy_folder = cls._database_paths(inputs)
        mag_files = cls._mag_files(inputs)
        if len(mag_files) > 1:
            cmd = ['CAT', 'bins', '-s', '.FASTA', '-b', 'inputs']
        else:
            identifiers = cls._element_identifiers(inputs, mag_files)
            bin_file = cls._galaxy_bin_identifier(identifiers[0]) if identifiers else ''
            cmd = ['CAT', 'bin', '-b', bin_file]
        cmd.extend(['--database_folder', database_folder, '--taxonomy_folder', taxonomy_folder])
        if cls._use_previous(inputs) == 'yes':
            cmd.extend(['--proteins_fasta', str(inputs.get('proteins_fasta', '')), '--diamond_alignment', str(inputs.get('diamond_alignment', ''))])
        return cmd

    @classmethod
    def _after_tabpad_commands(cls, inputs: dict[str, Any]) -> list[str]:
        if len(cls._mag_files(inputs)) <= 1:
            return []
        return ['(for i in *.concatenated.*; do ln -s "$i" "${i/concatenated./}"; done)']

    @classmethod
    def _tabpad_classification_command(cls, inputs: dict[str, Any]) -> str:
        if len(cls._mag_files(inputs)) <= 1:
            return super()._tabpad_classification_command(inputs)
        return f'{shlex.quote(cls._tabpad_path(inputs))} *.ORF2LCA.txt *.bin2classification.txt'

    @classmethod
    def _summarise_command(cls, inputs: dict[str, Any], summary_input: str) -> str:
        return _shell_join(['CAT', 'summarise', '-i', summary_input, '-o', 'classification_summary.txt'])

    @classmethod
    def _validate_required_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._mag_files(inputs):
            return 'at least one mags value is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mags': ('FASTA', {'multiple': True, 'min_items': 1, 'description': 'Metagenome-assembled genome FASTA files'}), 'database_folder': ('DIRECTORY', {'description': 'CAT database folder for cached database mode'}), 'taxonomy_folder': ('DIRECTORY', {'description': 'CAT taxonomy folder for cached database mode'})}, 'optional': {'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection element identifiers for MAG files'}), **cls._common_optional_inputs()}, 'hidden': {'output': ('STRING', {})}}


class CatAddNamesNode(_CatBaseNode):
    """Add taxonomic names to CAT or BAT classification outputs."""
    NODE_ID = 'cat_add_names'
    DISPLAY_NAME = 'CAT add_names'
    DESCRIPTION = 'Annotate CAT or BAT classification tables with taxonomic names.'
    SEARCH_ALIASES = [*_CatBaseNode.SEARCH_ALIASES, 'cat_add_names', 'CAT add_names', 'taxonomic names', 'official taxonomic ranks', 'ORF2LCA', 'contig2classification', 'bin2classification']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)

    @classmethod
    def _names_txt_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_names.txt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        names_txt = cls._names_txt_path(inputs)
        cmd = ['CAT', 'add_names', '-i', str(inputs.get('input', '')), '--taxonomy_folder', str(inputs.get('taxonomy_folder', ''))]
        if inputs.get('only_official', True):
            cmd.append('--only_official')
        if inputs.get('exclude_scores', False):
            cmd.append('--exclude_scores')
        cmd.extend(['-o', names_txt])
        return f'{_shell_join(cmd)} && {_shell_join(cls._tabpad_command(inputs, names_txt))}'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not str(inputs.get('taxonomy_folder', '')).strip():
            return 'taxonomy_folder is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'CAT or BAT classification table or ORF2LCA output'}), 'taxonomy_folder': ('DIRECTORY', {'description': 'CAT taxonomy folder containing NCBI taxonomy files'})}, 'optional': {'only_official': ('BOOLEAN', {'default': True, 'description': 'Only output official taxonomic rank names'}), 'exclude_scores': ('BOOLEAN', {'default': False, 'description': 'Exclude bit-score support scores in the lineage columns'}), 'tabpad_path': cls._tabpad_input()}, 'hidden': {'output': ('STRING', {})}}


class CatSummariseNode(_CatBaseNode):
    """Summarise CAT or BAT taxonomic assignments by official name."""
    NODE_ID = 'cat_summarise'
    DISPLAY_NAME = 'CAT summarise'
    DESCRIPTION = 'Summarise CAT or BAT assignments by official taxonomic name.'
    SEARCH_ALIASES = [*_CatBaseNode.SEARCH_ALIASES, 'cat_summarise', 'CAT summarise', 'classification.summary.txt', 'number of assignments', 'taxonomic summary', 'official taxonomic names']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)

    @classmethod
    def _summary_txt_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_names_summary.txt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        summary_txt = cls._summary_txt_path(inputs)
        cmd = ['CAT', 'summarise']
        if str(inputs.get('contigs_fasta', '')).strip():
            cmd.extend(['-c', str(inputs.get('contigs_fasta', ''))])
        cmd.extend(['-i', str(inputs.get('input', '')), '-o', summary_txt])
        return f'{_shell_join(cmd)} && {_shell_join(cls._tabpad_command(inputs, summary_txt))}'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Official-name CAT/BAT classification table from CAT add_names'})}, 'optional': {'contigs_fasta': ('FASTA', {'default': '', 'description': 'Contigs FASTA used for CAT contigs summaries; optional for BAT bin summaries'}), 'tabpad_path': cls._tabpad_input()}, 'hidden': {'output': ('STRING', {})}}
