"""celltypist — single_cell node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class CellTypistNode(CommandNode):
    """Annotate single-cell RNA-seq AnnData objects with CellTypist."""
    NODE_ID = 'celltypist'
    DISPLAY_NAME = 'CellTypist'
    REQUIRED_CONDA_PACKAGES = ['celltypist']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Automated cell type annotation for scRNA-seq datasets.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'CellTypist', 'celltypist', 'automated cell type annotation', 'scRNA-seq', 'single-cell annotation', 'immune populations', 'Immune_All_High_v1', 'prob match', 'majority voting', 'dotplot']
    RETURN_TYPES = ('H5AD', 'IMAGE', 'PDF_REPORT', 'IMAGE')
    RETURN_NAMES = ('anndata_out', 'out_png', 'out_pdf', 'out_svg')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://www.celltypist.org/'
    CITATION_DOIS = [CELLTYPIST_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CELLTYPIST_CITATION_DOI}']
    CITATION_TEXT = CELLTYPIST_CITATION_TEXT
    VERSION = '1.7.1+galaxy1'
    SHELL = True
    MODEL_SOURCES = ['cached', 'history']
    HISTORY_MODEL_SELECTS = ['select_model', 'train_model']
    MODES = ['best match', 'prob match']
    DOTPLOT_GENERATE_OPTIONS = ['no', 'yes']
    DOTPLOT_PREDICTIONS = ['majority_voting', 'predicted_labels']
    DOTPLOT_FORMATS = ['png', 'pdf', 'svg']
    NAME_PATTERN = re.compile('[0-9a-zA-Z_]+')

    @classmethod
    def _bool_value(cls, value: Any, default: bool=False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() not in {'false', '0', 'no', ''}
        return bool(value)

    @classmethod
    def _model_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('model_source', 'cached') or 'cached')

    @classmethod
    def _history_model_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('history_model_select', 'select_model') or 'select_model')

    @classmethod
    def _dotplot_generate(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('dotplot_generate', 'no') or 'no')

    @classmethod
    def _dotplot_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('dotplot_format', 'png') or 'png')

    @classmethod
    def _dotplot_prediction(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('dotplot_prediction', 'majority_voting') or 'majority_voting')

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        lines = ['import scanpy as sc', 'import celltypist', 'from celltypist import models', f"adata = sc.read_h5ad({str(inputs.get('adata', ''))!r})"]
        if cls._model_source(inputs) == 'history' and cls._history_model_select(inputs) == 'train_model':
            lines.extend([f"train_adata = sc.read_h5ad({str(inputs.get('train_anndata', ''))!r})", 'model = celltypist.train(X=train_adata,', f"                    labels={str(inputs.get('labels', ''))!r},", f"                    batch_number={int(inputs.get('batch_number', 100))},", f"                    batch_size={int(inputs.get('batch_size', 1000))},", f"                    epochs={int(inputs.get('epochs', 10))},", f"                    feature_selection={cls._bool_value(inputs.get('feature_selection'), False)},", f"                    top_genes={int(inputs.get('top_genes', 300))})"])
        elif cls._model_source(inputs) == 'history':
            lines.append(f"model = models.Model.load(model={str(inputs.get('history_model', ''))!r})")
        else:
            lines.append(f"model = models.Model.load(model={str(inputs.get('cached_model', 'Immune_All_High_v1'))!r})")
        lines.extend(['predictions = celltypist.annotate(adata,', '                model=model,'])
        if cls._bool_value(inputs.get('majority_voting'), False):
            lines.append('                majority_voting=True,')
        if cls._bool_value(inputs.get('transpose_input'), False):
            lines.append('                transpose_input=True,')
        lines.extend([f"                mode={str(inputs.get('mode', 'best match') or 'best match')!r},", f"                p_thres={float(inputs.get('p_thres', 0.5))},", f"                min_prop={float(inputs.get('min_prop', 0))})", 'adata = predictions.to_adata()', f"adata.write_h5ad({cls._out_path(inputs, 'anndata.h5ad')!r}, compression='gzip')"])
        if cls._dotplot_generate(inputs) == 'yes':
            lines.append(f"celltypist.dotplot(predictions, use_as_reference={str(inputs.get('dotplot_reference', 'cell_type') or 'cell_type')!r}, use_as_prediction={cls._dotplot_prediction(inputs)!r}, save='.{cls._dotplot_format(inputs)}', show=None)")
        return '\n'.join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        return f"mkdir -p {shlex.quote(out)} && cd {shlex.quote(out)} && cat > celltypist.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython celltypist.py"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'anndata.h5ad']
        if cls._dotplot_generate(inputs) == 'yes':
            figures = out / 'figures'
            figures.mkdir(parents=True, exist_ok=True)
            outputs.append(figures / f'{cls._dotplot_prediction(inputs)}.{cls._dotplot_format(inputs)}')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('adata', '')).strip():
            return 'adata is required'
        model_source = cls._model_source(inputs)
        if model_source not in cls.MODEL_SOURCES:
            return f"model_source must be one of: {', '.join(cls.MODEL_SOURCES)}"
        if model_source == 'cached' and 'cached_model' in inputs and (not str(inputs.get('cached_model', '')).strip()):
            return 'cached_model is required when model_source is cached'
        if model_source == 'history':
            history_model_select = cls._history_model_select(inputs)
            if history_model_select not in cls.HISTORY_MODEL_SELECTS:
                return f"history_model_select must be one of: {', '.join(cls.HISTORY_MODEL_SELECTS)}"
            if history_model_select == 'select_model' and (not str(inputs.get('history_model', '')).strip()):
                return 'history_model is required when history_model_select is select_model'
            if history_model_select == 'train_model':
                if not str(inputs.get('train_anndata', '')).strip():
                    return 'train_anndata is required when history_model_select is train_model'
                labels = str(inputs.get('labels', '')).strip()
                if not labels:
                    return 'labels is required when history_model_select is train_model'
                if cls.NAME_PATTERN.fullmatch(labels) is None:
                    return 'labels must match [0-9a-zA-Z_]+'
        mode = str(inputs.get('mode', 'best match') or 'best match')
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        for name, default in {'p_thres': 0.5, 'min_prop': 0}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be numeric'
            if value < 0 or value > 1:
                return f'{name} must be between 0 and 1'
        dotplot_generate = cls._dotplot_generate(inputs)
        if dotplot_generate not in cls.DOTPLOT_GENERATE_OPTIONS:
            return f"dotplot_generate must be one of: {', '.join(cls.DOTPLOT_GENERATE_OPTIONS)}"
        if dotplot_generate == 'yes':
            reference = str(inputs.get('dotplot_reference', 'cell_type') or 'cell_type')
            if cls.NAME_PATTERN.fullmatch(reference) is None:
                return 'dotplot_reference must match [0-9a-zA-Z_]+'
            prediction = cls._dotplot_prediction(inputs)
            if prediction not in cls.DOTPLOT_PREDICTIONS:
                return f"dotplot_prediction must be one of: {', '.join(cls.DOTPLOT_PREDICTIONS)}"
            dotplot_format = cls._dotplot_format(inputs)
            if dotplot_format not in cls.DOTPLOT_FORMATS:
                return f"dotplot_format must be one of: {', '.join(cls.DOTPLOT_FORMATS)}"
        numeric_mins = {'batch_number': (0, 100), 'batch_size': (1, 1000), 'epochs': (1, 10), 'top_genes': (1, 300)}
        for name, (minimum, default) in numeric_mins.items():
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be numeric'
            if value < minimum:
                return f'{name} must be greater than or equal to {minimum}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'adata': ('H5AD', {'description': 'Input AnnData H5AD file'})}, 'optional': {'model_source': ('STRING', {'default': 'cached', 'options': cls.MODEL_SOURCES}), 'cached_model': ('STRING', {'default': 'Immune_All_High_v1'}), 'history_model_select': ('STRING', {'default': 'select_model', 'options': cls.HISTORY_MODEL_SELECTS}), 'history_model': ('FILE', {'default': ''}), 'train_anndata': ('H5AD', {'default': ''}), 'labels': ('STRING', {'default': ''}), 'batch_number': ('INT', {'default': 100, 'min': 0}), 'batch_size': ('INT', {'default': 1000, 'min': 1}), 'epochs': ('INT', {'default': 10, 'min': 1}), 'feature_selection': ('BOOLEAN', {'default': False}), 'top_genes': ('INT', {'default': 300, 'min': 1}), 'majority_voting': ('BOOLEAN', {'default': False}), 'transpose_input': ('BOOLEAN', {'default': False}), 'mode': ('STRING', {'default': 'best match', 'options': cls.MODES}), 'p_thres': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 1}), 'min_prop': ('FLOAT', {'default': 0, 'min': 0, 'max': 1}), 'dotplot_generate': ('STRING', {'default': 'no', 'options': cls.DOTPLOT_GENERATE_OPTIONS}), 'dotplot_reference': ('STRING', {'default': 'cell_type'}), 'dotplot_prediction': ('STRING', {'default': 'majority_voting', 'options': cls.DOTPLOT_PREDICTIONS}), 'dotplot_format': ('STRING', {'default': 'png', 'options': cls.DOTPLOT_FORMATS})}, 'hidden': {'output': ('STRING', {})}}
