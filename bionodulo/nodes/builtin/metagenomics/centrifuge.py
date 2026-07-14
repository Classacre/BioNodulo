"""centrifuge — metagenomics node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _DiamondGalaxyMixin:
    REQUIRED_CONDA_PACKAGES = ['diamond']
    REQUIRED_EXECUTABLES = ['diamond']
    DOCUMENTATION_URL = 'https://github.com/bbuchfink/diamond/wiki'
    CITATION_DOIS = [DIAMOND_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{DIAMOND_CITATION_DOI}']
    CITATION_TEXT = DIAMOND_CITATION_TEXT
    VERSION = '2.2.2+galaxy0'

    @classmethod
    def _outfmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('outfmt', '6') or '6')

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return DIAMOND_OUTPUT_FORMATS.get(cls._outfmt(inputs), DIAMOND_OUTPUT_FORMATS['6'])[2]

    @classmethod
    def _selected_fields(cls, inputs: dict[str, Any]) -> list[str]:
        fields = _as_list(inputs.get('fields'))
        if len(fields) == 1 and ' ' in fields[0]:
            fields = [field for field in fields[0].replace(',', ' ').split() if field]
        elif len(fields) == 1 and ',' in fields[0]:
            fields = [field for field in fields[0].split(',') if field]
        return fields or DIAMOND_DEFAULT_FIELDS.copy()

    @classmethod
    def _add_output_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        outfmt = cls._outfmt(inputs)
        cmd.extend(['--outfmt', outfmt])
        if outfmt in {'6', '104'}:
            cmd.extend(cls._selected_fields(inputs))
            if outfmt == '6':
                cmd.extend(['--header', str(inputs.get('header', '0') or '0')])
        cmd.extend(['--out', f'{_out(inputs)}/{cls._output_filename(inputs)}'])
        if outfmt == '102' and inputs.get('include_lineage'):
            cmd.append('--include-lineage')

    @classmethod
    def _add_hit_filter_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get('hit_filter_select', 'max') or 'max') == 'max':
            cmd.extend(['--max-target-seqs', str(inputs.get('max_target_seqs', 25) or 25)])
        else:
            cmd.extend(['--top', str(inputs.get('top', 0) or 0)])

    @classmethod
    def _add_identity_filter_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        _add_if_value(cmd, '--id', inputs.get('id', 0))
        _add_if_value(cmd, '--approx-id', inputs.get('approx_id', 0))
        _add_if_value(cmd, '--query-cover', inputs.get('query_cover', 0))
        _add_if_value(cmd, '--subject-cover', inputs.get('subject_cover', 0))

    @classmethod
    def _add_score_filter_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get('filter_score_select', 'evalue') or 'evalue') == 'evalue':
            cmd.extend(['--evalue', str(inputs.get('evalue', 0.001) or 0.001)])
        else:
            cmd.extend(['--min-score', str(inputs.get('min_score', 0) or 0)])

    @classmethod
    def _add_taxon_filter(cls, cmd: list[str], inputs: dict[str, Any], *, prefix: str='') -> None:
        selector_key = 'tax_exclude_select' if prefix == 'tax_exclude_' else 'tax_select'
        selector = str(inputs.get(selector_key, 'no') or 'no')
        key = 'taxon_exclude' if prefix == 'tax_exclude_' else 'taxonlist'
        flag = '--taxon_exclude' if prefix == 'tax_exclude_' else '--taxonlist'
        if selector in {'list', 'file'}:
            _add_if_value(cmd, flag, inputs.get(key))

    @classmethod
    def _selected_optional_query_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('output_unal'))

    @classmethod
    def _query_ext_is_fastq(cls, inputs: dict[str, Any]) -> bool:
        return 'fastq' in Path(str(inputs.get('query', ''))).suffixes or 'fastq' in str(inputs.get('query', '')).lower()

    @classmethod
    def _planned_outputs(cls, inputs: dict[str, Any], output_dir: str | Path, node_id: str) -> list[Path]:
        out = Path(output_dir) / node_id
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._output_filename(inputs)]
        selected = cls._selected_optional_query_outputs(inputs)
        query_ext = 'fastq' if cls._query_ext_is_fastq(inputs) else 'fasta'
        if '--un' in selected:
            outputs.append(out / f'unaligned_queries.{query_ext}')
        if '--al' in selected:
            outputs.append(out / f'aligned_queries.{query_ext}')
        if inputs.get('log'):
            outputs.append(out / 'diamond.log')
        return outputs

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        outfmt = cls._outfmt(inputs)
        if outfmt not in DIAMOND_OUTPUT_FORMATS:
            return f"outfmt must be one of: {', '.join(DIAMOND_OUTPUT_FORMATS)}"
        selected = cls._selected_optional_query_outputs(inputs)
        unsupported = [name for name in selected if name not in {'--un', '--al'}]
        if unsupported:
            return f"output_unal contains unsupported values: {', '.join(unsupported)}"
        hit_filter = str(inputs.get('hit_filter_select', 'max') or 'max')
        if hit_filter not in {'max', 'top'}:
            return 'hit_filter_select must be one of: max, top'
        filter_score = str(inputs.get('filter_score_select', 'evalue') or 'evalue')
        if filter_score not in {'evalue', 'min-score'}:
            return 'filter_score_select must be one of: evalue, min-score'
        return True
class _Beacon2SearchBaseNode(CommandNode):
    """Shared command rendering for Beacon2 import wrappers that query MongoDB collections."""
    REQUIRED_CONDA_PACKAGES = ['beacon2-import']
    CATEGORY = 'metadata'
    REQUIRED_EXECUTABLES = ['beacon2-search']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2-import'
    CITATION_DOIS = [BEACON2_IMPORT_DOI]
    CITATION_URLS = [f'{DOI_URL}{BEACON2_IMPORT_DOI}']
    CITATION_TEXT = BEACON2_IMPORT_CITATION_TEXT
    VERSION = '2.2.4+galaxy0'
    SHELL = True
    SEARCH_COLLECTION = ''
    OUTPUT_FILENAME = ''
    REQUIRED_QUERY_FLAGS: tuple[tuple[str, str, str, str], ...] = ()
    QUERY_FLAGS: tuple[tuple[str, str, str], ...] = ()
    TYPED_QUERY_FLAGS: tuple[tuple[str, str, str, str], ...] = ()
    QUERY_FLAG_OPTIONS: dict[str, list[str]] = {}

    @classmethod
    def _db_host(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('db_host', '127.0.0.1') or '127.0.0.1')

    @classmethod
    def _db_port(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get('db_port', 27017) or 27017)

    @classmethod
    def _credentials_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/beacon2_db_auth.json'

    @classmethod
    def _credentials_json(cls, inputs: dict[str, Any]) -> str:
        credentials = {'db_auth_source': str(inputs.get('db_auth_source', 'admin') or 'admin'), 'db_user': str(inputs.get('db_user', 'root') or 'root'), 'db_password': str(inputs.get('db_password', 'example') or 'example')}
        return json.dumps(credentials, indent=2)

    @classmethod
    def _query_cmd(cls, inputs: dict[str, Any], credentials_path: str) -> list[str]:
        cmd = ['beacon2-search', cls.SEARCH_COLLECTION, '--db-host', cls._db_host(inputs), '--db-port', str(cls._db_port(inputs)), '--database', str(inputs.get('database', '')), '--collection', str(inputs.get('collection', '')), '--advance-connection', '--db-auth-config', credentials_path]
        for key, flag, _type_name, _description in cls.REQUIRED_QUERY_FLAGS:
            cmd.extend([flag, str(inputs.get(key, ''))])
        for key, flag, _description in cls.QUERY_FLAGS:
            value = inputs.get(key)
            if value is not None and str(value) != '':
                cmd.extend([flag, str(value)])
        cmd.extend(['>', f'{_out(inputs)}/{cls.OUTPUT_FILENAME}'])
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        credentials_path = cls._credentials_path(inputs)
        config = f"cat > {shlex.quote(credentials_path)} <<'JSON'\n{cls._credentials_json(inputs)}\nJSON\n"
        return ' && '.join([f'mkdir -p {shlex.quote(out)}', f'{config}{_shell_join(cls._query_cmd(inputs, credentials_path))}'])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('database', '')).strip():
            return 'database is required'
        if not str(inputs.get('collection', '')).strip():
            return 'collection is required'
        try:
            cls._db_port(inputs)
        except (TypeError, ValueError):
            return 'db_port must be an integer'
        for key, _flag, type_name, _description in cls.REQUIRED_QUERY_FLAGS:
            value = inputs.get(key)
            if value is None or str(value) == '':
                return f'{key} is required'
            if type_name == 'INT':
                try:
                    int(value)
                except (TypeError, ValueError):
                    return f'{key} must be an integer'
        for key, _flag, type_name, _description in cls.TYPED_QUERY_FLAGS:
            value = inputs.get(key)
            if value is not None and str(value) != '':
                if type_name == 'INT':
                    try:
                        int(value)
                    except (TypeError, ValueError):
                        return f'{key} must be an integer'
                options = cls.QUERY_FLAG_OPTIONS.get(key)
                if options is not None and str(value) not in options:
                    return f"{key} must be one of: {', '.join(options)}"
        for key, _flag, _description in cls.QUERY_FLAGS:
            value = inputs.get(key)
            options = cls.QUERY_FLAG_OPTIONS.get(key)
            if options is not None and value is not None and (str(value) != '') and (str(value) not in options):
                return f"{key} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {'db_host': ('STRING', {'default': '127.0.0.1', 'description': 'Hostname or IP address of the Beacon MongoDB database'}), 'db_port': ('INT', {'default': 27017, 'description': 'Port of the Beacon MongoDB database'}), 'db_auth_source': ('STRING', {'default': 'admin', 'advanced': True, 'description': 'MongoDB authentication source for Beacon2 queries'}), 'db_user': ('STRING', {'default': 'root', 'advanced': True, 'description': 'MongoDB username for Beacon2 queries'}), 'db_password': ('STRING', {'default': 'example', 'advanced': True, 'description': 'MongoDB password for Beacon2 queries'})}
        for key, _flag, description in cls.QUERY_FLAGS:
            metadata: dict[str, Any] = {'default': '', 'description': description}
            options = cls.QUERY_FLAG_OPTIONS.get(key)
            if options is not None:
                metadata['options'] = options
            optional[key] = ('STRING', metadata)
        for key, _flag, type_name, description in cls.TYPED_QUERY_FLAGS:
            metadata = {'default': '', 'description': description}
            options = cls.QUERY_FLAG_OPTIONS.get(key)
            if options is not None:
                metadata['options'] = options
            optional[key] = (type_name, metadata)
        required: dict[str, Any] = {'database': ('STRING', {'description': 'Targeted Beacon database'}), 'collection': ('STRING', {'description': 'Targeted Beacon collection in the selected database'})}
        for key, _flag, type_name, description in cls.REQUIRED_QUERY_FLAGS:
            required[key] = (type_name, {'description': description})
        return {'required': required, 'optional': optional, 'hidden': {'output': ('STRING', {})}}


class CentrifugeNode(CommandNode):
    """Classify metagenomic reads with Centrifuge."""
    NODE_ID = 'centrifuge'
    DISPLAY_NAME = 'Centrifuge'
    REQUIRED_CONDA_PACKAGES = ['centrifuge']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Read-based metagenome characterization with Centrifuge.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Centrifuge', 'metagenomic classification', 'taxonomic classification', 'read-based metagenomics', 'SRA accession', 'FM index']
    RETURN_TYPES = ('TSV', 'SAM', 'TSV')
    RETURN_NAMES = ('tabular_output', 'sam_output', 'report')
    REQUIRED_EXECUTABLES = ['centrifuge']
    DOCUMENTATION_URL = 'https://ccb.jhu.edu/software/centrifuge/'
    CITATION_DOIS = ['10.1101/gr.210641.116']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.210641.116']
    CITATION_TEXT = 'Centrifuge: rapid and sensitive classification of metagenomic sequences.'
    VERSION = '1.0.4_beta'
    SHELL = True
    _DEFAULT_TAB_COLUMNS = 'readID,seqID,taxID,score,2ndBestScore,hitLength,queryLength,numMatches'
    _TAB_COLUMNS = {'readID', 'seqID', 'taxID', 'score', '2ndBestScore', 'hitLength', 'queryLength', 'numMatches'}

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _paired_values(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        raw_paired_values = inputs.get('paired_reads')
        if raw_paired_values is None or raw_paired_values == '':
            paired_values: list[Any] = []
        elif isinstance(raw_paired_values, (list, tuple)) and len(raw_paired_values) >= 2 and (not isinstance(raw_paired_values[0], (dict, list, tuple))):
            paired_values = [raw_paired_values]
        elif isinstance(raw_paired_values, (list, tuple)):
            paired_values = list(raw_paired_values)
        else:
            paired_values = [raw_paired_values]
        pairs: list[tuple[str, str]] = []
        for value in paired_values:
            if isinstance(value, dict):
                forward = value.get('forward', value.get('input_1', value.get('r1', '')))
                reverse = value.get('reverse', value.get('input_2', value.get('r2', '')))
                pairs.append((str(forward), str(reverse)))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                pairs.append((str(value[0]), str(value[1])))
            elif value:
                pair_root = str(value).rstrip('/')
                pairs.append((f'{pair_root}/forward', f'{pair_root}/reverse'))
        return pairs

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return 'centrifuge_output.sam' if str(inputs.get('out_fmt', 'tab')) == 'sam' else 'centrifuge_output.tsv'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('db', '')).strip():
            return 'Centrifuge database is required'
        if not _as_list(inputs.get('unpaired_reads')) and (not cls._paired_values(inputs)) and (not str(inputs.get('sra', '')).strip()):
            return 'At least one unpaired read, paired read collection, or SRA accession is required'
        if inputs.get('norc', False) and inputs.get('nofw', False):
            return 'Centrifuge cannot disable both forward and reverse-complement mapping'
        try:
            min_hitlen = int(inputs.get('min_hitlen', 22))
        except (TypeError, ValueError):
            return 'Minimum hit length must be an integer'
        if min_hitlen < 16:
            return 'Minimum hit length must be at least 16'
        columns = str(inputs.get('tab_fmt_cols', cls._DEFAULT_TAB_COLUMNS))
        for column in columns.split(','):
            if column and column not in cls._TAB_COLUMNS:
                return f'Unsupported Centrifuge tabular output column: {column}'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['centrifuge', '--out-fmt', str(inputs.get('out_fmt', 'tab')), '--tab-fmt-cols', str(inputs.get('tab_fmt_cols', cls._DEFAULT_TAB_COLUMNS)), '--threads', str(inputs.get('threads', 1))]
        for key, flag in (('skip', '--skip'), ('upto', '--upto'), ('trim5', '--trim5'), ('trim3', '--trim3')):
            _add_if_value(cmd, flag, inputs.get(key))
        for key, flag in (('ignore_quals', '--ignore-quals'), ('nofw', '--nofw'), ('norc', '--norc'), ('non_deterministic', '--non-deterministic')):
            if inputs.get(key, False):
                cmd.append(flag)
        _add_if_value(cmd, '--seed', inputs.get('seed'))
        cmd.extend(['--min-hitlen', str(inputs.get('min_hitlen', 22))])
        _add_if_value(cmd, '--min-totallen', inputs.get('min_totallen'))
        _add_if_value(cmd, '--host-taxids', inputs.get('host_taxids'))
        _add_if_value(cmd, '--exclude-taxids', inputs.get('exclude_taxids'))
        cmd.extend(['-x', str(inputs.get('db', ''))])
        for read_path in _as_list(inputs.get('unpaired_reads')):
            cmd.extend(['-U', read_path])
        for forward, reverse in cls._paired_values(inputs):
            cmd.extend(['-1', forward, '-2', reverse])
        _add_if_value(cmd, '--sra-acc', inputs.get('sra'))
        cmd.extend(['-S', cls._out_path(inputs, cls._output_filename(inputs)), '--report-file', cls._out_path(inputs, 'centrifuge_report.tsv')])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs), out / 'centrifuge_report.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'db': ('DIRECTORY', {'description': 'Centrifuge index filename prefix or database directory'})}, 'optional': {'unpaired_reads': ('FASTQ', {'default': [], 'multiple': True, 'description': 'One or more unpaired FASTQ read files'}), 'paired_reads': ('FASTQ_LIST', {'default': [], 'multiple': True, 'description': 'One or more paired read collections'}), 'sra': ('STRING', {'default': '', 'description': 'Comma-separated SRA accessions, e.g. SRR353653,SRR353654'}), 'out_fmt': ('STRING', {'default': 'tab', 'options': ['tab', 'sam'], 'description': 'Classification output format'}), 'tab_fmt_cols': ('STRING', {'default': cls._DEFAULT_TAB_COLUMNS, 'description': 'Comma-separated output columns for tabular Centrifuge output'}), 'skip': ('INT', {'default': '', 'min': 0, 'description': 'Initial reads or read pairs to skip'}), 'upto': ('INT', {'default': '', 'min': 0, 'description': 'Stop after this many reads or read pairs'}), 'trim5': ('INT', {'default': '', 'min': 0, 'description': 'Trim bases from the 5 prime end'}), 'trim3': ('INT', {'default': '', 'min': 0, 'description': 'Trim bases from the 3 prime end'}), 'ignore_quals': ('BOOLEAN', {'default': False, 'description': 'Treat all quality values as Phred 30'}), 'nofw': ('BOOLEAN', {'default': False, 'description': 'Do not align the forward strand'}), 'norc': ('BOOLEAN', {'default': False, 'description': 'Do not align the reverse-complement strand'}), 'seed': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'non_deterministic': ('BOOLEAN', {'default': False, 'description': 'Use non-deterministic random seeding', 'advanced': True}), 'min_hitlen': ('INT', {'default': 22, 'min': 16, 'description': 'Minimum length of partial hits'}), 'min_totallen': ('INT', {'default': '', 'min': 0, 'description': 'Minimum summed length of partial hits per read'}), 'host_taxids': ('STRING', {'default': '', 'description': 'Comma-separated host taxonomic IDs', 'advanced': True}), 'exclude_taxids': ('STRING', {'default': '', 'description': 'Comma-separated taxonomic IDs to exclude', 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
