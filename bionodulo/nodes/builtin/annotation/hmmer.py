"""hmmer — annotation node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class HMMERAlimaskNode(CommandNode):
    """Apply an HMMER model or alignment coordinate mask to an MSA."""
    NODE_ID = 'hmmer_alimask'
    DISPLAY_NAME = 'HMMER alimask'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Append a mask line to a multiple sequence alignment using HMMER alimask.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'alimask', 'alignment mask', 'model range', 'Stockholm alignment']
    RETURN_TYPES = ('ALIGNMENT',)
    RETURN_NAMES = ('masked_alignment',)
    REQUIRED_EXECUTABLES = ['alimask']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'HMMER web server: interactive sequence similarity searching.'
    VERSION = '3.4'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        range_flag = '--alirange' if str(inputs.get('range_type', 'model')) == 'ali' else '--modelrange'
        cmd = ['alimask', range_flag, ','.join(_as_list(inputs.get('ranges')))]
        input_format = str(inputs.get('input_format', '--amino'))
        if input_format:
            cmd.append(input_format)
        model_construction = str(inputs.get('model_construction', 'fast'))
        if model_construction:
            cmd.append(model_construction if model_construction.startswith('--') else f'--{model_construction}')
        if model_construction in {'fast', '--fast'}:
            _add_if_value(cmd, '--symfrac', inputs.get('symfrac', 0.5))
        _add_if_value(cmd, '--fragthresh', inputs.get('fragthresh', 0.5))
        relative_weighting = str(inputs.get('relative_weighting', '--wpb'))
        if relative_weighting:
            cmd.append(relative_weighting)
        if relative_weighting == '--wblosum':
            _add_if_value(cmd, '--wid', inputs.get('wid', 0.62))
        _add_if_value(cmd, '--seed', inputs.get('seed', 42))
        cmd.extend([str(inputs.get('msafile', '')), f'{out}/masked.sto'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'masked.sto']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'msafile': ('ALIGNMENT', {'description': 'Multiple sequence alignment to mask'}), 'range_type': ('STRING', {'default': 'model', 'options': ['model', 'ali'], 'description': 'Interpret ranges in model or alignment coordinates'}), 'ranges': ('STRING', {'list': True, 'description': 'One or more inclusive ranges such as 12-40'})}, 'optional': {'input_format': ('STRING', {'default': '--amino', 'options': ['--amino', '--dna', '--rna'], 'description': 'Alignment alphabet'}), 'model_construction': ('STRING', {'default': 'fast', 'options': ['fast', 'hand'], 'description': 'How alimask chooses consensus columns for model-coordinate ranges'}), 'symfrac': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Residue fraction threshold for fast consensus-column assignment', 'displayOptions': {'show': {'model_construction': ['fast']}}}), 'fragthresh': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Sequence-length fraction below which sequences are fragments'}), 'relative_weighting': ('STRING', {'default': '--wpb', 'options': ['--wpb', '--wgsc', '--wblosum', '--wnone', '--wgiven'], 'description': 'Relative sequence weighting strategy'}), 'wid': ('FLOAT', {'default': 0.62, 'min': 0, 'max': 1, 'description': 'Identity cutoff for BLOSUM-style weighting', 'displayOptions': {'show': {'relative_weighting': ['--wblosum']}}}), 'seed': ('INT', {'default': 42, 'min': 0, 'description': 'Random seed; 0 chooses a random seed'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERHmmbuildNode(CommandNode):
    """Build a profile HMM from a multiple sequence alignment."""
    NODE_ID = 'hmmer_hmmbuild'
    DISPLAY_NAME = 'HMMER hmmbuild'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Build a profile HMM from a multiple sequence alignment.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'hmmbuild', 'profile HMM', 'multiple sequence alignment', 'HMM profile']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('hmm_profile',)
    REQUIRED_EXECUTABLES = ['hmmbuild']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'HMMER web server: interactive sequence similarity searching.'
    VERSION = '3.4'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['hmmbuild']
        _add_if_value(cmd, '-n', inputs.get('hmmname'))
        input_format = str(inputs.get('input_format_select', '--amino'))
        if input_format:
            cmd.append(input_format)
        model_construction = str(inputs.get('model_construction', 'fast'))
        if model_construction:
            cmd.append(model_construction if model_construction.startswith('--') else f'--{model_construction}')
        if model_construction in {'fast', '--fast'}:
            _add_if_value(cmd, '--symfrac', inputs.get('symfrac', 0.5))
        _add_if_value(cmd, '--fragthresh', inputs.get('fragthresh', 0.5))
        relative_weighting = str(inputs.get('relative_weighting', '--wpb'))
        if relative_weighting:
            cmd.append(relative_weighting)
        if relative_weighting == '--wblosum':
            _add_if_value(cmd, '--wid', inputs.get('wid', 0.62))
        effective_weighting = str(inputs.get('effective_weighting', ''))
        if effective_weighting:
            cmd.append(effective_weighting if effective_weighting.startswith('--') else f'--{effective_weighting}')
        if effective_weighting == 'eent':
            _add_if_value(cmd, '--eset', inputs.get('eset', 0))
            _add_if_value(cmd, '--ere', inputs.get('ere', 0))
            _add_if_value(cmd, '--esigma', inputs.get('esigma', 45))
        elif effective_weighting == 'eclust':
            _add_if_value(cmd, '--eset', inputs.get('eset', 0))
            _add_if_value(cmd, '--eid', inputs.get('eid', 0.62))
        prior = str(inputs.get('prior', ''))
        if prior:
            cmd.append(prior)
        if str(inputs.get('single_sequence_scoring', 'false')) == 'singlemx':
            _add_if_value(cmd, '--popen', inputs.get('popen', 0.02))
            _add_if_value(cmd, '--pextend', inputs.get('pextend', 0.4))
        _add_if_value(cmd, '--EmL', inputs.get('eml', 200))
        _add_if_value(cmd, '--EmN', inputs.get('emn', 200))
        _add_if_value(cmd, '--EvL', inputs.get('evl', 200))
        _add_if_value(cmd, '--EvN', inputs.get('evn', 200))
        _add_if_value(cmd, '--EfL', inputs.get('efl', 100))
        _add_if_value(cmd, '--EfN', inputs.get('efn', 200))
        _add_if_value(cmd, '--Eft', inputs.get('eft', 0.04))
        _add_if_value(cmd, '--cpu', max(1, int(inputs.get('threads', 1)) - 1))
        _add_if_value(cmd, '--seed', inputs.get('seed', 42))
        _add_if_value(cmd, '--w_beta', inputs.get('w_beta'))
        _add_if_value(cmd, '--w_length', inputs.get('w_length'))
        _add_if_value(cmd, '--maxinsertlen', inputs.get('maxinsertlen'))
        cmd.extend([f'{out}/profile.hmm', str(inputs.get('msafile', ''))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'profile.hmm']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'msafile': ('ALIGNMENT', {'description': 'Stockholm, Clustal, or FASTA multiple sequence alignment'})}, 'optional': {'hmmname': ('STRING', {'default': '', 'description': 'Name for the HMM'}), 'input_format_select': ('STRING', {'default': '--amino', 'options': ['--amino', '--dna', '--rna'], 'description': 'Alignment alphabet'}), 'model_construction': ('STRING', {'default': 'fast', 'options': ['fast', 'hand'], 'description': 'Profile model construction strategy'}), 'symfrac': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Residue fraction threshold for fast consensus-column assignment', 'displayOptions': {'show': {'model_construction': ['fast']}}}), 'fragthresh': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1, 'description': 'Sequence-length fraction below which sequences are fragments'}), 'relative_weighting': ('STRING', {'default': '--wpb', 'options': ['--wpb', '--wgsc', '--wblosum', '--wnone', '--wgiven'], 'description': 'Relative sequence weighting strategy'}), 'wid': ('FLOAT', {'default': 0.62, 'min': 0, 'max': 1, 'description': 'Identity cutoff for BLOSUM-style weighting', 'displayOptions': {'show': {'relative_weighting': ['--wblosum']}}}), 'effective_weighting': ('STRING', {'default': '', 'options': ['', 'eent', 'eclust', 'enone'], 'description': 'Effective sequence weighting strategy'}), 'eset': ('FLOAT', {'default': 0, 'description': 'Explicit effective sequence number', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eent', 'eclust']}}}), 'ere': ('FLOAT', {'default': 0, 'description': 'Minimum relative entropy per position for eent', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eent']}}}), 'esigma': ('FLOAT', {'default': 45, 'description': 'Minimum total relative entropy for eent', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eent']}}}), 'eid': ('FLOAT', {'default': 0.62, 'min': 0, 'max': 1, 'description': 'Single-linkage identity cutoff for eclust', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eclust']}}}), 'prior': ('STRING', {'default': '', 'options': ['', '--pnone', '--plaplace'], 'description': 'Alternative prior strategy', 'advanced': True}), 'single_sequence_scoring': ('STRING', {'default': 'false', 'options': ['false', 'singlemx'], 'description': 'Single-sequence scoring mode', 'advanced': True}), 'popen': ('FLOAT', {'default': 0.02, 'min': 0, 'max': 0.5, 'description': 'Gap open probability for singlemx', 'advanced': True, 'displayOptions': {'show': {'single_sequence_scoring': ['singlemx']}}}), 'pextend': ('FLOAT', {'default': 0.4, 'min': 0, 'max': 1, 'description': 'Gap extend probability for singlemx', 'advanced': True, 'displayOptions': {'show': {'single_sequence_scoring': ['singlemx']}}}), 'eml': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'emn': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'evl': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'evn': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'efl': ('INT', {'default': 100, 'min': 1, 'advanced': True}), 'efn': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'eft': ('FLOAT', {'default': 0.04, 'min': 0, 'max': 1, 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'seed': ('INT', {'default': 42, 'min': 0, 'description': 'Random seed; 0 chooses a random seed'}), 'w_beta': ('FLOAT', {'default': '', 'advanced': True, 'description': 'Window-length tail mass'}), 'w_length': ('INT', {'default': '', 'advanced': True, 'description': 'Window length'}), 'maxinsertlen': ('INT', {'default': '', 'advanced': True, 'description': 'Pretend all inserts are at most this length'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERHmmconvertNode(CommandNode):
    """Convert HMM profile files between HMMER formats."""
    NODE_ID = 'hmmer_hmmconvert'
    DISPLAY_NAME = 'HMMER hmmconvert'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Convert HMM profile files between HMMER formats.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'hmmconvert', 'HMMER2', 'HMMER3', 'profile conversion']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('converted_profile',)
    REQUIRED_EXECUTABLES = ['hmmconvert']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'HMMER web server: interactive sequence similarity searching.'
    VERSION = '3.4'
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return 'converted.hmm2' if str(inputs.get('format', '-a')) == '-2' else 'converted.hmm3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['hmmconvert', str(inputs.get('format', '-a')), str(inputs.get('hmmfile', ''))]
        _add_shell_redirect(cmd, f'{out}/{cls._output_name(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'hmmfile': ('FILE', {'description': 'Input profile HMM in HMMER2 or HMMER3 format'}), 'format': ('STRING', {'default': '-a', 'options': ['-a', '-2'], 'description': 'Output HMMER3 ASCII or backward-compatible HMMER2 ASCII format'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERHmmemitNode(CommandNode):
    """Sample sequences or consensus output from a profile HMM."""
    NODE_ID = 'hmmer_hmmemit'
    DISPLAY_NAME = 'HMMER hmmemit'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Sample sequences or consensus output from a profile HMM.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'hmmemit', 'emit sequences', 'consensus sequence', 'profile sampling']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('emitted_sequences',)
    REQUIRED_EXECUTABLES = ['hmmemit']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'HMMER web server: interactive sequence similarity searching.'
    VERSION = '3.4'
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return 'emitted.sto' if str(inputs.get('output_mode', 'fasta')) == 'aln' else 'emitted.fasta'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_mode = str(inputs.get('output_mode', 'fasta'))
        cmd = ['hmmemit']
        if output_mode == 'aln':
            _add_if_value(cmd, '-N', inputs.get('n_alignment', 1))
            cmd.append('-a')
        elif output_mode == 'mrcs':
            cmd.append('-c')
        elif output_mode == 'mrcsf':
            _add_if_value(cmd, '--minl', inputs.get('minl', 0.7))
            _add_if_value(cmd, '--minu', inputs.get('minu', 0.2))
            cmd.append('-C')
        elif output_mode == 'sample':
            _add_if_value(cmd, '-N', inputs.get('n_sample', 1))
            cmd.append('-p')
            _add_if_value(cmd, '-L', inputs.get('length'))
            emission_profile = str(inputs.get('emission_profile', '--local'))
            if emission_profile:
                cmd.append(emission_profile)
        else:
            _add_if_value(cmd, '-N', inputs.get('n_fasta', 1))
        _add_if_value(cmd, '--seed', inputs.get('seed', 42))
        cmd.append(str(inputs.get('hmmfile', '')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/{cls._output_name(inputs)}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'hmmfile': ('FILE', {'description': 'Profile HMM file'}), 'output_mode': ('STRING', {'default': 'fasta', 'options': ['fasta', 'aln', 'mrcs', 'mrcsf', 'sample'], 'description': 'Emit FASTA, alignment, consensus, or profile-sampled sequences'})}, 'optional': {'n_fasta': ('INT', {'default': 1, 'min': 1, 'description': 'Number of FASTA sequences to generate', 'displayOptions': {'show': {'output_mode': ['fasta']}}}), 'n_alignment': ('INT', {'default': 1, 'min': 1, 'description': 'Number of sequences to include in the emitted alignment', 'displayOptions': {'show': {'output_mode': ['aln']}}}), 'n_sample': ('INT', {'default': 1, 'min': 1, 'description': 'Number of profile-sampled sequences to generate', 'displayOptions': {'show': {'output_mode': ['sample']}}}), 'minl': ('FLOAT', {'default': 0.7, 'description': 'Fancier consensus lower probability threshold', 'displayOptions': {'show': {'output_mode': ['mrcsf']}}}), 'minu': ('FLOAT', {'default': 0.2, 'description': 'Fancier consensus uppercase probability threshold', 'displayOptions': {'show': {'output_mode': ['mrcsf']}}}), 'length': ('INT', {'default': '', 'description': 'Expected target length for profile sampling', 'displayOptions': {'show': {'output_mode': ['sample']}}}), 'emission_profile': ('STRING', {'default': '--local', 'options': ['--local', '--unilocal', '--glocal', '--uniglocal'], 'description': 'Search-profile alignment mode for sampled sequences', 'displayOptions': {'show': {'output_mode': ['sample']}}}), 'seed': ('INT', {'default': 42, 'min': 0, 'description': 'Random seed; 0 chooses a random seed'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERHmmfetchNode(CommandNode):
    """Retrieve selected profile HMM models from a HMM file."""
    NODE_ID = 'hmmer_hmmfetch'
    DISPLAY_NAME = 'HMMER hmmfetch'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Retrieve selected profile HMM models from a HMM file.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'hmmfetch', 'retrieve HMM', 'profile HMM names', 'Pfam subset']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('selected_hmm_models',)
    REQUIRED_EXECUTABLES = ['hmmfetch']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'HMMER web server: interactive sequence similarity searching.'
    VERSION = '3.4'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['hmmfetch', '-f', str(inputs.get('hmmfile', '')), str(inputs.get('keyfile', ''))]
        _add_shell_redirect(cmd, f'{_out(inputs)}/selected.hmm')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'selected.hmm']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'hmmfile': ('FILE', {'description': 'Profile HMM file to retrieve models from'}), 'keyfile': ('FILE', {'description': 'Text or tabular file with one HMM name per line'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERJackhmmerNode(CommandNode):
    """Iteratively search protein sequences against a protein FASTA database."""
    NODE_ID = 'hmmer_jackhmmer'
    DISPLAY_NAME = 'HMMER jackhmmer'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Iteratively search protein sequences against a protein FASTA database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'jackhmmer', 'iterative search', 'profile iteration', 'PSI-BLAST-like']
    RETURN_TYPES = ('STATS_FILE', 'TSV', 'TSV')
    RETURN_NAMES = ('output', 'tblout', 'domtblout')
    REQUIRED_EXECUTABLES = ['jackhmmer']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'HMMER web server: interactive sequence similarity searching.'
    VERSION = '3.4'
    SHELL = True
    DEFAULT_OUTPUT_FORMATS = ('tblout', 'domtblout')

    @classmethod
    def _output_formats(cls, inputs: dict[str, Any]) -> list[str]:
        if 'output_formats' not in inputs:
            return list(cls.DEFAULT_OUTPUT_FORMATS)
        return _as_list(inputs.get('output_formats'))

    @classmethod
    def _add_output_format_flags(cls, cmd: list[str], inputs: dict[str, Any], out: str) -> None:
        output_formats = set(cls._output_formats(inputs))
        if 'tblout' in output_formats:
            cmd.extend(['--tblout', f'{out}/results.tblout'])
        if 'domtblout' in output_formats:
            cmd.extend(['--domtblout', f'{out}/domains.domtblout'])

    @classmethod
    def _add_output_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key, flag in (('acc', '--acc'), ('noali', '--noali'), ('notextw', '--notextw')):
            if inputs.get(key):
                cmd.append(flag)

    @classmethod
    def _add_single_sequence_scoring(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get('single_sequence_scoring', 'false')) == 'singlemx':
            _add_if_value(cmd, '--popen', inputs.get('popen', 0.02))
            _add_if_value(cmd, '--pextend', inputs.get('pextend', 0.4))

    @classmethod
    def _add_thresholds(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        threshold_mode = str(inputs.get('threshold_mode', 'evalue'))
        if threshold_mode == 'score':
            _add_if_value(cmd, '-T', inputs.get('score_threshold'))
            _add_if_value(cmd, '--incT', inputs.get('incT'))
        else:
            _add_if_value(cmd, '-E', inputs.get('evalue', 10))
            _add_if_value(cmd, '--incE', inputs.get('incE'))

    @classmethod
    def _add_acceleration_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get('max'):
            cmd.append('--max')
        _add_if_value(cmd, '--F1', inputs.get('F1', 0.02))
        _add_if_value(cmd, '--F2', inputs.get('F2', 0.001))
        _add_if_value(cmd, '--F3', inputs.get('F3', 1e-05))
        if inputs.get('nobias'):
            cmd.append('--nobias')

    @classmethod
    def _add_weighting_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        relative_weighting = str(inputs.get('relative_weighting', '--wpb'))
        if relative_weighting:
            cmd.append(relative_weighting)
        if relative_weighting == '--wblosum':
            _add_if_value(cmd, '--wid', inputs.get('wid', 0.62))
        effective_weighting = str(inputs.get('effective_weighting', ''))
        if effective_weighting:
            cmd.append(effective_weighting if effective_weighting.startswith('--') else f'--{effective_weighting}')
        if effective_weighting == 'eent':
            _add_if_value(cmd, '--eset', inputs.get('eset', 0))
            _add_if_value(cmd, '--ere', inputs.get('ere', 0))
            _add_if_value(cmd, '--esigma', inputs.get('esigma', 45))
        elif effective_weighting == 'eclust':
            _add_if_value(cmd, '--eset', inputs.get('eset', 0))
            _add_if_value(cmd, '--eid', inputs.get('eid', 0.62))
        prior = str(inputs.get('prior', ''))
        if prior:
            cmd.append(prior)

    @classmethod
    def _add_calibration_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        _add_if_value(cmd, '--EmL', inputs.get('eml', 200))
        _add_if_value(cmd, '--EmN', inputs.get('emn', 200))
        _add_if_value(cmd, '--EvL', inputs.get('evl', 200))
        _add_if_value(cmd, '--EvN', inputs.get('evn', 200))
        _add_if_value(cmd, '--EfL', inputs.get('efl', 100))
        _add_if_value(cmd, '--EfN', inputs.get('efn', 200))
        _add_if_value(cmd, '--Eft', inputs.get('eft', 0.04))

    @classmethod
    def _add_advanced_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get('nonull2'):
            cmd.append('--nonull2')
        _add_if_value(cmd, '-Z', inputs.get('z'))
        _add_if_value(cmd, '--domZ', inputs.get('domz'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['jackhmmer', '-N', str(inputs.get('iterations', 5))]
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_single_sequence_scoring(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        cls._add_weighting_options(cmd, inputs)
        cls._add_calibration_options(cmd, inputs)
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, '--cpu', max(1, int(inputs.get('threads', 1)) - 1))
        _add_if_value(cmd, '--seed', inputs.get('seed', 42))
        cmd.extend([str(inputs.get('seqfile', '')), str(inputs.get('seqdb', ''))])
        _add_shell_redirect(cmd, f'{out}/output.txt')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = {'output': out / 'output.txt'}
        output_formats = set(cls._output_formats(inputs))
        if 'tblout' in output_formats:
            outputs['tblout'] = out / 'results.tblout'
        if 'domtblout' in output_formats:
            outputs['domtblout'] = out / 'domains.domtblout'
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'seqfile': ('FASTA', {'description': 'Protein sequence FASTA to search with'}), 'seqdb': ('FASTA', {'description': 'Protein sequence database FASTA'})}, 'optional': {'iterations': ('INT', {'default': 5, 'min': 1, 'description': 'Maximum number of iterations'}), 'output_formats': ('STRING', {'default': ['tblout', 'domtblout'], 'options': ['tblout', 'domtblout'], 'list': True, 'description': 'Additional tabular output files to write'}), 'acc': ('BOOLEAN', {'default': False, 'description': 'Prefer accessions over names in output'}), 'noali': ('BOOLEAN', {'default': False, 'description': 'Suppress alignment blocks in text output'}), 'notextw': ('BOOLEAN', {'default': False, 'description': 'Use unlimited text output line width'}), 'single_sequence_scoring': ('STRING', {'default': 'false', 'options': ['false', 'singlemx'], 'description': 'Single-sequence scoring mode'}), 'popen': ('FLOAT', {'default': 0.02, 'min': 0, 'max': 0.5, 'description': 'Gap open probability for singlemx', 'displayOptions': {'show': {'single_sequence_scoring': ['singlemx']}}}), 'pextend': ('FLOAT', {'default': 0.4, 'min': 0, 'max': 1, 'description': 'Gap extend probability for singlemx', 'displayOptions': {'show': {'single_sequence_scoring': ['singlemx']}}}), 'threshold_mode': ('STRING', {'default': 'evalue', 'options': ['evalue', 'score'], 'description': 'Reporting threshold mode'}), 'evalue': ('FLOAT', {'default': 10, 'min': 0, 'description': 'E-value reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['evalue']}}}), 'incE': ('FLOAT', {'default': '', 'description': 'E-value inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['evalue']}}}), 'score_threshold': ('FLOAT', {'default': '', 'description': 'Bit score reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['score']}}}), 'incT': ('FLOAT', {'default': '', 'description': 'Bit score inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['score']}}}), 'max': ('BOOLEAN', {'default': False, 'description': 'Turn all heuristic filters off', 'advanced': True}), 'F1': ('FLOAT', {'default': 0.02, 'min': 0, 'advanced': True}), 'F2': ('FLOAT', {'default': 0.001, 'min': 0, 'advanced': True}), 'F3': ('FLOAT', {'default': 1e-05, 'min': 0, 'advanced': True}), 'nobias': ('BOOLEAN', {'default': False, 'description': 'Turn off composition bias filter', 'advanced': True}), 'relative_weighting': ('STRING', {'default': '--wpb', 'options': ['--wpb', '--wgsc', '--wblosum', '--wnone', '--wgiven'], 'description': 'Relative sequence weighting strategy', 'advanced': True}), 'wid': ('FLOAT', {'default': 0.62, 'min': 0, 'max': 1, 'description': 'Identity cutoff for BLOSUM-style weighting', 'advanced': True, 'displayOptions': {'show': {'relative_weighting': ['--wblosum']}}}), 'effective_weighting': ('STRING', {'default': '', 'options': ['', 'eent', 'eclust', 'enone'], 'description': 'Effective sequence weighting strategy', 'advanced': True}), 'eset': ('FLOAT', {'default': 0, 'description': 'Explicit effective sequence number', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eent', 'eclust']}}}), 'ere': ('FLOAT', {'default': 0, 'description': 'Minimum relative entropy per position for eent', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eent']}}}), 'esigma': ('FLOAT', {'default': 45, 'description': 'Minimum total relative entropy for eent', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eent']}}}), 'eid': ('FLOAT', {'default': 0.62, 'min': 0, 'max': 1, 'description': 'Single-linkage identity cutoff for eclust', 'advanced': True, 'displayOptions': {'show': {'effective_weighting': ['eclust']}}}), 'prior': ('STRING', {'default': '', 'options': ['', '--pnone', '--plaplace'], 'description': 'Alternative prior strategy', 'advanced': True}), 'eml': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'emn': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'evl': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'evn': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'efl': ('INT', {'default': 100, 'min': 1, 'advanced': True}), 'efn': ('INT', {'default': 200, 'min': 1, 'advanced': True}), 'eft': ('FLOAT', {'default': 0.04, 'min': 0, 'max': 1, 'advanced': True}), 'nonull2': ('BOOLEAN', {'default': False, 'description': 'Turn off biased composition score corrections', 'advanced': True}), 'z': ('INT', {'default': '', 'description': 'Comparisons for E-value calculation', 'advanced': True}), 'domz': ('INT', {'default': '', 'description': 'Significant sequences for domain E-value calculation', 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'seed': ('INT', {'default': 42, 'min': 0, 'description': 'Random seed; 0 chooses a random seed'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERHmmsearchNode(CommandNode):
    """Search sequence databases with profile HMMs using hmmsearch."""
    NODE_ID = 'hmmer_hmmsearch'
    DISPLAY_NAME = 'HMMER hmmsearch'
    REQUIRED_CONDA_PACKAGES = ['hmmer']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Search one or more profile HMMs against a sequence FASTA database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'hmmsearch', 'profile hmm', 'domain search']
    RETURN_TYPES = ('STATS_FILE', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('output', 'tblout', 'domtblout', 'pfamtblout')
    REQUIRED_EXECUTABLES = ['hmmsearch']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/nar/gkr367']
    CITATION_URLS = ['https://doi.org/10.1093/nar/gkr367']
    CITATION_TEXT = 'Accelerated profile HMM searches.'
    VERSION = '3.4'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['hmmsearch', '--cpu', str(inputs.get('threads', 1))]
        _add_if_value(cmd, '-E', inputs.get('evalue'))
        _add_if_value(cmd, '--incE', inputs.get('incE'))
        _add_if_value(cmd, '--domE', inputs.get('domE'))
        _add_if_value(cmd, '--incdomE', inputs.get('incdomE'))
        if inputs.get('cut_ga'):
            cmd.append('--cut_ga')
        if inputs.get('cut_tc'):
            cmd.append('--cut_tc')
        if inputs.get('cut_nc'):
            cmd.append('--cut_nc')
        if inputs.get('notextw'):
            cmd.append('--notextw')
        out = _out(inputs)
        cmd.extend(['--tblout', f'{out}/results.tblout', '--domtblout', f'{out}/domains.domtblout', '--pfamtblout', f'{out}/pfam.tblout', '-o', f'{out}/output.txt', str(inputs.get('hmmfile', '')), str(inputs.get('seqdb', ''))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.txt', out / 'results.tblout', out / 'domains.domtblout', out / 'pfam.tblout']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'hmmfile': ('FILE', {'description': 'Profile HMM file'}), 'seqdb': ('FASTA', {'description': 'Sequence database FASTA'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'evalue': ('FLOAT', {'default': 10, 'min': 0}), 'incE': ('FLOAT', {'default': '', 'advanced': True}), 'domE': ('FLOAT', {'default': '', 'advanced': True}), 'incdomE': ('FLOAT', {'default': '', 'advanced': True}), 'cut_ga': ('BOOLEAN', {'default': False, 'advanced': True}), 'cut_tc': ('BOOLEAN', {'default': False, 'advanced': True}), 'cut_nc': ('BOOLEAN', {'default': False, 'advanced': True}), 'notextw': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
