"""kraken — metagenomics node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class KrakenNode(CommandNode):
    """Assign taxonomy to reads with classic Kraken."""
    NODE_ID = 'kraken'
    DISPLAY_NAME = 'Kraken'
    REQUIRED_CONDA_PACKAGES = ['kraken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Assign taxonomic labels to sequencing reads with Kraken.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Kraken', 'taxonomic classification', 'metagenomics', 'k-mer exact alignment', 'classified reads', 'unclassified reads', 'quick mode']
    RETURN_TYPES = ('KRAKEN_OUTPUT', 'FASTQ', 'FASTQ')
    RETURN_NAMES = ('classification', 'classified_reads', 'unclassified_reads')
    REQUIRED_EXECUTABLES = ['kraken']
    DOCUMENTATION_URL = 'http://ccb.jhu.edu/software/kraken/'
    CITATION_DOIS = ['10.1186/gb-2014-15-3-r46']
    CITATION_URLS = [f'{DOI_URL}10.1186/gb-2014-15-3-r46']
    CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
    VERSION = '1.1.1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/classification.kraken'

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get('input_format', '')).lower()
        if input_format in {'fasta', 'fastq'}:
            return input_format
        paths = [str(inputs.get('input_sequences', '')), str(inputs.get('forward_input', '')), str(inputs.get('reverse_input', ''))]
        raw_pair = inputs.get('input_pair')
        if isinstance(raw_pair, dict):
            paths.extend([str(raw_pair.get('forward', '')), str(raw_pair.get('reverse', ''))])
        elif isinstance(raw_pair, (list, tuple)):
            paths.extend((str(value) for value in raw_pair))
        if any((Path(path).suffix.lower() in {'.fa', '.fasta', '.fna'} for path in paths if path)):
            return 'fasta'
        return 'fastq'

    @classmethod
    def _paired_collection(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        pair = inputs.get('input_pair')
        if isinstance(pair, dict):
            return (str(pair.get('forward', '')), str(pair.get('reverse', '')))
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return (str(pair[0]), str(pair[1]))
        if pair:
            root = str(pair).rstrip('/')
            return (f'{root}/forward', f'{root}/reverse')
        return ('', '')

    @classmethod
    def _read_inputs(cls, inputs: dict[str, Any]) -> list[str]:
        input_type = str(inputs.get('input_type', 'single'))
        if input_type == 'paired':
            return [str(inputs.get('forward_input', '')), str(inputs.get('reverse_input', ''))]
        if input_type == 'paired_collection':
            return list(cls._paired_collection(inputs))
        return [str(inputs.get('input_sequences', ''))]

    @classmethod
    def _split_suffix(cls, inputs: dict[str, Any]) -> str:
        return 'fasta' if cls._input_format(inputs) == 'fasta' else 'fastq'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('db', '')).strip():
            return 'Kraken database is required'
        input_type = str(inputs.get('input_type', 'single'))
        if input_type == 'paired':
            if not str(inputs.get('forward_input', '')).strip() or not str(inputs.get('reverse_input', '')).strip():
                return 'Forward and reverse reads are required for paired input'
        elif input_type == 'paired_collection':
            forward, reverse = cls._paired_collection(inputs)
            if not forward or not reverse:
                return 'Paired collection input is required'
        elif not str(inputs.get('input_sequences', '')).strip():
            return 'Single-end input sequences are required'
        if str(inputs.get('quick', 'no')) == 'yes':
            try:
                min_hits = int(inputs.get('min_hits', 1))
            except (TypeError, ValueError):
                return 'Quick mode min_hits must be an integer'
            if min_hits < 1:
                return 'Quick mode min_hits must be at least 1'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_type = str(inputs.get('input_type', 'single'))
        input_format = cls._input_format(inputs)
        cmd = ['kraken', '--threads', str(inputs.get('threads', 1)), '--db', str(inputs.get('db', ''))]
        if inputs.get('only_classified_output', False):
            cmd.append('--only-classified-output')
        if str(inputs.get('quick', 'no')) == 'yes':
            cmd.extend(['--quick', '--min-hits', str(inputs.get('min_hits', 1))])
        cmd.append('--fastq-input' if input_format == 'fastq' else '--fasta-input')
        cmd.extend((read for read in cls._read_inputs(inputs) if read))
        if input_type in {'paired', 'paired_collection'}:
            cmd.append('--paired')
            if inputs.get('check_names', False):
                cmd.append('--check-names')
        if inputs.get('split_reads', False):
            suffix = cls._split_suffix(inputs)
            cmd.extend(['--classified-out', f'{_out(inputs)}/classified_reads.{suffix}', '--unclassified-out', f'{_out(inputs)}/unclassified_reads.{suffix}'])
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'classification.kraken']
        if inputs.get('split_reads', False):
            suffix = cls._split_suffix(inputs)
            outputs.extend([out / f'classified_reads.{suffix}', out / f'unclassified_reads.{suffix}'])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'paired', 'paired_collection'], 'description': 'Single reads, paired reads, or a paired collection'}), 'db': ('DIRECTORY', {'description': 'Kraken database directory'}), 'input_sequences': ('FASTQ', {'description': 'Single-end FASTA or FASTQ reads', 'displayOptions': {'show': {'input_type': ['single']}}})}, 'optional': {'forward_input': ('FASTQ', {'default': '', 'description': 'Forward reads for paired input', 'displayOptions': {'show': {'input_type': ['paired']}}}), 'reverse_input': ('FASTQ', {'default': '', 'description': 'Reverse reads for paired input', 'displayOptions': {'show': {'input_type': ['paired']}}}), 'input_pair': ('FASTQ_LIST', {'default': [], 'description': 'Paired read collection as [forward, reverse] or mapping', 'displayOptions': {'show': {'input_type': ['paired_collection']}}}), 'input_format': ('STRING', {'default': 'fastq', 'options': ['fastq', 'fasta'], 'description': 'Input read format'}), 'split_reads': ('BOOLEAN', {'default': False, 'description': 'Write classified and unclassified read outputs'}), 'quick': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'description': 'Enable Kraken quick operation'}), 'min_hits': ('INT', {'default': 1, 'min': 1, 'description': 'Number of hits required for classification in quick mode', 'displayOptions': {'show': {'quick': ['yes']}}}), 'only_classified_output': ('BOOLEAN', {'default': False, 'description': 'Print no Kraken output for unclassified sequences'}), 'check_names': ('BOOLEAN', {'default': False, 'description': 'Verify paired read names match', 'displayOptions': {'show': {'input_type': ['paired', 'paired_collection']}}}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class KrakenReportNode(CommandNode):
    """Generate a classic Kraken taxonomy report."""
    NODE_ID = 'kraken_report'
    DISPLAY_NAME = 'Kraken Report'
    REQUIRED_CONDA_PACKAGES = ['kraken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate a tabular sample report from classic Kraken classification output.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Kraken Report', 'kraken-report', 'sample report', 'taxonomy summary', 'classification report', 'NCBI taxonomy ID']
    RETURN_TYPES = ('KRAKEN_REPORT',)
    RETURN_NAMES = ('report',)
    REQUIRED_EXECUTABLES = ['kraken-report']
    DOCUMENTATION_URL = 'http://ccb.jhu.edu/software/kraken/'
    CITATION_DOIS = ['10.1186/gb-2014-15-3-r46']
    CITATION_URLS = [f'{DOI_URL}10.1186/gb-2014-15-3-r46']
    CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
    VERSION = '1.3.1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/kraken_report.tsv'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('db', '')).strip():
            return 'Kraken database is required'
        if not str(inputs.get('kraken_output', '')).strip():
            return 'Kraken classification output is required'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['kraken-report', '--db', str(inputs.get('db', '')), str(inputs.get('kraken_output', ''))]
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'kraken_report.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'kraken_output': ('KRAKEN_OUTPUT', {'description': 'Taxonomy classification produced by Kraken'}), 'db': ('DIRECTORY', {'description': 'Kraken database used for the original classification'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}


class KrakenFilterNode(CommandNode):
    """Filter classic Kraken classification output by confidence threshold."""
    NODE_ID = 'kraken_filter'
    DISPLAY_NAME = 'Kraken Filter'
    REQUIRED_CONDA_PACKAGES = ['kraken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Filter classic Kraken classification output by confidence score.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Kraken Filter', 'kraken-filter', 'confidence threshold', 'classification filter', 'taxonomy confidence', 'unclassified']
    RETURN_TYPES = ('KRAKEN_OUTPUT',)
    RETURN_NAMES = ('filtered_output',)
    REQUIRED_EXECUTABLES = ['kraken-filter']
    DOCUMENTATION_URL = 'http://ccb.jhu.edu/software/kraken/'
    CITATION_DOIS = ['10.1186/gb-2014-15-3-r46']
    CITATION_URLS = [f'{DOI_URL}10.1186/gb-2014-15-3-r46']
    CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
    VERSION = '1.3.1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/filtered_output.kraken'

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> float:
        return float(inputs.get('threshold', 0))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('db', '')).strip():
            return 'Kraken database is required'
        if not str(inputs.get('input', '')).strip():
            return 'Kraken classification output is required'
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return 'Confidence threshold must be a number between 0 and 1'
        if not 0 <= threshold <= 1:
            return 'Confidence threshold must be between 0 and 1'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['kraken-filter', '--db', str(inputs.get('db', '')), '--threshold', str(inputs.get('threshold', 0)), str(inputs.get('input', ''))]
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'filtered_output.kraken']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('KRAKEN_OUTPUT', {'description': 'Taxonomy classification produced by Kraken'}), 'db': ('DIRECTORY', {'description': 'Kraken database used for the original classification'})}, 'optional': {'threshold': ('FLOAT', {'default': 0, 'min': 0, 'max': 1, 'description': 'Confidence threshold between 0 and 1'})}, 'hidden': {'output': ('STRING', {})}}


class KrakenTranslateNode(CommandNode):
    """Convert classic Kraken taxonomy IDs to lineage names."""
    NODE_ID = 'kraken_translate'
    DISPLAY_NAME = 'Kraken Translate'
    REQUIRED_CONDA_PACKAGES = ['kraken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Convert Kraken taxonomy IDs into taxonomic lineage names.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Kraken Translate', 'kraken-translate', 'taxonomy labels', 'lineage names', 'MPA format', 'standard ranks']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('translated',)
    REQUIRED_EXECUTABLES = ['kraken-translate']
    DOCUMENTATION_URL = 'http://ccb.jhu.edu/software/kraken/'
    CITATION_DOIS = ['10.1186/gb-2014-15-3-r46']
    CITATION_URLS = [f'{DOI_URL}10.1186/gb-2014-15-3-r46']
    CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
    VERSION = '1.3.1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/translated.tsv'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('db', '')).strip():
            return 'Kraken database is required'
        if not str(inputs.get('input', '')).strip():
            return 'Kraken classification output is required'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['kraken-translate', '--db', str(inputs.get('db', ''))]
        if inputs.get('mpa_format', False):
            cmd.append('--mpa-format')
        cmd.append(str(inputs.get('input', '')))
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'translated.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Taxonomy classification produced by Kraken'}), 'db': ('DIRECTORY', {'description': 'Kraken database used for the original classification'})}, 'optional': {'mpa_format': ('BOOLEAN', {'default': False, 'description': 'Restrict labels to standard rank assignments in MPA format'})}, 'hidden': {'output': ('STRING', {})}}


class KrakenMpaReportNode(CommandNode):
    """Generate a classic Kraken MPA-style multi-sample report."""
    NODE_ID = 'kraken_mpa_report'
    DISPLAY_NAME = 'Kraken MPA Report'
    REQUIRED_CONDA_PACKAGES = ['kraken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Summarize classic Kraken classifications across taxonomic ranks for multiple samples.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Kraken MPA Report', 'kraken-mpa-report', 'multiple samples', 'taxonomic ranks', 'MetaPhlAn style', 'show zeros', 'header line']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output_report',)
    REQUIRED_EXECUTABLES = ['kraken-mpa-report']
    DOCUMENTATION_URL = 'http://ccb.jhu.edu/software/kraken/'
    CITATION_DOIS = ['10.1186/gb-2014-15-3-r46']
    CITATION_URLS = [f'{DOI_URL}10.1186/gb-2014-15-3-r46']
    CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
    VERSION = '1.3.1'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_report.tsv'

    @classmethod
    def _sample_names(cls, classifications: list[str], identifiers: list[str]) -> list[str]:
        names: list[str] = []
        for index, classification in enumerate(classifications):
            if index < len(identifiers) and identifiers[index]:
                name_base = str(identifiers[index]).replace('/', '-').replace('\t', '-')
            else:
                name_base = classification
            name = name_base
            duplicate_index = 1
            while name in names:
                name = f'{name_base}_{duplicate_index}'
                duplicate_index += 1
            names.append(name)
        return names

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('db', '')).strip():
            return 'Kraken database is required'
        if not _as_list(inputs.get('classification')):
            return 'At least one Kraken classification output is required'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        classifications = _as_list(inputs.get('classification'))
        names = cls._sample_names(classifications, _as_list(inputs.get('element_identifiers')))
        setup = [f'ln -s {shlex.quote(classification)} {shlex.quote(name)}' for classification, name in zip(classifications, names) if classification != name]
        cmd = ['kraken-mpa-report', '--db', str(inputs.get('db', '')), *names]
        if inputs.get('show_zeros', False):
            cmd.append('--show-zeros')
        if inputs.get('header_line', False):
            cmd.append('--header-line')
        _add_shell_redirect(cmd, cls._output_path(inputs))
        rendered = _shell_join(cmd)
        if setup:
            return ' && '.join([*setup, rendered])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output_report.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'classification': ('TSV', {'multiple': True, 'description': 'One or more Kraken classification outputs'}), 'db': ('DIRECTORY', {'description': 'Kraken database used for the original classification'})}, 'optional': {'element_identifiers': ('STRING', {'default': [], 'multiple': True, 'description': 'Optional Galaxy element identifiers for sample names'}), 'show_zeros': ('BOOLEAN', {'default': False, 'description': 'Display taxa even if they lack reads in every sample'}), 'header_line': ('BOOLEAN', {'default': False, 'description': 'Display a header line indicating sample IDs'})}, 'hidden': {'output': ('STRING', {})}}
