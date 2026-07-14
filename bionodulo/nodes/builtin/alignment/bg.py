"""bg — alignment node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class GalaxyDiamondNode(_DiamondGalaxyMixin, CommandNode):
    """Galaxy wrapper-compatible DIAMOND alignment node."""
    NODE_ID = 'bg_diamond'
    DISPLAY_NAME = 'Diamond'
    CATEGORY = 'alignment'
    DESCRIPTION = 'Align protein or translated nucleotide sequences against a protein database with DIAMOND.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bg_diamond', 'diamond', 'Diamond', 'blastp', 'blastx', 'protein alignment', 'translated search', 'DAA']
    RETURN_TYPES = tuple((value[0] for value in DIAMOND_OUTPUT_FORMATS.values())) + ('FASTA', 'FASTA', 'TXT')
    RETURN_NAMES = tuple((value[1] for value in DIAMOND_OUTPUT_FORMATS.values())) + ('unaligned_queries', 'aligned_queries', 'log_file')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        method = str(inputs.get('method', 'blastp') or 'blastp')
        cmd = ['diamond', method, '--threads', str(inputs.get('threads', 12)), '--db', str(inputs.get('database', '')), '--query', str(inputs.get('query', ''))]
        if method == 'blastx':
            _add_if_value(cmd, '--query-gencode', inputs.get('query_gencode', 1))
            _add_if_value(cmd, '--strand', inputs.get('query_strand', 'both'))
            _add_if_value(cmd, '--min-orf', inputs.get('min_orf', 1))
            if inputs.get('frameshift'):
                cmd.extend(['--frameshift', str(inputs.get('frameshift'))])
                if inputs.get('range_culling'):
                    cmd.append('--range-culling')
        elif inputs.get('no_self_hits'):
            cmd.append('--no-self-hits')
        cls._add_output_args(cmd, inputs)
        if cls._outfmt(inputs) != '100':
            cmd.extend(['--compress', '0'])
        sensitivity = str(inputs.get('sensitivity', '') or '')
        if sensitivity:
            cmd.append(sensitivity)
        _add_if_value(cmd, '--gapopen', inputs.get('gapopen'))
        _add_if_value(cmd, '--gapextend', inputs.get('gapextend'))
        cmd.extend(['--matrix', str(inputs.get('matrix', 'BLOSUM62') or 'BLOSUM62'), '--comp-based-stats', str(inputs.get('comp_based_stats', '1') or '1'), '--masking', str(inputs.get('masking', 'tantan') or 'tantan')])
        cls._add_hit_filter_args(cmd, inputs)
        cls._add_score_filter_args(cmd, inputs)
        cls._add_identity_filter_args(cmd, inputs)
        _add_if_value(cmd, '--block-size', inputs.get('block_size', 2))
        query_ext = 'fastq' if cls._query_ext_is_fastq(inputs) else 'fasta'
        selected = cls._selected_optional_query_outputs(inputs)
        if '--un' in selected:
            cmd.extend(['--un', f'{_out(inputs)}/unaligned_queries.{query_ext}', '--unfmt', query_ext])
        if '--al' in selected:
            cmd.extend(['--al', f'{_out(inputs)}/aligned_queries.{query_ext}', '--alfmt', query_ext])
        _add_if_value(cmd, '--max-hsps', inputs.get('max_hsps'))
        cls._add_taxon_filter(cmd, inputs)
        cls._add_taxon_filter(cmd, inputs, prefix='tax_exclude_')
        _add_if_value(cmd, '--seed-cut', inputs.get('seed_cut'))
        if inputs.get('freq_masking'):
            cmd.append('--freq-masking')
        _add_if_value(cmd, '--motif-masking', inputs.get('motif_masking', '0'))
        _add_if_value(cmd, '--soft-masking', inputs.get('soft_masking', '0'))
        if inputs.get('iterate'):
            cmd.append('--iterate')
        if inputs.get('swipe'):
            cmd.append('--swipe')
        cmd.extend(['--algo', str(inputs.get('algo', '0') or '0')])
        _add_if_value(cmd, '--global-ranking', inputs.get('global_ranking'))
        cmd.extend(['--index-chunks', str(inputs.get('index_chunks', 4) or 4), '--file-buffer-size', str(inputs.get('file_buffer_size', 67108864) or 67108864)])
        if inputs.get('log'):
            cmd.append('--log')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._planned_outputs(inputs, output_dir, cls.NODE_ID)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('query', '')).strip():
            return 'query is required'
        if not str(inputs.get('database', '')).strip():
            return 'database is required'
        method = str(inputs.get('method', 'blastp') or 'blastp')
        if method not in {'blastp', 'blastx'}:
            return 'method must be one of: blastp, blastx'
        common_validation = cls._validate_common(inputs)
        if common_validation is not True:
            return common_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTA', {'description': 'Input query file in FASTA or FASTQ format'}), 'database': ('FILE', {'description': 'DIAMOND .dmnd database or staged Galaxy database path'}), 'method': ('STRING', {'default': 'blastp', 'options': ['blastp', 'blastx'], 'description': 'Alignment mode'})}, 'optional': {'threads': ('INT', {'default': 12, 'min': 1, 'max': 128, 'display': 'slider'}), 'outfmt': ('STRING', {'default': '6', 'options': list(DIAMOND_OUTPUT_FORMATS), 'description': 'DIAMOND output format'}), 'fields': ('STRING_LIST', {'default': DIAMOND_DEFAULT_FIELDS.copy(), 'multiple': True, 'options': DIAMOND_FIELD_OPTIONS}), 'header': ('STRING', {'default': '0', 'options': ['0', 'simple', 'verbose'], 'advanced': True}), 'sensitivity': ('STRING', {'default': '', 'options': DIAMOND_SENSITIVITY_OPTIONS}), 'filter_score_select': ('STRING', {'default': 'evalue', 'options': ['evalue', 'min-score']}), 'evalue': ('FLOAT', {'default': 0.001, 'min': 0}), 'min_score': ('INT', {'default': 0, 'min': 0}), 'hit_filter_select': ('STRING', {'default': 'max', 'options': ['max', 'top']}), 'max_target_seqs': ('INT', {'default': 25, 'min': 0}), 'top': ('INT', {'default': 0, 'min': 0, 'max': 100}), 'id': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'approx_id': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'query_cover': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'subject_cover': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'matrix': ('STRING', {'default': 'BLOSUM62', 'advanced': True}), 'gapopen': ('INT', {'default': '', 'advanced': True}), 'gapextend': ('INT', {'default': '', 'advanced': True}), 'comp_based_stats': ('STRING', {'default': '1', 'options': ['0', '1', '2', '3', '4', '5'], 'advanced': True}), 'masking': ('STRING', {'default': 'tantan', 'options': ['none', 'tantan', 'seg'], 'advanced': True}), 'query_gencode': ('INT', {'default': 1, 'min': 1, 'advanced': True}), 'query_strand': ('STRING', {'default': 'both', 'options': ['both', 'plus', 'minus'], 'advanced': True}), 'min_orf': ('INT', {'default': 1, 'min': 1, 'advanced': True}), 'frameshift': ('INT', {'default': '', 'advanced': True}), 'range_culling': ('BOOLEAN', {'default': False, 'advanced': True}), 'tax_select': ('STRING', {'default': 'no', 'options': ['no', 'list', 'file'], 'advanced': True}), 'taxonlist': ('STRING', {'default': '', 'advanced': True}), 'tax_exclude_select': ('STRING', {'default': 'no', 'options': ['no', 'list', 'file'], 'advanced': True}), 'taxon_exclude': ('STRING', {'default': '', 'advanced': True}), 'output_unal': ('STRING_LIST', {'default': [], 'multiple': True, 'options': ['--un', '--al'], 'description': 'Optional query FASTA/FASTQ outputs'}), 'log': ('BOOLEAN', {'default': False, 'description': 'Output a DIAMOND log file'}), 'max_hsps': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'seed_cut': ('FLOAT', {'default': '', 'min': 0, 'advanced': True}), 'freq_masking': ('BOOLEAN', {'default': False, 'advanced': True}), 'motif_masking': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'soft_masking': ('STRING', {'default': '0', 'options': ['0', 'seg', 'tantan'], 'advanced': True}), 'iterate': ('BOOLEAN', {'default': False, 'advanced': True}), 'swipe': ('BOOLEAN', {'default': False, 'advanced': True}), 'algo': ('STRING', {'default': '0', 'options': ['0', '1', 'ctg'], 'advanced': True}), 'global_ranking': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'block_size': ('FLOAT', {'default': 2, 'min': 0, 'advanced': True}), 'index_chunks': ('INT', {'default': 4, 'min': 1, 'advanced': True}), 'file_buffer_size': ('INT', {'default': 67108864, 'min': 1, 'advanced': True}), 'include_lineage': ('BOOLEAN', {'default': False, 'advanced': True}), 'no_self_hits': ('BOOLEAN', {'default': True, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class GalaxyDiamondViewNode(_DiamondGalaxyMixin, CommandNode):
    """Galaxy wrapper-compatible DIAMOND view node."""
    NODE_ID = 'bg_diamond_view'
    DISPLAY_NAME = 'Diamond view'
    CATEGORY = 'alignment'
    DESCRIPTION = 'Generate formatted DIAMOND output from DAA alignment files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bg_diamond_view', 'diamond', 'Diamond view', 'DAA', 'diamond view', 'BLAST XML', 'SAM']
    RETURN_TYPES = tuple((value[0] for value in DIAMOND_OUTPUT_FORMATS.values()))
    RETURN_NAMES = tuple((value[1] for value in DIAMOND_OUTPUT_FORMATS.values()))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['diamond', 'view', '--threads', str(inputs.get('threads', 1)), '--daa', str(inputs.get('daa', ''))]
        cls._add_output_args(cmd, inputs)
        cls._add_hit_filter_args(cmd, inputs)
        cls._add_identity_filter_args(cmd, inputs)
        if inputs.get('forwardonly'):
            cmd.append('--forwardonly')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('daa', '')).strip():
            return 'daa is required'
        common_validation = cls._validate_common(inputs)
        if common_validation is not True:
            return common_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'daa': ('FILE', {'description': 'Input DIAMOND DAA alignment file'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'outfmt': ('STRING', {'default': '6', 'options': list(DIAMOND_OUTPUT_FORMATS), 'description': 'DIAMOND output format'}), 'fields': ('STRING_LIST', {'default': DIAMOND_DEFAULT_FIELDS.copy(), 'multiple': True, 'options': DIAMOND_FIELD_OPTIONS}), 'header': ('STRING', {'default': '0', 'options': ['0', 'simple', 'verbose'], 'advanced': True}), 'hit_filter_select': ('STRING', {'default': 'max', 'options': ['max', 'top']}), 'max_target_seqs': ('INT', {'default': 25, 'min': 0}), 'top': ('INT', {'default': 0, 'min': 0, 'max': 100}), 'id': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'approx_id': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'query_cover': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'subject_cover': ('FLOAT', {'default': 0, 'min': 0, 'max': 100}), 'include_lineage': ('BOOLEAN', {'default': False, 'advanced': True}), 'forwardonly': ('BOOLEAN', {'default': False, 'description': 'Only show alignments of the forward strand'})}, 'hidden': {'output': ('STRING', {})}}
