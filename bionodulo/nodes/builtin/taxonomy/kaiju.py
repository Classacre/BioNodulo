"""kaiju — taxonomy node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class KaijuNode(CommandNode):
    """Classify metagenomic reads with the Galaxy IUC Kaiju wrapper behavior."""
    NODE_ID = 'kaiju'
    DISPLAY_NAME = 'Kaiju'
    REQUIRED_CONDA_PACKAGES = ['kaiju']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Classify metagenomic reads or report best matching database sequences with Kaiju.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'kaiju', 'taxonomic classification', 'metagenomics', 'protein-level classifier', 'best matching sequence']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('taxonomic_classification', 'best_matching_sequences')
    REQUIRED_EXECUTABLES = ['kaiju', 'kaijup', 'kaijux']
    DOCUMENTATION_URL = 'https://github.com/bioinformatics-centre/kaiju'
    CITATION_DOIS = ['10.1038/ncomms11257']
    CITATION_URLS = [f'{DOI_URL}10.1038/ncomms11257']
    CITATION_TEXT = 'Fast and sensitive taxonomic classification for metagenomics with Kaiju.'
    VERSION = '1.10.1'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        task = str(inputs.get('task', 'tax'))
        protein = bool(inputs.get('protein', False))
        reference = str(inputs.get('reference_database', '')).rstrip('/')
        if task == 'tax':
            cmd = ['kaiju', '-t', f'{reference}/nodes.dmp', '-o', f'{out}/kaiju_taxonomy.tsv']
        else:
            cmd = ['kaijup' if protein else 'kaijux', '-o', f'{out}/kaiju_best_sequences.tsv']
        cmd.extend(['-f', f'{reference}/database.fmi'])
        if str(inputs.get('input_type', 'single')) == 'paired':
            cmd.extend(['-i', str(inputs.get('reads_1', '')), '-j', str(inputs.get('reads_2', ''))])
        else:
            cmd.extend(['-i', str(inputs.get('reads', ''))])
        cmd.extend(['-z', str(inputs.get('threads', 1))])
        if protein:
            cmd.append('-p')
        cmd.append('-x' if inputs.get('low_complexity', True) else '-X')
        mode = str(inputs.get('mode', 'greedy'))
        cmd.extend(['-a', mode])
        if mode == 'greedy':
            cmd.extend(['-e', str(inputs.get('mismatches', 3)), '-m', str(inputs.get('match_length', 11)), '-s', str(inputs.get('match_score', 65)), '-E', str(inputs.get('evalue', 0.01))])
        if inputs.get('verbose', False):
            cmd.append('-v')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get('task', 'tax')) == 'best_sequence':
            return [out / 'kaiju_best_sequences.tsv']
        return [out / 'kaiju_taxonomy.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_type': ('STRING', {'default': 'single', 'options': ['single', 'paired'], 'description': 'Single or paired read inputs'}), 'reads': ('FASTQ', {'description': 'Single-end FASTA/FASTQ reads'}), 'reads_1': ('FASTQ', {'description': 'Forward reads for paired input'}), 'reads_2': ('FASTQ', {'description': 'Reverse reads for paired input'}), 'reference_database': ('DIRECTORY', {'description': 'Kaiju database directory containing database.fmi and nodes.dmp'})}, 'optional': {'task': ('STRING', {'default': 'tax', 'options': ['tax', 'best_sequence'], 'description': 'Taxonomic classification or best sequence lookup'}), 'protein': ('BOOLEAN', {'default': False, 'description': 'Input sequences are protein sequences'}), 'low_complexity': ('BOOLEAN', {'default': True, 'description': 'Enable SEG low-complexity filtering'}), 'mode': ('STRING', {'default': 'greedy', 'options': ['greedy', 'mem'], 'description': 'Kaiju MEM or greedy search mode'}), 'mismatches': ('INT', {'default': 3, 'min': 0, 'description': 'Greedy-mode mismatches allowed'}), 'match_length': ('INT', {'default': 11, 'min': 1, 'description': 'Greedy-mode minimum match length'}), 'match_score': ('INT', {'default': 65, 'min': 1, 'description': 'Greedy-mode minimum match score'}), 'evalue': ('FLOAT', {'default': 0.01, 'min': 0, 'description': 'Greedy-mode minimum E-value'}), 'verbose': ('BOOLEAN', {'default': False, 'description': 'Include additional classification columns'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class KaijuAddTaxonNamesNode(CommandNode):
    """Append taxon names or taxonomic paths to Kaiju output tables."""
    NODE_ID = 'kaiju_add_taxon_names'
    DISPLAY_NAME = 'Kaiju Add Taxon Names'
    REQUIRED_CONDA_PACKAGES = ['kaiju']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Append taxon names or taxonomic paths to Kaiju output tables.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'kaiju', 'kaiju-addTaxonNames', 'taxon names', 'Print full taxon path', 'readable taxonomy']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('taxon_names_table',)
    REQUIRED_EXECUTABLES = ['kaiju-addTaxonNames']
    DOCUMENTATION_URL = KaijuNode.DOCUMENTATION_URL
    CITATION_DOIS = KaijuNode.CITATION_DOIS
    CITATION_URLS = KaijuNode.CITATION_URLS
    CITATION_TEXT = KaijuNode.CITATION_TEXT
    VERSION = KaijuNode.VERSION

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reference = str(inputs.get('reference_database', '')).rstrip('/')
        cmd = ['kaiju-addTaxonNames', '-t', f'{reference}/nodes.dmp', '-n', f'{reference}/names.dmp', '-i', str(inputs.get('kaiju_table', '')), '-o', f'{out}/kaiju_taxon_names.tsv']
        if inputs.get('exclude_unclassified', False):
            cmd.append('-u')
        rank = str(inputs.get('rank', ''))
        if rank:
            cmd.extend(['-r', rank])
        if inputs.get('print_full_taxon_path', False):
            cmd.append('-p')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'kaiju_taxon_names.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'kaiju_table': ('TSV', {'description': 'Kaiju output table'}), 'reference_database': ('DIRECTORY', {'description': 'Kaiju database directory containing nodes.dmp and names.dmp'})}, 'optional': {'exclude_unclassified': ('BOOLEAN', {'default': False, 'description': 'Do not count unclassified reads in percentage totals'}), 'rank': ('STRING', {'default': '', 'options': ['', 'phylum', 'class', 'order', 'family', 'genus', 'species'], 'description': 'Optional rank whose taxon name should be appended'}), 'print_full_taxon_path': ('BOOLEAN', {'default': False, 'description': 'Print the full taxon path instead of a rank-specific taxon name'})}, 'hidden': {'output': ('STRING', {})}}


class KaijuMergeOutputsNode(CommandNode):
    """Merge Kaiju and Kraken-style classification tables."""
    NODE_ID = 'kaiju_merge_outputs'
    DISPLAY_NAME = 'Kaiju Merge Outputs'
    REQUIRED_CONDA_PACKAGES = ['kaiju']
    CATEGORY = 'taxonomy'
    DESCRIPTION = 'Merge Kaiju and Kraken-style classification output tables with conflict resolution.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'kaiju', 'kaiju-mergeOutputs', 'merge classifications', 'conflict resolution', 'Kraken table']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('merged_classification',)
    REQUIRED_EXECUTABLES = ['kaiju-mergeOutputs']
    DOCUMENTATION_URL = KaijuNode.DOCUMENTATION_URL
    CITATION_DOIS = KaijuNode.CITATION_DOIS
    CITATION_URLS = KaijuNode.CITATION_URLS
    CITATION_TEXT = KaijuNode.CITATION_TEXT
    VERSION = KaijuNode.VERSION
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        conflict_mode = str(inputs.get('conflict_mode', 'lca'))
        cmd = ['kaiju-mergeOutputs', '-i', 'kaiju.out.sort', '-j', 'kraken.out.sort', '-o', f'{out}/kaiju_merged_outputs.tsv', '-c', conflict_mode]
        if conflict_mode in {'lca', 'lowest'}:
            reference = str(inputs.get('reference_database', '')).rstrip('/')
            cmd.extend(['-t', f'{reference}/nodes.dmp'])
        if inputs.get('use_score', False):
            cmd.append('-s')
        cmd.append('-v')
        commands = [f"sort -k2,2 {shlex.quote(str(inputs.get('kaiju_table', '')))} > kaiju.out.sort", f"sort -k2,2 {shlex.quote(str(inputs.get('kraken_table', '')))} > kraken.out.sort", shlex.join(cmd)]
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'kaiju_merged_outputs.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'kaiju_table': ('TSV', {'description': 'Kaiju output table sorted by read identifier before merging'}), 'kraken_table': ('TSV', {'description': 'Second classification table in Kaiju/Kraken column format'})}, 'optional': {'reference_database': ('DIRECTORY', {'description': 'Kaiju database directory containing nodes.dmp for LCA conflict modes'}), 'conflict_mode': ('STRING', {'default': 'lca', 'options': ['1', '2', 'lca', 'lowest'], 'description': 'Resolve conflicting taxon IDs from the first input, second input, LCA, or lowest lineage match'}), 'use_score': ('BOOLEAN', {'default': False, 'description': 'Use the fourth-column classification score to prefer better-scoring taxa'})}, 'hidden': {'output': ('STRING', {})}}
