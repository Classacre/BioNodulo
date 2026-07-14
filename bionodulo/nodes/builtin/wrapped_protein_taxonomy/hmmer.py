"""hmmer — wrapped_protein_taxonomy node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class HMMERPhmmerNode(HMMERJackhmmerNode):
    """Search protein sequences against a protein FASTA database."""
    NODE_ID = 'hmmer_phmmer'
    DISPLAY_NAME = 'HMMER phmmer'
    DESCRIPTION = 'Search protein sequences against a protein FASTA database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'phmmer', 'protein search', 'BLASTP-like', 'sequence homology']
    RETURN_TYPES = ('STATS_FILE', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('output', 'tblout', 'domtblout', 'pfamtblout')
    REQUIRED_EXECUTABLES = ['phmmer']
    DEFAULT_OUTPUT_FORMATS = ('tblout', 'domtblout', 'pfamtblout')

    @classmethod
    def _add_output_format_flags(cls, cmd: list[str], inputs: dict[str, Any], out: str) -> None:
        super()._add_output_format_flags(cmd, inputs, out)
        if 'pfamtblout' in set(cls._output_formats(inputs)):
            cmd.extend(['--pfamtblout', f'{out}/pfam.tblout'])

    @classmethod
    def _add_thresholds(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        threshold_mode = str(inputs.get('threshold_mode', 'evalue'))
        if threshold_mode == 'score':
            _add_if_value(cmd, '-T', inputs.get('score_threshold'))
            _add_if_value(cmd, '--incT', inputs.get('incT'))
            _add_if_value(cmd, '--domT', inputs.get('domT'))
            _add_if_value(cmd, '--incdomT', inputs.get('incdomT'))
        else:
            _add_if_value(cmd, '-E', inputs.get('evalue', 10))
            _add_if_value(cmd, '--incE', inputs.get('incE'))
            _add_if_value(cmd, '--domE', inputs.get('domE', 10))
            _add_if_value(cmd, '--incdomE', inputs.get('incdomE'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['phmmer']
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_single_sequence_scoring(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
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
        if 'pfamtblout' in output_formats:
            outputs['pfamtblout'] = out / 'pfam.tblout'
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        jackhmmer_inputs = super().INPUT_TYPES()
        optional = dict(jackhmmer_inputs['optional'])
        optional.pop('iterations')
        for jackhmmer_only in ('relative_weighting', 'wid', 'effective_weighting', 'eset', 'ere', 'esigma', 'eid', 'prior'):
            optional.pop(jackhmmer_only, None)
        optional['output_formats'] = ('STRING', {'default': ['tblout', 'domtblout', 'pfamtblout'], 'options': ['tblout', 'domtblout', 'pfamtblout'], 'list': True, 'description': 'Additional tabular output files to write'})
        optional['domE'] = ('FLOAT', {'default': 10, 'min': 0, 'description': 'Domain E-value reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['evalue']}}})
        optional['incdomE'] = ('FLOAT', {'default': '', 'description': 'Domain E-value inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['evalue']}}})
        optional['domT'] = ('FLOAT', {'default': '', 'description': 'Domain bit score reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['score']}}})
        optional['incdomT'] = ('FLOAT', {'default': '', 'description': 'Domain bit score inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['score']}}})
        return {'required': jackhmmer_inputs['required'], 'optional': optional, 'hidden': {'output': ('STRING', {})}}


class HMMERNhmmerNode(HMMERJackhmmerNode):
    """Search nucleotide queries against a nucleotide FASTA database."""
    NODE_ID = 'hmmer_nhmmer'
    DISPLAY_NAME = 'HMMER nhmmer'
    DESCRIPTION = 'Search a nucleotide profile HMM or alignment against a nucleotide FASTA database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'nhmmer', 'DNA search', 'RNA search', 'BLASTN-like', 'nucleotide homology']
    RETURN_TYPES = ('STATS_FILE', 'TSV', 'TEXT', 'TEXT')
    RETURN_NAMES = ('output', 'tblout', 'dfamtblout', 'aliscoresout')
    REQUIRED_EXECUTABLES = ['nhmmer']
    DOCUMENTATION_URL = 'http://hmmer.org/documentation.html'
    CITATION_DOIS = ['10.1093/bioinformatics/btt403']
    CITATION_URLS = ['https://doi.org/10.1093/bioinformatics/btt403']
    CITATION_TEXT = 'nhmmer: DNA homology search with profile HMMs.'
    DEFAULT_OUTPUT_FORMATS = ('tblout', 'dfamtblout')

    @classmethod
    def _add_output_format_flags(cls, cmd: list[str], inputs: dict[str, Any], out: str) -> None:
        output_formats = set(cls._output_formats(inputs))
        if 'tblout' in output_formats:
            cmd.extend(['--tblout', f'{out}/results.tblout'])
        if 'dfamtblout' in output_formats:
            cmd.extend(['--dfamtblout', f'{out}/dfam.tblout'])
        if 'aliscoresout' in output_formats:
            cmd.extend(['--aliscoresout', f'{out}/alignment_scores.txt'])

    @classmethod
    def _add_thresholds(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        threshold_mode = str(inputs.get('threshold_mode', 'evalue'))
        if threshold_mode == 'score':
            _add_if_value(cmd, '-T', inputs.get('score_threshold'))
            _add_if_value(cmd, '--incT', inputs.get('incT'))
        elif threshold_mode == 'cut':
            cut_mode = str(inputs.get('cut_mode', 'none'))
            if cut_mode != 'none':
                cmd.append(cut_mode)
        else:
            _add_if_value(cmd, '-E', inputs.get('evalue', 10))
            _add_if_value(cmd, '--incE', inputs.get('incE'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['nhmmer']
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_single_sequence_scoring(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        input_format = str(inputs.get('input_format_select', '--dna'))
        if input_format:
            cmd.append(input_format)
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, '--w_beta', inputs.get('w_beta'))
        _add_if_value(cmd, '--w_length', inputs.get('w_length'))
        _add_if_value(cmd, '--cpu', max(1, int(inputs.get('threads', 1)) - 1))
        _add_if_value(cmd, '--seed', inputs.get('seed', 42))
        cmd.extend([str(inputs.get('hmmfile', '')), str(inputs.get('seqfile', ''))])
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
        if 'dfamtblout' in output_formats:
            outputs['dfamtblout'] = out / 'dfam.tblout'
        if 'aliscoresout' in output_formats:
            outputs['aliscoresout'] = out / 'alignment_scores.txt'
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'hmmfile': ('FILE', {'description': 'Nucleotide profile HMM, alignment, or single-sequence query'}), 'seqfile': ('FASTA', {'description': 'Target nucleotide FASTA database'})}, 'optional': {'output_formats': ('STRING', {'default': ['tblout', 'dfamtblout'], 'options': ['tblout', 'dfamtblout', 'aliscoresout'], 'list': True, 'description': 'Additional tabular or positional score output files to write'}), 'acc': ('BOOLEAN', {'default': False, 'description': 'Prefer accessions over names in output'}), 'noali': ('BOOLEAN', {'default': False, 'description': 'Suppress alignment blocks in text output'}), 'notextw': ('BOOLEAN', {'default': False, 'description': 'Use unlimited text output line width'}), 'single_sequence_scoring': ('STRING', {'default': 'false', 'options': ['false', 'singlemx'], 'description': 'Single-sequence scoring mode'}), 'popen': ('FLOAT', {'default': 0.02, 'min': 0, 'max': 0.5, 'description': 'Gap open probability for singlemx', 'displayOptions': {'show': {'single_sequence_scoring': ['singlemx']}}}), 'pextend': ('FLOAT', {'default': 0.4, 'min': 0, 'max': 1, 'description': 'Gap extend probability for singlemx', 'displayOptions': {'show': {'single_sequence_scoring': ['singlemx']}}}), 'threshold_mode': ('STRING', {'default': 'evalue', 'options': ['evalue', 'score', 'cut'], 'description': 'Reporting threshold mode'}), 'evalue': ('FLOAT', {'default': 10, 'min': 0, 'description': 'E-value reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['evalue']}}}), 'incE': ('FLOAT', {'default': '', 'description': 'E-value inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['evalue']}}}), 'score_threshold': ('FLOAT', {'default': '', 'description': 'Bit score reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['score']}}}), 'incT': ('FLOAT', {'default': '', 'description': 'Bit score inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['score']}}}), 'cut_mode': ('STRING', {'default': 'none', 'options': ['none', '--cut_ga', '--cut_nc', '--cut_tc'], 'description': 'Use model-specific GA, NC, or TC cutoffs', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['cut']}}}), 'max': ('BOOLEAN', {'default': False, 'description': 'Turn all heuristic filters off', 'advanced': True}), 'F1': ('FLOAT', {'default': 0.02, 'min': 0, 'advanced': True}), 'F2': ('FLOAT', {'default': 0.001, 'min': 0, 'advanced': True}), 'F3': ('FLOAT', {'default': 1e-05, 'min': 0, 'advanced': True}), 'nobias': ('BOOLEAN', {'default': False, 'description': 'Turn off composition bias filter', 'advanced': True}), 'input_format_select': ('STRING', {'default': '--dna', 'options': ['--dna', '--rna'], 'description': 'Alphabet for the query model and target sequences'}), 'nonull2': ('BOOLEAN', {'default': False, 'description': 'Turn off biased composition score corrections', 'advanced': True}), 'z': ('INT', {'default': '', 'description': 'Comparisons for E-value calculation', 'advanced': True}), 'domz': ('INT', {'default': '', 'description': 'Significant sequences for domain E-value calculation', 'advanced': True}), 'w_beta': ('FLOAT', {'default': '', 'advanced': True, 'description': 'Tail mass at which nhmmer sets window length'}), 'w_length': ('INT', {'default': '', 'advanced': True, 'description': 'Override nhmmer window length'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'seed': ('INT', {'default': 42, 'min': 0, 'description': 'Random seed; 0 chooses a random seed'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERNhmmscanNode(HMMERNhmmerNode):
    """Search nucleotide sequences against a nucleotide profile HMM database."""
    NODE_ID = 'hmmer_nhmmscan'
    DISPLAY_NAME = 'HMMER nhmmscan'
    DESCRIPTION = 'Search nucleotide sequences against a nucleotide profile HMM database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'nhmmscan', 'Dfam scan', 'DNA profile database', 'nucleotide profiles']
    REQUIRED_EXECUTABLES = ['nhmmscan', 'hmmpress']

    @classmethod
    def _hmm_database(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('hmm_source', 'history')) == 'indexed':
            return str(inputs.get('hmmdb', ''))
        return str(inputs.get('hmmfile', ''))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        hmm_database = cls._hmm_database(inputs)
        cmd: list[str] = []
        if str(inputs.get('hmm_source', 'history')) == 'history':
            cmd.extend(['hmmpress', hmm_database, '&&'])
        cmd.append('nhmmscan')
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        _add_if_value(cmd, '--B1', inputs.get('B1', 110))
        _add_if_value(cmd, '--B2', inputs.get('B2', 240))
        _add_if_value(cmd, '--B3', inputs.get('B3', 1000))
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, '--w_beta', inputs.get('w_beta'))
        _add_if_value(cmd, '--w_length', inputs.get('w_length'))
        _add_if_value(cmd, '--cpu', max(1, int(inputs.get('threads', 1)) - 1))
        _add_if_value(cmd, '--seed', inputs.get('seed', 42))
        cmd.extend([hmm_database, str(inputs.get('seqfile', ''))])
        _add_shell_redirect(cmd, f'{out}/output.txt')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'hmm_source': ('STRING', {'default': 'history', 'options': ['history', 'indexed'], 'description': 'Use a workflow HMM database or an already indexed database path'}), 'hmmfile': ('FILE', {'default': '', 'description': 'Nucleotide profile HMM database from the workflow history', 'displayOptions': {'show': {'hmm_source': ['history']}}}), 'hmmdb': ('FILE', {'default': '', 'description': 'Pre-indexed nucleotide profile HMM database', 'displayOptions': {'show': {'hmm_source': ['indexed']}}}), 'seqfile': ('FASTA', {'description': 'Nucleotide sequence FASTA queries'})}, 'optional': {'output_formats': ('STRING', {'default': ['tblout', 'dfamtblout'], 'options': ['tblout', 'dfamtblout', 'aliscoresout'], 'list': True, 'description': 'Additional tabular or positional score output files to write'}), 'acc': ('BOOLEAN', {'default': False, 'description': 'Prefer accessions over names in output'}), 'noali': ('BOOLEAN', {'default': False, 'description': 'Suppress alignment blocks in text output'}), 'notextw': ('BOOLEAN', {'default': False, 'description': 'Use unlimited text output line width'}), 'threshold_mode': ('STRING', {'default': 'evalue', 'options': ['evalue', 'score', 'cut'], 'description': 'Reporting threshold mode'}), 'evalue': ('FLOAT', {'default': 10, 'min': 0, 'description': 'E-value reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['evalue']}}}), 'incE': ('FLOAT', {'default': '', 'description': 'E-value inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['evalue']}}}), 'score_threshold': ('FLOAT', {'default': '', 'description': 'Bit score reporting threshold', 'displayOptions': {'show': {'threshold_mode': ['score']}}}), 'incT': ('FLOAT', {'default': '', 'description': 'Bit score inclusion threshold', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['score']}}}), 'cut_mode': ('STRING', {'default': 'none', 'options': ['none', '--cut_ga', '--cut_nc', '--cut_tc'], 'description': 'Use model-specific GA, NC, or TC cutoffs', 'advanced': True, 'displayOptions': {'show': {'threshold_mode': ['cut']}}}), 'max': ('BOOLEAN', {'default': False, 'description': 'Turn all heuristic filters off', 'advanced': True}), 'F1': ('FLOAT', {'default': 0.02, 'min': 0, 'advanced': True}), 'F2': ('FLOAT', {'default': 0.001, 'min': 0, 'advanced': True}), 'F3': ('FLOAT', {'default': 1e-05, 'min': 0, 'advanced': True}), 'nobias': ('BOOLEAN', {'default': False, 'description': 'Turn off composition bias filter', 'advanced': True}), 'B1': ('INT', {'default': 110, 'min': 1, 'description': 'MSV biased-composition modifier window length', 'advanced': True}), 'B2': ('INT', {'default': 240, 'min': 1, 'description': 'Viterbi biased-composition modifier window length', 'advanced': True}), 'B3': ('INT', {'default': 1000, 'min': 1, 'description': 'Forward biased-composition modifier window length', 'advanced': True}), 'nonull2': ('BOOLEAN', {'default': False, 'description': 'Turn off biased composition score corrections', 'advanced': True}), 'z': ('INT', {'default': '', 'description': 'Comparisons for E-value calculation', 'advanced': True}), 'domz': ('INT', {'default': '', 'description': 'Significant sequences for domain E-value calculation', 'advanced': True}), 'w_beta': ('FLOAT', {'default': '', 'advanced': True, 'description': 'Tail mass at which nhmmscan sets window length'}), 'w_length': ('INT', {'default': '', 'advanced': True, 'description': 'Override nhmmscan window length'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'seed': ('INT', {'default': 42, 'min': 0, 'description': 'Random seed; 0 chooses a random seed'})}, 'hidden': {'output': ('STRING', {})}}


class HMMERHmmscanNode(HMMERHmmsearchNode):
    """Search sequences against a profile HMM database using hmmscan."""
    NODE_ID = 'hmmer_hmmscan'
    DISPLAY_NAME = 'HMMER hmmscan'
    DESCRIPTION = 'Search protein sequences against a profile HMM database.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'hmmer', 'hmmscan', 'pfam', 'domain annotation']
    REQUIRED_EXECUTABLES = ['hmmscan']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['hmmscan', '--cpu', str(inputs.get('threads', 1))]
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
        cmd.extend(['--tblout', f'{out}/results.tblout', '--domtblout', f'{out}/domains.domtblout', '--pfamtblout', f'{out}/pfam.tblout', '-o', f'{out}/output.txt', str(inputs.get('hmmdb', '')), str(inputs.get('seqfile', ''))])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'seqfile': ('FASTA', {'description': 'Sequence FASTA'}), 'hmmdb': ('FILE', {'description': 'Profile HMM database'})}, 'optional': HMMERHmmsearchNode.INPUT_TYPES()['optional'], 'hidden': {'output': ('STRING', {})}}
