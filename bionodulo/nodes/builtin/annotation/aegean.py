"""aegean — annotation node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AegeanCanonGff3Node(CommandNode):
    """Canonicalize GFF3 files with AEGeAn CanonGFF3."""
    NODE_ID = 'aegean_canongff3'
    DISPLAY_NAME = 'AEGeAn CanonGFF3'
    REQUIRED_CONDA_PACKAGES = ['aegean']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Clean GFF3 annotations so they contain canonical protein-coding gene features.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AEGeAn', 'CanonGFF3', 'canon-gff3', 'aegean_canongff3', 'canonical protein-coding genes', 'GFF3 cleanup', 'infer gene features']
    RETURN_TYPES = ('GFF3',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['canon-gff3']
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AEGEAN_CITATION_URL]
    CITATION_TEXT = AEGEAN_CITATION_TEXT
    VERSION = '0.16.0+galaxy2'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/canonical.gff3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['canon-gff3']
        cmd.extend(_as_list(inputs.get('gff3file')))
        if inputs.get('infer'):
            cmd.append('--infer')
        _add_if_value(cmd, '-s', inputs.get('source'))
        cmd.extend(['-o', cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'canonical.gff3']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get('gff3file')):
            return 'at least one GFF3 input file is required'
        source = str(inputs.get('source', '') or '')
        if source and re.fullmatch('\\w+', source) is None:
            return 'source may only contain letters, numbers, and underscores'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gff3file': ('GFF3_LIST', {'multiple': True, 'description': 'One or more GFF3 annotation files to canonicalize'})}, 'optional': {'infer': ('BOOLEAN', {'default': False, 'description': 'Infer missing gene features for transcripts lacking an explicit parent gene'}), 'source': ('STRING', {'default': '', 'description': 'Reset the source column of each feature to this alphanumeric or underscore label'})}, 'hidden': {'output': ('STRING', {})}}


class AegeanGaevalNode(CommandNode):
    """Evaluate gene model support with AEGeAn GAEVAL."""
    NODE_ID = 'aegean_gaeval'
    DISPLAY_NAME = 'AEGeAn GAEVAL'
    REQUIRED_CONDA_PACKAGES = ['aegean']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Compute gene model coverage and integrity scores from transcript alignments.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AEGeAn', 'GAEVAL', 'gaeval', 'aegean_gaeval', 'gene model integrity', 'transcript alignment support', 'annotation evaluation']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('output',)
    REQUIRED_EXECUTABLES = ['gaeval']
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AEGEAN_CITATION_URL]
    CITATION_TEXT = AEGEAN_CITATION_TEXT
    VERSION = '0.16.0+galaxy2'
    WEIGHT_DEFAULTS = {'alpha': 0.6, 'beta': 0.3, 'gamma': 0.05, 'epsilon': 0.05}
    EXPECTED_DEFAULTS = {'expcds': 400, 'exp5putr': 200, 'exp3putr': 100}

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/gaeval.tsv'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['gaeval', str(inputs.get('alignmentgff3', '')), str(inputs.get('genesgff3', '')), '-a', str(inputs.get('alpha', cls.WEIGHT_DEFAULTS['alpha'])), '-b', str(inputs.get('beta', cls.WEIGHT_DEFAULTS['beta'])), '-g', str(inputs.get('gamma', cls.WEIGHT_DEFAULTS['gamma'])), '-e', str(inputs.get('epsilon', cls.WEIGHT_DEFAULTS['epsilon'])), '-c', str(inputs.get('expcds', cls.EXPECTED_DEFAULTS['expcds'])), '-5', str(inputs.get('exp5putr', cls.EXPECTED_DEFAULTS['exp5putr'])), '-3', str(inputs.get('exp3putr', cls.EXPECTED_DEFAULTS['exp3putr'])), '>', cls._output_path(inputs)]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'gaeval.tsv']

    @classmethod
    def _validate_range(cls, inputs: dict[str, Any], key: str, minimum: float, maximum: float) -> bool | str:
        value = inputs.get(key)
        if value is None or value == '':
            return True
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return f'{key} must be numeric'
        if numeric < minimum or numeric > maximum:
            return f'{key} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('alignmentgff3', '')).strip():
            return 'alignmentgff3 is required'
        if not str(inputs.get('genesgff3', '')).strip():
            return 'genesgff3 is required'
        for key in cls.WEIGHT_DEFAULTS:
            result = cls._validate_range(inputs, key, 0, 1)
            if result is not True:
                return result
        for key in cls.EXPECTED_DEFAULTS:
            result = cls._validate_range(inputs, key, 0, 1000)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignmentgff3': ('GFF3', {'description': 'Transcript alignment GFF3 file'}), 'genesgff3': ('GFF3', {'description': 'Gene prediction or annotation GFF3 file'})}, 'optional': {'alpha': ('FLOAT', {'default': cls.WEIGHT_DEFAULTS['alpha'], 'min': 0, 'max': 1, 'description': 'Weight for intron confirmation or expected CDS length support'}), 'beta': ('FLOAT', {'default': cls.WEIGHT_DEFAULTS['beta'], 'min': 0, 'max': 1, 'description': 'Weight for exon coverage in the integrity score'}), 'gamma': ('FLOAT', {'default': cls.WEIGHT_DEFAULTS['gamma'], 'min': 0, 'max': 1, 'description': 'Weight for expected 5 prime UTR length support'}), 'epsilon': ('FLOAT', {'default': cls.WEIGHT_DEFAULTS['epsilon'], 'min': 0, 'max': 1, 'description': 'Weight for expected 3 prime UTR length support'}), 'expcds': ('INT', {'default': cls.EXPECTED_DEFAULTS['expcds'], 'min': 0, 'max': 1000, 'description': 'Expected CDS length in base pairs'}), 'exp5putr': ('INT', {'default': cls.EXPECTED_DEFAULTS['exp5putr'], 'min': 0, 'max': 1000, 'description': 'Expected 5 prime UTR length in base pairs'}), 'exp3putr': ('INT', {'default': cls.EXPECTED_DEFAULTS['exp3putr'], 'min': 0, 'max': 1000, 'description': 'Expected 3 prime UTR length in base pairs'})}, 'hidden': {'output': ('STRING', {})}}


class AegeanLocusPocusNode(CommandNode):
    """Calculate interval loci from GFF3 annotations with AEGeAn LocusPocus."""
    NODE_ID = 'aegean_locuspocus'
    DISPLAY_NAME = 'AEGeAn LocusPocus'
    REQUIRED_CONDA_PACKAGES = ['aegean']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Calculate interval locus coordinates from GFF3 gene annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AEGeAn', 'LocusPocus', 'locuspocus', 'aegean_locuspocus', 'iLoci', 'interval loci', 'gene locus coordinates']
    RETURN_TYPES = ('GFF3', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('output', 'output_ilens', 'output_genemap', 'output_transmap')
    REQUIRED_EXECUTABLES = ['locuspocus']
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS = [LOCUSPOCUS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{LOCUSPOCUS_CITATION_DOI}']
    CITATION_TEXT = LOCUSPOCUS_CITATION_TEXT
    VERSION = '0.16.0+galaxy2'
    MODES = ['', '--skipends', '--endsonly']
    REFINE_OPTIONS = ['', '--refine']
    OUTPUT_FILES = ['ilens', 'genemap', 'transmap']
    OPTIONAL_OUTPUT_NAMES = {'ilens': 'ilens.tsv', 'genemap': 'genemap.tsv', 'transmap': 'transmap.tsv'}

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/loci.gff3'

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('outputfiles'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['locuspocus', str(inputs.get('genesgff3', '')), '-l', str(inputs.get('delta', 500))]
        mode = str(inputs.get('mode', '') or '')
        if mode:
            cmd.append(mode)
        if inputs.get('skipiloci'):
            cmd.append('--skipiiloci')
        if str(inputs.get('refine', '') or '') == '--refine' and inputs.get('cds'):
            cmd.append('--cds')
        cmd.extend(['-m', str(inputs.get('minoverlap', 1))])
        cmd.extend(['-f', str(inputs.get('filter', 'gene') or 'gene')])
        _add_if_value(cmd, '-p', inputs.get('parent'))
        if inputs.get('pseudo'):
            cmd.append('--pseudo')
        selected = cls._selected_outputs(inputs)
        for output_name in cls.OUTPUT_FILES:
            if output_name in selected:
                cmd.extend([f'--{output_name}', f'{out}/{cls.OPTIONAL_OUTPUT_NAMES[output_name]}'])
        _add_if_value(cmd, '-n', inputs.get('namefmt'))
        if inputs.get('retainids'):
            cmd.append('--retainids')
        cmd.extend(['-o', cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'loci.gff3']
        selected = cls._selected_outputs(inputs)
        for output_name in cls.OUTPUT_FILES:
            if output_name in selected:
                outputs.append(out / cls.OPTIONAL_OUTPUT_NAMES[output_name])
        return outputs

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, minimum: int, maximum: int) -> bool | str:
        value = inputs.get(key)
        if value is None or value == '':
            return True
        try:
            integer = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if integer < minimum or integer > maximum:
            return f'{key} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('genesgff3', '')).strip():
            return 'genesgff3 is required'
        for key, minimum, maximum in (('delta', 0, 1000), ('minoverlap', 1, 20)):
            result = cls._validate_int_range(inputs, key, minimum, maximum)
            if result is not True:
                return result
        mode = str(inputs.get('mode', '') or '')
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        refine = str(inputs.get('refine', '') or '')
        if refine not in cls.REFINE_OPTIONS:
            return f"refine must be one of: {', '.join(cls.REFINE_OPTIONS)}"
        unsupported_outputs = [value for value in cls._selected_outputs(inputs) if value not in cls.OUTPUT_FILES]
        if unsupported_outputs:
            return f"outputfiles contains unsupported values: {', '.join(unsupported_outputs)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'genesgff3': ('GFF3', {'description': 'Gene annotation GFF3 file'})}, 'optional': {'delta': ('INT', {'default': 500, 'min': 0, 'max': 1000, 'description': 'Gene locus extension in base pairs'}), 'mode': ('STRING', {'default': '', 'options': cls.MODES, 'description': 'Mode for reporting unannotated interval loci at sequence ends'}), 'skipiloci': ('BOOLEAN', {'default': False, 'description': 'Do not report intergenic iLoci'}), 'refine': ('STRING', {'default': '', 'options': cls.REFINE_OPTIONS, 'description': 'Enable refine mode for overlapping genes'}), 'cds': ('BOOLEAN', {'default': False, 'description': 'In refine mode, use CDS rather than UTRs for overlap handling'}), 'minoverlap': ('INT', {'default': 1, 'min': 1, 'max': 20, 'description': 'Minimum overlapping nucleotides for grouping genes in one iLocus'}), 'filter': ('STRING', {'default': 'gene', 'description': 'Comma-separated feature types used to annotate intervals'}), 'parent': ('STRING', {'default': '', 'description': 'Create missing parent features with a child:parent type mapping'}), 'pseudo': ('BOOLEAN', {'default': False, 'description': 'Correct erroneously labeled pseudogenes'}), 'retainids': ('BOOLEAN', {'default': False, 'description': 'Retain original feature IDs'}), 'namefmt': ('STRING', {'default': '', 'description': 'Format string for newly created locus IDs, such as locus%lu'}), 'outputfiles': ('STRING_LIST', {'default': [], 'multiple': True, 'options': cls.OUTPUT_FILES, 'description': 'Optional LocusPocus side-output tables to emit'})}, 'hidden': {'output': ('STRING', {})}}


class AegeanParsevalNode(CommandNode):
    """Compare two GFF3 gene annotation sets with AEGeAn ParsEval."""
    NODE_ID = 'aegean_parseval'
    DISPLAY_NAME = 'AEGeAn ParsEval'
    REQUIRED_CONDA_PACKAGES = ['aegean']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Compare two GFF3 gene annotation sets for the same sequence.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AEGeAn', 'ParsEval', 'parseval', 'aegean_parseval', 'gene annotation comparison', 'gene structure comparison', 'GFF3 annotation comparison']
    RETURN_TYPES = ('TXT', 'HTML_REPORT')
    RETURN_NAMES = ('output_txt', 'output_html')
    REQUIRED_EXECUTABLES = ['parseval']
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS = [PARSEVAL_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PARSEVAL_CITATION_DOI}']
    CITATION_TEXT = PARSEVAL_CITATION_TEXT
    VERSION = '0.16.0+galaxy2'
    OUTPUT_TYPES = ['text', 'html']

    @classmethod
    def _output_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output_type', 'text') or 'text')

    @classmethod
    def _text_output(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/parseval.txt'

    @classmethod
    def _html_output(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/parseval.html'

    @classmethod
    def _html_files_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/parseval_html.files'

    @classmethod
    def _base_cmd(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['parseval', str(inputs.get('referencegff3', '')), str(inputs.get('predictiongff3', '')), '--delta', str(inputs.get('delta', 0)), '--maxtrans', str(inputs.get('maxtrans', 32)), '-w']
        _add_if_value(cmd, '--refrlabel', inputs.get('refrlabel'))
        _add_if_value(cmd, '--predlabel', inputs.get('predlabel'))
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_type = cls._output_type(inputs)
        cmd = cls._base_cmd(inputs)
        if output_type == 'html':
            html_files = cls._html_files_path(inputs)
            html_index = f'{html_files}/index.html'
            cmd.extend(['-f', 'html', '-o', html_files])
            return ' && '.join([_shell_join(['mkdir', '-p', html_files]), _shell_join(cmd), f"echo {shlex.quote('</div> </body> </html>')} >> {shlex.quote(html_index)}", _shell_join(['cp', html_index, cls._html_output(inputs)])])
        cmd.extend(['-f', 'text', '-o', cls._text_output(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._output_type(inputs) == 'html':
            return [out / 'parseval.html']
        return [out / 'parseval.txt']

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, minimum: int, maximum: int) -> bool | str:
        value = inputs.get(key)
        if value is None or value == '':
            return True
        try:
            integer = int(value)
        except (TypeError, ValueError):
            return f'{key} must be an integer'
        if integer < minimum or integer > maximum:
            return f'{key} must be between {minimum} and {maximum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('referencegff3', '')).strip():
            return 'referencegff3 is required'
        if not str(inputs.get('predictiongff3', '')).strip():
            return 'predictiongff3 is required'
        for key, minimum, maximum in (('delta', 0, 20), ('maxtrans', 1, 50)):
            result = cls._validate_int_range(inputs, key, minimum, maximum)
            if result is not True:
                return result
        output_type = cls._output_type(inputs)
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'referencegff3': ('GFF3', {'description': 'Reference annotation GFF3 file'}), 'predictiongff3': ('GFF3', {'description': 'Prediction annotation GFF3 file'})}, 'optional': {'delta': ('INT', {'default': 0, 'min': 0, 'max': 20, 'description': 'Number of nucleotides to extend gene loci'}), 'maxtrans': ('INT', {'default': 32, 'min': 1, 'max': 50, 'description': 'Maximum transcripts allowed per locus'}), 'output_type': ('STRING', {'default': 'text', 'options': cls.OUTPUT_TYPES, 'description': 'Generate plain text or HTML ParsEval output'}), 'refrlabel': ('STRING', {'default': '', 'description': 'Optional label for the reference annotations'}), 'predlabel': ('STRING', {'default': '', 'description': 'Optional label for the prediction annotations'})}, 'hidden': {'output': ('STRING', {})}}
