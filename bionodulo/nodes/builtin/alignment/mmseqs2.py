"""mmseqs2 — alignment node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class MMseqs2EasySearchNode(CommandNode):
    """Run MMseqs2 easy-search for sensitive sequence homology search."""
    NODE_ID = 'mmseqs2_easy_search'
    DISPLAY_NAME = 'MMseqs2 Easy Search'
    REQUIRED_CONDA_PACKAGES = ['mmseqs2']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Run MMseqs2 easy-search for protein, nucleotide, or translated homology searches.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mmseqs2', 'mmseqs', 'easy-search', 'homology', 'sequence search']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('search_results',)
    REQUIRED_EXECUTABLES = ['mmseqs']
    DOCUMENTATION_URL = 'https://github.com/soedinglab/MMseqs2/wiki'
    CITATION_DOIS = ['10.1038/nbt.3988', '10.1038/s41467-018-04964-5', '10.1093/bioinformatics/btab184']
    CITATION_URLS = ['https://doi.org/10.1038/nbt.3988', 'https://doi.org/10.1038/s41467-018-04964-5', 'https://doi.org/10.1093/bioinformatics/btab184']
    CITATION_TEXT = 'MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets.'
    VERSION = '17-b804f'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['mmseqs', 'easy-search', str(inputs.get('query_fasta', '')), str(inputs.get('target_fasta', inputs.get('target_database', ''))), f'{out}/search_results', f'{out}/tmp', '--search-type', str(inputs.get('search_type', 0)), '-s', str(inputs.get('sensitivity', 5.7)), '-e', str(inputs.get('evalue', 0.001)), '--min-seq-id', str(inputs.get('min_seq_id', 0.0)), '-c', str(inputs.get('cov', 0.0)), '--cov-mode', str(inputs.get('cov_mode', 0))]
        _add_if_value(cmd, '--format-output', inputs.get('format_output', 'query,target,pident,evalue,bits'))
        _add_if_value(cmd, '--num-iterations', inputs.get('num_iterations', 1))
        cmd.extend(['--threads', str(inputs.get('threads', 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'search_results']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query_fasta': ('FASTA', {'description': 'Query FASTA/Q file'}), 'target_fasta': ('FASTA', {'description': 'Target FASTA database'})}, 'optional': {'search_type': ('INT', {'default': 0, 'min': 0, 'max': 4, 'description': '0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide'}), 'sensitivity': ('FLOAT', {'default': 5.7, 'min': 1, 'max': 15}), 'evalue': ('FLOAT', {'default': 0.001, 'min': 0}), 'min_seq_id': ('FLOAT', {'default': 0.0, 'min': 0, 'max': 1}), 'cov': ('FLOAT', {'default': 0.0, 'min': 0, 'max': 1}), 'cov_mode': ('INT', {'default': 0, 'min': 0, 'max': 5}), 'format_output': ('STRING', {'default': 'query,target,pident,evalue,bits'}), 'num_iterations': ('INT', {'default': 1, 'min': 1, 'max': 20, 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class MMseqs2EasyLinsearchNode(CommandNode):
    """Run MMseqs2 easy-linsearch for linear-time homology search."""
    NODE_ID = 'mmseqs2_easy_linsearch'
    DISPLAY_NAME = 'MMseqs2 Easy Linsearch'
    REQUIRED_CONDA_PACKAGES = ['mmseqs2']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Run fast linear-time homology searches against large MMseqs2 target databases.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mmseqs2', 'mmseqs', 'easy-linsearch', 'linsearch', 'linear homology search']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('search_results',)
    REQUIRED_EXECUTABLES = ['mmseqs']
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ['10.1038/nbt.3988']
    CITATION_URLS = [f'{DOI_URL}10.1038/nbt.3988']
    CITATION_TEXT = MMseqs2EasySearchNode.CITATION_TEXT
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _sequence_link_name(cls, prefix: str, source: Any) -> str:
        suffixes = [suffix.lower() for suffix in Path(str(source or '')).suffixes]
        allowed_exts = {'fasta', 'fa', 'fastq', 'fq', 'faa', 'fna', 'ffn'}
        if len(suffixes) >= 2 and suffixes[-1] == '.gz':
            ext = suffixes[-2].lstrip('.').replace('sanger', '').replace('illumina', '')
            if ext in allowed_exts:
                return f'{prefix}.{ext}.gz'
        if suffixes:
            ext = suffixes[-1].lstrip('.').replace('sanger', '').replace('illumina', '')
            if ext in allowed_exts:
                return f'{prefix}.{ext}'
        return f'{prefix}.fasta'

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--add-self-matches', str(inputs.get('add_self_matches', 0)), '--mask', str(inputs.get('mask', 1)), '--mask-prob', str(inputs.get('mask_prob', 0.9)), '--mask-lower-case', str(inputs.get('mask_lower_case', 0)), '--mask-n-repeat', str(inputs.get('mask_n_repeat', 0))])

    @classmethod
    def _add_kmermatcher_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--kmer-per-seq', str(inputs.get('kmer_per_seq', 21))])

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--id-offset', str(inputs.get('id_offset', 0))])

    @classmethod
    def _format_fields(cls, inputs: dict[str, Any]) -> str:
        fields = _as_list(inputs.get('format_fields', ['query', 'target', 'pident', 'evalue', 'bits']))
        return ','.join(fields)

    @classmethod
    def _add_output_format_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        format_mode = str(inputs.get('format_mode', '0'))
        format_fields = cls._format_fields(inputs)
        if format_mode in {'0', '2', '4'} and format_fields:
            cmd.extend(['--format-output', format_fields])
        cmd.extend(['--format-mode', format_mode])

    @classmethod
    def _add_search_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--search-type', str(inputs.get('search_type', 0)), '--threads', str(inputs.get('threads', 1)), '--max-seq-len', str(inputs.get('max_seq_len', 65535))])

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        if str(inputs.get('target_source', 'history')) == 'cached':
            database_root = str(inputs.get('target_database', ''))
            if inputs.get('create_linindex'):
                prelude = [f'cp -r {shlex.quote(database_root)}/database* .', f"mmseqs createlinindex database {shlex.quote(f'{out}/tmp')}"]
                return (prelude, 'database')
            target = f"{database_root.rstrip('/')}/database" if database_root else 'database'
            return ([], target)
        target_fasta = str(inputs.get('target_fasta', ''))
        linked_target = cls._sequence_link_name('target', target_fasta)
        return ([f'ln -sf {shlex.quote(target_fasta)} {shlex.quote(linked_target)}'], linked_target)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get('query_fasta', ''))
        linked_query = cls._sequence_link_name('query', query_fasta)
        prelude = [f'ln -sf {shlex.quote(query_fasta)} {shlex.quote(linked_query)}']
        target_prelude, target = cls._target_command_part(inputs, out)
        prelude.extend(target_prelude)
        effective_inputs = dict(inputs)
        effective_inputs.setdefault('min_seq_id', 0)
        effective_inputs.setdefault('cov', 0)
        cmd = ['mmseqs', 'easy-linsearch', linked_query, target, f'{out}/search_results', f'{out}/tmp']
        MMseqs2EasyLinclustNode._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        MMseqs2EasyClusterNode._add_align_options(cmd, effective_inputs)
        cls._add_kmermatcher_options(cmd, effective_inputs)
        cls._add_misc_options(cmd, effective_inputs)
        cls._add_output_format_options(cmd, effective_inputs)
        cls._add_search_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = {'1': 'sam', '3': 'html'}.get(str(inputs.get('format_mode', '0')), 'tsv')
        return [out / f'search_results.{suffix}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query_fasta': ('FASTA', {'description': 'Query FASTA/FASTQ file'}), 'target_source': ('STRING', {'default': 'history', 'options': ['history', 'cached'], 'description': 'Use a target FASTA from history or a cached MMseqs2 database'}), 'target_fasta': ('FASTA', {'default': '', 'description': 'Target FASTA/FASTQ file for history mode', 'displayOptions': {'show': {'target_source': ['history']}}}), 'target_database': ('FILE', {'default': '', 'description': 'Cached MMseqs2 database directory containing database* files', 'displayOptions': {'show': {'target_source': ['cached']}}})}, 'optional': {'dbtype': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'description': 'Input data type: automatic, amino acid, or nucleotide'}), 'comp_bias_corr_scale': ('FLOAT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['1']}}}), 'zdrop': ('INT', {'default': 40, 'min': 0, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['2']}}}), 'kmer_per_seq_scale': ('FLOAT', {'default': 0.0, 'min': 0, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['1', '2']}}}), 'adjust_kmer_len': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['2']}}}), 'add_self_matches': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'mask': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'mask_prob': ('FLOAT', {'default': 0.9, 'min': 0, 'advanced': True}), 'mask_lower_case': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'mask_n_repeat': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'convertalis': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'alignment_output_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4', '5'], 'advanced': True}), 'wrapped_scoring': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'min_aln_len': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'seq_id_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'advanced': True}), 'alt_ali': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'score_bias': ('FLOAT', {'default': 0, 'advanced': True}), 'realign': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'realign_score_bias': ('FLOAT', {'default': -0.2, 'advanced': True}), 'realign_max_seqs': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'corr_score_weight': ('FLOAT', {'default': 0, 'advanced': True}), 'alignment_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'advanced': True}), 'evalue': ('FLOAT', {'default': 0.001, 'min': 0}), 'min_seq_id': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'cov': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'cov_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4', '5']}), 'max_rejected': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'max_accept': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'kmer_per_seq': ('INT', {'default': 21, 'min': 1, 'advanced': True}), 'id_offset': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'format_fields': ('STRING', {'default': ['query', 'target', 'pident', 'evalue', 'bits'], 'options': ['query', 'target', 'pident', 'alnlen', 'mismatch', 'gapopen', 'qstart', 'qend', 'tstart', 'tend', 'evalue', 'bits', 'qcov', 'tcov'], 'list': True, 'description': 'Comma-separated fields for BLAST tabular-like output modes'}), 'format_mode': ('STRING', {'default': '0', 'options': ['0', '4', '2', '1', '3'], 'description': 'MMseqs2 output format mode: BLAST-like, SAM, or HTML'}), 'search_type': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'description': '0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'max_seq_len': ('INT', {'default': 65535, 'min': 1, 'advanced': True}), 'create_linindex': ('BOOLEAN', {'default': False, 'advanced': True, 'description': 'Create a linear index for copied cached database files before searching', 'displayOptions': {'show': {'target_source': ['cached']}}})}, 'hidden': {'output': ('STRING', {})}}


class MMseqs2EasyRBHNode(CommandNode):
    """Identify reciprocal best hits with MMseqs2 easy-rbh."""
    NODE_ID = 'mmseqs2_easy_rbh'
    DISPLAY_NAME = 'MMseqs2 Easy RBH'
    REQUIRED_CONDA_PACKAGES = ['mmseqs2']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Identify reciprocal best hits between two sequence sets for ortholog detection.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mmseqs2', 'mmseqs', 'easy-rbh', 'reciprocal best hit', 'ortholog detection']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('search_results',)
    REQUIRED_EXECUTABLES = ['mmseqs']
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ['10.1038/nbt.3988']
    CITATION_URLS = [f'{DOI_URL}10.1038/nbt.3988']
    CITATION_TEXT = MMseqs2EasySearchNode.CITATION_TEXT
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        if str(inputs.get('target_source', 'history')) == 'cached':
            database_root = str(inputs.get('target_database', ''))
            target = f"{database_root.rstrip('/')}/database" if database_root else 'database'
            return ([], target)
        target_fasta = str(inputs.get('target_fasta', ''))
        linked_target = MMseqs2EasyLinsearchNode._sequence_link_name('target', target_fasta)
        return ([f'ln -s {shlex.quote(target_fasta)} {shlex.quote(linked_target)}'], linked_target)

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--add-self-matches', str(inputs.get('add_self_matches', 0)), '-k', str(inputs.get('kmer_length', 0)), '--mask', str(inputs.get('mask', 1)), '--mask-prob', str(inputs.get('mask_prob', 0.9)), '--mask-lower-case', str(inputs.get('mask_lower_case', 0)), '--mask-n-repeat', str(inputs.get('mask_n_repeat', 0)), '--spaced-kmer-mode', str(inputs.get('spaced_kmer_mode', 1))])

    @classmethod
    def _add_search_common_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['-s', str(inputs.get('sensitivity', 5.7)), '--max-seqs', str(inputs.get('max_seqs', 300)), '--split', str(inputs.get('split', 0)), '--split-mode', str(inputs.get('split_mode', 2)), '--diag-score', str(inputs.get('diag_score', 1)), '--exact-kmer-matching', str(inputs.get('exact_kmer_matching', 0)), '--min-ungapped-score', str(inputs.get('min_ungapped_score', 15))])

    @classmethod
    def _add_common_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--threads', str(inputs.get('threads', 1)), '--max-seq-len', str(inputs.get('max_seq_len', 65535))])

    @classmethod
    def _add_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--filter-hits', str(inputs.get('filter_hits', 0)), '--sort-results', str(inputs.get('sort_results', 0)), '--chain-alignments', str(inputs.get('chain_alignments', 0)), '--merge-query', str(inputs.get('merge_query', 1)), '--strand', str(inputs.get('strand', 1))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get('query_fasta', ''))
        linked_query = MMseqs2EasyLinsearchNode._sequence_link_name('query', query_fasta)
        prelude = [f'ln -s {shlex.quote(query_fasta)} {shlex.quote(linked_query)}']
        target_prelude, target = cls._target_command_part(inputs)
        prelude.extend(target_prelude)
        effective_inputs = dict(inputs)
        effective_inputs.setdefault('min_seq_id', 0)
        effective_inputs.setdefault('cov', 0)
        cmd = ['mmseqs', 'easy-rbh', linked_query, target, f'{out}/search_results', f'{out}/tmp']
        MMseqs2EasyClusterNode._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        cls._add_search_common_options(cmd, effective_inputs)
        MMseqs2EasyClusterNode._add_align_options(cmd, effective_inputs)
        MMseqs2EasyLinsearchNode._add_output_format_options(cmd, effective_inputs)
        cmd.extend(['--search-type', str(effective_inputs.get('search_type', 0))])
        cls._add_common_options(cmd, effective_inputs)
        cls._add_expert_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = {'1': 'sam', '3': 'html'}.get(str(inputs.get('format_mode', '0')), 'tsv')
        return [out / f'search_results.{suffix}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query_fasta': ('FASTA', {'description': 'Query FASTA/FASTQ file'}), 'target_source': ('STRING', {'default': 'history', 'options': ['history', 'cached'], 'description': 'Use a target FASTA from history or a cached MMseqs2 database'}), 'target_fasta': ('FASTA', {'default': '', 'description': 'Target FASTA file for history mode', 'displayOptions': {'show': {'target_source': ['history']}}}), 'target_database': ('FILE', {'default': '', 'description': 'Cached MMseqs2 database directory containing database* files', 'displayOptions': {'show': {'target_source': ['cached']}}})}, 'optional': {'dbtype': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'description': 'Input data type: automatic, amino acid, or nucleotide'}), 'comp_bias_corr_scale': ('FLOAT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['1']}}}), 'zdrop': ('INT', {'default': 40, 'min': 0, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['2']}}}), 'add_self_matches': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'kmer_length': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'mask': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'mask_prob': ('FLOAT', {'default': 0.9, 'min': 0, 'advanced': True}), 'mask_lower_case': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'mask_n_repeat': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'spaced_kmer_mode': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'sensitivity': ('FLOAT', {'default': 5.7, 'min': 1, 'max': 7.5}), 'max_seqs': ('INT', {'default': 300, 'min': 0, 'advanced': True}), 'split': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'split_mode': ('STRING', {'default': '2', 'options': ['0', '1', '2'], 'advanced': True}), 'diag_score': ('INT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True}), 'exact_kmer_matching': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'min_ungapped_score': ('INT', {'default': 15, 'min': 0, 'advanced': True}), 'convertalis': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'alignment_output_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4', '5'], 'advanced': True}), 'wrapped_scoring': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'min_aln_len': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'seq_id_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'advanced': True}), 'alt_ali': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'score_bias': ('FLOAT', {'default': 0, 'advanced': True}), 'realign': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'realign_score_bias': ('FLOAT', {'default': -0.2, 'advanced': True}), 'realign_max_seqs': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'corr_score_weight': ('FLOAT', {'default': 0, 'advanced': True}), 'alignment_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'advanced': True}), 'evalue': ('FLOAT', {'default': 0.001, 'min': 0}), 'min_seq_id': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'cov': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'cov_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4', '5']}), 'max_rejected': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'max_accept': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'format_fields': MMseqs2EasyLinsearchNode.INPUT_TYPES()['optional']['format_fields'], 'format_mode': MMseqs2EasyLinsearchNode.INPUT_TYPES()['optional']['format_mode'], 'search_type': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'description': '0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'max_seq_len': ('INT', {'default': 65535, 'min': 1, 'advanced': True}), 'filter_hits': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'sort_results': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'chain_alignments': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'merge_query': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'strand': ('STRING', {'default': '1', 'options': ['0', '1', '2'], 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
