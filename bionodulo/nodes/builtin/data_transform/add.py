"""add — data_transform node(s). One tool per file (extracted from wrapped_alignment_taxonomy.py)."""
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


class ColumnMakerNode(CommandNode):
    """Compute expressions on tabular rows and add, insert, or replace columns."""
    NODE_ID = 'Add_a_column1'
    DISPLAY_NAME = 'Compute on rows'
    REQUIRED_CONDA_PACKAGES = ['python', 'numpy']
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Compute one or more expressions on each tabular row and add, insert, or replace columns.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'column_maker', 'Add_a_column1', 'Compute on rows', 'computed columns', 'append columns', 'insert columns', 'replace columns', 'tabular expression', 'data manipulation']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('out_file1',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = f'{DOI_URL}{COLUMN_MAKER_CITATION_DOI}'
    CITATION_DOIS = [COLUMN_MAKER_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{COLUMN_MAKER_CITATION_DOI}']
    CITATION_TEXT = COLUMN_MAKER_CITATION_TEXT
    VERSION = '2.1+galaxy0'
    SHELL = True
    ADD_COLUMN_MODES = ['', 'I', 'R']
    HEADER_OPTIONS = ['no', 'yes']
    NON_COMPUTABLE_ACTIONS = ['--fail-on-non-computable', '--skip-non-computable', '--keep-non-computable', '--non-computable-blank', '--non-computable-default']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_file1.tsv'

    @classmethod
    def _actions_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/expressions.txt'

    @classmethod
    def _header_lines_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('header_lines_select', 'no') or 'no')

    @classmethod
    def _column_types(cls, inputs: dict[str, Any]) -> str:
        column_types = str(inputs.get('column_types', ''))
        if inputs.get('auto_col_types', True):
            return column_types
        return ','.join(('str' for _ in column_types.split(',')))

    @classmethod
    def _expression_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        expressions = inputs.get('expressions')
        if isinstance(expressions, (list, tuple)) and expressions:
            return [dict(item) for item in expressions if isinstance(item, dict)]
        return [{'cond': inputs.get('cond', 'c3-c2'), 'mode': inputs.get('add_column_mode', ''), 'pos': inputs.get('pos', ''), 'new_column_name': inputs.get('new_column_name', '')}]

    @classmethod
    def _action_spec(cls, item: dict[str, Any]) -> str:
        mode = str(item.get('mode', item.get('add_column_mode', '')) or '')
        pos = str(item.get('pos', '') or '')
        col_add_spec = '' if mode == '' else f'{pos}{mode}'
        return f"{item.get('cond', '')};{col_add_spec};{item.get('new_column_name', '')}"

    @classmethod
    def _action_specs(cls, inputs: dict[str, Any]) -> list[str]:
        return [cls._action_spec(item) for item in cls._expression_items(inputs)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        write_actions = ['printf', '%s\\n', *cls._action_specs(inputs)]
        command = f"{_shell_join(['mkdir', '-p', out])} && {_shell_join(write_actions)} > {shlex.quote(cls._actions_path(inputs))}"
        py_cmd = ['python', str(inputs.get('script_path', 'column_maker.py') or 'column_maker.py'), '--column-types', cls._column_types(inputs)]
        if inputs.get('avoid_scientific_notation'):
            py_cmd.append('--avoid-scientific-notation')
        if cls._header_lines_select(inputs) == 'yes':
            py_cmd.append('--header')
        py_cmd.extend(['--file', cls._actions_path(inputs)])
        if inputs.get('fail_on_non_existent_columns', True):
            py_cmd.append('--fail-on-non-existent-columns')
        non_computable_action = str(inputs.get('non_computable_action', '--fail-on-non-computable') or '--fail-on-non-computable')
        py_cmd.append(non_computable_action)
        if non_computable_action == '--non-computable-default':
            py_cmd.append(str(inputs.get('non_computable_default', 'nan') or 'nan'))
        py_cmd.extend([str(inputs.get('input', '')), cls._output_path(inputs)])
        return f'{command} && {_shell_join(py_cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out_file1.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not str(inputs.get('column_types', '')).strip():
            return 'column_types is required'
        if cls._header_lines_select(inputs) not in cls.HEADER_OPTIONS:
            return f"header_lines_select must be one of: {', '.join(cls.HEADER_OPTIONS)}"
        non_computable_action = str(inputs.get('non_computable_action', '--fail-on-non-computable') or '--fail-on-non-computable')
        if non_computable_action not in cls.NON_COMPUTABLE_ACTIONS:
            return f"non_computable_action must be one of: {', '.join(cls.NON_COMPUTABLE_ACTIONS)}"
        for item in cls._expression_items(inputs):
            if not str(item.get('cond', '')).strip():
                return 'cond is required for every expression'
            mode = str(item.get('mode', item.get('add_column_mode', '')) or '')
            if mode not in cls.ADD_COLUMN_MODES:
                return f"add_column_mode must be one of: {', '.join(cls.ADD_COLUMN_MODES)}"
            if mode in {'I', 'R'}:
                try:
                    pos = int(item.get('pos', 0) or 0)
                except (TypeError, ValueError):
                    return 'pos must be an integer when inserting or replacing'
                if pos < 1:
                    return 'pos must be at least 1 when inserting or replacing'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Tabular dataset whose rows will receive computed columns'}), 'column_types': ('STRING', {'description': 'Comma-separated Python/Galaxy column types, for example str,int,int,str'})}, 'optional': {'expressions': ('JSON', {'default': [], 'is_list': True, 'description': 'Galaxy repeat-style expression objects with cond, mode, pos, and new_column_name'}), 'cond': ('STRING', {'default': 'c3-c2', 'description': 'Single expression used when expressions is empty'}), 'add_column_mode': ('STRING', {'default': '', 'options': cls.ADD_COLUMN_MODES, 'description': 'Append, insert, or replace mode for the single expression'}), 'pos': ('INT', {'default': 1, 'min': 1, 'description': '1-based insert/replace column position'}), 'new_column_name': ('STRING', {'default': '', 'description': 'Header name for the computed column when header mode is enabled'}), 'header_lines_select': ('STRING', {'default': 'no', 'options': cls.HEADER_OPTIONS, 'description': 'Whether the input has a header line with column names'}), 'avoid_scientific_notation': ('BOOLEAN', {'default': False, 'description': 'Write fully expanded decimal values for new floating-point columns'}), 'auto_col_types': ('BOOLEAN', {'default': True, 'description': 'Use supplied Galaxy column types instead of treating all columns as str'}), 'fail_on_non_existent_columns': ('BOOLEAN', {'default': True, 'description': 'Fail if an expression references a missing column'}), 'non_computable_action': ('STRING', {'default': '--fail-on-non-computable', 'options': cls.NON_COMPUTABLE_ACTIONS, 'description': 'How to handle rows where an expression cannot be computed'}), 'non_computable_default': ('STRING', {'default': 'nan', 'description': 'Replacement value for --non-computable-default'}), 'script_path': ('FILE', {'default': 'column_maker.py', 'advanced': True, 'description': 'Path to the Galaxy column_maker.py helper script'})}, 'hidden': {'output': ('STRING', {})}}
