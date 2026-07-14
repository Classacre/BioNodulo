"""cemitool — rna_seq node(s). One tool per file (extracted from wrapped_core_data.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _DatamashBaseNode(CommandNode):
    """Shared metadata and helpers for GNU Datamash Galaxy wrappers."""
    REQUIRED_CONDA_PACKAGES = ['datamash']
    CATEGORY = 'data_transform'
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('out_file',)
    DOCUMENTATION_URL = DATAMASH_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [DATAMASH_CITATION_URL]
    CITATION_TEXT = DATAMASH_CITATION_TEXT
    VERSION = '1.9'
    SHELL = True
    INPUT_EXT_OPTIONS = ['tabular', 'tsv', 'csv']

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_ext', 'tabular') or 'tabular')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_file.tsv'

    @classmethod
    def _separator_args(cls, inputs: dict[str, Any]) -> list[str]:
        return ['-t', ','] if cls._input_ext(inputs) == 'csv' else []

    @classmethod
    def _redirect_stdin_stdout(cls, cmd: list[str], inputs: dict[str, Any]) -> str:
        cmd.extend(['>', cls._output_path(inputs)])
        input_file = shlex.quote(str(inputs.get('in_file', '')))
        return _shell_join(cmd).replace(' > ', f' < {input_file} > ')

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out_file.tsv']

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_file', '')).strip():
            return 'in_file is required'
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('TSV', {'description': 'Input tabular, TSV, or CSV dataset'})}, 'optional': {'input_ext': ('STRING', {'default': 'tabular', 'options': cls.INPUT_EXT_OPTIONS, 'description': 'Input file format'})}, 'hidden': {'output': ('STRING', {})}}


class CEMiToolNode(CommandNode):
    """Run CEMiTool gene co-expression network analysis."""
    NODE_ID = 'cemitool'
    DISPLAY_NAME = 'CEMiTool'
    REQUIRED_CONDA_PACKAGES = ['bioconductor-cemitool', 'r-ggplot2', 'r-getopt']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Run gene co-expression network analyses with CEMiTool.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CEMiTool', 'cemitool', 'gene co-expression network analyses', 'co-expression modules', 'coexpression', 'WGCNA', 'over representation analysis', 'Gene Set Enrichment Analysis', 'GSEA', 'module eigengene']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'TSV', 'TSV', 'TXT', 'TSV', 'TSV', 'TSV', 'TSV', 'HTML_REPORT')
    RETURN_NAMES = ('plots', 'module', 'modules_genes', 'parameters', 'selected_genes', 'summary_eigengene', 'summary_mean', 'summary_median', 'interactions_output', 'output_html')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/CEMiTool'
    CITATION_DOIS = CEMITOOL_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CEMITOOL_CITATION_DOIS]
    CITATION_TEXT = CEMITOOL_CITATION_TEXT
    VERSION = '1.34.0+galaxy0'
    SHELL = True
    OUTPUT_SELECTIONS = ['report', 'tables', 'plots']
    COR_METHODS = ['pearson', 'spearman']
    COR_FUNCTIONS = ['cor', 'bicor']
    NETWORK_TYPES = ['signed', 'unsigned']
    TOM_TYPES = ['signed', 'unsigned']
    SUMMARY_METHODS = ['mean', 'median']
    SAMPLE_COLUMN_PATTERN = re.compile('[0-9a-zA-Z:-_]+')
    TABLE_OUTPUTS = [('module', 'module.tsv'), ('modules_genes', 'modules_genes.gmt'), ('parameters', 'parameters.tsv'), ('selected_genes', 'selected_genes.txt'), ('summary_eigengene', 'summary_eigengene.tsv'), ('summary_mean', 'summary_mean.tsv'), ('summary_median', 'summary_median.tsv')]

    @classmethod
    def _bool_text(cls, value: Any, default: bool) -> str:
        if value is None:
            return 'TRUE' if default else 'FALSE'
        if isinstance(value, str):
            return 'FALSE' if value.lower() in {'false', '0', 'no', ''} else 'TRUE'
        return 'TRUE' if bool(value) else 'FALSE'

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get('outputs'))
        return outputs or ['report']

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('cemitool_script', 'CEMiTool.R') or 'CEMiTool.R')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['Rscript', cls._script(inputs), '-M', str(inputs.get('expression_matrix', ''))]
        _add_if_value(cmd, '-A', inputs.get('annotation'))
        _add_if_value(cmd, '-P', inputs.get('pathways'))
        _add_if_value(cmd, '-I', inputs.get('interactions'))
        _add_if_value(cmd, '-B', inputs.get('beta'))
        cmd.extend(['-f', cls._bool_text(inputs.get('filter'), True), '-i', str(inputs.get('filter_pval', 0.1)), '-a', cls._bool_text(inputs.get('apply_vst'), False), '-n', str(inputs.get('n_genes', 1000)), '-e', str(inputs.get('eps', 0.1)), '-c', str(inputs.get('cor_method', 'pearson') or 'pearson'), '-y', str(inputs.get('cor_function', 'cor') or 'cor'), '-x', str(inputs.get('network_type', 'unsigned') or 'unsigned'), '-t', str(inputs.get('tom_type', 'unsigned') or 'unsigned'), '-m', cls._bool_text(inputs.get('merge_similar'), False), '-r', str(inputs.get('rank_method', 'mean') or 'mean'), '-g', str(inputs.get('min_ngen', 30)), '-d', str(inputs.get('diss_thresh', 0.8)), '-h', str(inputs.get('center_func', 'mean') or 'mean'), '-o', str(inputs.get('ora_pval', 0.05)), '-l', cls._bool_text(inputs.get('gsea_scale'), True), '-w', str(inputs.get('gsea_min_size', 15)), '-z', str(inputs.get('gsea_max_size', 1000)), '-v', str(inputs.get('sample_column_name', 'SampleName') or 'SampleName')])
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(cls._selected_outputs(inputs))
        outputs: list[Path] = []
        if 'plots' in selected:
            plots = out / 'Plots'
            plots.mkdir(parents=True, exist_ok=True)
            outputs.append(plots)
        if 'tables' in selected:
            tables = out / 'Tables'
            tables.mkdir(parents=True, exist_ok=True)
            outputs.extend((tables / filename for _, filename in cls.TABLE_OUTPUTS))
            if str(inputs.get('interactions', '')).strip():
                outputs.append(tables / 'interactions.tsv')
        if 'report' in selected:
            report_dir = out / 'Reports' / 'Report'
            report_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(report_dir / 'report.html')
        return outputs

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_float_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if value < 0 or value > 1:
            return f'{name} must be between 0 and 1'
        return True

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, minimum: int, default: Any) -> bool | str:
        raw = inputs.get(name, default)
        if raw == '' and name == 'beta':
            return True
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return f'{name} must be an integer'
        if value < minimum:
            return f'{name} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('expression_matrix', '')).strip():
            return 'expression_matrix is required'
        unsupported = [output for output in cls._selected_outputs(inputs) if output not in cls.OUTPUT_SELECTIONS]
        if unsupported:
            return f"outputs values must be one or more of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        for name, default in {'filter_pval': 0.1, 'eps': 0.1, 'diss_thresh': 0.8, 'ora_pval': 0.05}.items():
            result = cls._validate_float_range(inputs, name, default)
            if result is not True:
                return result
        for name, minimum, default in [('beta', 0, ''), ('n_genes', 0, 1000), ('min_ngen', 0, 30), ('gsea_min_size', 0, 15), ('gsea_max_size', 0, 1000)]:
            result = cls._validate_int_min(inputs, name, minimum, default)
            if result is not True:
                return result
        choice_checks = [('cor_method', cls.COR_METHODS, 'pearson'), ('cor_function', cls.COR_FUNCTIONS, 'cor'), ('network_type', cls.NETWORK_TYPES, 'unsigned'), ('tom_type', cls.TOM_TYPES, 'unsigned'), ('rank_method', cls.SUMMARY_METHODS, 'mean'), ('center_func', cls.SUMMARY_METHODS, 'mean')]
        for name, options, default in choice_checks:
            result = cls._validate_choice(inputs, name, options, default)
            if result is not True:
                return result
        sample_column_name = str(inputs.get('sample_column_name', 'SampleName') or 'SampleName')
        if cls.SAMPLE_COLUMN_PATTERN.fullmatch(sample_column_name) is None:
            return 'sample_column_name must match [0-9a-zA-Z:-_]+'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'expression_matrix': ('TSV', {'description': 'Expression matrix'})}, 'optional': {'annotation': ('TSV', {'default': '', 'description': 'Sample annotation table'}), 'pathways': ('FILE', {'default': '', 'description': 'GMT pathway list for ORA'}), 'interactions': ('TSV', {'default': '', 'description': 'Interaction data with gene pairs'}), 'beta': ('INT', {'default': '', 'min': 0, 'description': 'Optional WGCNA beta value'}), 'outputs': ('STRING_LIST', {'default': ['report'], 'options': cls.OUTPUT_SELECTIONS, 'multiple': True}), 'cemitool_script': ('FILE', {'default': 'CEMiTool.R', 'advanced': True}), 'filter': ('BOOLEAN', {'default': True}), 'filter_pval': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1}), 'apply_vst': ('BOOLEAN', {'default': False}), 'n_genes': ('INT', {'default': 1000, 'min': 0}), 'eps': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1}), 'cor_method': ('STRING', {'default': 'pearson', 'options': cls.COR_METHODS}), 'cor_function': ('STRING', {'default': 'cor', 'options': cls.COR_FUNCTIONS}), 'network_type': ('STRING', {'default': 'unsigned', 'options': cls.NETWORK_TYPES}), 'tom_type': ('STRING', {'default': 'unsigned', 'options': cls.TOM_TYPES}), 'merge_similar': ('BOOLEAN', {'default': False}), 'rank_method': ('STRING', {'default': 'mean', 'options': cls.SUMMARY_METHODS}), 'min_ngen': ('INT', {'default': 30, 'min': 0}), 'diss_thresh': ('FLOAT', {'default': 0.8, 'min': 0, 'max': 1}), 'center_func': ('STRING', {'default': 'mean', 'options': cls.SUMMARY_METHODS}), 'ora_pval': ('FLOAT', {'default': 0.05, 'min': 0, 'max': 1}), 'gsea_scale': ('BOOLEAN', {'default': True}), 'gsea_min_size': ('INT', {'default': 15, 'min': 0}), 'gsea_max_size': ('INT', {'default': 1000, 'min': 0}), 'sample_column_name': ('STRING', {'default': 'SampleName'})}, 'hidden': {'output': ('STRING', {})}}
