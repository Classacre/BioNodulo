"""beacon2 — wrapped_protein_taxonomy node(s). One tool per file (extracted from wrapped_protein_taxonomy.py)."""
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


class Beacon2AnalysesNode(_Beacon2SearchBaseNode):
    """Query the analyses collection in a Beacon database."""
    NODE_ID = 'beacon2_analyses'
    DISPLAY_NAME = 'Beacon2 Analyses'
    DESCRIPTION = 'Query the analyses collection in a Beacon database for bioinformatic procedures that identify variants.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_analyses', 'Beacon2 Analyses', 'beacon2-search analyses', 'analyses collection', 'bioinformatic procedures', 'variant caller', 'pipelineName']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_analyses_query',)
    SEARCH_COLLECTION = 'analyses'
    OUTPUT_FILENAME = 'analyses_query_findings.json'
    QUERY_FLAGS = (('aligner', '--aligner', 'Reference to mapping or alignment software, such as bwa-0.7.8'), ('analysisDate', '--analysisDate', 'Date at which analysis was performed'), ('biosampleId', '--biosampleId', 'ID of the biosample this analysis reports on'), ('identification', '--identification', 'Analysis reference ID, external accession, or internal ID'), ('individualId', '--individualId', 'ID of the individual this analysis reports on'), ('pipelineName', '--pipelineName', 'Analysis pipeline and version'), ('pipelineRef', '--pipelineRef', 'Link to the analysis pipeline resource'), ('runId', '--runId', 'Run identifier, external accession, or internal ID'), ('variantCaller', '--variantCaller', 'Variant calling software or pipeline'))


class Beacon2BiosamplesNode(_Beacon2SearchBaseNode):
    """Query the biosamples collection in a Beacon database."""
    NODE_ID = 'beacon2_biosamples'
    DISPLAY_NAME = 'Beacon2 Biosamples'
    DESCRIPTION = 'Query the biosamples collection in a Beacon database for samples taken from individuals.'
    VERSION = '1.0.0'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_biosamples', 'Beacon2 Biosamples', 'beacon2-search biosamples', 'biosamples collection', 'samples taken from individuals', 'biosampleStatus', 'sampleOriginDetail', 'tumorProgression']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_biosamples_query',)
    SEARCH_COLLECTION = 'biosamples'
    OUTPUT_FILENAME = 'biosamples_query_findings.json'
    QUERY_FLAGS = (('biosampleStatus', '--biosampleStatus', 'Ontology value classifying the sample status'), ('collectionDate', '--collectionDate', 'Date of biosample collection in ISO8601 format'), ('collectionMoment', '--collectionMoment', 'Age or duration at sample collection in ISO8601 duration format'), ('identification', '--identification', 'Biosample identifier, external accession, or internal ID'), ('diagnosticMarkers', '--diagnosticMarkers', 'Clinically relevant biomarkers'), ('histologicalDiagnosis', '--histologicalDiagnosis', 'Diagnosis inferred from histological examination'), ('obtentionProcedure', '--obtentionProcedure', 'Ontology value describing the sample obtention procedure'), ('pathologicalStage', '--pathologicalStage', 'Pathological stage, if applicable'), ('pathologicalTnmFinding', '--pathologicalTnmFinding', 'Pathological TNM finding'), ('featureType', '--featureType', 'Ontology term describing a phenotype feature'), ('severity', '--severity', 'Ontology class describing condition severity'), ('sampleOriginDetail', '--sampleOriginDetail', 'Tissue or sample-origin detail'), ('sampleOriginType', '--sampleOriginType', 'Category of sample origin'), ('sampleProcessing', '--sampleProcessing', 'Specimen processing status'), ('sampleStorage', '--sampleStorage', 'Specimen storage status'), ('tumorGrade', '--tumorGrade', 'Tumor grade term'), ('tumorProgression', '--tumorProgression', 'Tumor progression category'))


class Beacon2BracketNode(_Beacon2SearchBaseNode):
    """Query Beacon genomic variations by bracketed start and end ranges."""
    NODE_ID = 'beacon2_bracket'
    DISPLAY_NAME = 'Beacon2 Bracket'
    DESCRIPTION = 'Query Beacon genomic variations by sequence ranges for both start and end positions.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_bracket', 'Beacon2 Bracket', 'beacon2-search bracket', 'bracket query', 'genomic variation range', 'copy number variation', 'structural variant range']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_bracket_query',)
    SEARCH_COLLECTION = 'bracket'
    OUTPUT_FILENAME = 'bracket_query_findings.json'
    REQUIRED_QUERY_FLAGS = (('start_minimum', '--start-minimum', 'INT', 'Minimum start position of the genomic variation'), ('start_maximum', '--start-maximum', 'INT', 'Maximum start position of the genomic variation'), ('end_minimum', '--end-minimum', 'INT', 'Minimum end position of the genomic variation'), ('end_maximum', '--end-maximum', 'INT', 'Maximum end position of the genomic variation'))
    QUERY_FLAGS = (('variantType', '--variantType', 'Targeted variant type to search for'), ('referenceName', '--referenceName', 'Reference name such as chr1/1, chr2/2, chr3/3'))


class Beacon2CNVNode(_Beacon2SearchBaseNode):
    """Query Beacon copy number variants from genomicVariations."""
    NODE_ID = 'beacon2_cnv'
    DISPLAY_NAME = 'Beacon2 CNV'
    DESCRIPTION = 'Query copy number variants from the Beacon genomicVariations collection with optional overlap filters.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_cnv', 'Beacon2 CNV', 'beacon2-search cnv', 'copy number variants', 'genomicVariations', 'variantStateId', 'copy number loss', 'copy number gain']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_cnv_query',)
    SEARCH_COLLECTION = 'cnv'
    OUTPUT_FILENAME = 'cnv_query_findings.json'
    VARIANT_STATE_OPTIONS = ['', 'EFO:0030070', 'EFO:0030071', 'EFO:0030072', 'EFO:0030073', 'EFO:0030067', 'EFO:0030068', 'EFO:0020073', 'EFO:0030069']
    QUERY_FLAGS = (('variantInternalId', '--variantInternalId', 'Variant internal ID, such as 11:52900000-134452384:DEL'), ('analysisId', '--analysisId', 'Analysis identifier'), ('individualId', '--individualId', 'Individual identifier'), ('start', '--start', 'Start position'), ('end', '--end', 'End position'), ('chromosome', '--chromosome', 'Chromosome number without chr prefix'), ('variantStateId', '--variantStateId', 'Copy-number state ontology term'), ('sequenceId', '--sequenceId', 'Reference sequence ID, such as refseq:NC_000011.10'), ('variantType', '--variantType', 'Variant type such as DEL or DUP'), ('primarySite', '--primarySite', 'Primary site, such as breast or brain'), ('diseaseType', '--diseaseType', 'Disease type'), ('gene', '--gene', 'Gene name, such as BRCA1'))
    TYPED_QUERY_FLAGS = (('start', '--start', 'INT', 'Start position'), ('end', '--end', 'INT', 'End position'))
    QUERY_FLAG_OPTIONS = {'variantStateId': VARIANT_STATE_OPTIONS}


class Beacon2CohortsNode(_Beacon2SearchBaseNode):
    """Query the cohorts collection in a Beacon database."""
    NODE_ID = 'beacon2_cohorts'
    DISPLAY_NAME = 'Beacon2 Cohorts'
    DESCRIPTION = 'Query the cohorts collection in a Beacon database for populations or groups sharing common attributes.'
    VERSION = '1.0.0'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_cohorts', 'Beacon2 Cohorts', 'beacon2-search cohorts', 'cohorts collection', 'cohortDataTypes', 'cohortType', 'genders']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_cohorts_query',)
    SEARCH_COLLECTION = 'cohorts'
    OUTPUT_FILENAME = 'cohorts_query_findings.json'
    QUERY_FLAGS = (('cohortDataTypes', '--cohortDataTypes', 'Type of cohort data, such as clinical history'), ('cohortDesign', '--cohortDesign', 'Study-design plan or protocol, such as longitudinal study design'), ('cohortSize', '--cohortSize', 'Count of unique individuals in the cohort'), ('identification', '--identification', 'Cohort identifier, such as cohort0001'), ('cohortType', '--cohortType', 'Cohort type by definition, such as study-defined'), ('genders', '--genders', 'Gender filter for the cohort'), ('name', '--name', 'Name of the cohort'))
    TYPED_QUERY_FLAGS = (('cohortSize', '--cohortSize', 'INT', 'Count of unique individuals in the cohort'),)
    QUERY_FLAG_OPTIONS = {'genders': ['', 'male', 'female']}


class Beacon2DatasetsNode(_Beacon2SearchBaseNode):
    """Query the datasets collection in a Beacon database."""
    NODE_ID = 'beacon2_datasets'
    DISPLAY_NAME = 'Beacon2 Datasets'
    DESCRIPTION = 'Query the datasets collection in a Beacon database for repositories containing variants or individuals.'
    VERSION = '1.0.0'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_datasets', 'Beacon2 Datasets', 'beacon2-search datasets', 'datasets collection', 'dataUseConditions', 'ontologyModifiers', 'repository']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_datasets_query',)
    SEARCH_COLLECTION = 'datasets'
    OUTPUT_FILENAME = 'datasets_query_findings.json'
    QUERY_FLAGS = (('dataUseConditions', '--dataUseConditions', 'Data-use conditions applying to this dataset'), ('ontologyModifiers', '--ontologyModifiers', 'Ontology modifiers that further specify the dataset'), ('identification', '--identification', 'Unique identifier of the dataset'), ('name', '--name', 'Name of the dataset'))


class Beacon2GeneNode(_Beacon2SearchBaseNode):
    """Query Beacon genomic variants by gene symbol."""
    NODE_ID = 'beacon2_gene'
    DISPLAY_NAME = 'Beacon2 Gene'
    DESCRIPTION = 'Query Beacon genomic variants by HGNC gene symbol.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_gene', 'Beacon2 Gene', 'beacon2-search gene', 'geneId', 'HGNC gene symbol', 'genomic variants', 'aminoacidChange']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_gene_query',)
    SEARCH_COLLECTION = 'gene'
    OUTPUT_FILENAME = 'gene_query_findings.json'
    REQUIRED_QUERY_FLAGS = (('geneId', '--geneId', 'STRING', 'HGNC gene symbol used to query Beacon variants'),)
    QUERY_FLAGS = (('alternateBases', '--alternateBases', 'Targeted alternate bases to search for'), ('variantType', '--variantType', 'Targeted variant type to search for'), ('aminoacidChange', '--aminoacidChange', 'Targeted amino-acid change to search for'), ('variantMinLength', '--variantMinLength', 'Targeted minimum variant length'), ('variantMaxLength', '--variantMaxLength', 'Targeted maximum variant length'))
    TYPED_QUERY_FLAGS = (('variantMinLength', '--variantMinLength', 'INT', 'Targeted minimum variant length'), ('variantMaxLength', '--variantMaxLength', 'INT', 'Targeted maximum variant length'))


class Beacon2IndividualsNode(_Beacon2SearchBaseNode):
    """Query the individuals collection in a Beacon database."""
    NODE_ID = 'beacon2_individuals'
    DISPLAY_NAME = 'Beacon2 Individuals'
    DESCRIPTION = 'Query the individuals collection in a Beacon database for patients or healthy controls.'
    VERSION = '1.0.0'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_individuals', 'Beacon2 Individuals', 'beacon2-search individuals', 'individuals collection', 'patients', 'healthy controls', 'geographicOrigin', 'familyHistory']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_individuals_query',)
    SEARCH_COLLECTION = 'individuals'
    OUTPUT_FILENAME = 'individuals_query_findings.json'
    QUERY_FLAGS = (('ageGroup', '--ageGroup', 'Age group or age at onset, such as Adult 18-65 Years Old'), ('diseaseCode', '--diseaseCode', 'Disease code or label'), ('familyHistory', '--familyHistory', 'Family-history flag'), ('severity', '--severity', 'Clinical severity'), ('stage', '--stage', 'Disease stage'), ('ethnicity', '--ethnicity', 'Ethnicity term or label'), ('geographicOrigin', '--geographicOrigin', 'Geographic origin term or label'), ('identification', '--identification', 'Individual identifier or internal ID'), ('assayCode', '--assayCode', 'Assay code or label'), ('sex', '--sex', 'Sex filter'))
    QUERY_FLAG_OPTIONS = {'familyHistory': ['', 'true', 'false'], 'sex': ['', 'male', 'female']}


class Beacon2RangeNode(_Beacon2SearchBaseNode):
    """Query Beacon genomic variants by sequence range."""
    NODE_ID = 'beacon2_range'
    DISPLAY_NAME = 'Beacon2 Range'
    DESCRIPTION = 'Query Beacon genomic variants overlapping a start and end position range.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_range', 'Beacon2 Range', 'beacon2-search range', 'range query', 'genomic variants', 'start', 'end', 'referenceName']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_ranged_query',)
    SEARCH_COLLECTION = 'range'
    OUTPUT_FILENAME = 'ranged_query_findings.json'
    REQUIRED_QUERY_FLAGS = (('start', '--start', 'INT', 'Start position'), ('end', '--end', 'INT', 'End position'))
    QUERY_FLAGS = (('referenceName', '--referenceName', 'Reference name such as chr1/1, chr2/2, chr3/3'), ('alternateBases', '--alternateBases', 'Targeted alternate bases to search for'), ('variantType', '--variantType', 'Targeted variant type to search for'), ('aminoacidChange', '--aminoacidChange', 'Targeted amino-acid change to search for'), ('variantMinLength', '--variantMinLength', 'Targeted minimum variant length'), ('variantMaxLength', '--variantMaxLength', 'Targeted maximum variant length'))
    TYPED_QUERY_FLAGS = (('variantMinLength', '--variantMinLength', 'INT', 'Targeted minimum variant length'), ('variantMaxLength', '--variantMaxLength', 'INT', 'Targeted maximum variant length'))


class Beacon2RunsNode(_Beacon2SearchBaseNode):
    """Query the runs collection in a Beacon database."""
    NODE_ID = 'beacon2_runs'
    DISPLAY_NAME = 'Beacon2 Runs'
    DESCRIPTION = 'Query the runs collection in a Beacon database for sequencing and library preparation metadata.'
    VERSION = '1.0.0'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_runs', 'Beacon2 Runs', 'beacon2-search runs', 'runs collection', 'sequencing runs', 'libraryLayout', 'librarySource', 'platformModel']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_runs_query',)
    SEARCH_COLLECTION = 'runs'
    OUTPUT_FILENAME = 'runs_query_findings.json'
    QUERY_FLAGS = (('identification', '--identification', 'Run identifier'), ('individualId', '--individualId', 'Reference to the individual ID, such as TCGA-AO-A0JJ'), ('libraryLayout', '--libraryLayout', 'Library layout, such as PAIRED or SINGLE'), ('librarySelection', '--librarySelection', 'Selection method for library preparation, such as RANDOM or RT-PCR'), ('librarySource', '--librarySource', 'Source of the sequencing or hybridization library'), ('libraryStrategy', '--libraryStrategy', 'Library strategy, such as WGS'), ('platform', '--platform', 'General platform technology label, such as Illumina'), ('platformModel', '--platformModel', 'Experimental platform model or methodology, such as Illumina HiSeq 3000'), ('runDate', '--runDate', 'Date at which the experiment was performed'))


class Beacon2SequenceNode(_Beacon2SearchBaseNode):
    """Query Beacon for a precise alternate/reference sequence."""
    NODE_ID = 'beacon2_sequence'
    DISPLAY_NAME = 'Beacon2 Sequence'
    DESCRIPTION = 'Query Beacon for the existence of a specified sequence at a genomic position.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beacon2', 'Beacon v2', 'beacon2_sequence', 'Beacon2 Sequence', 'beacon2-search sequence', 'sequence query', 'alternateBases', 'referenceBases', 'SNV', 'INDEL']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('out_sequence_query',)
    SEARCH_COLLECTION = 'sequence'
    OUTPUT_FILENAME = 'sequenced_query_findings.json'
    REQUIRED_QUERY_FLAGS = (('alternateBases', '--alternateBases', 'STRING', 'Alternate bases to query for'), ('referenceBases', '--referenceBases', 'STRING', 'Reference bases to query against'))
    QUERY_FLAGS = (('referenceName', '--referenceName', 'Reference name such as chr1/1, chr2/2, chr3/3'), ('start', '--start', 'Start position'), ('collectionIds', '--collectionIds', 'Dataset or collection ID filter'))
    TYPED_QUERY_FLAGS = (('start', '--start', 'INT', 'Start position'),)
