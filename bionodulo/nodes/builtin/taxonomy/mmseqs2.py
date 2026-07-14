"""mmseqs2 — taxonomy node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class MMseqs2EasyTaxonomyNode(CommandNode):
    """Assign taxonomy to sequences with MMseqs2 easy-taxonomy."""
    NODE_ID = 'mmseqs2_easy_taxonomy'
    DISPLAY_NAME = 'MMseqs2 Easy Taxonomy'
    REQUIRED_CONDA_PACKAGES = ['mmseqs2']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Assign taxonomy to query sequences against an MMseqs2 taxonomy database using LCA.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mmseqs2', 'mmseqs', 'easy-taxonomy', 'taxonomy assignment', 'LCA', 'metagenomic classification']
    RETURN_TYPES = ('TSV', 'TXT', 'TSV', 'TXT')
    RETURN_NAMES = ('lca_results', 'kraken_report', 'top_hit_alignments', 'top_hit_report')
    REQUIRED_EXECUTABLES = ['mmseqs']
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ['10.1093/bioinformatics/btab184']
    CITATION_URLS = [f'{DOI_URL}10.1093/bioinformatics/btab184']
    CITATION_TEXT = 'Fast and sensitive taxonomic assignment to metagenomic contigs.'
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        database_root = str(inputs.get('target_database', ''))
        if inputs.get('download_tax_db'):
            return ([f'cp -r {shlex.quote(database_root)}/database* .', f"mmseqs createtaxdb database {shlex.quote(f'{out}/tmp')}"], 'database')
        target = f"{database_root.rstrip('/')}/database" if database_root else 'database'
        return ([], target)

    @classmethod
    def _add_profile_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--mask-profile', str(inputs.get('mask_profile', 1)), '--e-profile', str(inputs.get('e_profile', 0.001)), '--wg', str(inputs.get('wg', 0)), '--filter-msa', str(inputs.get('filter_msa', 1)), '--filter-min-enable', str(inputs.get('filter_min_enable', 0)), '--max-seq-id', str(inputs.get('max_seq_id', 0.9)), '--qid', str(inputs.get('qid', '0')), '--qsc', str(inputs.get('qsc', -20)), '--cov', str(inputs.get('profile_cov', 0)), '--diff', str(inputs.get('diff', 1000)), '--pseudo-cnt-mode', str(inputs.get('pseudo_cnt_mode', 0)), '--exhaustive-search', str(inputs.get('exhaustive_search', 0)), '--lca-search', str(inputs.get('lca_search', 0))])

    @classmethod
    def _add_taxonomy_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--orf-filter-e', str(inputs.get('orf_filter_e', 100)), '--orf-filter-s', str(inputs.get('orf_filter_s', 2)), '--lca-mode', str(inputs.get('lca_mode', 3)), '--majority', str(inputs.get('majority', 0.5)), '--vote-mode', str(inputs.get('vote_mode', 1)), '--tax-lineage', str(inputs.get('tax_lineage', 0))])
        _add_if_value(cmd, '--blacklist', inputs.get('blacklist'))
        _add_if_value(cmd, '--taxon-list', inputs.get('taxon_list'))

    @classmethod
    def _add_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--filter-hits', str(inputs.get('filter_hits', 0)), '--sort-results', str(inputs.get('sort_results', 0)), '--chain-alignments', str(inputs.get('chain_alignments', 0)), '--merge-query', str(inputs.get('merge_query', 1))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get('query_fasta', ''))
        linked_query = MMseqs2EasyLinsearchNode._sequence_link_name('query', query_fasta)
        prelude = [f'ln -s {shlex.quote(query_fasta)} {shlex.quote(linked_query)}']
        target_prelude, target = cls._target_command_part(inputs, out)
        prelude.extend(target_prelude)
        effective_inputs = dict(inputs)
        effective_inputs.setdefault('evalue', 1)
        effective_inputs.setdefault('min_seq_id', 0)
        effective_inputs.setdefault('cov', 0)
        effective_inputs.setdefault('max_rejected', 5)
        effective_inputs.setdefault('max_accept', 30)
        cmd = ['mmseqs', 'easy-taxonomy', linked_query, target, f'{out}/result', f'{out}/tmp']
        MMseqs2EasyClusterNode._add_dbtype_options(cmd, effective_inputs)
        MMseqs2EasyRBHNode._add_prefilter_options(cmd, effective_inputs)
        MMseqs2EasyRBHNode._add_search_common_options(cmd, effective_inputs)
        MMseqs2EasyClusterNode._add_align_options(cmd, effective_inputs)
        cls._add_profile_options(cmd, effective_inputs)
        cls._add_taxonomy_options(cmd, effective_inputs)
        cmd.extend(['--search-type', str(effective_inputs.get('search_type', 0))])
        MMseqs2EasyRBHNode._add_common_options(cmd, effective_inputs)
        cls._add_expert_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(_as_list(inputs.get('output_selection')))
        outputs = [out / 'result_lca.tsv']
        if 'output_selection' not in inputs:
            selected = {'report'}
        if 'report' in selected:
            outputs.append(out / 'result_report.txt')
        if 'tophit_aln' in selected:
            outputs.append(out / 'result_tophit_aln.tsv')
        if 'tophit_report' in selected:
            outputs.append(out / 'result_tophit_report.txt')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query_fasta': ('FASTA', {'description': 'Query FASTA/FASTQ file'}), 'database_type': ('STRING', {'default': 'amino_acid_tax', 'options': ['amino_acid_tax', 'nucleotides_tax'], 'description': 'Taxonomy database type: amino acid or nucleotide'}), 'target_database': ('FILE', {'default': '', 'description': 'Cached MMseqs2 taxonomy database directory'})}, 'optional': {'dbtype': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'description': 'Input data type: automatic, amino acid, or nucleotide'}), 'comp_bias_corr_scale': ('FLOAT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['1']}}}), 'zdrop': ('INT', {'default': 40, 'min': 0, 'advanced': True, 'displayOptions': {'show': {'dbtype': ['2']}}}), 'add_self_matches': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'kmer_length': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'mask': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'mask_prob': ('FLOAT', {'default': 0.9, 'min': 0, 'advanced': True}), 'mask_lower_case': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'mask_n_repeat': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'spaced_kmer_mode': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'sensitivity': ('FLOAT', {'default': 5.7, 'min': 1, 'max': 7.5}), 'max_seqs': ('INT', {'default': 300, 'min': 0, 'advanced': True}), 'split': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'split_mode': ('STRING', {'default': '2', 'options': ['0', '1', '2'], 'advanced': True}), 'diag_score': ('INT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True}), 'exact_kmer_matching': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'min_ungapped_score': ('INT', {'default': 15, 'min': 0, 'advanced': True}), 'convertalis': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'alignment_output_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4', '5'], 'advanced': True}), 'wrapped_scoring': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'min_aln_len': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'seq_id_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'advanced': True}), 'alt_ali': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'score_bias': ('FLOAT', {'default': 0, 'advanced': True}), 'realign': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'realign_score_bias': ('FLOAT', {'default': -0.2, 'advanced': True}), 'realign_max_seqs': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'corr_score_weight': ('FLOAT', {'default': 0, 'advanced': True}), 'alignment_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'advanced': True}), 'evalue': ('FLOAT', {'default': 1, 'min': 0}), 'min_seq_id': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'cov': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'cov_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4', '5']}), 'max_rejected': ('INT', {'default': 5, 'min': 0, 'advanced': True}), 'max_accept': ('INT', {'default': 30, 'min': 0, 'advanced': True}), 'mask_profile': ('INT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True}), 'e_profile': ('FLOAT', {'default': 0.001, 'min': 0, 'advanced': True}), 'wg': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'filter_msa': ('INT', {'default': 1, 'min': 0, 'max': 1, 'advanced': True}), 'filter_min_enable': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'max_seq_id': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1, 'advanced': True}), 'qid': ('STRING', {'default': '0', 'advanced': True}), 'qsc': ('FLOAT', {'default': -20, 'min': -50, 'max': 100, 'advanced': True}), 'profile_cov': ('FLOAT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'diff': ('INT', {'default': 1000, 'min': 0, 'advanced': True}), 'pseudo_cnt_mode': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'exhaustive_search': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'lca_search': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'orf_filter_e': ('FLOAT', {'default': 100, 'min': 0, 'advanced': True}), 'orf_filter_s': ('FLOAT', {'default': 2, 'min': 0, 'advanced': True}), 'lca_mode': ('STRING', {'default': '3', 'options': ['1', '3', '4']}), 'majority': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1}), 'vote_mode': ('STRING', {'default': '1', 'options': ['0', '1', '2']}), 'tax_lineage': ('STRING', {'default': '0', 'options': ['0', '1', '2']}), 'blacklist': ('STRING', {'default': '', 'advanced': True}), 'taxon_list': ('STRING', {'default': '', 'advanced': True}), 'search_type': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'description': '0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'max_seq_len': ('INT', {'default': 65535, 'min': 1, 'advanced': True}), 'filter_hits': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'sort_results': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'chain_alignments': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'merge_query': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'output_selection': ('STRING', {'default': ['report'], 'options': ['report', 'tophit_aln', 'tophit_report'], 'list': True, 'description': 'Additional MMseqs2 taxonomy outputs to keep'}), 'download_tax_db': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class MMseqs2TaxonomyAssignmentNode(CommandNode):
    """Run the lower-level MMseqs2 taxonomy assignment pipeline."""
    NODE_ID = 'mmseqs2_taxonomy_assignment'
    DISPLAY_NAME = 'MMseqs2 Taxonomy'
    REQUIRED_CONDA_PACKAGES = ['mmseqs2']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Run the fine-grained MMseqs2 taxonomy workflow with optional taxon filtering and reports.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'mmseqs2', 'mmseqs', 'taxonomy', 'taxonomy assignment', 'filtertaxseqdb', 'Kraken report', 'Krona report']
    RETURN_TYPES = ('TSV', 'TXT', 'HTML')
    RETURN_NAMES = ('taxonomy_tsv', 'kraken_report', 'krona_report')
    REQUIRED_EXECUTABLES = ['mmseqs']
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ['10.1093/bioinformatics/btab184']
    CITATION_URLS = [f'{DOI_URL}10.1093/bioinformatics/btab184']
    CITATION_TEXT = 'Fast and sensitive taxonomic assignment to metagenomic contigs.'
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _database_source(cls, inputs: dict[str, Any]) -> str:
        if inputs.get('download_tax_db'):
            return 'database'
        database_root = str(inputs.get('target_database', ''))
        return f"{database_root.rstrip('/')}/database" if database_root else 'database'

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--add-self-matches', str(inputs.get('add_self_matches', 0)), '-s', str(inputs.get('sensitivity', 2)), '-k', str(inputs.get('kmer_length', 0)), '--target-search-mode', str(inputs.get('target_search_mode', 0)), '--max-seqs', str(inputs.get('max_seqs', 300)), '--split', str(inputs.get('split', 0)), '--split-mode', str(inputs.get('split_mode', 2)), '--diag-score', str(inputs.get('diag_score', 1)), '--exact-kmer-matching', str(inputs.get('exact_kmer_matching', 0)), '--mask', str(inputs.get('mask', 1)), '--mask-prob', str(inputs.get('mask_prob', 0.9)), '--mask-lower-case', str(inputs.get('mask_lower_case', 0)), '--mask-n-repeat', str(inputs.get('mask_n_repeat', 0)), '--min-ungapped-score', str(inputs.get('min_ungapped_score', 15)), '--spaced-kmer-mode', str(inputs.get('spaced_kmer_mode', 1))])

    @classmethod
    def _add_align_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['-a', str(inputs.get('convertalis', 0)), '--alignment-mode', str(inputs.get('alignment_mode', 1)), '--alignment-output-mode', str(inputs.get('alignment_output_mode', 0)), '--wrapped-scoring', str(inputs.get('wrapped_scoring', 0)), '-e', str(inputs.get('evalue', 1)), '--min-seq-id', str(inputs.get('min_seq_id', 0)), '--min-aln-len', str(inputs.get('min_aln_len', 0)), '--seq-id-mode', str(inputs.get('seq_id_mode', 0)), '--alt-ali', str(inputs.get('alt_ali', 0)), '-c', str(inputs.get('cov', 0)), '--cov-mode', str(inputs.get('cov_mode', 0)), '--max-rejected', str(inputs.get('max_rejected', 5)), '--max-accept', str(inputs.get('max_accept', 30)), '--score-bias', str(inputs.get('score_bias', 0)), '--realign', str(inputs.get('realign', 0)), '--realign-score-bias', str(inputs.get('realign_score_bias', -0.2)), '--realign-max-seqs', str(inputs.get('realign_max_seqs', 2147483647)), '--corr-score-weight', str(inputs.get('corr_score_weight', 0)), '--exhaustive-search-filter', str(inputs.get('exhaustive_search_filter', 0))])

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        MMseqs2EasyTaxonomyNode._add_taxonomy_options(cmd, inputs)
        cmd.extend(['--rescore-mode', str(inputs.get('rescore_mode', 0)), '--allow-deletion', str(inputs.get('allow_deletion', 0)), '--min-length', str(inputs.get('min_length', 30)), '--max-length', str(inputs.get('max_length', 32734)), '--max-gaps', str(inputs.get('max_gaps', 2147483647)), '--contig-start-mode', str(inputs.get('contig_start_mode', 2)), '--contig-end-mode', str(inputs.get('contig_end_mode', 2)), '--orf-start-mode', str(inputs.get('orf_start_mode', 1)), '--forward-frames', str(inputs.get('forward_frames', '1,2,3')), '--reverse-frames', str(inputs.get('reverse_frames', '1,2,3')), '--translation-table', str(inputs.get('translation_table', 1)), '--translate', str(inputs.get('translate', 0)), '--use-all-table-starts', str(inputs.get('use_all_table_starts', 0)), '--id-offset', str(inputs.get('id_offset', 0)), '--sequence-overlap', str(inputs.get('sequence_overlap', 0)), '--sequence-split-mode', str(inputs.get('sequence_split_mode', 1)), '--headers-split-mode', str(inputs.get('headers_split_mode', 0)), '--search-type', str(inputs.get('search_type', 3 if inputs.get('database_type') == 'nucleotides_tax' else 0)), '--prefilter-mode', str(inputs.get('prefilter_mode', 0))])

    @classmethod
    def _add_common_and_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(['--threads', str(inputs.get('threads', 1)), '--max-seq-len', str(inputs.get('max_seq_len', 65535)), '--filter-hits', str(inputs.get('filter_hits', 0)), '--sort-results', str(inputs.get('sort_results', 0)), '--chain-alignments', str(inputs.get('chain_alignments', 0)), '--merge-query', str(inputs.get('merge_query', 1))])

    @classmethod
    def _taxonomy_command(cls, inputs: dict[str, Any], out: str, taxonomy_database: str) -> list[str]:
        cmd = ['mmseqs', 'taxonomy', f'{out}/sequenceDB', taxonomy_database, f'{out}/output_taxonomy', f'{out}/tmp']
        dbtype = str(inputs.get('dbtype', '0'))
        if dbtype == '1':
            _add_if_value(cmd, '--comp-bias-corr-scale', inputs.get('comp_bias_corr_scale', 1))
        elif dbtype == '2':
            _add_if_value(cmd, '--zdrop', inputs.get('zdrop', 40))
        cls._add_prefilter_options(cmd, inputs)
        cls._add_align_options(cmd, inputs)
        MMseqs2EasyTaxonomyNode._add_profile_options(cmd, inputs)
        cls._add_misc_options(cmd, inputs)
        cls._add_common_and_expert_options(cmd, inputs)
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get('input_fasta', ''))
        commands = [shlex.join(['ln', '-s', '-f', input_fasta, 'input']), shlex.join(['mmseqs', 'createdb', 'input', f'{out}/sequenceDB', '--dbtype', str(inputs.get('dbtype', 0)), '--shuffle', str(inputs.get('shuffle', 1))])]
        if inputs.get('download_tax_db'):
            database_root = str(inputs.get('target_database', ''))
            commands.extend([f'cp -r {shlex.quote(database_root)}/database* .', shlex.join(['mmseqs', 'createtaxdb', 'database', f'{out}/tmp'])])
        taxonomy_database = cls._database_source(inputs)
        filter_taxon_list = str(inputs.get('filter_taxon_list', ''))
        if filter_taxon_list:
            filtered_database = f'{out}/database_filtered'
            commands.append(shlex.join(['mmseqs', 'filtertaxseqdb', taxonomy_database, filtered_database, '--taxon-list', filter_taxon_list]))
            taxonomy_database = filtered_database
        commands.append(shlex.join(cls._taxonomy_command(inputs, out, taxonomy_database)))
        commands.append(shlex.join(['mmseqs', 'createtsv', f'{out}/sequenceDB', f'{out}/output_taxonomy', f'{out}/taxo_result.tsv', '--first-seq-as-repr', str(inputs.get('first_seq_as_repr', 0)), '--target-column', str(inputs.get('target_column', 1)), '--full-header', str(inputs.get('full_header', 0)), '--idx-seq-src', str(inputs.get('idx_seq_src', 0)), '--threads', str(inputs.get('threads', 1))]))
        if inputs.get('keep_kraken_report', True):
            commands.append(shlex.join(['mmseqs', 'taxonomyreport', taxonomy_database, f'{out}/output_taxonomy', f'{out}/taxo_result.txt', '--report-mode', '0', '--threads', str(inputs.get('threads', 1))]))
        if inputs.get('keep_krona_report', True):
            commands.append(shlex.join(['mmseqs', 'taxonomyreport', taxonomy_database, f'{out}/output_taxonomy', f'{out}/taxo_result.html', '--report-mode', '1', '--threads', str(inputs.get('threads', 1))]))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'taxo_result.tsv']
        if inputs.get('keep_kraken_report', True):
            outputs.append(out / 'taxo_result.txt')
        if inputs.get('keep_krona_report', True):
            outputs.append(out / 'taxo_result.html')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        taxonomy_optional = dict(MMseqs2EasyTaxonomyNode.INPUT_TYPES()['optional'])
        taxonomy_optional.update({'sensitivity': ('FLOAT', {'default': 2, 'min': 1, 'max': 7.5}), 'target_search_mode': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'alignment_mode': ('STRING', {'default': '1', 'options': ['0', '1', '2', '3', '4'], 'advanced': True}), 'exhaustive_search_filter': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'filter_taxon_list': ('STRING', {'default': '', 'description': 'Optional taxon list for pre-filtering the taxonomy database'}), 'rescore_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2', '3', '4'], 'advanced': True}), 'allow_deletion': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'min_length': ('INT', {'default': 30, 'min': 0, 'advanced': True}), 'max_length': ('INT', {'default': 32734, 'min': 0, 'advanced': True}), 'max_gaps': ('INT', {'default': 2147483647, 'min': 0, 'advanced': True}), 'contig_start_mode': ('STRING', {'default': '2', 'options': ['0', '1', '2'], 'advanced': True}), 'contig_end_mode': ('STRING', {'default': '2', 'options': ['0', '1', '2'], 'advanced': True}), 'orf_start_mode': ('STRING', {'default': '1', 'options': ['0', '1', '2'], 'advanced': True}), 'forward_frames': ('STRING', {'default': '1,2,3', 'advanced': True}), 'reverse_frames': ('STRING', {'default': '1,2,3', 'advanced': True}), 'translation_table': ('STRING', {'default': '1', 'options': ['1', '2', '3', '4', '5', '6', '9', '10', '11', '12', '13', '14', '15', '16', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31'], 'advanced': True}), 'translate': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'use_all_table_starts': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'id_offset': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'sequence_overlap': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'sequence_split_mode': ('STRING', {'default': '1', 'options': ['0', '1'], 'advanced': True}), 'headers_split_mode': ('STRING', {'default': '0', 'options': ['0', '1'], 'advanced': True}), 'prefilter_mode': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'advanced': True}), 'first_seq_as_repr': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'target_column': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'full_header': ('INT', {'default': 0, 'min': 0, 'max': 1, 'advanced': True}), 'idx_seq_src': ('STRING', {'default': '0', 'options': ['0', '1', '2'], 'advanced': True}), 'keep_kraken_report': ('BOOLEAN', {'default': True, 'description': 'Generate a Kraken-style taxonomy report'}), 'keep_krona_report': ('BOOLEAN', {'default': True, 'description': 'Generate a Krona HTML taxonomy report'})})
        taxonomy_optional.pop('output_selection', None)
        return {'required': {'input_fasta': ('FASTA', {'description': 'Query FASTA/FASTQ file'}), 'database_type': ('STRING', {'default': 'amino_acid_tax', 'options': ['amino_acid_tax', 'nucleotides_tax'], 'description': 'Taxonomy database type: amino acid or nucleotide'}), 'target_database': ('FILE', {'default': '', 'description': 'Cached MMseqs2 taxonomy database directory'})}, 'optional': taxonomy_optional, 'hidden': {'output': ('STRING', {})}}
