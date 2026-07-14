"""chewbbaca — typing node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ChewBBACAAlleleCallNode(CommandNode):
    """Determine allelic profiles for genome assemblies with chewBBACA."""
    NODE_ID = 'chewbbaca_allelecall'
    DISPLAY_NAME = 'ChewBBACA AlleleCall'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Determine allelic profiles for genome assemblies with a chewBBACA schema.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_allelecall', 'ChewBBACA AlleleCall', 'AlleleCall', 'cgMLST', 'wgMLST', 'allelic profiles', 'schema_seed', 'bacterial typing']
    RETURN_TYPES = ('TSV_LIST', 'TXT_LIST', 'FASTA', 'FASTA', 'FASTA')
    RETURN_NAMES = ('allelecall_results', 'allelecall_log', 'unclassified_fasta', 'missing_fasta', 'novel_fasta')
    REQUIRED_EXECUTABLES = ['chewBBACA.py', 'unzip']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True
    OUTPUT_OPTIONS = ['output_unclassified', 'output_missing', 'output_novel', 'hash_profile']
    PRODIGAL_MODES = ['single', 'meta']
    MODES = ['1', '2', '3', '4']

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('input_file', inputs.get('input_files')))

    @classmethod
    def _output_selector(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('output_selector'))

    @classmethod
    def _safe_input_name(cls, path: str) -> str:
        name = Path(path).name
        if '.' in name:
            stem, ext = name.rsplit('.', 1)
            return f'{_safe_element_identifier(stem)}.{_safe_element_identifier(ext)}'
        return _safe_element_identifier(name)

    @classmethod
    def _prodigal_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('prodigal_mode', 'single') or 'single')

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('mode', '4') or '4')

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', 'mkdir input', 'mkdir schema']
        for input_file in cls._input_files(inputs):
            commands.append(_shell_join(['ln', '-sf', input_file, f'input/{cls._safe_input_name(input_file)}']))
        commands.append(_shell_join(['unzip', str(inputs.get('input_schema', '')), '-d', 'schema']))
        cmd = ['chewBBACA.py', 'AlleleCall']
        _add_if_value(cmd, '--ptf', inputs.get('training_file'))
        if cls._bool_flag(inputs, 'cds_input'):
            cmd.append('--cds-input')
        _add_if_value(cmd, '--gl', inputs.get('genes_list'))
        _add_if_value(cmd, '--bsr', inputs.get('blast_score_ratio'))
        _add_if_value(cmd, '--l', inputs.get('minimum_length'))
        _add_if_value(cmd, '--t', inputs.get('translation_table'))
        _add_if_value(cmd, '--st', inputs.get('size_threshold'))
        if cls._bool_flag(inputs, 'no_inferred'):
            cmd.append('--no-inferred')
        cmd.extend(['--pm', cls._prodigal_mode(inputs), '--mode', cls._mode(inputs), '--force-continue'])
        selected = set(cls._output_selector(inputs))
        if 'output_unclassified' in selected:
            cmd.append('--output-unclassified')
        if 'output_missing' in selected:
            cmd.append('--output-missing')
        if 'output_novel' in selected:
            cmd.append('--output-novel')
        if 'hash_profile' in selected:
            cmd.extend(['--hash-profile', 'md5'])
        cmd.extend(['-i', 'input', '-g', 'schema/schema_seed/', '-o', 'output'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output'
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out, out]
        selected = set(cls._output_selector(inputs))
        if 'output_unclassified' in selected:
            outputs.append(out / 'unclassified_sequences.fasta')
        if 'output_missing' in selected:
            outputs.append(out / 'missing_classes.fasta')
        if 'output_novel' in selected:
            outputs.append(out / 'novel_alleles.fasta')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'is_list': True, 'multiple': True, 'description': 'Genome assemblies'}), 'input_schema': ('FILE', {'description': 'chewBBACA schema ZIP archive'})}, 'optional': {'genes_list': ('TXT', {'default': ''}), 'training_file': ('FILE', {'default': ''}), 'cds_input': ('BOOLEAN', {'default': False}), 'blast_score_ratio': ('FLOAT', {'default': '', 'min': 0, 'max': 1}), 'minimum_length': ('INT', {'default': '', 'min': 0}), 'translation_table': ('INT', {'default': '', 'min': 0}), 'size_threshold': ('FLOAT', {'default': '', 'min': 0}), 'no_inferred': ('BOOLEAN', {'default': False}), 'prodigal_mode': ('STRING', {'default': 'single', 'options': cls.PRODIGAL_MODES}), 'mode': ('STRING', {'default': '4', 'options': cls.MODES}), 'output_selector': ('STRING_LIST', {'default': [], 'options': cls.OUTPUT_OPTIONS, 'multiple': True, 'display': 'checkboxes'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _validate_optional_int(cls, inputs: dict[str, Any], name: str) -> bool | str:
        raw = inputs.get(name, '')
        if raw == '':
            return True
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return f'{name} must be an integer'
        if value < 0:
            return f'{name} must be greater than or equal to 0'
        return True

    @classmethod
    def _validate_optional_float(cls, inputs: dict[str, Any], name: str, upper: float | None=None) -> bool | str:
        raw = inputs.get(name, '')
        if raw == '':
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if value < 0:
            return f'{name} must be greater than or equal to 0'
        if upper is not None and value > upper:
            return f'{name} must be between 0 and {int(upper)}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one input_file value is required'
        if not str(inputs.get('input_schema', '')).strip():
            return 'input_schema is required'
        if cls._mode(inputs) not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        if cls._prodigal_mode(inputs) not in cls.PRODIGAL_MODES:
            return f"prodigal_mode must be one of: {', '.join(cls.PRODIGAL_MODES)}"
        result = cls._validate_optional_float(inputs, 'blast_score_ratio', 1)
        if result is not True:
            return result
        for name in ('minimum_length', 'translation_table'):
            result = cls._validate_optional_int(inputs, name)
            if result is not True:
                return result
        result = cls._validate_optional_float(inputs, 'size_threshold')
        if result is not True:
            return result
        unsupported = [value for value in cls._output_selector(inputs) if value not in cls.OUTPUT_OPTIONS]
        if unsupported:
            return f"output_selector values must be one or more of: {', '.join(cls.OUTPUT_OPTIONS)}"
        return True


class ChewBBACAAlleleCallEvaluatorNode(CommandNode):
    """Build chewBBACA allele calling evaluation reports."""
    NODE_ID = 'chewbbaca_allelecallevaluator'
    DISPLAY_NAME = 'chewBBACA AlleleCallEvaluator'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Build an interactive report for chewBBACA allele calling result evaluation.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_allelecallevaluator', 'chewBBACA AlleleCallEvaluator', 'AlleleCallEvaluator', 'AlleleCall', 'cgMLST', 'presence absence', 'distance matrix', 'Neighbor-Joining tree']
    RETURN_TYPES = ('HTML_REPORT', 'FASTA', 'TSV', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('html_file', 'cgMLST_MSA', 'cgMLST_profiles', 'distance_matrix_symmetric', 'masked_profiles', 'presence_absence')
    REQUIRED_EXECUTABLES = ['chewBBACA.py', 'unzip', 'cp', 'mv']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True
    COMPUTATION_OPTIONS = ['light', 'no-pa', 'no-dm', 'no-tree', 'cg-alignment']
    OUTPUT_OPTIONS = ['cgMLST_MSA.fasta', 'cgMLST_profiles.tsv', 'distance_matrix_symmetric.tsv', 'masked_profiles.tsv', 'presence_absence.tsv']

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('input_file', inputs.get('input_files')))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('element_identifiers'))

    @classmethod
    def _input_name(cls, input_file: str, index: int, inputs: dict[str, Any]) -> str:
        element_identifiers = cls._element_identifiers(inputs)
        if index < len(element_identifiers):
            return f'{_safe_element_identifier(element_identifiers[index])}.tsv'
        return f'{_safe_element_identifier(Path(input_file).stem)}.tsv'

    @classmethod
    def _computation(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('computation'))

    @classmethod
    def _output_selector(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('output_selector'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        html_files = f'{out}/html_files'
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', 'mkdir input', _shell_join(['mkdir', '-p', 'schema', html_files])]
        for index, input_file in enumerate(cls._input_files(inputs)):
            commands.append(_shell_join(['ln', '-sf', input_file, f'input/{cls._input_name(input_file, index, inputs)}']))
        commands.append(_shell_join(['unzip', str(inputs.get('input_schema', '')), '-d', 'schema']))
        cmd = ['chewBBACA.py', 'AlleleCallEvaluator']
        _add_if_value(cmd, '-a', inputs.get('annotations'))
        selected_computation = set(cls._computation(inputs))
        for option in cls.COMPUTATION_OPTIONS:
            if option in selected_computation:
                cmd.append(f'--{option}')
        cmd.extend(['-i', 'input', '-g', 'schema/schema_seed/', '-o', html_files])
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(['cp', f'{html_files}/allelecall_report.html', f'{out}/output.html']))
        commands.append(f'mv {html_files}/*.fasta {html_files}/*.tsv .')
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.html']
        selected = set(cls._output_selector(inputs))
        for output_name in cls.OUTPUT_OPTIONS:
            if output_name in selected:
                outputs.append(out / output_name)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('TSV', {'is_list': True, 'multiple': True, 'description': 'AlleleCall result tables'}), 'input_schema': ('FILE', {'description': 'chewBBACA schema ZIP archive'})}, 'optional': {'annotations': ('TSV', {'default': ''}), 'computation': ('STRING_LIST', {'default': [], 'options': cls.COMPUTATION_OPTIONS, 'multiple': True, 'display': 'checkboxes'}), 'output_selector': ('STRING_LIST', {'default': [], 'options': cls.OUTPUT_OPTIONS, 'multiple': True, 'display': 'checkboxes'})}, 'hidden': {'element_identifiers': ('STRING_LIST', {'default': []}), 'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one input_file value is required'
        if not str(inputs.get('input_schema', '')).strip():
            return 'input_schema is required'
        unsupported = [value for value in cls._computation(inputs) if value not in cls.COMPUTATION_OPTIONS]
        if unsupported:
            return f"computation values must be one or more of: {', '.join(cls.COMPUTATION_OPTIONS)}"
        unsupported = [value for value in cls._output_selector(inputs) if value not in cls.OUTPUT_OPTIONS]
        if unsupported:
            return f"output_selector values must be one or more of: {', '.join(cls.OUTPUT_OPTIONS)}"
        return True


class ChewBBACACreateSchemaNode(CommandNode):
    """Create chewBBACA gene-by-gene schemas from genome assemblies."""
    NODE_ID = 'chewbbaca_createschema'
    DISPLAY_NAME = 'chewBBACA CreateSchema'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Create a gene-by-gene schema.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_createschema', 'chewBBACA CreateSchema', 'CreateSchema', 'schema_seed', 'cgMLST', 'wgMLST', 'gene-by-gene schema', 'bacterial typing']
    RETURN_TYPES = ('ZIP', 'TXT', 'TSV')
    RETURN_NAMES = ('schema', 'txt_file', 'tsv_file')
    REQUIRED_EXECUTABLES = ['chewBBACA.py', 'zip']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True
    PRODIGAL_MODES = ['single', 'meta']

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('input_file', inputs.get('input_files')))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('element_identifiers'))

    @classmethod
    def _element_extensions(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('element_extensions'))

    @classmethod
    def _input_name(cls, input_file: str, index: int, inputs: dict[str, Any]) -> str:
        element_identifiers = cls._element_identifiers(inputs)
        base = element_identifiers[index] if index < len(element_identifiers) else Path(input_file).stem
        element_extensions = cls._element_extensions(inputs)
        if index < len(element_extensions) and element_extensions[index]:
            ext = element_extensions[index]
        else:
            suffix = Path(input_file).suffix.lstrip('.')
            ext = suffix or 'fasta'
        return f'{_safe_element_identifier(base)}.{_safe_element_identifier(ext)}'

    @classmethod
    def _prodigal_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('prodigal_mode', 'single') or 'single')

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', 'mkdir input']
        for index, input_file in enumerate(cls._input_files(inputs)):
            commands.append(_shell_join(['ln', '-sf', input_file, f'input/{cls._input_name(input_file, index, inputs)}']))
        cmd = ['chewBBACA.py', 'CreateSchema']
        _add_if_value(cmd, '--ptf', inputs.get('training_file'))
        if cls._bool_flag(inputs, 'cds_input'):
            cmd.append('--cds-input')
        cmd.extend(['--bsr', str(inputs.get('blast_score_ratio', 0.6)), '--l', str(inputs.get('minimum_length', 201)), '--t', str(inputs.get('translation_table', 11)), '--st', str(inputs.get('size_threshold', 0.2)), '--pm', cls._prodigal_mode(inputs), '-i', 'input', '-o', 'output'])
        commands.append(_shell_join(cmd))
        commands.extend(['cd output/', 'zip -r schema_seed.zip schema_seed'])
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output'
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'schema_seed.zip']
        if cls._bool_flag(inputs, 'show_cds_invalid'):
            outputs.append(out / 'invalid_cds.txt')
        if cls._bool_flag(inputs, 'show_cds_coord'):
            outputs.append(out / 'cds_coordinates.tsv')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'is_list': True, 'multiple': True, 'description': 'Genome assemblies'})}, 'optional': {'training_file': ('FILE', {'default': ''}), 'cds_input': ('BOOLEAN', {'default': False}), 'minimum_length': ('INT', {'default': 201, 'min': 0}), 'blast_score_ratio': ('FLOAT', {'default': 0.6, 'min': 0, 'max': 1}), 'translation_table': ('INT', {'default': 11, 'min': 0}), 'size_threshold': ('FLOAT', {'default': 0.2, 'min': 0}), 'prodigal_mode': ('STRING', {'default': 'single', 'options': cls.PRODIGAL_MODES}), 'show_cds_invalid': ('BOOLEAN', {'default': False}), 'show_cds_coord': ('BOOLEAN', {'default': False})}, 'hidden': {'element_identifiers': ('STRING_LIST', {'default': []}), 'element_extensions': ('STRING_LIST', {'default': []}), 'output': ('STRING', {})}}

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be an integer'
        if value < minimum:
            return f'{name} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def _validate_float_min(cls, inputs: dict[str, Any], name: str, default: float, minimum: float, maximum: float | None=None) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if value < minimum:
            return f'{name} must be greater than or equal to {minimum:g}'
        if maximum is not None and value > maximum:
            return f'{name} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one input_file value is required'
        if cls._prodigal_mode(inputs) not in cls.PRODIGAL_MODES:
            return f"prodigal_mode must be one of: {', '.join(cls.PRODIGAL_MODES)}"
        result = cls._validate_float_min(inputs, 'blast_score_ratio', 0.6, 0, 1)
        if result is not True:
            return result
        result = cls._validate_int_min(inputs, 'minimum_length', 201, 0)
        if result is not True:
            return result
        result = cls._validate_int_min(inputs, 'translation_table', 11, 0)
        if result is not True:
            return result
        result = cls._validate_float_min(inputs, 'size_threshold', 0.2, 0)
        if result is not True:
            return result
        return True


class ChewBBACADownloadSchemaNode(CommandNode):
    """Download chewBBACA schemas from Chewie-NS."""
    NODE_ID = 'chewbbaca_downloadschema'
    DISPLAY_NAME = 'chewBBACA DownloadSchema'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Download a schema from Chewie-NS.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_downloadschema', 'chewBBACA DownloadSchema', 'DownloadSchema', 'Chewie-NS', 'schema_seed', 'cgMLST', 'wgMLST', 'bacterial typing']
    RETURN_TYPES = ('ZIP',)
    RETURN_NAMES = ('schema',)
    REQUIRED_EXECUTABLES = ['chewBBACA.py', 'mv', 'zip']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True
    SPECIES_OPTIONS = {'1': 'Streptococcus pyogenes', '2': 'Acinetobacter baumannii', '3': 'Arcobacter butzleri', '4': 'Campylobacter jejuni', '5': 'Escherichia coli', '6': 'Listeria monocytogenes', '7': 'Yersinia enterocolitica', '8': 'Salmonella enterica', '9': 'Streptococcus agalactiae', '10': 'Brucella melitensis', '11': 'Brucella', '12': 'Clostridium perfringens', '13': 'Clostridium chauvoei', '14': 'Bacillus anthracis', '15': 'Klebsiella oxytoca', '16': 'Clostridium neonatale'}

    @classmethod
    def _species_id(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('species_id', '') or '')

    @classmethod
    def _schema_id(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('schema_id', 1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', _shell_join(['chewBBACA.py', 'DownloadSchema', '-sp', cls._species_id(inputs), '-sc', str(cls._schema_id(inputs)), '-o', 'output']), 'mv output/* schema_seed', 'zip -r schema_seed.zip schema_seed']
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'schema_seed.zip']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'species_id': ('STRING', {'options': list(cls.SPECIES_OPTIONS), 'option_labels': cls.SPECIES_OPTIONS, 'description': 'Chewie-NS species ID'})}, 'optional': {'schema_id': ('INT', {'default': 1, 'min': 1})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._species_id(inputs).strip():
            return 'species_id is required'
        if cls._species_id(inputs) not in cls.SPECIES_OPTIONS:
            return f"species_id must be one of: {', '.join(cls.SPECIES_OPTIONS)}"
        try:
            schema_id = int(cls._schema_id(inputs))
        except (TypeError, ValueError):
            return 'schema_id must be an integer'
        if schema_id < 1:
            return 'schema_id must be greater than or equal to 1'
        return True


class ChewBBACAExtractCgMLSTNode(CommandNode):
    """Determine core-genome loci from chewBBACA allelic profiles."""
    NODE_ID = 'chewbbaca_extractcgmlst'
    DISPLAY_NAME = 'chewBBACA ExtractCgMLST'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Determine the set of loci that constitute the core genome.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_extractcgmlst', 'chewBBACA ExtractCgMLST', 'ExtractCgMLST', 'core genome', 'cgMLST', 'presence threshold', 'allelic profiles', 'bacterial typing']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('output_collection',)
    REQUIRED_EXECUTABLES = ['chewBBACA.py']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('threshold', '0.95 0.99 1') or '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['chewBBACA.py', 'ExtractCgMLST', '--t', cls._threshold(inputs)]
        _add_if_value(cmd, '--r', inputs.get('genes2remove'))
        _add_if_value(cmd, '--g', inputs.get('genomes2remove'))
        cmd.extend(['-i', str(inputs.get('input_file', '')), '-o', 'output'])
        return ' && '.join([_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output_collection'
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('TSV', {'description': 'Allelic profiles table'})}, 'optional': {'genomes2remove': ('TXT', {'default': ''}), 'threshold': ('STRING', {'default': '0.95 0.99 1'}), 'genes2remove': ('TSV', {'default': ''})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        threshold = cls._threshold(inputs)
        if not threshold.strip():
            return 'threshold is required'
        if re.fullmatch('[ .0-9]+', threshold) is None:
            return 'threshold may contain only spaces, periods, and digits'
        return True


class ChewBBACAJoinProfilesNode(CommandNode):
    """Join chewBBACA allele calling profiles from multiple runs."""
    NODE_ID = 'chewbbaca_joinprofiles'
    DISPLAY_NAME = 'chewBBACA JoinProfiles'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Join allele calling results from different runs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_joinprofiles', 'chewBBACA JoinProfiles', 'JoinProfiles', 'allele calling results', 'common loci', 'cgMLST', 'wgMLST', 'bacterial typing']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('JoinedProfile',)
    REQUIRED_EXECUTABLES = ['chewBBACA.py']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True

    @classmethod
    def _profiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('input1', inputs.get('profiles')))

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['chewBBACA.py', 'JoinProfiles', '-p', *cls._profiles(inputs), '-o', 'JoinedProfile.tsv']
        if cls._bool_flag(inputs, 'common'):
            cmd.append('--common')
        return ' && '.join([_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'JoinedProfile.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input1': ('TSV', {'is_list': True, 'multiple': True, 'description': 'AlleleCall result tables'})}, 'optional': {'common': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._profiles(inputs):
            return 'at least one input1 value is required'
        return True


class ChewBBACANSStatsNode(CommandNode):
    """Retrieve Chewie-NS species and schema statistics with chewBBACA."""
    NODE_ID = 'chewbbaca_nsstats'
    DISPLAY_NAME = 'chewBBACA NSStats'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Retrieve basic information about the species and schemas in Chewie-NS.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_nsstats', 'chewBBACA NSStats', 'NSStats', 'Chewie-NS', 'species schemas', 'schema statistics', 'cgMLST', 'bacterial typing']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('NSStats',)
    REQUIRED_EXECUTABLES = ['chewBBACA.py']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True
    MODES = ['species', 'schemas']

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('mode', '') or '')

    @classmethod
    def _species_id(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('species_id', '') or '')

    @classmethod
    def _schema_id(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get('schema_id', '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['chewBBACA.py', 'NSStats', '-m', cls._mode(inputs)]
        _add_if_value(cmd, '--sp', cls._species_id(inputs))
        _add_if_value(cmd, '--sc', cls._schema_id(inputs))
        _add_shell_redirect(cmd, 'NSStats.txt')
        return ' && '.join([_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'NSStats.txt']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mode': ('STRING', {'options': cls.MODES})}, 'optional': {'species_id': ('STRING', {'default': '', 'options': list(ChewBBACADownloadSchemaNode.SPECIES_OPTIONS), 'option_labels': ChewBBACADownloadSchemaNode.SPECIES_OPTIONS}), 'schema_id': ('INT', {'default': '', 'min': 1})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._mode(inputs).strip():
            return 'mode is required'
        if cls._mode(inputs) not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        species_id = cls._species_id(inputs)
        if species_id and species_id not in ChewBBACADownloadSchemaNode.SPECIES_OPTIONS:
            return f"species_id must be one of: {', '.join(ChewBBACADownloadSchemaNode.SPECIES_OPTIONS)}"
        schema_id = cls._schema_id(inputs)
        if schema_id != '':
            try:
                schema_id_value = int(schema_id)
            except (TypeError, ValueError):
                return 'schema_id must be an integer'
            if schema_id_value < 1:
                return 'schema_id must be greater than or equal to 1'
        return True


class ChewBBACAPrepExternalSchemaNode(CommandNode):
    """Adapt external schemas for chewBBACA."""
    NODE_ID = 'chewbbaca_prepexternalschema'
    DISPLAY_NAME = 'chewBBACA PrepExternalSchema'
    REQUIRED_CONDA_PACKAGES = ['chewbbaca', 'blast', 'zip', 'fasttree']
    CATEGORY = 'typing'
    DESCRIPTION = 'Adapt an external schema to be used with chewBBACA.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'chewBBACA', 'chewbbaca_prepexternalschema', 'chewBBACA PrepExternalSchema', 'PrepExternalSchema', 'external schema', 'schema adaptation', 'schema_seed', 'cgMLST', 'bacterial typing']
    RETURN_TYPES = ('ZIP',)
    RETURN_NAMES = ('schema',)
    REQUIRED_EXECUTABLES = ['unzip', 'chewBBACA.py', 'zip']
    DOCUMENTATION_URL = 'https://chewbbaca.readthedocs.io/'
    CITATION_DOIS = [CHEWBBACA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CHEWBBACA_CITATION_DOI}']
    CITATION_TEXT = CHEWBBACA_CITATION_TEXT
    VERSION = '3.3.10+galaxy1'
    SHELL = True

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str) -> bool:
        value = inputs.get(key, False)
        if isinstance(value, str):
            return value.lower() not in {'', 'false', '0', 'no'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['mkdir', '-p', out]), f'cd {shlex.quote(out)}', _shell_join(['unzip', str(inputs.get('input_schema', '')), '-d', 'schema'])]
        cmd = ['chewBBACA.py', 'PrepExternalSchema']
        _add_if_value(cmd, '--ptf', inputs.get('training_file'))
        _add_if_value(cmd, '--gl', inputs.get('genes_list'))
        cmd.extend(['--bsr', str(inputs.get('blast_score_ratio', 0.6)), '--l', str(inputs.get('minimum_length', 0)), '--t', str(inputs.get('translation_table', 11)), '--st', str(inputs.get('size_threshold', 0.2))])
        if cls._bool_flag(inputs, 'size_filter'):
            cmd.append('--size-filter')
        cmd.extend(['-g', 'schema/', '-o', 'schema_seed'])
        commands.append(_shell_join(cmd))
        commands.append('zip -r PExternalschema_seed.zip schema_seed')
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'PExternalschema_seed.zip']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_schema': ('FILE', {'description': 'External schema ZIP archive'})}, 'optional': {'training_file': ('FILE', {'default': ''}), 'genes_list': ('TXT', {'default': ''}), 'minimum_length': ('INT', {'default': 0, 'min': 0}), 'blast_score_ratio': ('FLOAT', {'default': 0.6, 'min': 0, 'max': 1}), 'translation_table': ('INT', {'default': 11, 'min': 0}), 'size_threshold': ('FLOAT', {'default': 0.2, 'min': 0}), 'size_filter': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_schema', '')).strip():
            return 'input_schema is required'
        result = ChewBBACACreateSchemaNode._validate_float_min(inputs, 'blast_score_ratio', 0.6, 0, 1)
        if result is not True:
            return result
        result = ChewBBACACreateSchemaNode._validate_int_min(inputs, 'minimum_length', 0, 0)
        if result is not True:
            return result
        result = ChewBBACACreateSchemaNode._validate_int_min(inputs, 'translation_table', 11, 0)
        if result is not True:
            return result
        result = ChewBBACACreateSchemaNode._validate_float_min(inputs, 'size_threshold', 0.2, 0)
        if result is not True:
            return result
        return True
