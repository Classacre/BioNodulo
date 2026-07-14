"""barcode — sequence node(s). One tool per file (extracted from wrapped_alignment_taxonomy.py)."""
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


class BarcodeSplitterNode(CommandNode):
    """Split FASTQ files into barcode-specific output files."""
    NODE_ID = 'barcode_splitter'
    DISPLAY_NAME = 'Barcode Splitter'
    REQUIRED_CONDA_PACKAGES = ['barcode_splitter']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Split FASTQ reads into barcode-specific files using one or more index reads.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Barcode Splitter', 'barcode_splitter', 'barcode demultiplexing', 'index reads', 'FASTQ splitting', 'barcodes', 'dual index', 'split_all']
    RETURN_TYPES = ('TSV', 'DIRECTORY')
    RETURN_NAMES = ('summary', 'split_output')
    REQUIRED_EXECUTABLES = ['barcode_splitter']
    DOCUMENTATION_URL = BARCODE_SPLITTER_CITATION_URL
    CITATION_DOIS = [BARCODE_SPLITTER_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BARCODE_SPLITTER_CITATION_DOI}', BARCODE_SPLITTER_CITATION_URL]
    CITATION_TEXT = BARCODE_SPLITTER_CITATION_TEXT
    VERSION = '0.18.4.0'
    SHELL = True
    RUN_TYPES = ['single', 'paired', 'flexible']
    FORMATS = ['fastq', 'fastqsanger', 'fastqsolexa', 'fastqillumina']
    READ_TYPES = ['single', 'forward', 'reverse', 'index', 'singleindex', 'forwardindex', 'reverseindex']
    INDEX_READ_TYPES = ['index', 'singleindex', 'forwardindex', 'reverseindex']

    @classmethod
    def _run_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('run_type', 'single') or 'single')

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('format', 'fastq') or 'fastq')

    @classmethod
    def _split_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/split'

    @classmethod
    def _summary_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/summary.tsv'

    @classmethod
    def _idxfiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('idxfiles'))

    @classmethod
    def _flexible_seqfiles(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        raw = inputs.get('flexible_seqfiles') or []
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @classmethod
    def _single_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files = [str(inputs.get('snglinput', '')), *cls._idxfiles(inputs)]
        idx_positions = [pos for pos in range(2, len(files) + 1)]
        return (files, idx_positions, bool(inputs.get('split_all', False)))

    @classmethod
    def _paired_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files = [str(inputs.get('fwdinput', '')), str(inputs.get('revinput', '')), *cls._idxfiles(inputs)]
        idx_positions = [pos for pos in range(3, len(files) + 1)]
        return (files, idx_positions, bool(inputs.get('split_all', False)))

    @classmethod
    def _flexible_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files: list[str] = []
        idx_positions: list[int] = []
        auto_split_all = bool(inputs.get('split_all', False))
        for index, item in enumerate(cls._flexible_seqfiles(inputs), start=1):
            readtype = str(item.get('readtype', 'single') or 'single')
            files.append(str(item.get('input', '')))
            if readtype in cls.INDEX_READ_TYPES:
                idx_positions.append(index)
                auto_split_all = True
        return (files, idx_positions, auto_split_all)

    @classmethod
    def _files_and_indexes(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        run_type = cls._run_type(inputs)
        if run_type == 'paired':
            return cls._paired_files(inputs)
        if run_type == 'flexible':
            return cls._flexible_files(inputs)
        return cls._single_files(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files, idx_positions, auto_split_all = cls._files_and_indexes(inputs)
        split_dir = cls._split_dir(inputs)
        sequence_format = cls._format(inputs)
        cmd = ['mkdir', '-p', split_dir, '&&', 'barcode_splitter', '--bcfile', str(inputs.get('bcfile', '')), '--mismatches', str(inputs.get('mismatches', 1)), '--galaxy']
        if inputs.get('barcodes_at_end', False):
            cmd.append('--barcodes_at_end')
        cmd.extend(['--prefix', f'{split_dir}/'])
        cmd.extend(files)
        cmd.append('--idxread')
        cmd.extend((str(position) for position in idx_positions))
        cmd.extend(['--format', sequence_format, '--suffix', f'.{sequence_format}'])
        if auto_split_all:
            cmd.append('--split_all')
        cmd.extend(['>', cls._summary_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        split_dir = out / 'split'
        split_dir.mkdir(parents=True, exist_ok=True)
        return [out / 'summary.tsv', split_dir]

    @classmethod
    def _validate_mismatches(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            mismatches = int(inputs.get('mismatches', 1))
        except (TypeError, ValueError):
            return 'mismatches must be an integer'
        if mismatches < 0 or mismatches > 2:
            return 'mismatches must be between 0 and 2'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('bcfile', '')).strip():
            return 'bcfile is required'
        run_type = cls._run_type(inputs)
        if run_type not in cls.RUN_TYPES:
            return f"run_type must be one of: {', '.join(cls.RUN_TYPES)}"
        mismatches_result = cls._validate_mismatches(inputs)
        if mismatches_result is not True:
            return mismatches_result
        sequence_format = cls._format(inputs)
        if sequence_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        if run_type == 'single':
            if not str(inputs.get('snglinput', '')).strip():
                return 'snglinput is required'
            if not cls._idxfiles(inputs):
                return 'at least one index read is required'
        elif run_type == 'paired':
            if not str(inputs.get('fwdinput', '')).strip():
                return 'fwdinput is required'
            if not str(inputs.get('revinput', '')).strip():
                return 'revinput is required'
            if not cls._idxfiles(inputs):
                return 'at least one index read is required'
        else:
            seqfiles = cls._flexible_seqfiles(inputs)
            if not seqfiles:
                return 'flexible_seqfiles must include at least one read'
            has_index = False
            for item in seqfiles:
                if not str(item.get('input', '')).strip():
                    return 'flexible_seqfiles entries require input'
                readtype = str(item.get('readtype', 'single') or 'single')
                if readtype not in cls.READ_TYPES:
                    return f"readtype must be one of: {', '.join(cls.READ_TYPES)}"
                if readtype in cls.INDEX_READ_TYPES:
                    has_index = True
            if not has_index:
                return 'at least one index read is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bcfile': ('TSV', {'description': 'Tab-delimited barcode table: sample identifier followed by one or more barcode columns'})}, 'optional': {'run_type': ('STRING', {'default': 'single', 'options': cls.RUN_TYPES, 'description': 'Galaxy run interface: single-end, paired-end, or flexible read layout'}), 'snglinput': ('FASTQ', {'default': '', 'description': 'Single-end read file for single run mode'}), 'fwdinput': ('FASTQ', {'default': '', 'description': 'Forward read file for paired run mode'}), 'revinput': ('FASTQ', {'default': '', 'description': 'Reverse read file for paired run mode'}), 'idxfiles': ('FASTQ_LIST', {'default': [], 'multiple': True, 'description': 'Index read files supplied after the main read files'}), 'idxreadnames': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy index read labels used for collection identifiers'}), 'flexible_seqfiles': ('JSON', {'default': [], 'is_list': True, 'description': 'Flexible-mode read objects with input, readtype, and optional readname fields'}), 'mismatches': ('INT', {'default': 1, 'min': 0, 'max': 2, 'description': 'Number of allowed mismatches per barcode'}), 'barcodes_at_end': ('BOOLEAN', {'default': False, 'description': 'Match barcodes at the end of all index sequences'}), 'split_all': ('BOOLEAN', {'default': False, 'description': 'Also split index-only files into the output directory'}), 'format': ('STRING', {'default': 'fastq', 'options': cls.FORMATS, 'description': 'FASTQ datatype extension used for discovered split files'})}, 'hidden': {'output': ('STRING', {})}}
