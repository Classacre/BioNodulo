"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class AnnDataExportNode(CommandNode):
    """Export AnnData H5AD matrices and annotations to tabular files."""

    NODE_ID = "anndata_export"
    DISPLAY_NAME = "Export AnnData"
    REQUIRED_CONDA_PACKAGES = ["anndata", "scanpy", "loompy", "pandas"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Export an AnnData H5AD matrix and annotations to tabular files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AnnData",
        "anndata_export",
        "Export AnnData",
        "H5AD",
        "write_csvs",
        "obs annotations",
        "var annotations",
        "single-cell matrix export",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("tabular_x", "tabular_obs", "tabular_obsm", "tabular_var", "tabular_varm")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.write_csvs.html"
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}"]
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = "0.11.4+galaxy3"
    SHELL = True

    OUTPUT_FILES = ["X.csv", "obs.csv", "obsm.csv", "var.csv", "varm.csv"]

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/anndata_export.py"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        input_path = str(inputs.get("input", ""))
        return "\n".join(
            [
                "import anndata as ad",
                f"adata = ad.read_h5ad({input_path!r}, backed='r')",
                'adata.write_csvs(\'.\', sep="\\t", skip_data=False)',
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = cls._script_path(inputs)
        return (
            f"mkdir -p {shlex.quote(out)} && "
            f"cat > {shlex.quote(script_path)} <<'PY'\n"
            f"{cls._script_body(inputs)}\n"
            f"PY\n"
            f"cd {shlex.quote(out)} && python {shlex.quote(Path(script_path).name)}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / filename for filename in cls.OUTPUT_FILES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("H5AD", {"description": "Annotated data matrix to export"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AnnDataImportNode(CommandNode):
    """Create AnnData H5AD objects from loom, tabular, 10x, MTX, UMI-tools, or annotated matrices."""

    NODE_ID = "anndata_import"
    DISPLAY_NAME = "Import Anndata"
    REQUIRED_CONDA_PACKAGES = ["anndata", "scanpy", "loompy", "pandas"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Create an AnnData H5AD object from loom, tabular, 10x, MTX, UMI-tools, or annotated matrix inputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AnnData",
        "anndata_import",
        "Import Anndata",
        "H5AD",
        "read_loom",
        "read_csv",
        "read_10x_h5",
        "read_10x_mtx",
        "read_mtx",
        "read_umi_tools",
        "Matrix Market",
        "UMI-tools",
    ]
    RETURN_TYPES = ("H5AD",)
    RETURN_NAMES = ("anndata",)
    REQUIRED_EXECUTABLES = ["python", "gzip"]
    DOCUMENTATION_URL = "https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html"
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}"]
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = "0.11.4+galaxy3"
    SHELL = True

    ADATA_FORMATS = ["loom", "tabular", "10x_h5", "mtx", "umi_tools", "custom"]
    TENX_USES = ["no", "legacy_10x", "v3_10x"]
    VAR_NAMES = ["gene_symbols", "gene_ids"]

    @classmethod
    def _adata_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("adata_format", "loom") or "loom")

    @classmethod
    def _tenx_use(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("tenx_use", "no") or "no")

    @classmethod
    def _bool_text(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return "False" if value.lower() in {"false", "0", "no"} else "True"
        return "True" if bool(value) else "False"

    @classmethod
    def _delimiter(cls, inputs: dict[str, Any]) -> str:
        delimiter = str(inputs.get("delimiter", "\\t") or "\\t")
        if delimiter.lower() in {"tab", "tabular", "tsv", "\\t"}:
            return "\\t"
        return delimiter

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        adata_format = cls._adata_format(inputs)
        lines = ["import anndata as ad"]
        if adata_format == "loom":
            lines.extend(
                [
                    "adata = ad.read_loom(",
                    f"    {str(inputs.get('input', ''))!r},",
                    f"    sparse={cls._bool_text(inputs, 'sparse', True)},",
                    f"    cleanup={cls._bool_text(inputs, 'cleanup', False)},",
                    f"    X_name={str(inputs.get('x_name', 'spliced'))!r},",
                    f"    obs_names={str(inputs.get('obs_names', 'CellID'))!r},",
                    f"    var_names={str(inputs.get('var_names', 'Gene'))!r})",
                ]
            )
        elif adata_format == "tabular":
            lines.extend(
                [
                    "from scipy.sparse import csr_matrix",
                    (
                        f"adata = ad.read_csv({str(inputs.get('input', ''))!r}, "
                        f"delimiter={cls._delimiter(inputs)!r}, "
                        f"first_column_names={cls._bool_text(inputs, 'first_column_names', True)})"
                    ),
                    "adata.X = csr_matrix(adata.X)",
                ]
            )
        elif adata_format == "10x_h5":
            lines.extend(["import scanpy as sc", f"adata = sc.read_10x_h5({str(inputs.get('input', ''))!r})"])
        elif adata_format == "mtx":
            tenx_use = cls._tenx_use(inputs)
            if tenx_use == "no":
                lines.append(f"adata = ad.read_mtx(filename={str(inputs.get('matrix', ''))!r})")
            else:
                lines.extend(
                    [
                        "import scanpy as sc",
                        (
                            "adata = sc.read_10x_mtx('mtx', "
                            f"var_names={str(inputs.get('var_names', 'gene_symbols'))!r}, "
                            f"make_unique={cls._bool_text(inputs, 'make_unique', True)}, "
                            "cache=False, "
                            f"gex_only={cls._bool_text(inputs, 'gex_only', True)})"
                        ),
                    ]
                )
        elif adata_format == "umi_tools":
            lines.append("adata = ad.read_umi_tools('umi_tools_input.gz')")
        else:
            lines.extend(
                [
                    "import pandas as pd",
                    f"adata = ad.read_mtx(filename={str(inputs.get('mtx', ''))!r})",
                    "adata = adata.transpose().copy()",
                    f"obs = pd.read_csv({str(inputs.get('obs', ''))!r}, sep='\\t', index_col=0)",
                    f"var = pd.read_csv({str(inputs.get('var', ''))!r}, sep='\\t', index_col=0)",
                    "if adata.shape[0] != obs.shape[0]:",
                    '    raise ValueError(f"Mismatch: adata has {adata.shape[0]} cells, but obs has {obs.shape[0]} rows.")',
                    "if adata.shape[1] != var.shape[0]:",
                    '    raise ValueError(f"Mismatch: adata has {adata.shape[1]} genes, but var has {var.shape[0]} rows.")',
                    "adata.obs = obs",
                    "adata.var = var",
                ]
            )
        lines.extend(["adata.write('anndata.h5ad', compression='gzip')", "print(adata)"])
        return "\n".join(lines)

    @classmethod
    def _stage_commands(cls, inputs: dict[str, Any]) -> list[str]:
        adata_format = cls._adata_format(inputs)
        if adata_format == "umi_tools":
            return [f"gzip -c {shlex.quote(str(inputs.get('input', '')))} > umi_tools_input.gz"]
        if adata_format != "mtx":
            return []
        tenx_use = cls._tenx_use(inputs)
        if tenx_use == "no":
            return []
        commands = [
            "mkdir -p mtx",
            f"cp {shlex.quote(str(inputs.get('matrix', '')))} mtx/matrix.mtx",
        ]
        if tenx_use == "legacy_10x":
            commands.extend(
                [
                    f"cp {shlex.quote(str(inputs.get('genes', '')))} mtx/genes.tsv",
                    f"cp {shlex.quote(str(inputs.get('barcodes', '')))} mtx/barcodes.tsv",
                ]
            )
        else:
            commands.extend(
                [
                    "gzip mtx/matrix.mtx",
                    f"cp {shlex.quote(str(inputs.get('features', '')))} mtx/features.tsv",
                    "gzip mtx/features.tsv",
                    f"cp {shlex.quote(str(inputs.get('barcodes', '')))} mtx/barcodes.tsv",
                    "gzip mtx/barcodes.tsv",
                ]
            )
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}", f"cd {shlex.quote(out)}", *cls._stage_commands(inputs)]
        commands.append(f"cat > anndata_import.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_import.py")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "anndata.h5ad"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        adata_format = cls._adata_format(inputs)
        if adata_format not in cls.ADATA_FORMATS:
            return f"adata_format must be one of: {', '.join(cls.ADATA_FORMATS)}"
        if adata_format in {"loom", "tabular", "10x_h5", "umi_tools"} and not str(inputs.get("input", "")).strip():
            return f"input is required when adata_format is {adata_format}"
        if adata_format == "mtx":
            if not str(inputs.get("matrix", "")).strip():
                return "matrix is required when adata_format is mtx"
            tenx_use = cls._tenx_use(inputs)
            if tenx_use not in cls.TENX_USES:
                return f"tenx_use must be one of: {', '.join(cls.TENX_USES)}"
            if tenx_use == "legacy_10x":
                if not str(inputs.get("genes", "")).strip():
                    return "genes is required when tenx_use is legacy_10x"
                if not str(inputs.get("barcodes", "")).strip():
                    return "barcodes is required when tenx_use is legacy_10x"
            if tenx_use == "v3_10x":
                if not str(inputs.get("features", "")).strip():
                    return "features is required when tenx_use is v3_10x"
                if not str(inputs.get("barcodes", "")).strip():
                    return "barcodes is required when tenx_use is v3_10x"
        if adata_format == "custom":
            for key in ("mtx", "obs", "var"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when adata_format is custom"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "optional": {
                "adata_format": ("STRING", {"default": "loom", "options": cls.ADATA_FORMATS}),
                "input": ("FILE", {"default": "", "description": "Input loom, tabular, 10x H5, or UMI-tools matrix"}),
                "sparse": ("BOOLEAN", {"default": True}),
                "cleanup": ("BOOLEAN", {"default": False}),
                "x_name": ("STRING", {"default": "spliced"}),
                "obs_names": ("STRING", {"default": "CellID"}),
                "var_names": ("STRING", {"default": "Gene", "options": ["Gene", *cls.VAR_NAMES]}),
                "delimiter": ("STRING", {"default": "\\t", "options": ["\\t", ","]}),
                "first_column_names": ("BOOLEAN", {"default": True}),
                "matrix": ("FILE", {"default": "", "description": "Matrix Market file for MTX import"}),
                "tenx_use": ("STRING", {"default": "no", "options": cls.TENX_USES}),
                "genes": ("TSV", {"default": "", "description": "Cell Ranger v2 genes.tsv"}),
                "features": ("TSV", {"default": "", "description": "Cell Ranger v3 features.tsv"}),
                "barcodes": ("TSV", {"default": "", "description": "10x barcodes.tsv"}),
                "make_unique": ("BOOLEAN", {"default": True}),
                "gex_only": ("BOOLEAN", {"default": True}),
                "mtx": ("FILE", {"default": "", "description": "Custom Matrix Market count matrix"}),
                "obs": ("TSV", {"default": "", "description": "Custom cell annotations"}),
                "var": ("TSV", {"default": "", "description": "Custom gene annotations"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CellTypistNode(CommandNode):
    """Annotate single-cell RNA-seq AnnData objects with CellTypist."""

    NODE_ID = "celltypist"
    DISPLAY_NAME = "CellTypist"
    REQUIRED_CONDA_PACKAGES = ["celltypist"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Automated cell type annotation for scRNA-seq datasets."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CellTypist",
        "celltypist",
        "automated cell type annotation",
        "scRNA-seq",
        "single-cell annotation",
        "immune populations",
        "Immune_All_High_v1",
        "prob match",
        "majority voting",
        "dotplot",
    ]
    RETURN_TYPES = ("H5AD", "IMAGE", "PDF_REPORT", "IMAGE")
    RETURN_NAMES = ("anndata_out", "out_png", "out_pdf", "out_svg")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.celltypist.org/"
    CITATION_DOIS = [CELLTYPIST_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CELLTYPIST_CITATION_DOI}"]
    CITATION_TEXT = CELLTYPIST_CITATION_TEXT
    VERSION = "1.7.1+galaxy1"
    SHELL = True

    MODEL_SOURCES = ["cached", "history"]
    HISTORY_MODEL_SELECTS = ["select_model", "train_model"]
    MODES = ["best match", "prob match"]
    DOTPLOT_GENERATE_OPTIONS = ["no", "yes"]
    DOTPLOT_PREDICTIONS = ["majority_voting", "predicted_labels"]
    DOTPLOT_FORMATS = ["png", "pdf", "svg"]
    NAME_PATTERN = re.compile(r"[0-9a-zA-Z_]+")

    @classmethod
    def _bool_value(cls, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() not in {"false", "0", "no", ""}
        return bool(value)

    @classmethod
    def _model_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("model_source", "cached") or "cached")

    @classmethod
    def _history_model_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("history_model_select", "select_model") or "select_model")

    @classmethod
    def _dotplot_generate(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("dotplot_generate", "no") or "no")

    @classmethod
    def _dotplot_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("dotplot_format", "png") or "png")

    @classmethod
    def _dotplot_prediction(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("dotplot_prediction", "majority_voting") or "majority_voting")

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        lines = [
            "import scanpy as sc",
            "import celltypist",
            "from celltypist import models",
            f"adata = sc.read_h5ad({str(inputs.get('adata', ''))!r})",
        ]
        if cls._model_source(inputs) == "history" and cls._history_model_select(inputs) == "train_model":
            lines.extend(
                [
                    f"train_adata = sc.read_h5ad({str(inputs.get('train_anndata', ''))!r})",
                    "model = celltypist.train(X=train_adata,",
                    f"                    labels={str(inputs.get('labels', ''))!r},",
                    f"                    batch_number={int(inputs.get('batch_number', 100))},",
                    f"                    batch_size={int(inputs.get('batch_size', 1000))},",
                    f"                    epochs={int(inputs.get('epochs', 10))},",
                    f"                    feature_selection={cls._bool_value(inputs.get('feature_selection'), False)},",
                    f"                    top_genes={int(inputs.get('top_genes', 300))})",
                ]
            )
        elif cls._model_source(inputs) == "history":
            lines.append(f"model = models.Model.load(model={str(inputs.get('history_model', ''))!r})")
        else:
            lines.append(f"model = models.Model.load(model={str(inputs.get('cached_model', 'Immune_All_High_v1'))!r})")

        lines.extend(["predictions = celltypist.annotate(adata,", "                model=model,"])
        if cls._bool_value(inputs.get("majority_voting"), False):
            lines.append("                majority_voting=True,")
        if cls._bool_value(inputs.get("transpose_input"), False):
            lines.append("                transpose_input=True,")
        lines.extend(
            [
                f"                mode={str(inputs.get('mode', 'best match') or 'best match')!r},",
                f"                p_thres={float(inputs.get('p_thres', 0.5))},",
                f"                min_prop={float(inputs.get('min_prop', 0))})",
                "adata = predictions.to_adata()",
                f"adata.write_h5ad({cls._out_path(inputs, 'anndata.h5ad')!r}, compression='gzip')",
            ]
        )
        if cls._dotplot_generate(inputs) == "yes":
            lines.append(
                "celltypist.dotplot("
                f"predictions, use_as_reference={str(inputs.get('dotplot_reference', 'cell_type') or 'cell_type')!r}, "
                f"use_as_prediction={cls._dotplot_prediction(inputs)!r}, "
                f"save='.{cls._dotplot_format(inputs)}', show=None)"
            )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        return (
            f"mkdir -p {shlex.quote(out)} && cd {shlex.quote(out)} && "
            f"cat > celltypist.py <<'PY'\n"
            f"{cls._script_body(inputs)}\n"
            f"PY\n"
            "python celltypist.py"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "anndata.h5ad"]
        if cls._dotplot_generate(inputs) == "yes":
            figures = out / "figures"
            figures.mkdir(parents=True, exist_ok=True)
            outputs.append(figures / f"{cls._dotplot_prediction(inputs)}.{cls._dotplot_format(inputs)}")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("adata", "")).strip():
            return "adata is required"
        model_source = cls._model_source(inputs)
        if model_source not in cls.MODEL_SOURCES:
            return f"model_source must be one of: {', '.join(cls.MODEL_SOURCES)}"
        if model_source == "cached" and "cached_model" in inputs and not str(inputs.get("cached_model", "")).strip():
            return "cached_model is required when model_source is cached"
        if model_source == "history":
            history_model_select = cls._history_model_select(inputs)
            if history_model_select not in cls.HISTORY_MODEL_SELECTS:
                return f"history_model_select must be one of: {', '.join(cls.HISTORY_MODEL_SELECTS)}"
            if history_model_select == "select_model" and not str(inputs.get("history_model", "")).strip():
                return "history_model is required when history_model_select is select_model"
            if history_model_select == "train_model":
                if not str(inputs.get("train_anndata", "")).strip():
                    return "train_anndata is required when history_model_select is train_model"
                labels = str(inputs.get("labels", "")).strip()
                if not labels:
                    return "labels is required when history_model_select is train_model"
                if cls.NAME_PATTERN.fullmatch(labels) is None:
                    return "labels must match [0-9a-zA-Z_]+"
        mode = str(inputs.get("mode", "best match") or "best match")
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        for name, default in {"p_thres": 0.5, "min_prop": 0}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < 0 or value > 1:
                return f"{name} must be between 0 and 1"
        dotplot_generate = cls._dotplot_generate(inputs)
        if dotplot_generate not in cls.DOTPLOT_GENERATE_OPTIONS:
            return f"dotplot_generate must be one of: {', '.join(cls.DOTPLOT_GENERATE_OPTIONS)}"
        if dotplot_generate == "yes":
            reference = str(inputs.get("dotplot_reference", "cell_type") or "cell_type")
            if cls.NAME_PATTERN.fullmatch(reference) is None:
                return "dotplot_reference must match [0-9a-zA-Z_]+"
            prediction = cls._dotplot_prediction(inputs)
            if prediction not in cls.DOTPLOT_PREDICTIONS:
                return f"dotplot_prediction must be one of: {', '.join(cls.DOTPLOT_PREDICTIONS)}"
            dotplot_format = cls._dotplot_format(inputs)
            if dotplot_format not in cls.DOTPLOT_FORMATS:
                return f"dotplot_format must be one of: {', '.join(cls.DOTPLOT_FORMATS)}"
        numeric_mins = {
            "batch_number": (0, 100),
            "batch_size": (1, 1000),
            "epochs": (1, 10),
            "top_genes": (1, 300),
        }
        for name, (minimum, default) in numeric_mins.items():
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "adata": ("H5AD", {"description": "Input AnnData H5AD file"}),
            },
            "optional": {
                "model_source": ("STRING", {"default": "cached", "options": cls.MODEL_SOURCES}),
                "cached_model": ("STRING", {"default": "Immune_All_High_v1"}),
                "history_model_select": (
                    "STRING",
                    {"default": "select_model", "options": cls.HISTORY_MODEL_SELECTS},
                ),
                "history_model": ("FILE", {"default": ""}),
                "train_anndata": ("H5AD", {"default": ""}),
                "labels": ("STRING", {"default": ""}),
                "batch_number": ("INT", {"default": 100, "min": 0}),
                "batch_size": ("INT", {"default": 1000, "min": 1}),
                "epochs": ("INT", {"default": 10, "min": 1}),
                "feature_selection": ("BOOLEAN", {"default": False}),
                "top_genes": ("INT", {"default": 300, "min": 1}),
                "majority_voting": ("BOOLEAN", {"default": False}),
                "transpose_input": ("BOOLEAN", {"default": False}),
                "mode": ("STRING", {"default": "best match", "options": cls.MODES}),
                "p_thres": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
                "min_prop": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "dotplot_generate": ("STRING", {"default": "no", "options": cls.DOTPLOT_GENERATE_OPTIONS}),
                "dotplot_reference": ("STRING", {"default": "cell_type"}),
                "dotplot_prediction": (
                    "STRING",
                    {"default": "majority_voting", "options": cls.DOTPLOT_PREDICTIONS},
                ),
                "dotplot_format": ("STRING", {"default": "png", "options": cls.DOTPLOT_FORMATS}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CEMiToolNode(CommandNode):
    """Run CEMiTool gene co-expression network analysis."""

    NODE_ID = "cemitool"
    DISPLAY_NAME = "CEMiTool"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-cemitool", "r-ggplot2", "r-getopt"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Run gene co-expression network analyses with CEMiTool."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CEMiTool",
        "cemitool",
        "gene co-expression network analyses",
        "co-expression modules",
        "coexpression",
        "WGCNA",
        "over representation analysis",
        "Gene Set Enrichment Analysis",
        "GSEA",
        "module eigengene",
    ]
    RETURN_TYPES = (
        "DIRECTORY",
        "TSV",
        "TSV",
        "TSV",
        "TXT",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "HTML_REPORT",
    )
    RETURN_NAMES = (
        "plots",
        "module",
        "modules_genes",
        "parameters",
        "selected_genes",
        "summary_eigengene",
        "summary_mean",
        "summary_median",
        "interactions_output",
        "output_html",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/CEMiTool"
    CITATION_DOIS = CEMITOOL_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CEMITOOL_CITATION_DOIS]
    CITATION_TEXT = CEMITOOL_CITATION_TEXT
    VERSION = "1.34.0+galaxy0"
    SHELL = True

    OUTPUT_SELECTIONS = ["report", "tables", "plots"]
    COR_METHODS = ["pearson", "spearman"]
    COR_FUNCTIONS = ["cor", "bicor"]
    NETWORK_TYPES = ["signed", "unsigned"]
    TOM_TYPES = ["signed", "unsigned"]
    SUMMARY_METHODS = ["mean", "median"]
    SAMPLE_COLUMN_PATTERN = re.compile(r"[0-9a-zA-Z:-_]+")
    TABLE_OUTPUTS = [
        ("module", "module.tsv"),
        ("modules_genes", "modules_genes.gmt"),
        ("parameters", "parameters.tsv"),
        ("selected_genes", "selected_genes.txt"),
        ("summary_eigengene", "summary_eigengene.tsv"),
        ("summary_mean", "summary_mean.tsv"),
        ("summary_median", "summary_median.tsv"),
    ]

    @classmethod
    def _bool_text(cls, value: Any, default: bool) -> str:
        if value is None:
            return "TRUE" if default else "FALSE"
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no", ""} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("outputs"))
        return outputs or ["report"]

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("cemitool_script", "CEMiTool.R") or "CEMiTool.R")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ["Rscript", cls._script(inputs), "-M", str(inputs.get("expression_matrix", ""))]
        _add_if_value(cmd, "-A", inputs.get("annotation"))
        _add_if_value(cmd, "-P", inputs.get("pathways"))
        _add_if_value(cmd, "-I", inputs.get("interactions"))
        _add_if_value(cmd, "-B", inputs.get("beta"))
        cmd.extend(
            [
                "-f",
                cls._bool_text(inputs.get("filter"), True),
                "-i",
                str(inputs.get("filter_pval", 0.1)),
                "-a",
                cls._bool_text(inputs.get("apply_vst"), False),
                "-n",
                str(inputs.get("n_genes", 1000)),
                "-e",
                str(inputs.get("eps", 0.1)),
                "-c",
                str(inputs.get("cor_method", "pearson") or "pearson"),
                "-y",
                str(inputs.get("cor_function", "cor") or "cor"),
                "-x",
                str(inputs.get("network_type", "unsigned") or "unsigned"),
                "-t",
                str(inputs.get("tom_type", "unsigned") or "unsigned"),
                "-m",
                cls._bool_text(inputs.get("merge_similar"), False),
                "-r",
                str(inputs.get("rank_method", "mean") or "mean"),
                "-g",
                str(inputs.get("min_ngen", 30)),
                "-d",
                str(inputs.get("diss_thresh", 0.8)),
                "-h",
                str(inputs.get("center_func", "mean") or "mean"),
                "-o",
                str(inputs.get("ora_pval", 0.05)),
                "-l",
                cls._bool_text(inputs.get("gsea_scale"), True),
                "-w",
                str(inputs.get("gsea_min_size", 15)),
                "-z",
                str(inputs.get("gsea_max_size", 1000)),
                "-v",
                str(inputs.get("sample_column_name", "SampleName") or "SampleName"),
            ]
        )
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(cls._selected_outputs(inputs))
        outputs: list[Path] = []
        if "plots" in selected:
            plots = out / "Plots"
            plots.mkdir(parents=True, exist_ok=True)
            outputs.append(plots)
        if "tables" in selected:
            tables = out / "Tables"
            tables.mkdir(parents=True, exist_ok=True)
            outputs.extend(tables / filename for _, filename in cls.TABLE_OUTPUTS)
            if str(inputs.get("interactions", "")).strip():
                outputs.append(tables / "interactions.tsv")
        if "report" in selected:
            report_dir = out / "Reports" / "Report"
            report_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(report_dir / "report.html")
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
            return f"{name} must be numeric"
        if value < 0 or value > 1:
            return f"{name} must be between 0 and 1"
        return True

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], name: str, minimum: int, default: Any) -> bool | str:
        raw = inputs.get(name, default)
        if raw == "" and name == "beta":
            return True
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum:
            return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("expression_matrix", "")).strip():
            return "expression_matrix is required"
        unsupported = [output for output in cls._selected_outputs(inputs) if output not in cls.OUTPUT_SELECTIONS]
        if unsupported:
            return f"outputs values must be one or more of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        for name, default in {
            "filter_pval": 0.1,
            "eps": 0.1,
            "diss_thresh": 0.8,
            "ora_pval": 0.05,
        }.items():
            result = cls._validate_float_range(inputs, name, default)
            if result is not True:
                return result
        for name, minimum, default in [
            ("beta", 0, ""),
            ("n_genes", 0, 1000),
            ("min_ngen", 0, 30),
            ("gsea_min_size", 0, 15),
            ("gsea_max_size", 0, 1000),
        ]:
            result = cls._validate_int_min(inputs, name, minimum, default)
            if result is not True:
                return result
        choice_checks = [
            ("cor_method", cls.COR_METHODS, "pearson"),
            ("cor_function", cls.COR_FUNCTIONS, "cor"),
            ("network_type", cls.NETWORK_TYPES, "unsigned"),
            ("tom_type", cls.TOM_TYPES, "unsigned"),
            ("rank_method", cls.SUMMARY_METHODS, "mean"),
            ("center_func", cls.SUMMARY_METHODS, "mean"),
        ]
        for name, options, default in choice_checks:
            result = cls._validate_choice(inputs, name, options, default)
            if result is not True:
                return result
        sample_column_name = str(inputs.get("sample_column_name", "SampleName") or "SampleName")
        if cls.SAMPLE_COLUMN_PATTERN.fullmatch(sample_column_name) is None:
            return "sample_column_name must match [0-9a-zA-Z:-_]+"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "expression_matrix": ("TSV", {"description": "Expression matrix"}),
            },
            "optional": {
                "annotation": ("TSV", {"default": "", "description": "Sample annotation table"}),
                "pathways": ("FILE", {"default": "", "description": "GMT pathway list for ORA"}),
                "interactions": ("TSV", {"default": "", "description": "Interaction data with gene pairs"}),
                "beta": ("INT", {"default": "", "min": 0, "description": "Optional WGCNA beta value"}),
                "outputs": (
                    "STRING_LIST",
                    {"default": ["report"], "options": cls.OUTPUT_SELECTIONS, "multiple": True},
                ),
                "cemitool_script": ("FILE", {"default": "CEMiTool.R", "advanced": True}),
                "filter": ("BOOLEAN", {"default": True}),
                "filter_pval": ("FLOAT", {"default": 0.1, "min": 0, "max": 1}),
                "apply_vst": ("BOOLEAN", {"default": False}),
                "n_genes": ("INT", {"default": 1000, "min": 0}),
                "eps": ("FLOAT", {"default": 0.1, "min": 0, "max": 1}),
                "cor_method": ("STRING", {"default": "pearson", "options": cls.COR_METHODS}),
                "cor_function": ("STRING", {"default": "cor", "options": cls.COR_FUNCTIONS}),
                "network_type": ("STRING", {"default": "unsigned", "options": cls.NETWORK_TYPES}),
                "tom_type": ("STRING", {"default": "unsigned", "options": cls.TOM_TYPES}),
                "merge_similar": ("BOOLEAN", {"default": False}),
                "rank_method": ("STRING", {"default": "mean", "options": cls.SUMMARY_METHODS}),
                "min_ngen": ("INT", {"default": 30, "min": 0}),
                "diss_thresh": ("FLOAT", {"default": 0.8, "min": 0, "max": 1}),
                "center_func": ("STRING", {"default": "mean", "options": cls.SUMMARY_METHODS}),
                "ora_pval": ("FLOAT", {"default": 0.05, "min": 0, "max": 1}),
                "gsea_scale": ("BOOLEAN", {"default": True}),
                "gsea_min_size": ("INT", {"default": 15, "min": 0}),
                "gsea_max_size": ("INT", {"default": 1000, "min": 0}),
                "sample_column_name": ("STRING", {"default": "SampleName"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ChartsNode(CommandNode):
    """Generate tabular chart data with Galaxy Charts R modules."""

    NODE_ID = "charts"
    DISPLAY_NAME = "Charts"
    REQUIRED_CONDA_PACKAGES = ["r-getopt", "r-matrix"]
    CATEGORY = "visualization"
    DESCRIPTION = "Generate tabular chart data from tabular inputs with Galaxy Charts R modules."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Charts",
        "charts",
        "Chart Utilities",
        "boxplot",
        "heatmap",
        "histogram",
        "histogramdiscrete",
        "R chart modules",
        "tabular visualization",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = CHARTS_CITATION_URL
    CITATION_URLS = [CHARTS_CITATION_URL]
    CITATION_TEXT = CHARTS_CITATION_TEXT
    VERSION = "1.0.1"
    SHELL = True

    MODULES = ["boxplot", "heatmap", "histogram", "histogramdiscrete"]

    @classmethod
    def _module(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("module", "boxplot") or "boxplot")

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("charts_script", "charts.r") or "charts.r")

    @classmethod
    def _workdir(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("charts_workdir", "./") or "./")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "Rscript",
            cls._script(inputs),
            "-w",
            cls._workdir(inputs),
            "-m",
            cls._module(inputs),
            "-i",
            str(inputs.get("input", "")),
            "-c",
            str(inputs.get("columns", "")),
            "-s",
            str(inputs.get("settings", "")),
            "-o",
            cls._output_path(inputs),
        ]
        return f"{_shell_join(['mkdir', '-p', out])} && cd {shlex.quote(out)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if cls._module(inputs) not in cls.MODULES:
            return f"module must be one of: {', '.join(cls.MODULES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Input tabular dataset"}),
            },
            "optional": {
                "module": ("STRING", {"default": "boxplot", "options": cls.MODULES}),
                "columns": (
                    "STRING",
                    {"default": "", "description": "Column mapping string, such as key1: 2, key2: 3"},
                ),
                "settings": (
                    "STRING",
                    {"default": "", "description": "Options string, such as key1: value, key2: value"},
                ),
                "charts_script": ("FILE", {"default": "charts.r", "advanced": True}),
                "charts_workdir": ("STRING", {"default": "./", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AnnDataInspectNode(CommandNode):
    """Inspect AnnData H5AD matrices, annotations, embeddings, and unstructured results."""

    NODE_ID = "anndata_inspect"
    DISPLAY_NAME = "Inspect AnnData"
    REQUIRED_CONDA_PACKAGES = ["anndata", "scanpy", "loompy", "pandas"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Inspect AnnData H5AD matrices, annotations, embeddings, and unstructured analysis results."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AnnData",
        "anndata_inspect",
        "Inspect AnnData",
        "H5AD",
        "chunk_X",
        "obs",
        "var",
        "uns",
        "obsm",
        "varm",
        "rank_genes_groups",
        "X_draw_graph",
    ]
    RETURN_TYPES = (
        "TXT",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "FILE",
        "FILE",
        "FILE",
        "FILE",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "DIRECTORY",
        "TSV",
        "TSV",
    )
    RETURN_NAMES = (
        "general",
        "X",
        "obs",
        "var",
        "chunk_X",
        "uns_neighbors_connectivities",
        "uns_neighbors_distances",
        "uns_paga_connectivities",
        "uns_paga_connectivities_tree",
        "uns_pca_variance",
        "uns_pca_variance_ratio",
        "uns_rank_genes_groups_names",
        "uns_rank_genes_groups_scores",
        "uns_rank_genes_groups_logfoldchanges",
        "uns_rank_genes_groups_pvals",
        "uns_rank_genes_groups_pvals_adj",
        "obsm_X_pca",
        "obsm_X_umap",
        "obsm_X_tsne",
        "obsm_X_draw_graph",
        "obsm_X_diffmap",
        "varm_PCs",
    )
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html"
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}"]
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = "0.11.4+galaxy3"
    SHELL = True

    INFO_OPTIONS = ["general", "obs", "var", "X", "chunk_X", "uns", "obsm", "varm"]
    CHUNK_OPTIONS = ["random", "specified"]
    UNS_OPTIONS = ["neighbors", "paga", "pca", "rank_genes_groups"]
    OBSM_OPTIONS = ["X_pca", "X_umap", "X_tsne", "X_draw_graph", "X_diffmap"]
    VARM_OPTIONS = ["PCs"]

    @classmethod
    def _info(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("info", "general") or "general")

    @classmethod
    def _bool_text(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return "False" if value.lower() in {"false", "0", "no"} else "True"
        return "True" if bool(value) else "False"

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _common_script_prefix(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "import anndata as ad",
            "import pandas as pd",
            "from scipy import io",
            "pd.options.display.precision = 15",
            f"adata = ad.read_h5ad({str(inputs.get('input', ''))!r}, backed='r')",
        ]

    @classmethod
    def _specified_chunk_select(cls, inputs: dict[str, Any]) -> list[int]:
        return [int(value.strip()) for value in str(inputs.get("chunk_list", "")).split(",") if value.strip()]

    @classmethod
    def _branch_script(cls, inputs: dict[str, Any]) -> list[str]:
        info = cls._info(inputs)
        if info == "general":
            return [
                f"with open({cls._path(inputs, 'general.txt')!r}, 'w', encoding='utf-8') as f:",
                "    print(adata, file=f)",
            ]
        if info == "X":
            return [f"adata.to_df().to_csv({cls._path(inputs, 'X.tsv')!r}, sep='\\t')"]
        if info == "obs":
            return [f"adata.obs.to_csv({cls._path(inputs, 'obs.tsv')!r}, sep='\\t')"]
        if info == "var":
            return [f"adata.var.to_csv({cls._path(inputs, 'var.tsv')!r}, sep='\\t')"]
        if info == "chunk_X":
            if str(inputs.get("chunk_info", "random") or "random") == "specified":
                lines = [f"X = adata.chunk_X(select={cls._specified_chunk_select(inputs)!r})"]
            else:
                lines = [
                    (
                        f"X = adata.chunk_X(select={int(inputs.get('chunk_size', 1000) or 1000)}, "
                        f"replace={cls._bool_text(inputs, 'chunk_replace', True)})"
                    )
                ]
            lines.append(f"pd.DataFrame(X).to_csv({cls._path(inputs, 'chunk_X.tsv')!r}, sep='\\t')")
            return lines
        if info == "uns":
            uns_info = str(inputs.get("uns_info", "neighbors") or "neighbors")
            if uns_info == "neighbors":
                return [
                    f"io.mmwrite({cls._path(inputs, 'uns_neighbors_connectivities.mtx')!r}, adata.obsp['connectivities'])",
                    f"io.mmwrite({cls._path(inputs, 'uns_neighbors_distances.mtx')!r}, adata.obsp['distances'])",
                ]
            if uns_info == "paga":
                return [
                    f"io.mmwrite({cls._path(inputs, 'uns_paga_connectivities.mtx')!r}, adata.uns['paga']['connectivities'])",
                    (
                        f"io.mmwrite({cls._path(inputs, 'uns_paga_connectivities_tree.mtx')!r}, "
                        "adata.uns['paga']['connectivities_tree'])"
                    ),
                ]
            if uns_info == "pca":
                return [
                    f"pd.DataFrame(adata.uns['pca']['variance']).to_csv({cls._path(inputs, 'uns_pca_variance.tsv')!r}, sep='\\t', index=False)",
                    (
                        f"pd.DataFrame(adata.uns['pca']['variance_ratio']).to_csv("
                        f"{cls._path(inputs, 'uns_pca_variance_ratio.tsv')!r}, sep='\\t', index=False)"
                    ),
                ]
            return [
                f"pd.DataFrame(adata.uns['rank_genes_groups']['logfoldchanges']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_logfoldchanges.tsv')!r}, sep='\\t', index=False)",
                f"pd.DataFrame(adata.uns['rank_genes_groups']['names']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_names.tsv')!r}, sep='\\t', index=False)",
                f"pd.DataFrame(adata.uns['rank_genes_groups']['pvals']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_pvals.tsv')!r}, sep='\\t', index=False)",
                f"pd.DataFrame(adata.uns['rank_genes_groups']['pvals_adj']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_pvals_adj.tsv')!r}, sep='\\t', index=False)",
                f"pd.DataFrame(adata.uns['rank_genes_groups']['scores']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_scores.tsv')!r}, sep='\\t', index=False)",
            ]
        if info == "obsm":
            obsm_info = str(inputs.get("obsm_info", "X_pca") or "X_pca")
            if obsm_info == "X_draw_graph":
                return [
                    "for key in adata.obsm.keys():",
                    "    if key.startswith('X_draw_graph'):",
                    f"        pd.DataFrame(adata.obsm[key]).to_csv(f'{cls._path(inputs, 'obsm_X_draw_graph')}/{{key}}.tsv', sep='\\t', index=False)",
                ]
            filename = f"obsm_{obsm_info}.tsv"
            return [
                f"pd.DataFrame(adata.obsm[{obsm_info!r}]).to_csv({cls._path(inputs, filename)!r}, sep='\\t', index=False)"
            ]
        return [f"pd.DataFrame(adata.varm['PCs']).to_csv({cls._path(inputs, 'varm_PCs.tsv')!r}, sep='\\t', index=False)"]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        return "\n".join([*cls._common_script_prefix(inputs), *cls._branch_script(inputs)])

    @classmethod
    def _pre_commands(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._info(inputs) == "obsm" and str(inputs.get("obsm_info", "X_pca") or "X_pca") == "X_draw_graph":
            return [f"mkdir -p {shlex.quote(cls._path(inputs, 'obsm_X_draw_graph'))}"]
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}", f"cd {shlex.quote(out)}", *cls._pre_commands(inputs)]
        commands.append(f"cat > anndata_inspect.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_inspect.py")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        info = cls._info(inputs)
        if info == "general":
            return [out / "general.txt"]
        if info == "X":
            return [out / "X.tsv"]
        if info == "obs":
            return [out / "obs.tsv"]
        if info == "var":
            return [out / "var.tsv"]
        if info == "chunk_X":
            return [out / "chunk_X.tsv"]
        if info == "uns":
            uns_info = str(inputs.get("uns_info", "neighbors") or "neighbors")
            if uns_info == "neighbors":
                return [out / "uns_neighbors_connectivities.mtx", out / "uns_neighbors_distances.mtx"]
            if uns_info == "paga":
                return [out / "uns_paga_connectivities.mtx", out / "uns_paga_connectivities_tree.mtx"]
            if uns_info == "pca":
                return [out / "uns_pca_variance.tsv", out / "uns_pca_variance_ratio.tsv"]
            return [
                out / "uns_rank_genes_groups_names.tsv",
                out / "uns_rank_genes_groups_scores.tsv",
                out / "uns_rank_genes_groups_logfoldchanges.tsv",
                out / "uns_rank_genes_groups_pvals.tsv",
                out / "uns_rank_genes_groups_pvals_adj.tsv",
            ]
        if info == "obsm":
            obsm_info = str(inputs.get("obsm_info", "X_pca") or "X_pca")
            if obsm_info == "X_draw_graph":
                directory = out / "obsm_X_draw_graph"
                directory.mkdir(parents=True, exist_ok=True)
                return [directory]
            return [out / f"obsm_{obsm_info}.tsv"]
        return [out / "varm_PCs.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        info = cls._info(inputs)
        if info not in cls.INFO_OPTIONS:
            return f"info must be one of: {', '.join(cls.INFO_OPTIONS)}"
        if info == "chunk_X":
            chunk_info = str(inputs.get("chunk_info", "random") or "random")
            if chunk_info not in cls.CHUNK_OPTIONS:
                return f"chunk_info must be one of: {', '.join(cls.CHUNK_OPTIONS)}"
            if chunk_info == "specified" and not str(inputs.get("chunk_list", "")).strip():
                return "chunk_list is required when chunk_info is specified"
        if info == "uns" and str(inputs.get("uns_info", "neighbors") or "neighbors") not in cls.UNS_OPTIONS:
            return f"uns_info must be one of: {', '.join(cls.UNS_OPTIONS)}"
        if info == "obsm" and str(inputs.get("obsm_info", "X_pca") or "X_pca") not in cls.OBSM_OPTIONS:
            return f"obsm_info must be one of: {', '.join(cls.OBSM_OPTIONS)}"
        if info == "varm" and str(inputs.get("varm_info", "PCs") or "PCs") not in cls.VARM_OPTIONS:
            return f"varm_info must be one of: {', '.join(cls.VARM_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("H5AD", {"description": "Annotated data matrix to inspect"}),
            },
            "optional": {
                "info": ("STRING", {"default": "general", "options": cls.INFO_OPTIONS}),
                "chunk_info": ("STRING", {"default": "random", "options": cls.CHUNK_OPTIONS}),
                "chunk_size": ("INT", {"default": 1000, "min": 1}),
                "chunk_replace": ("BOOLEAN", {"default": True}),
                "chunk_list": ("STRING", {"default": ""}),
                "uns_info": ("STRING", {"default": "neighbors", "options": cls.UNS_OPTIONS}),
                "obsm_info": ("STRING", {"default": "X_pca", "options": cls.OBSM_OPTIONS}),
                "varm_info": ("STRING", {"default": "PCs", "options": cls.VARM_OPTIONS}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AnnDataManipulateNode(CommandNode):
    """Manipulate AnnData H5AD objects using the Galaxy IUC AnnData wrapper operations."""

    NODE_ID = "anndata_manipulate"
    DISPLAY_NAME = "Manipulate AnnData"
    REQUIRED_CONDA_PACKAGES = ["anndata", "scanpy", "loompy", "pandas"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Manipulate AnnData H5AD objects by concatenating, renaming, annotating, copying, splitting, or transposing."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AnnData",
        "anndata_manipulate",
        "Manipulate AnnData",
        "H5AD",
        "concatenate",
        "obs_names_make_unique",
        "var_names_make_unique",
        "rename_categories",
        "remove_keys",
        "flag_genes",
        "rename_obs",
        "rename_var",
        "strings_to_categoricals",
        "transpose",
        "add_annotation",
        "split_on_obs",
        "copy_obs",
        "copy_uns",
        "copy_embed",
        "copy_layers",
        "copy_X",
        "save_raw",
    ]
    RETURN_TYPES = ("H5AD", "DIRECTORY")
    RETURN_NAMES = ("anndata", "output_h5ad_split")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html"
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}"]
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = "0.11.4+galaxy3"
    SHELL = True

    FUNCTIONS = [
        "concatenate",
        "obs_names_make_unique",
        "var_names_make_unique",
        "rename_categories",
        "remove_keys",
        "flag_genes",
        "rename_obs",
        "rename_var",
        "strings_to_categoricals",
        "transpose",
        "add_annotation",
        "split_on_obs",
        "copy_obs",
        "copy_uns",
        "copy_embed",
        "copy_layers",
        "copy_X",
        "save_raw",
    ]
    JOIN_OPTIONS = ["-", "_", " ", "/"]
    CONCAT_JOIN_OPTIONS = ["inner", "outer"]
    UNS_MERGE_OPTIONS = ["None", "same", "unique", "first", "only"]
    ANNOTATION_TARGETS = ["var", "obs"]

    @classmethod
    def _function(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("function", "concatenate") or "concatenate")

    @staticmethod
    def _bool_value(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() not in {"false", "0", "no", ""}
        return bool(value)

    @staticmethod
    def _repeat_dicts(value: Any) -> list[dict[str, Any]]:
        if value is None or value == "":
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, (list, tuple)):
            rows: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, dict):
                    rows.append(item)
                else:
                    rows.append({"source_key": item})
            return rows
        return [{"source_key": value}]

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        lines = [
            "import anndata as ad",
            f"adata = ad.read_h5ad({str(inputs.get('input', ''))!r}, backed='r')",
            *cls._branch_script(inputs),
        ]
        if cls._function(inputs) != "split_on_obs":
            lines.extend(["adata.write('anndata.h5ad', compression='gzip')", "print(adata)"])
        return "\n".join(lines)

    @classmethod
    def _branch_script(cls, inputs: dict[str, Any]) -> list[str]:
        function = cls._function(inputs)
        if function == "concatenate":
            lines = ["adata = adata.to_memory()"]
            other_adatas = _as_list(inputs.get("other_adatas"))
            for index, path in enumerate(other_adatas):
                lines.append(f"adata_{index} = ad.read_h5ad({path!r}, backed='r').to_memory()")
            lines.append("adata = adata.concatenate(")
            for index, _path_value in enumerate(other_adatas):
                lines.append(f"    adata_{index},")
            lines.append(f"    join={str(inputs.get('join', 'inner') or 'inner')!r},")
            index_unique = str(inputs.get("index_unique", "-"))
            if index_unique != "":
                lines.append(f"    index_unique={index_unique!r},")
            else:
                lines.append("    index_unique=None,")
            uns_merge = str(inputs.get("uns_merge", "None") or "None")
            if uns_merge != "None":
                lines.append(f"    uns_merge={uns_merge!r},")
            else:
                lines.append("    uns_merge=None,")
            lines.append(f"    batch_key={str(inputs.get('batch_key', 'batch') or 'batch')!r})")
            return lines
        if function == "var_names_make_unique":
            return [f"adata.var_names_make_unique(join={str(inputs.get('join', '-') or '-')!r})"]
        if function == "obs_names_make_unique":
            return [f"adata.obs_names_make_unique(join={str(inputs.get('join', '-') or '-')!r})"]
        if function == "rename_categories":
            return cls._rename_categories_script(inputs)
        if function == "remove_keys":
            return cls._remove_keys_script(inputs)
        if function == "flag_genes":
            return cls._flag_genes_script(inputs)
        if function == "rename_obs":
            return cls._rename_axis_script(inputs, axis="obs")
        if function == "rename_var":
            return cls._rename_axis_script(inputs, axis="var")
        if function == "strings_to_categoricals":
            return ["adata.strings_to_categoricals()"]
        if function == "transpose":
            return ["adata = adata.to_memory()", "adata = adata.transpose()"]
        if function == "add_annotation":
            return cls._add_annotation_script(inputs)
        if function == "split_on_obs":
            return cls._split_on_obs_script(inputs)
        if function in {"copy_obs", "copy_uns", "copy_embed", "copy_layers"}:
            return cls._copy_keyed_script(inputs, function)
        if function == "copy_X":
            return cls._copy_x_script(inputs)
        if function == "save_raw":
            return ["adata = adata.to_memory()", "adata.raw = adata"]
        return []

    @classmethod
    def _rename_categories_script(cls, inputs: dict[str, Any]) -> list[str]:
        key = str(inputs.get("key", ""))
        categories = [value.strip() for value in str(inputs.get("categories", "")).split(",") if value.strip()]
        lines = [f"categories = {categories!r}"]
        if str(inputs.get("new_key", "no") or "no") != "yes":
            lines.append(f"adata.rename_categories(key={key!r}, categories=categories)")
            return lines
        key_name = str(inputs.get("key_name", ""))
        return [
            *lines,
            f"if {key!r} in adata.obs:",
            "    print('changing key in obs')",
            f"    adata.obs[{key_name!r}] = adata.obs[{key!r}]",
            f"    adata.rename_categories(key={key_name!r}, categories=categories)",
            f"elif {key!r} in adata.var:",
            "    print('changing key in var')",
            f"    adata.var[{key_name!r}] = adata.var[{key!r}]",
            f"    adata.rename_categories(key={key_name!r}, categories=categories)",
            "else:",
            "    print('changing key in uns')",
            f"    adata.uns[{key_name!r}] = adata.uns[{key!r}]",
            f"    adata.rename_categories(key={key_name!r}, categories=categories)",
        ]

    @staticmethod
    def _csv_values(value: Any) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @classmethod
    def _remove_keys_script(cls, inputs: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        obs_keys = cls._csv_values(inputs.get("obs_keys"))
        if obs_keys:
            lines.append(f"adata.obs = adata.obs.drop(columns={obs_keys!r})")
        var_keys = cls._csv_values(inputs.get("var_keys"))
        if var_keys:
            lines.append(f"adata.var = adata.var.drop(columns={var_keys!r})")
        return lines

    @classmethod
    def _flag_genes_script(cls, inputs: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for flag in cls._repeat_dicts(inputs.get("gene_flags")):
            startswith = str(flag.get("startswith", ""))
            col_in = str(flag.get("col_in", "") or "")
            col_out = str(flag.get("col_out", ""))
            if col_in:
                lines.append(f"k_cat = adata.var[{col_in!r}].str.startswith({startswith!r})")
            else:
                lines.append(f"k_cat = adata.var_names.str.startswith({startswith!r})")
            lines.extend(
                [
                    "if k_cat.sum() > 0:",
                    f"    adata.var[{col_out!r}] = k_cat",
                    "else:",
                    f"    print(\"No genes starting with {startswith} found.\")",
                ]
            )
        return lines

    @classmethod
    def _rename_axis_script(cls, inputs: dict[str, Any], axis: str) -> list[str]:
        from_key = str(inputs.get(f"from_{axis}", ""))
        to_key = str(inputs.get(f"to_{axis}", ""))
        lines = [f"adata.{axis}[{to_key!r}] = adata.{axis}[{from_key!r}]"]
        if not cls._bool_value(inputs.get("keep_original"), default=False):
            lines.append(f"del adata.{axis}[{from_key!r}]")
        return lines

    @classmethod
    def _add_annotation_script(cls, inputs: dict[str, Any]) -> list[str]:
        target = str(inputs.get("var_obs", "var") or "var")
        new_annot = str(inputs.get("new_annot", ""))
        if target == "obs":
            return [
                "import pandas as pd",
                f"extra_annot_t = pd.read_csv({new_annot!r}, sep='\\t').reset_index(drop=True)",
                "obs_index = adata.obs.index",
                "obs = pd.concat([adata.obs.reset_index(drop=True), extra_annot_t], axis=1)",
                "obs.index = obs_index",
                "adata.obs = obs",
            ]
        return [
            "import pandas as pd",
            f"extra_annot_t = pd.read_csv({new_annot!r}, sep='\\t').reset_index(drop=True)",
            "var_index = adata.var_names",
            "var = pd.concat([adata.var.reset_index(drop=True), extra_annot_t], axis=1)",
            "var.index = var_index",
            "adata.var = var",
        ]

    @classmethod
    def _split_on_obs_script(cls, inputs: dict[str, Any]) -> list[str]:
        key = str(inputs.get("key", ""))
        return [
            "import os",
            "adata = adata.to_memory()",
            "res_dir = 'output_split'",
            "os.makedirs(res_dir, exist_ok=True)",
            f"for s, field_value in enumerate(adata.obs[{key!r}].unique()):",
            f"    ad_s = adata[adata.obs[{key!r}] == field_value].copy()",
            f"    ad_s.write(f\"{{res_dir}}/{key}_{{s}}.h5ad\", compression='gzip')",
        ]

    @classmethod
    def _copy_keyed_script(cls, inputs: dict[str, Any], function: str) -> list[str]:
        source = str(inputs.get("source_adata", ""))
        lines = [f"source_adata = ad.read_h5ad({source!r}, backed='r')"]
        container_by_function = {
            "copy_obs": "obs",
            "copy_uns": "uns",
            "copy_embed": "obsm",
            "copy_layers": "layers",
        }
        label_by_function = {
            "copy_obs": "Obs column",
            "copy_uns": "Uns key",
            "copy_embed": "Embedding key",
            "copy_layers": "Layer",
        }
        container = container_by_function[function]
        label = label_by_function[function]
        for row in cls._repeat_dicts(inputs.get("keys")):
            source_key = str(row.get("source_key", "") or "")
            target_key = str(row.get("target_key", "") or "") or source_key
            lines.extend(
                [
                    f"if {source_key!r} in source_adata.{container}:",
                    f"    adata.{container}[{target_key!r}] = source_adata.{container}[{source_key!r}]",
                    "else:",
                    f"    print(\"{label} {source_key} not found in source AnnData.\")",
                ]
            )
        return lines

    @classmethod
    def _copy_x_script(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get("source_adata", ""))
        target_key = str(inputs.get("target_key", "") or "")
        lines = [f"source_adata = ad.read_h5ad({source!r}, backed='r')"]
        if target_key:
            lines.append(f"adata.layers[{target_key!r}] = source_adata.X")
        else:
            lines.append("adata.X = source_adata.X")
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}", f"cd {shlex.quote(out)}"]
        commands.append(f"cat > anndata_manipulate.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_manipulate.py")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._function(inputs) == "split_on_obs":
            split_dir = out / "output_split"
            split_dir.mkdir(parents=True, exist_ok=True)
            return [split_dir]
        return [out / "anndata.h5ad"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        function = cls._function(inputs)
        if function not in cls.FUNCTIONS:
            return f"function must be one of: {', '.join(cls.FUNCTIONS)}"
        if function == "concatenate" and not _as_list(inputs.get("other_adatas")):
            return "other_adatas is required when function is concatenate"
        if function in {"obs_names_make_unique", "var_names_make_unique"}:
            if str(inputs.get("join", "-") or "-") not in cls.JOIN_OPTIONS:
                return f"join must be one of: {', '.join(cls.JOIN_OPTIONS)}"
        if function == "rename_categories":
            for key in ("key", "categories"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when function is rename_categories"
            if str(inputs.get("new_key", "no") or "no") == "yes" and not str(inputs.get("key_name", "")).strip():
                return "key_name is required when new_key is yes"
        if function == "flag_genes":
            if not cls._repeat_dicts(inputs.get("gene_flags")):
                return "gene_flags is required when function is flag_genes"
        if function == "rename_obs":
            for key in ("from_obs", "to_obs"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when function is rename_obs"
        if function == "rename_var":
            for key in ("from_var", "to_var"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when function is rename_var"
        if function == "add_annotation":
            if str(inputs.get("var_obs", "var") or "var") not in cls.ANNOTATION_TARGETS:
                return f"var_obs must be one of: {', '.join(cls.ANNOTATION_TARGETS)}"
            if not str(inputs.get("new_annot", "")).strip():
                return "new_annot is required when function is add_annotation"
        if function == "split_on_obs" and not str(inputs.get("key", "")).strip():
            return "key is required when function is split_on_obs"
        if function in {"copy_obs", "copy_uns", "copy_embed", "copy_layers"}:
            if not str(inputs.get("source_adata", "")).strip():
                return f"source_adata is required when function is {function}"
            if not cls._repeat_dicts(inputs.get("keys")):
                return f"keys is required when function is {function}"
        if function == "copy_X" and not str(inputs.get("source_adata", "")).strip():
            return "source_adata is required when function is copy_X"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("H5AD", {"description": "Annotated data matrix to manipulate"}),
            },
            "optional": {
                "function": ("STRING", {"default": "concatenate", "options": cls.FUNCTIONS}),
                "other_adatas": (
                    "H5AD",
                    {"default": "", "multiple": True, "description": "Additional AnnData matrices for concatenation"},
                ),
                "join": ("STRING", {"default": "-", "options": [*cls.JOIN_OPTIONS, *cls.CONCAT_JOIN_OPTIONS]}),
                "batch_key": ("STRING", {"default": "batch"}),
                "uns_merge": ("STRING", {"default": "None", "options": cls.UNS_MERGE_OPTIONS}),
                "index_unique": ("STRING", {"default": "-", "options": ["", *cls.JOIN_OPTIONS]}),
                "key": ("STRING", {"default": "", "description": "Observation, variable, or unstructured annotation key"}),
                "categories": ("STRING", {"default": "", "description": "Comma-separated replacement categories"}),
                "new_key": ("STRING", {"default": "no", "options": ["yes", "no"]}),
                "key_name": ("STRING", {"default": ""}),
                "obs_keys": ("STRING", {"default": "", "description": "Comma-separated obs columns to remove"}),
                "var_keys": ("STRING", {"default": "", "description": "Comma-separated var columns to remove"}),
                "gene_flags": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Galaxy repeat-style flag definitions with startswith, col_in, and col_out",
                    },
                ),
                "from_obs": ("STRING", {"default": ""}),
                "to_obs": ("STRING", {"default": ""}),
                "from_var": ("STRING", {"default": ""}),
                "to_var": ("STRING", {"default": ""}),
                "keep_original": ("BOOLEAN", {"default": False}),
                "var_obs": ("STRING", {"default": "var", "options": cls.ANNOTATION_TARGETS}),
                "new_annot": ("TSV", {"default": "", "description": "Tabular annotations to append"}),
                "source_adata": ("H5AD", {"default": "", "description": "Source AnnData object for copy operations"}),
                "keys": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Galaxy repeat-style key mappings with source_key and optional target_key",
                    },
                ),
                "target_key": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ModifyLoomNode(CommandNode):
    """Manipulate, export, and import Loom files using the Galaxy IUC AnnData wrapper helpers."""

    NODE_ID = "modify_loom"
    DISPLAY_NAME = "Loom operations"
    REQUIRED_CONDA_PACKAGES = ["anndata", "scanpy", "loompy", "pandas"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Manipulate, export, and import Loom single-cell data files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Loom",
        "modify_loom",
        "Loom operations",
        "loompy",
        "loompy_to_tsv",
        "tsv_to_loompy",
        "H5AD to Loom",
        "Loom layers",
        "row attributes",
        "column attributes",
        "single-cell loom",
    ]
    RETURN_TYPES = ("LOOM", "DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("loomout", "layer_tsvs", "attribute_tsvs")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://linnarssonlab.org/loompy/"
    CITATION_DOIS: list[str] = []
    CITATION_URLS = ["https://github.com/linnarsson-lab/loompy"]
    CITATION_TEXT = "Loompy provides Loom file creation, manipulation, layers, and row/column attributes for single-cell data."
    VERSION = "0.11.4+galaxy3"
    SHELL = True

    OPERATIONS = ["manipulate", "export", "import"]
    ADD_TYPES = ["cols", "rows", "layers"]
    FILE_TYPES = ["ad", "tab"]

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("operation", "manipulate") or "manipulate")

    @classmethod
    def _add_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("add_type", "cols") or "cols")

    @classmethod
    def _file_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("file_type", "ad") or "ad")

    @staticmethod
    def _script(inputs: dict[str, Any], key: str, default: str) -> str:
        return str(inputs.get(key, default) or default)

    @classmethod
    def _import_script_body(cls, inputs: dict[str, Any]) -> str:
        return "\n".join(
            [
                "import anndata as ad",
                f"adata = ad.read_h5ad({str(inputs.get('anndata', ''))!r})",
                "adata.write_loom('converted.loom')",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}", f"cd {shlex.quote(out)}"]
        operation = cls._operation(inputs)
        if operation == "manipulate":
            commands.append(f"cp {shlex.quote(str(inputs.get('loom', '')))} converted.loom")
            cmd = [
                "python",
                cls._script(inputs, "modify_loom_script", "modify_loom.py"),
                "-f",
                "converted.loom",
                "-a",
                cls._add_type(inputs),
            ]
            add_type = cls._add_type(inputs)
            if add_type == "cols":
                cmd.extend(["-c", str(inputs.get("cols", ""))])
            elif add_type == "rows":
                cmd.extend(["-r", str(inputs.get("rows", ""))])
            else:
                cmd.append("-l")
                cmd.extend(_as_list(inputs.get("layers")))
            commands.append(_shell_join(cmd))
        elif operation == "export":
            commands.append("mkdir -p output attributes")
            commands.append(
                _shell_join(
                    [
                        "python",
                        cls._script(inputs, "loompy_to_tsv_script", "loompy_to_tsv.py"),
                        "-f",
                        str(inputs.get("loom", "")),
                    ]
                )
            )
        elif cls._file_type(inputs) == "ad":
            commands.append(f"cat > modify_loom_import.py <<'PY'\n{cls._import_script_body(inputs)}\nPY\npython modify_loom_import.py")
        else:
            cmd = [
                "python",
                cls._script(inputs, "tsv_to_loompy_script", "tsv_to_loompy.py"),
                "-c",
                str(inputs.get("coldata", "")),
                "-r",
                str(inputs.get("rowdata", "")),
                "-f",
                str(inputs.get("mainmatrix", "")),
            ]
            cmd.extend(_as_list(inputs.get("other_files")))
            commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._operation(inputs) == "export":
            layers = out / "output"
            attributes = out / "attributes"
            layers.mkdir(parents=True, exist_ok=True)
            attributes.mkdir(parents=True, exist_ok=True)
            return [layers, attributes]
        return [out / "converted.loom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        if operation in {"manipulate", "export"} and not str(inputs.get("loom", "")).strip():
            return f"loom is required when operation is {operation}"
        if operation == "manipulate":
            add_type = cls._add_type(inputs)
            if add_type not in cls.ADD_TYPES:
                return f"add_type must be one of: {', '.join(cls.ADD_TYPES)}"
            if add_type == "cols" and not str(inputs.get("cols", "")).strip():
                return "cols is required when add_type is cols"
            if add_type == "rows" and not str(inputs.get("rows", "")).strip():
                return "rows is required when add_type is rows"
            if add_type == "layers" and not _as_list(inputs.get("layers")):
                return "layers is required when add_type is layers"
        if operation == "import":
            file_type = cls._file_type(inputs)
            if file_type not in cls.FILE_TYPES:
                return f"file_type must be one of: {', '.join(cls.FILE_TYPES)}"
            if file_type == "ad" and not str(inputs.get("anndata", "")).strip():
                return "anndata is required when file_type is ad"
            if file_type == "tab":
                for key in ("mainmatrix", "coldata", "rowdata"):
                    if not str(inputs.get(key, "")).strip():
                        return f"{key} is required when file_type is tab"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "optional": {
                "operation": ("STRING", {"default": "manipulate", "options": cls.OPERATIONS}),
                "loom": ("LOOM", {"default": "", "description": "Loom file to manipulate or export"}),
                "add_type": ("STRING", {"default": "cols", "options": cls.ADD_TYPES}),
                "cols": ("TSV", {"default": "", "description": "Column attributes to add"}),
                "rows": ("TSV", {"default": "", "description": "Row attributes to add"}),
                "layers": ("TSV", {"default": "", "multiple": True, "description": "Layer matrix TSV files to add"}),
                "file_type": ("STRING", {"default": "ad", "options": cls.FILE_TYPES}),
                "anndata": ("H5AD", {"default": "", "description": "AnnData H5AD file to convert to Loom"}),
                "mainmatrix": ("TSV", {"default": "", "description": "Main matrix TSV for tabular Loom import"}),
                "other_files": ("TSV", {"default": "", "multiple": True, "description": "Optional additional layer TSV files"}),
                "coldata": ("TSV", {"default": "", "description": "Column attribute TSV"}),
                "rowdata": ("TSV", {"default": "", "description": "Row attribute TSV"}),
                "modify_loom_script": ("FILE", {"default": "modify_loom.py"}),
                "loompy_to_tsv_script": ("FILE", {"default": "loompy_to_tsv.py"}),
                "tsv_to_loompy_script": ("FILE", {"default": "tsv_to_loompy.py"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Anndata2RiNode(CommandNode):
    """Convert between AnnData H5AD and R SingleCellExperiment RDS objects."""

    NODE_ID = "anndata2ri"
    DISPLAY_NAME = "anndata2ri"
    REQUIRED_CONDA_PACKAGES = ["anndata2ri", "anndata", "bioconductor-singlecellexperiment"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Convert between AnnData and SingleCellExperiment objects."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "anndata2ri",
        "AnnData",
        "SingleCellExperiment",
        "SingleCellexperiment",
        "sce2anndata",
        "anndata2sce",
        "single-cell conversion",
        "H5AD",
        "RDS",
    ]
    RETURN_TYPES = ("H5AD", "FILE")
    RETURN_NAMES = ("output_anndata", "output_sce")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = ANNDATA2RI_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ANNDATA2RI_CITATION_URL]
    CITATION_TEXT = ANNDATA2RI_CITATION_TEXT
    VERSION = "1.3.2+galaxy1"
    SHELL = True

    DIRECTIONS = ["sce2anndata", "anndata2sce"]

    @classmethod
    def _direction(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("direction", "sce2anndata") or "sce2anndata")

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "outfile.rds" if cls._direction(inputs) == "anndata2sce" else "outfile.h5ad"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "anndata2ri.py")),
            cls._direction(inputs),
            str(inputs.get("input_object", "")),
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_object", "")).strip():
            return "input_object is required"
        direction = cls._direction(inputs)
        if direction not in cls.DIRECTIONS:
            return f"direction must be one of: {', '.join(cls.DIRECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_object": (
                    "FILE",
                    {"description": "AnnData H5AD or SingleCellExperiment RDS object to convert"},
                ),
            },
            "optional": {
                "direction": (
                    "STRING",
                    {
                        "default": "sce2anndata",
                        "options": cls.DIRECTIONS,
                        "description": "Conversion direction: SingleCellExperiment to AnnData or AnnData to SingleCellExperiment",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "anndata2ri.py",
                        "advanced": True,
                        "description": "Path to the Galaxy anndata2ri helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AnnotateMyIDsNode(CommandNode):
    """Annotate gene identifiers with Bioconductor organism annotation databases."""

    NODE_ID = "annotatemyids"
    DISPLAY_NAME = "annotateMyIDs"
    REQUIRED_CONDA_PACKAGES = [
        "bioconductor-org.hs.eg.db",
        "bioconductor-org.mm.eg.db",
        "bioconductor-org.dm.eg.db",
        "bioconductor-org.dr.eg.db",
        "bioconductor-org.rn.eg.db",
        "bioconductor-org.at.tair.db",
        "bioconductor-org.gg.eg.db",
        "bioconductor-org.bt.eg.db",
    ]
    CATEGORY = "annotation"
    DESCRIPTION = "Annotate a generic set of gene identifiers using Bioconductor organism annotation databases."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "annotateMyIDs",
        "annotatemyids",
        "AnnotationDbi",
        "Bioconductor",
        "org.Hs.eg.db",
        "gene identifier annotation",
        "Ensembl to Entrez",
        "gene symbols",
        "GO annotation",
        "KEGG annotation",
    ]
    RETURN_TYPES = ("TSV", "TXT")
    RETURN_NAMES = ("out_tab", "out_rscript")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://github.com/markdunning/galaxy-annotateMyIDs"
    CITATION_DOIS = ["10.18129/B9.bioc.AnnotationDbi"]
    CITATION_URLS = [
        "https://doi.org/10.18129/B9.bioc.AnnotationDbi",
        "https://github.com/markdunning/galaxy-annotateMyIDs",
    ]
    CITATION_TEXT = (
        "AnnotationDbi provides the Bioconductor interface used to query organism annotation packages; "
        "annotateMyIDs is a Galaxy wrapper by Mark Dunning for generic identifier annotation."
    )
    VERSION = "3.18.0+galaxy0"
    SHELL = True

    ORGANISMS = ["Hs", "Mm", "Rn", "Dm", "Dr", "At", "Gg", "Bt"]
    ID_TYPES = [
        "ENSEMBL",
        "ENSEMBLPROT",
        "ENSEMBLTRANS",
        "ENTREZID",
        "FLYBASE",
        "GO",
        "PATH",
        "MGI",
        "REFSEQ",
        "SYMBOL",
        "ZFIN",
    ]
    OUTPUT_COLUMNS = [
        "ALIAS",
        "ENSEMBL",
        "ENTREZID",
        "EVIDENCE",
        "SYMBOL",
        "GENENAME",
        "REFSEQ",
        "GO",
        "ONTOLOGY",
        "PATH",
    ]
    DEFAULT_OUTPUT_COLUMNS = ["ENSEMBL", "ENTREZID", "SYMBOL", "GENENAME"]

    @classmethod
    def _organism(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("organism", "Hs") or "Hs")

    @classmethod
    def _id_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("id_type", "ENSEMBL") or "ENSEMBL")

    @classmethod
    def _bool_r(cls, inputs: dict[str, Any], key: str, default: bool = False) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no", ""} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _output_cols(cls, inputs: dict[str, Any]) -> list[str]:
        values = _as_list(inputs.get("output_cols"))
        return values or list(cls.DEFAULT_OUTPUT_COLUMNS)

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/annotatemyids.R"

    @classmethod
    def _out_tab_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_tab.tsv"

    @classmethod
    def _out_rscript_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_rscript.txt"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        id_type = cls._id_type(inputs)
        organism = cls._organism(inputs)
        output_cols = ",".join(cls._output_cols(inputs))
        return "\n".join(
            [
                'options( show.error.messages=F, error = function () { cat( geterrmessage(), file=stderr() ); q( "no", 1, F ) } )',
                "",
                'loc <- Sys.setlocale("LC_MESSAGES", "en_US.UTF-8")',
                "",
                f'id_type <- "{id_type}"',
                f'organism <- "{organism}"',
                f'output_cols <- "{output_cols}"',
                f"file_has_header <- {cls._bool_r(inputs, 'file_has_header')}",
                f"remove_dups <- {cls._bool_r(inputs, 'remove_dups')}",
                "",
                f"input <- read.table({str(inputs.get('id_file', ''))!r}, header=file_has_header, sep=\"\\t\", quote=\"\")",
                "ids <- as.character(input[, 1])",
                "",
                'if(organism == "Hs"){',
                "    suppressPackageStartupMessages(library(org.Hs.eg.db))",
                "    db <- org.Hs.eg.db",
                '} else if (organism == "Mm"){',
                "    suppressPackageStartupMessages(library(org.Mm.eg.db))",
                "    db <- org.Mm.eg.db",
                '} else if (organism == "Dm"){',
                "    suppressPackageStartupMessages(library(org.Dm.eg.db))",
                "    db <- org.Dm.eg.db",
                '} else if (organism == "Dr"){',
                "    suppressPackageStartupMessages(library(org.Dr.eg.db))",
                "    db <- org.Dr.eg.db",
                '} else if (organism == "Rn"){',
                "    suppressPackageStartupMessages(library(org.Rn.eg.db))",
                "    db <- org.Rn.eg.db",
                '} else if (organism == "At"){',
                "    suppressPackageStartupMessages(library(org.At.tair.db))",
                "    db <- org.At.tair.db",
                '} else if (organism == "Gg"){',
                "    suppressPackageStartupMessages(library(org.Gg.eg.db))",
                "    db <- org.Gg.eg.db",
                '} else if (organism == "Bt"){',
                "    suppressPackageStartupMessages(library(org.Bt.eg.db))",
                "    db <- org.Bt.eg.db",
                "} else {",
                '    cat(paste("Organism type not supported", organism))',
                "}",
                "",
                'cols <- unlist(strsplit(output_cols, ","))',
                "result <- select(db, keys=ids, keytype=id_type, columns=cols)",
                "",
                "if(remove_dups) {",
                f"    result <- result[!duplicated(result${id_type}),]",
                "}",
                "",
                f"write.table(result, file={cls._out_tab_path(inputs)!r}, sep=\"\\t\", row.names=FALSE, quote=FALSE)",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = cls._script_path(inputs)
        run_script = f"Rscript {shlex.quote(script_path)}"
        if cls._bool_r(inputs, "rscriptOpt") == "TRUE":
            run_script = f"cp {shlex.quote(script_path)} {shlex.quote(cls._out_rscript_path(inputs))} && {run_script}"
        commands = [
            f"mkdir -p {shlex.quote(out)}",
            f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT\n{run_script}",
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out_tab.tsv"]
        if cls._bool_r(inputs, "rscriptOpt") == "TRUE":
            outputs.append(out / "out_rscript.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("id_file", "")).strip():
            return "id_file is required"
        organism = cls._organism(inputs)
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        id_type = cls._id_type(inputs)
        if id_type not in cls.ID_TYPES:
            return f"id_type must be one of: {', '.join(cls.ID_TYPES)}"
        if "output_cols" in inputs and not _as_list(inputs.get("output_cols")):
            return "output_cols is required"
        output_cols = cls._output_cols(inputs)
        if any(col not in cls.OUTPUT_COLUMNS for col in output_cols):
            return f"output_cols entries must be one of: {', '.join(cls.OUTPUT_COLUMNS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "id_file": ("TSV", {"description": "Tabular file whose first column contains identifiers to annotate"}),
            },
            "optional": {
                "file_has_header": ("BOOLEAN", {"default": False}),
                "organism": ("STRING", {"default": "Hs", "options": cls.ORGANISMS}),
                "id_type": ("STRING", {"default": "ENSEMBL", "options": cls.ID_TYPES}),
                "output_cols": (
                    "STRING",
                    {
                        "default": list(cls.DEFAULT_OUTPUT_COLUMNS),
                        "options": cls.OUTPUT_COLUMNS,
                        "multiple": True,
                        "display": "checkboxes",
                    },
                ),
                "remove_dups": ("BOOLEAN", {"default": False}),
                "rscriptOpt": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ArgNormNode(CommandNode):
    """Normalize ARG annotation tables to Antibiotic Resistance Ontology terms."""

    NODE_ID = "argnorm"
    DISPLAY_NAME = "argNorm"
    REQUIRED_CONDA_PACKAGES = ["argnorm"]
    CATEGORY = "annotation"
    DESCRIPTION = "Normalize antibiotic resistance gene annotations by mapping them to the Antibiotic Resistance Ontology."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "argnorm",
        "argNorm",
        "antibiotic resistance genes",
        "ARG normalization",
        "Antibiotic Resistance Ontology",
        "ARO",
        "CARD",
        "hAMRonization",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["argnorm"]
    DOCUMENTATION_URL = "https://github.com/BigDataBiology/argNorm"
    CITATION_DOIS = [ARGNORM_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ARGNORM_CITATION_DOI}"]
    CITATION_TEXT = ARGNORM_CITATION_TEXT
    VERSION = "1.0.0+galaxy0"
    SHELL = True

    TOOLS = ["deeparg", "argsoap", "abricate", "resfinder", "amrfinderplus", "groot", "hamronization"]
    ABRICATE_DBS = ["sarg", "ncbi", "resfinder", "resfinderfg", "deeparg", "megares", "argannot"]
    GROOT_DBS = ["groot-resfinder", "groot-argannot", "groot-card", "groot-db", "groot-core-db"]

    @classmethod
    def _tool(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("tool", "deeparg") or "deeparg")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/argnorm.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        tool = cls._tool(inputs)
        cmd = ["argnorm", tool]
        if tool == "abricate":
            cmd.extend(["--db", str(inputs.get("abricate_db", "sarg") or "sarg")])
        elif tool == "groot":
            cmd.extend(["--db", str(inputs.get("groot_db", "groot-resfinder") or "groot-resfinder")])
        cmd.extend(["-i", str(inputs.get("input", "")), "-o", cls._output_path(inputs)])
        if tool == "hamronization" and inputs.get("hamronized"):
            cmd.append("--hamronization_skip_unsupported_tool")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "argnorm.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        tool = cls._tool(inputs)
        if tool not in cls.TOOLS:
            return f"tool must be one of: {', '.join(cls.TOOLS)}"
        abricate_db = str(inputs.get("abricate_db", "sarg") or "sarg")
        if tool == "abricate" and abricate_db not in cls.ABRICATE_DBS:
            return f"abricate_db must be one of: {', '.join(cls.ABRICATE_DBS)}"
        groot_db = str(inputs.get("groot_db", "groot-resfinder") or "groot-resfinder")
        if tool == "groot" and groot_db not in cls.GROOT_DBS:
            return f"groot_db must be one of: {', '.join(cls.GROOT_DBS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "ARG annotation table from a supported tool"}),
            },
            "optional": {
                "tool": (
                    "STRING",
                    {
                        "default": "deeparg",
                        "options": cls.TOOLS,
                        "description": "Tool that produced the ARG annotation input",
                    },
                ),
                "abricate_db": (
                    "STRING",
                    {
                        "default": "sarg",
                        "options": cls.ABRICATE_DBS,
                        "description": "ABRicate database used for the input annotations",
                    },
                ),
                "groot_db": (
                    "STRING",
                    {
                        "default": "groot-resfinder",
                        "options": cls.GROOT_DBS,
                        "description": "Groot database used for the input annotations",
                    },
                ),
                "hamronized": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Skip unsupported tools in combined hAMRonization results",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AutoBIGSCliNode(CommandNode):
    """Perform MLST typing or list schemes from BIGSdb sequence definition databases."""

    NODE_ID = "autobigs-cli"
    DISPLAY_NAME = "autoBIGS.cli"
    REQUIRED_CONDA_PACKAGES = ["autobigs-cli"]
    CATEGORY = "typing"
    DESCRIPTION = "Automated MLST typing with BIGSdb sequence definition databases."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "autobigs",
        "autobigs-cli",
        "autoBIGS",
        "autoBIGS.cli",
        "MLST",
        "BIGSdb",
        "PubMLST",
        "Institut Pasteur",
        "sequence typing",
        "scheme",
    ]
    RETURN_TYPES = ("CSV", "CSV")
    RETURN_NAMES = ("mlst_profiles_output", "info_schemes_out")
    REQUIRED_EXECUTABLES = ["autoBIGS"]
    DOCUMENTATION_URL = AUTOBIGS_CLI_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AUTOBIGS_CLI_CITATION_URL]
    CITATION_TEXT = AUTOBIGS_CLI_CITATION_TEXT
    VERSION = "0.6.2+galaxy0"
    SHELL = True

    OPERATIONS = ["st", "info"]
    DATABASE_ORIGINS = ["pubmlst", "institutpasteur"]

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("operation", "st") or "st")

    @classmethod
    def _database_origin(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("database_origin", "pubmlst") or "pubmlst")

    @classmethod
    def _mlst_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/mlst_profiles_output.csv"

    @classmethod
    def _info_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/info_schemes_out.csv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        bigsdb = str(inputs.get("bigsdb", ""))
        if cls._operation(inputs) == "info":
            return _shell_join(
                [
                    "autoBIGS",
                    "info",
                    "--retrieve-bigsdb-schemes",
                    bigsdb,
                    "--csv",
                    cls._info_output_path(inputs),
                ]
            )

        cmd = [
            "autoBIGS",
            "st",
            "--scheme-name",
            str(inputs.get("scheme", "MLST") or "MLST"),
        ]
        cmd.extend(_as_list(inputs.get("fasta")))
        cmd.extend([bigsdb, cls._mlst_output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "mlst_profiles_output.csv", out / "info_schemes_out.csv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("bigsdb", "")).strip():
            return "bigsdb is required"
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        database_origin = cls._database_origin(inputs)
        if database_origin not in cls.DATABASE_ORIGINS:
            return f"database_origin must be one of: {', '.join(cls.DATABASE_ORIGINS)}"
        if operation == "st":
            if not _as_list(inputs.get("fasta")):
                return "fasta is required for st operation"
            if not str(inputs.get("scheme", "MLST")).strip():
                return "scheme is required for st operation"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bigsdb": (
                    "STRING",
                    {"description": "BIGSdb sequence definition database name, for example pubmlst_bordetella_seqdef"},
                ),
            },
            "optional": {
                "database_origin": (
                    "STRING",
                    {
                        "default": "pubmlst",
                        "options": cls.DATABASE_ORIGINS,
                        "description": "Remote BIGSdb source used to choose the sequence definition database",
                    },
                ),
                "operation": (
                    "STRING",
                    {"default": "st", "options": cls.OPERATIONS, "description": "Run sequence typing or list supported schemes"},
                ),
                "fasta": (
                    "FASTA",
                    {"default": [], "is_list": True, "description": "FASTA file or files to type in st mode"},
                ),
                "scheme": (
                    "STRING",
                    {"default": "MLST", "description": "BIGSdb SeqDef scheme name used for sequence typing"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MLSTNode(CommandNode):
    """Scan assemblies against PubMLST typing schemes with mlst."""

    NODE_ID = "mlst"
    DISPLAY_NAME = "MLST"
    REQUIRED_CONDA_PACKAGES = ["mlst"]
    CATEGORY = "typing"
    DESCRIPTION = "Scan genome assemblies against PubMLST schemes with Torsten Seemann's MLST."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MLST",
        "mlst",
        "PubMLST",
        "sequence typing",
        "scheme typing",
        "allele profile",
        "novel alleles",
    ]
    RETURN_TYPES = ("TSV", "FASTA")
    RETURN_NAMES = ("report", "novel_alleles")
    REQUIRED_EXECUTABLES = ["mlst"]
    DOCUMENTATION_URL = MLST_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [MLST_CITATION_URL]
    CITATION_TEXT = MLST_CITATION_TEXT
    VERSION = "2.22.0"
    SHELL = True

    ADVANCED_OPTIONS = ["simple", "advanced"]
    SET_SCHEME_OPTIONS = ["auto", "list", "manual"]

    @staticmethod
    def _label_for(path: str, label: str | None = None) -> str:
        return str(label or Path(path).name or "input.fasta")

    @classmethod
    def _staged_inputs(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        paths = _as_list(inputs.get("input_files"))
        labels = _as_list(inputs.get("input_labels"))
        return [
            (path, cls._label_for(path, labels[index] if index < len(labels) else None))
            for index, path in enumerate(paths)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_inputs = cls._staged_inputs(inputs)
        parts = [_shell_join(["ln", "-s", path, label]) for path, label in staged_inputs]
        cmd = ["mlst", "--nopath", "--threads", "${GALAXY_SLOTS:-1}"]
        if str(inputs.get("advanced", "simple")) == "advanced":
            if inputs.get("minid") not in (None, ""):
                cmd.append(f"--minid={inputs['minid']}")
            if inputs.get("mincov") not in (None, ""):
                cmd.append(f"--mincov={inputs['mincov']}")
            if inputs.get("novel"):
                cmd.extend(["--novel", f"{_out(inputs)}/novel_alleles.fasta"])
            set_scheme = str(inputs.get("set_scheme", "auto"))
            if set_scheme == "auto":
                if inputs.get("minscore") not in (None, ""):
                    cmd.append(f"--minscore={inputs['minscore']}")
                if str(inputs.get("exclude", "")).strip():
                    cmd.extend(["--exclude", str(inputs.get("exclude"))])
            elif set_scheme in {"list", "manual"}:
                if str(inputs.get("scheme", "")).strip():
                    cmd.append(f"--scheme={inputs['scheme']}")
                if inputs.get("legacy", True):
                    cmd.append("--legacy")
        cmd.extend(label for _, label in staged_inputs)
        cmd.extend([">", f"{_out(inputs)}/report.tsv"])
        parts.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "report.tsv"]
        if inputs.get("novel"):
            outputs.append(out / "novel_alleles.fasta")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("input_files")):
            return "at least one input_files value is required"
        advanced = str(inputs.get("advanced", "simple"))
        if advanced not in cls.ADVANCED_OPTIONS:
            return f"advanced must be one of: {', '.join(cls.ADVANCED_OPTIONS)}"
        if advanced == "advanced":
            for key in ("minid", "mincov", "minscore"):
                if inputs.get(key) in (None, ""):
                    continue
                value = int(inputs[key])
                if value < 0 or value > 100:
                    return f"{key} must be between 0 and 100"
            set_scheme = str(inputs.get("set_scheme", "auto"))
            if set_scheme not in cls.SET_SCHEME_OPTIONS:
                return f"set_scheme must be one of: {', '.join(cls.SET_SCHEME_OPTIONS)}"
            if set_scheme in {"list", "manual"} and not str(inputs.get("scheme", "")).strip():
                return "scheme is required when set_scheme is list or manual"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": (
                    "FASTA",
                    {
                        "multiple": True,
                        "description": "FASTA or GenBank genome assembly files to scan with mlst",
                    },
                ),
            },
            "optional": {
                "advanced": (
                    "STRING",
                    {"default": "simple", "options": cls.ADVANCED_OPTIONS, "description": "Use default or advanced mlst parameters"},
                ),
                "minid": ("INT", {"default": 95, "min": 0, "max": 100, "advanced": True}),
                "mincov": ("INT", {"default": 10, "min": 0, "max": 100, "advanced": True}),
                "novel": ("BOOLEAN", {"default": False, "description": "Write novel alleles to FASTA", "advanced": True}),
                "set_scheme": (
                    "STRING",
                    {"default": "auto", "options": cls.SET_SCHEME_OPTIONS, "description": "Auto-detect, select, or manually set scheme"},
                ),
                "minscore": ("INT", {"default": 50, "min": 0, "max": 100, "advanced": True}),
                "exclude": ("STRING", {"default": "", "description": "Comma-separated schemes to ignore in auto mode", "advanced": True}),
                "scheme": ("STRING", {"default": "", "description": "PubMLST scheme for list/manual modes"}),
                "legacy": ("BOOLEAN", {"default": True, "description": "Include allele header row when scheme is set"}),
                "input_labels": (
                    "STRING",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Optional Galaxy element identifiers used as readable output names",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MLSTListNode(CommandNode):
    """List MLST schemes and optional allele details."""

    NODE_ID = "mlst_list"
    DISPLAY_NAME = "MLST List"
    REQUIRED_CONDA_PACKAGES = ["mlst"]
    CATEGORY = "typing"
    DESCRIPTION = "List available PubMLST schemes and optional allele details from the MLST database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MLST List",
        "mlst --list",
        "mlst --longlist",
        "PubMLST schemes",
        "allele list",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["mlst"]
    DOCUMENTATION_URL = MLST_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [MLST_CITATION_URL]
    CITATION_TEXT = MLST_CITATION_TEXT
    VERSION = "2.22.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([
            "mlst",
            "--longlist" if inputs.get("list_type") else "--list",
            ">",
            f"{_out(inputs)}/report.txt",
        ])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "report.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "optional": {
                "list_type": ("BOOLEAN", {"default": False, "description": "Include allele columns with mlst --longlist"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class SeqSero2Node(CommandNode):
    """Predict Salmonella serotypes with SeqSero2."""

    NODE_ID = "seqsero2"
    DISPLAY_NAME = "SeqSero2"
    REQUIRED_CONDA_PACKAGES = ["seqsero2"]
    CATEGORY = "typing"
    DESCRIPTION = "Predict Salmonella serotypes from raw sequencing reads or genome assemblies."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "SeqSero2",
        "seqsero2",
        "Salmonella serotype",
        "Salmonella typing",
        "serotype prediction",
        "allele micro-assembly",
        "k-mer serotyping",
    ]
    RETURN_TYPES = ("TSV", "TXT")
    RETURN_NAMES = ("results", "log")
    REQUIRED_EXECUTABLES = ["SeqSero2_package.py"]
    DOCUMENTATION_URL = "https://github.com/denglab/SeqSero2"
    CITATION_DOIS = ["10.1128/AEM.01746-19"]
    CITATION_URLS = [f"{DOI_URL}10.1128/AEM.01746-19"]
    CITATION_TEXT = "SeqSero2: rapid and improved Salmonella serotype determination using whole-genome sequencing data."
    VERSION = "1.3.2+galaxy0"
    SHELL = True

    INPUT_TYPES_OPTIONS = ("paired", "collection", "assembly", "single", "nanopore")
    WORKFLOW_OPTIONS = ("a", "k")
    TYPE_VALUES = {
        "paired": "2",
        "collection": "2",
        "single": "3",
        "assembly": "4",
        "nanopore": "5",
    }

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "") or "")

    @classmethod
    def _workflow(cls, inputs: dict[str, Any]) -> str:
        input_type = cls._input_type(inputs)
        if input_type in {"assembly", "nanopore"}:
            return "k"
        return str(inputs.get("workflow", "a") or "a")

    @staticmethod
    def _extension(path: str, input_type: str) -> str:
        suffixes = "".join(Path(path).suffixes).lower()
        gz = suffixes.endswith(".gz")
        base = ".fasta" if input_type in {"assembly", "nanopore"} else ".fastq"
        return f"{base}.gz" if gz else base

    @classmethod
    def _stage_name(cls, path: str, input_type: str, label: str = "", suffix: str = "") -> str:
        stem = _safe_identifier(label or Path(path).stem or "input")
        if suffix:
            stem = f"{stem}_{suffix}"
        return f"{stem}{cls._extension(path, input_type)}"

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str, str]:
        collection = inputs.get("input_collection")
        if isinstance(collection, dict):
            forward = str(collection.get("forward", collection.get("read1", collection.get("reads_1", ""))))
            reverse = str(collection.get("reverse", collection.get("read2", collection.get("reads_2", ""))))
            label = str(collection.get("name", collection.get("element_identifier", forward or "collection")))
            return forward, reverse, label
        reads = _as_list(collection)
        return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "", reads[0] if reads else "collection")

    @classmethod
    def _staged_inputs(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        input_type = cls._input_type(inputs)
        if input_type == "collection":
            read1, read2, label = cls._collection_reads(inputs)
            return [
                (read1, cls._stage_name(read1, input_type, label, "forward")),
                (read2, cls._stage_name(read2, input_type, label, "reverse")),
            ]
        read1 = str(inputs.get("read1", ""))
        label1 = str(inputs.get("read1_label", "") or Path(read1).stem or "input")
        if input_type == "paired":
            read2 = str(inputs.get("read2", ""))
            label2 = str(inputs.get("read2_label", "") or label1)
            return [
                (read1, cls._stage_name(read1, input_type, label1, "forward")),
                (read2, cls._stage_name(read2, input_type, label2, "reverse")),
            ]
        return [(read1, cls._stage_name(read1, input_type, label1))]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out])]
        staged = cls._staged_inputs(inputs)
        commands.extend(_shell_join(["ln", "-s", source, staged_name]) for source, staged_name in staged)
        cmd = [
            "SeqSero2_package.py",
            "-m",
            cls._workflow(inputs),
            "-t",
            cls.TYPE_VALUES[cls._input_type(inputs)],
            "-i",
            staged[0][1],
        ]
        if cls._input_type(inputs) in {"paired", "collection"}:
            cmd.append(staged[1][1])
        cmd.extend(["-p", "${GALAXY_SLOTS:-4}", "-d", f"{out}/output"])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-4}'", "${GALAXY_SLOTS:-4}"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "SeqSero_result.tsv"]
        if inputs.get("logfile"):
            outputs.append(out / "SeqSero_log.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        if input_type == "collection":
            read1, read2, _ = cls._collection_reads(inputs)
            if not read1 or not read2:
                return "input_collection with forward and reverse reads is required for collection input"
        else:
            if not str(inputs.get("read1", "")).strip():
                return f"read1 is required for {input_type} input"
            if input_type == "paired" and not str(inputs.get("read2", "")).strip():
                return "read2 is required for paired input"
        workflow = cls._workflow(inputs)
        if workflow not in cls.WORKFLOW_OPTIONS:
            return f"workflow must be one of: {', '.join(cls.WORKFLOW_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "paired",
                        "options": list(cls.INPUT_TYPES_OPTIONS),
                        "description": "Galaxy SeqSero2 input layout",
                    },
                ),
                "read1": ("FILE", {"description": "Forward, single/interleaved, assembly, or nanopore input"}),
                "read2": ("FASTQ", {"description": "Reverse reads for paired input"}),
            },
            "optional": {
                "input_collection": (
                    "JSON",
                    {"default": {}, "description": "Paired collection with forward and reverse reads"},
                ),
                "workflow": (
                    "STRING",
                    {
                        "default": "a",
                        "options": list(cls.WORKFLOW_OPTIONS),
                        "description": "SeqSero2 workflow for raw reads: allele micro-assembly or k-mer",
                    },
                ),
                "logfile": (
                    "BOOLEAN",
                    {"default": False, "description": "Return SeqSero2 log output"},
                ),
                "read1_label": (
                    "STRING",
                    {"default": "", "description": "Optional Galaxy element identifier for read1", "advanced": True},
                ),
                "read2_label": (
                    "STRING",
                    {"default": "", "description": "Optional Galaxy element identifier for read2", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class B2BToolsSingleSequenceNode(CommandNode):
    """Run Bio2Byte single-sequence biophysical predictors on protein FASTA."""

    NODE_ID = "b2btools_single_sequence"
    DISPLAY_NAME = "b2bTools: Biophysical predictors for single sequences"
    REQUIRED_CONDA_PACKAGES = ["b2btools"]
    CATEGORY = "proteomics"
    DESCRIPTION = "Predict protein biophysical properties from amino-acid FASTA sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "b2btools",
        "Bio2Byte",
        "DynaMine",
        "DisoMine",
        "EFoldMine",
        "AgMata",
        "protein disorder",
        "backbone dynamics",
        "early folding",
        "beta aggregation",
        "biophysical predictors",
    ]
    RETURN_TYPES = ("JSON", "DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("predictions_output", "split_output", "split_output_plots")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://bio2byte.be/"
    CITATION_DOIS = B2BTOOLS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in B2BTOOLS_CITATION_DOIS]
    CITATION_TEXT = B2BTOOLS_CITATION_TEXT
    VERSION = "3.0.5+galaxy0"
    SHELL = True

    PREDICTOR_FLAGS = {
        "dynamine": "--dynamine",
        "disomine": "--disomine",
        "efoldmine": "--efoldmine",
        "agmata": "--agmata",
    }

    @classmethod
    def _node_output_dir(cls, inputs: dict[str, Any]) -> str:
        return _out(inputs)

    @classmethod
    def _tabular_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{cls._node_output_dir(inputs)}/tabular"

    @classmethod
    def _plots_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{cls._node_output_dir(inputs)}/plots"

    @classmethod
    def _json_path(cls, inputs: dict[str, Any]) -> str:
        return f"{cls._node_output_dir(inputs)}/predictions.json"

    @classmethod
    def _enabled_predictors(cls, inputs: dict[str, Any]) -> list[str]:
        return [key for key in cls.PREDICTOR_FLAGS if inputs.get(key, True)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mkdir",
            "-p",
            cls._tabular_dir(inputs),
            cls._plots_dir(inputs),
            "&&",
            "python",
            str(inputs.get("script_path", "script.py") or "script.py"),
            "--file",
            str(inputs.get("input", "")),
            "--output",
            cls._tabular_dir(inputs),
            "--json",
            cls._json_path(inputs),
        ]
        for predictor in cls._enabled_predictors(inputs):
            cmd.append(cls.PREDICTOR_FLAGS[predictor])
        if inputs.get("plot") or inputs.get("plot_all"):
            cmd.extend(["--plot-output", cls._plots_dir(inputs)])
        if inputs.get("plot"):
            cmd.append("--plot")
        if inputs.get("plot_all"):
            cmd.append("--plot_all")
        if inputs.get("highlight"):
            cmd.append("--highlight")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        tabular = out / "tabular"
        plots = out / "plots"
        tabular.mkdir(parents=True, exist_ok=True)
        plots.mkdir(parents=True, exist_ok=True)
        return [out / "predictions.json", tabular, plots]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not cls._enabled_predictors(inputs):
            return "at least one predictor must be selected"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Protein sequences in FASTA format"}),
            },
            "optional": {
                "dynamine": ("BOOLEAN", {"default": True, "description": "Predict backbone dynamics and related properties"}),
                "disomine": ("BOOLEAN", {"default": True, "description": "Predict protein disorder"}),
                "efoldmine": ("BOOLEAN", {"default": True, "description": "Predict early folding regions"}),
                "agmata": ("BOOLEAN", {"default": True, "description": "Predict beta-aggregation-prone regions"}),
                "plot": ("BOOLEAN", {"default": False, "description": "Plot predicted values for each sequence"}),
                "plot_all": ("BOOLEAN", {"default": False, "description": "Plot all sequences together for each predicted value"}),
                "highlight": ("BOOLEAN", {"default": False, "description": "Highlight known biophysical regions on plots"}),
                "script_path": (
                    "FILE",
                    {"default": "script.py", "advanced": True, "description": "Path to the Galaxy b2bTools helper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BpGenbank2Gff3Node(CommandNode):
    """Convert GenBank flat files to GFF3 with BioPerl."""

    NODE_ID = "bp_genbank2gff3"
    DISPLAY_NAME = "Genbank to GFF3"
    REQUIRED_CONDA_PACKAGES = ["perl-bioperl"]
    CATEGORY = "annotation"
    DESCRIPTION = "Convert GenBank flat files to GFF3 with BioPerl."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bp_genbank2gff3",
        "Genbank to GFF3",
        "GenBank",
        "GFF3",
        "BioPerl",
        "Unflattener",
        "Sequence Ontology",
        "Bio::Tools::GFF",
    ]
    RETURN_TYPES = ("GFF3",)
    RETURN_NAMES = ("gff3",)
    REQUIRED_EXECUTABLES = ["bp_genbank2gff3.pl"]
    DOCUMENTATION_URL = "https://bioperl.org/"
    CITATION_DOIS = [BP_GENBANK2GFF3_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BP_GENBANK2GFF3_CITATION_DOI}"]
    CITATION_TEXT = BP_GENBANK2GFF3_CITATION_TEXT
    VERSION = "1.1"
    SHELL = True

    SOFILE_OPTIONS = ["__none__", "live", "url"]
    ERROR_THRESHOLDS = ["0", "1", "2", "3"]
    MODELS = ["--CDS", "--noCDS"]

    @classmethod
    def _sofile(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sofile", "__none__") or "__none__")

    @classmethod
    def _ethresh(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ethresh", "1") or "1")

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("model", "--CDS") or "--CDS")

    @classmethod
    def _typesource(cls, inputs: dict[str, Any]) -> str:
        value = inputs.get("typesource", "contig")
        if value is None:
            return "contig"
        return str(value)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gff3.gff3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["bp_genbank2gff3.pl"]
        if inputs.get("infer_subfeatures", True) is False:
            cmd.append("--noinfer")
        sofile = cls._sofile(inputs)
        if sofile == "url":
            cmd.extend(["--sofile", str(inputs.get("so_url", ""))])
        elif sofile == "live":
            cmd.extend(["--sofile", "live"])
        cmd.extend(
            [
                "--outdir",
                "-",
                "--ethresh",
                cls._ethresh(inputs),
                cls._model(inputs),
                "--typesource",
                cls._typesource(inputs),
                str(inputs.get("genbank", "")),
                ">",
                cls._output_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gff3.gff3"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("genbank", "")).strip():
            return "genbank is required"
        sofile = cls._sofile(inputs)
        if sofile not in cls.SOFILE_OPTIONS:
            return f"sofile must be one of: {', '.join(cls.SOFILE_OPTIONS)}"
        if sofile == "url" and not str(inputs.get("so_url", "")).strip():
            return "so_url is required when sofile is url"
        ethresh = cls._ethresh(inputs)
        if ethresh not in cls.ERROR_THRESHOLDS:
            return f"ethresh must be one of: {', '.join(cls.ERROR_THRESHOLDS)}"
        model = cls._model(inputs)
        if model not in cls.MODELS:
            return f"model must be one of: {', '.join(cls.MODELS)}"
        if not cls._typesource(inputs).strip():
            return "typesource is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genbank": ("FILE", {"description": "GenBank flat file to convert to GFF3"}),
            },
            "optional": {
                "infer_subfeatures": (
                    "BOOLEAN",
                    {"default": True, "description": "Infer exon and mRNA subfeatures"},
                ),
                "sofile": (
                    "STRING",
                    {
                        "default": "__none__",
                        "options": cls.SOFILE_OPTIONS,
                        "description": "Sequence Ontology source",
                    },
                ),
                "so_url": (
                    "STRING",
                    {"default": "", "description": "Sequence Ontology OBO URL when sofile is url"},
                ),
                "ethresh": (
                    "STRING",
                    {
                        "default": "1",
                        "options": cls.ERROR_THRESHOLDS,
                        "description": "Error threshold for the BioPerl unflattener",
                    },
                ),
                "model": (
                    "STRING",
                    {"default": "--CDS", "options": cls.MODELS, "description": "GFF3 gene model"},
                ),
                "typesource": (
                    "STRING",
                    {"default": "contig", "description": "Sequence Ontology type for the landmark feature"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BasilNode(CommandNode):
    """Detect structural-variant breakpoints with BASIL."""

    NODE_ID = "basil"
    DISPLAY_NAME = "basil"
    REQUIRED_CONDA_PACKAGES = ["anise_basil"]
    CATEGORY = "variant"
    DESCRIPTION = "Detect structural-variant breakpoints, including large insertions, from BAM reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "basil",
        "BASIL",
        "anise_basil",
        "breakpoint detection",
        "structural variants",
        "large insertions",
        "insertion breakpoints",
        "one-end-anchor reads",
        "OEA",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["basil"]
    DOCUMENTATION_URL = f"{DOI_URL}{BASIL_CITATION_DOI}"
    CITATION_DOIS = [BASIL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BASIL_CITATION_DOI}"]
    CITATION_TEXT = BASIL_CITATION_TEXT
    VERSION = "1.2.0+galaxy2"
    SHELL = True

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_source_selector", inputs.get("reference_source", "history")) or "history")

    @classmethod
    def _support_threshold(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("min_oea_each_side", 2)
        if value is None or str(value) == "":
            return 2
        return int(value)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.vcf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "ln",
            "-f",
            "-s",
            str(inputs.get("ref", "")),
            "ref.fa",
            "&&",
            "ln",
            "-s",
            str(inputs.get("bam", "")),
            "in.bam",
            "&&",
            "basil",
            "--input-reference",
            "ref.fa",
            "--input-mapping",
            "in.bam",
            "--out-vcf",
            cls._output_path(inputs),
            "--oea-min-support-each-side",
            str(cls._support_threshold(inputs)),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.vcf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("ref", "")).strip():
            return "ref is required"
        if not str(inputs.get("bam", "")).strip():
            return "bam is required"
        reference_source = cls._reference_source(inputs)
        if reference_source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        try:
            min_oea_each_side = cls._support_threshold(inputs)
        except (TypeError, ValueError):
            return "min_oea_each_side must be an integer"
        if min_oea_each_side < 1:
            return "min_oea_each_side must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref": ("FASTA", {"description": "Reference genome FASTA from history or a built-in cached reference"}),
                "bam": ("BAM", {"description": "SAM/BAM alignments to scan for breakpoints"}),
            },
            "optional": {
                "reference_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a reference FASTA from history or a built-in cached reference",
                    },
                ),
                "min_oea_each_side": (
                    "INT",
                    {
                        "default": 2,
                        "min": 1,
                        "description": "Minimum OEA supporting reads on each side of an insertion breakpoint",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBGToBigWigNode(CommandNode):
    """Convert BAM, BED, or GFF coverage to a bigWig track."""

    NODE_ID = "bbgtobigwig"
    DISPLAY_NAME = "BAM BED GFF coverage bigWigs"
    REQUIRED_CONDA_PACKAGES = ["ucsc-bedgraphtobigwig", "bedtools", "coreutils", "python"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BAM, BED, or GFF coverage over a reference genome into a bigWig track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bbgtobigwig",
        "BAM BED GFF coverage bigWigs",
        "bigWig",
        "bedGraphToBigWig",
        "bedtools genomecov",
        "coverage tracks",
        "JBrowse2",
        "UCSC Genome Browser Utilities",
    ]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["bedtools", "bedGraphToBigWig", "python"]
    DOCUMENTATION_URL = f"{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}"
    CITATION_DOIS = [BBG_TO_BIGWIG_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}"]
    CITATION_TEXT = BBG_TO_BIGWIG_CITATION_TEXT
    VERSION = "0.1"
    SHELL = True

    GENOSRC_OPTIONS = ["indexed", "history"]
    INPUT_FORMAT_OPTIONS = ["auto", "bam", "bed", "gff", "gff3"]

    @classmethod
    def _genosrc(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("genosrc", "history") or "history")

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        selected = str(inputs.get("input_format", "auto") or "auto").lower()
        if selected != "auto":
            return selected
        ext = _bedtools_ext(inputs.get("input1"), default="")
        if ext == "unsorted.bam":
            return "bam"
        if ext in {"bam", "bed", "gff", "gff3"}:
            return ext
        return ""

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.bigwig"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "ln",
            "-s",
            str(inputs.get("chromfile", "")),
            "./CHROMFILE",
            "&&",
        ]
        input_format = cls._input_format(inputs)
        if input_format in {"gff", "gff3"}:
            cmd.extend(
                [
                    "python",
                    str(inputs.get("converter_script", "gff_to_bed_converter.py") or "gff_to_bed_converter.py"),
                    "<",
                    str(inputs.get("input1", "")),
                    ">",
                    "input2",
                    "&&",
                ]
            )
        else:
            cmd.extend(["ln", "-s", str(inputs.get("input1", "")), "input2", "&&"])
        cmd.extend(["bedtools", "genomecov", "-bg"])
        if input_format == "bam":
            cmd.extend(["-split", "-ibam", "input2"])
        else:
            cmd.extend(["-i", "input2", "-g", "./CHROMFILE"])
        cmd.extend(
            [
                "|",
                "LC_COLLATE=C",
                "sort",
                "-k1,1",
                "-k2,2n",
                ">",
                "temp.bg",
                "&&",
                "bedGraphToBigWig",
                "temp.bg",
                "./CHROMFILE",
                cls._output_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bigwig"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input1", "")).strip():
            return "input1 is required"
        if not str(inputs.get("chromfile", "")).strip():
            return "chromfile is required"
        genosrc = cls._genosrc(inputs)
        if genosrc not in cls.GENOSRC_OPTIONS:
            return f"genosrc must be one of: {', '.join(cls.GENOSRC_OPTIONS)}"
        selected = str(inputs.get("input_format", "auto") or "auto").lower()
        if selected not in cls.INPUT_FORMAT_OPTIONS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMAT_OPTIONS)}"
        if not cls._input_format(inputs):
            return "input_format could not be auto-detected from input1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("FILE", {"description": "BAM, BED, GFF, or GFF3 file to convert to bigWig coverage"}),
                "chromfile": (
                    "FILE",
                    {"description": "Chromosome lengths file or built-in reference genome length table"},
                ),
            },
            "optional": {
                "genosrc": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.GENOSRC_OPTIONS,
                        "description": "Whether chromosome lengths come from a built-in/indexed genome or history file",
                    },
                ),
                "input_format": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": cls.INPUT_FORMAT_OPTIONS,
                        "description": "Input format; auto detects from input1 extension",
                    },
                ),
                "converter_script": (
                    "FILE",
                    {
                        "default": "gff_to_bed_converter.py",
                        "advanced": True,
                        "description": "Galaxy helper script that converts GFF/GFF3 to BED before coverage",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Baredsc1DNode(CommandNode):
    """Estimate a one-dimensional baredSC expression distribution."""

    NODE_ID = "baredsc_1d"
    DISPLAY_NAME = "baredSC 1d"
    REQUIRED_CONDA_PACKAGES = ["baredsc", "gzip"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Compute a one-dimensional baredSC expression distribution for a single gene."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_1d",
        "baredSC 1d",
        "single gene",
        "single-cell expression distribution",
        "Bayesian Approach",
        "probability density function",
        "MCMC",
    ]
    RETURN_TYPES = ("NPZ", "TXT", "DIRECTORY", "TSV", "IMAGE", "DIRECTORY", "TXT")
    RETURN_NAMES = ("output", "neff", "qc_plots", "pdf", "plot", "other_outputs", "logevidence")
    REQUIRED_EXECUTABLES = ["baredSC_1d", "mkdir", "mv", "gunzip"]
    DOCUMENTATION_URL = BAREDSC_DOCUMENTATION_URL
    CITATION_DOIS = [BAREDSC_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BAREDSC_CITATION_DOI}"]
    CITATION_TEXT = BAREDSC_CITATION_TEXT
    VERSION = "1.1.3+galaxy0"
    SHELL = True

    FILETYPES = ["tabular", "anndata"]
    FILTER_COUNTS = ["0", "1", "2", "3"]
    SCALE_OPTIONS = ["Seurat", "log"]
    RESTART_OPTIONS = ["yes", "no"]
    IMAGE_FORMATS = ["png", "svg", "pdf"]

    @classmethod
    def _image_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("image_file_format", "png") or "png")

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output.npz",
            out / "output" / "baredSC_neff.txt",
            out / "QC",
            out / "output" / "baredSC_pdf.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
            out / "logevidence.txt",
        ]

    @classmethod
    def _append_required_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "anndata":
            cmd.extend(["--inputAnnData", str(inputs.get("inputAnnData", "") or "")])
        else:
            cmd.extend(["--input", str(inputs.get("input", "") or "")])
        cmd.extend(["--geneColName", str(inputs.get("geneColName", "") or "")])

    @classmethod
    def _append_filters(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        count = int(str(inputs.get("filter_nb", "0") or "0"))
        for idx in range(1, count + 1):
            cmd.extend(
                [
                    f"--metadata{idx}ColName",
                    str(inputs.get(f"metadata{idx}ColName", "") or ""),
                    f"--metadata{idx}Values",
                    str(inputs.get(f"metadata{idx}Values", "") or ""),
                ]
            )

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--xscale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(
            [
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScale",
                str(inputs.get("minScalex", 0.1)),
                "--seed",
                str(inputs.get("seed", 1)),
                "--nnorm",
                str(inputs.get("nnorm", 2)),
                "--nsampMCMC",
                str(inputs.get("nsampMCMC", 100000)),
            ]
        )
        if str(inputs.get("automatic_restart", "yes") or "yes") == "yes":
            cmd.extend(["--minNeff", str(inputs.get("minNeff", 200))])

    @classmethod
    def _append_plots(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        title = str(inputs.get("title", "") or "")
        if title:
            cmd.extend(["--title", title])
        remove_first = int(inputs.get("removeFirstSamples", -1))
        if remove_first != -1:
            cmd.extend(["--removeFirstSamples", str(remove_first)])
        cmd.extend(["--nsampInPlot", str(inputs.get("nsampInPlot", 100000))])
        pretty_bins = int(inputs.get("prettyBins", -1))
        if pretty_bins != -1:
            cmd.extend(["--prettyBins", str(pretty_bins)])

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--osampx",
                str(inputs.get("osampx", 10)),
                "--osampxpdf",
                str(inputs.get("osampxpdf", 5)),
                "--coviscale",
                str(inputs.get("coviscale", 1)),
                "--nis",
                str(inputs.get("nis", 1000)),
            ]
        )
        if str(inputs.get("burn_custom", "no") or "no") == "yes":
            nsamp_burn = int(inputs.get("nsampBurnMCMC", -1))
            if nsamp_burn != -1:
                cmd.extend(["--nsampBurnMCMC", str(nsamp_burn)])
            cmd.extend(["--T0BurnMCMC", str(inputs.get("T0BurnMCMC", 100))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        image_format = cls._image_format(inputs)
        cmd = ["baredSC_1d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--output", "output", "--figure", f"baredSC.{image_format}", "--logevidence", "logevidence.txt"])
        commands = [
            _shell_join(cmd),
            "mkdir QC output",
            "mv baredSC_convergence.* QC",
            f"mv baredSC_p.{shlex.quote(image_format)} QC",
            "mv baredSC_corner.* QC",
            "mv baredSC_neff.txt output",
            "mv baredSC_pdf.txt output",
            f"mv baredSC.{shlex.quote(image_format)} baredSC",
            "gunzip baredSC_means.txt.gz",
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "output").mkdir(parents=True, exist_ok=True)
        (out / "QC").mkdir(parents=True, exist_ok=True)
        (out / "other_outputs").mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("geneColName", "")).strip():
            return "geneColName is required"
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "tabular" and not str(inputs.get("input", "")).strip():
            return "input is required when filetype is tabular"
        if filetype not in cls.FILETYPES:
            return f"filetype must be one of: {', '.join(cls.FILETYPES)}"
        if filetype == "anndata" and not str(inputs.get("inputAnnData", "")).strip():
            return "inputAnnData is required when filetype is anndata"
        filter_nb = str(inputs.get("filter_nb", "0") or "0")
        if filter_nb not in cls.FILTER_COUNTS:
            return f"filter_nb must be one of: {', '.join(cls.FILTER_COUNTS)}"
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        if scale not in cls.SCALE_OPTIONS:
            return f"xscale must be one of: {', '.join(cls.SCALE_OPTIONS)}"
        restart = str(inputs.get("automatic_restart", "yes") or "yes")
        if restart not in cls.RESTART_OPTIONS:
            return f"automatic_restart must be one of: {', '.join(cls.RESTART_OPTIONS)}"
        image_format = cls._image_format(inputs)
        if image_format not in cls.IMAGE_FORMATS:
            return f"image_file_format must be one of: {', '.join(cls.IMAGE_FORMATS)}"
        numeric_mins = {
            "nx": (1, int, 100),
            "nnorm": (1, int, 2),
            "nsampMCMC": (1, int, 100000),
            "nsampInPlot": (1, int, 100000),
            "osampx": (1, int, 10),
            "osampxpdf": (1, int, 5),
        }
        for name, (minimum, caster, default) in numeric_mins.items():
            try:
                value = caster(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "geneColName": ("STRING", {"description": "Name of the column with gene counts"}),
            },
            "optional": {
                "filetype": ("STRING", {"default": "tabular", "options": cls.FILETYPES}),
                "input": ("TSV", {"description": "Input count table with one row per cell"}),
                "inputAnnData": ("H5AD", {"description": "AnnData file containing raw counts"}),
                "filter_nb": ("STRING", {"default": "0", "options": cls.FILTER_COUNTS}),
                "metadata1ColName": ("STRING", {"default": ""}),
                "metadata1Values": ("STRING", {"default": ""}),
                "metadata2ColName": ("STRING", {"default": ""}),
                "metadata2Values": ("STRING", {"default": ""}),
                "metadata3ColName": ("STRING", {"default": ""}),
                "metadata3Values": ("STRING", {"default": ""}),
                "xmin": ("FLOAT", {"default": 0}),
                "xmax": ("FLOAT", {"default": 2.5}),
                "xscale": ("STRING", {"default": "Seurat", "options": cls.SCALE_OPTIONS}),
                "targetSum": ("FLOAT", {"default": 10000}),
                "nx": ("INT", {"default": 100, "min": 1}),
                "minScalex": ("FLOAT", {"default": 0.1}),
                "seed": ("INT", {"default": 1}),
                "nnorm": ("INT", {"default": 2, "min": 1}),
                "nsampMCMC": ("INT", {"default": 100000, "min": 1}),
                "automatic_restart": ("STRING", {"default": "yes", "options": cls.RESTART_OPTIONS}),
                "minNeff": ("FLOAT", {"default": 200}),
                "image_file_format": ("STRING", {"default": "png", "options": cls.IMAGE_FORMATS}),
                "title": ("STRING", {"default": ""}),
                "removeFirstSamples": ("INT", {"default": -1}),
                "nsampInPlot": ("INT", {"default": 100000, "min": 1}),
                "prettyBins": ("INT", {"default": -1, "min": -1}),
                "osampx": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "osampxpdf": ("INT", {"default": 5, "min": 1, "advanced": True}),
                "coviscale": ("FLOAT", {"default": 1, "advanced": True}),
                "nis": ("INT", {"default": 1000, "advanced": True}),
                "burn_custom": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "nsampBurnMCMC": ("INT", {"default": -1, "advanced": True}),
                "T0BurnMCMC": ("FLOAT", {"default": 100, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Baredsc2DNode(Baredsc1DNode):
    """Estimate a two-dimensional baredSC expression distribution."""

    NODE_ID = "baredsc_2d"
    DISPLAY_NAME = "baredSC 2d"
    DESCRIPTION = "Compute a two-dimensional baredSC expression distribution for a pair of genes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_2d",
        "baredSC 2d",
        "pair of genes",
        "two-gene expression distribution",
        "single-cell expression distribution",
        "Bayesian Approach",
        "correlation",
        "splity",
        "MCMC",
    ]
    RETURN_TYPES = ("NPZ", "TXT", "DIRECTORY", "TSV", "TSV", "IMAGE", "DIRECTORY", "TXT")
    RETURN_NAMES = ("output", "neff", "qc_plots", "pdf2d", "pdf2d_flat", "plot", "other_outputs", "logevidence")
    REQUIRED_EXECUTABLES = ["baredSC_2d", "mkdir", "mv"]

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output.npz",
            out / "output" / "baredSC_neff.txt",
            out / "QC",
            out / "output" / "baredSC_pdf2d.txt",
            out / "output" / "baredSC_pdf2d_flat.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
            out / "logevidence.txt",
        ]

    @classmethod
    def _append_required_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "anndata":
            cmd.extend(["--inputAnnData", str(inputs.get("inputAnnData", "") or "")])
        else:
            cmd.extend(["--input", str(inputs.get("input", "") or "")])
        cmd.extend(
            [
                "--geneXColName",
                str(inputs.get("geneXColName", "") or ""),
                "--geneYColName",
                str(inputs.get("geneYColName", "") or ""),
            ]
        )

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScalex",
                str(inputs.get("minScalex", 0.1)),
                "--ymin",
                str(inputs.get("ymin", 0)),
                "--ymax",
                str(inputs.get("ymax", 2.5)),
                "--ny",
                str(inputs.get("ny", 100)),
                "--minScaley",
                str(inputs.get("minScaley", 0.1)),
                "--scale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(
            [
                "--seed",
                str(inputs.get("seed", 1)),
                "--nnorm",
                str(inputs.get("nnorm", 2)),
                "--nsampMCMC",
                str(inputs.get("nsampMCMC", 100000)),
            ]
        )
        if str(inputs.get("automatic_restart", "yes") or "yes") == "yes":
            cmd.extend(["--minNeff", str(inputs.get("minNeff", 200))])

    @classmethod
    def _append_plots(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        super()._append_plots(cmd, inputs)
        pretty_bins_x = int(inputs.get("prettyBinsx", -1))
        if pretty_bins_x != -1:
            cmd.extend(["--prettyBinsx", str(pretty_bins_x)])
        pretty_bins_y = int(inputs.get("prettyBinsy", -1))
        if pretty_bins_y != -1:
            cmd.extend(["--prettyBinsy", str(pretty_bins_y)])
        splity = str(inputs.get("splity", "") or "")
        if splity:
            cmd.extend(["--splity", splity])
        if inputs.get("log1pColorScale", False):
            cmd.append("--log1pColorScale")

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--osampx",
                str(inputs.get("osampx", 10)),
                "--osampxpdf",
                str(inputs.get("osampxpdf", 4)),
                "--osampy",
                str(inputs.get("osampy", 10)),
                "--osampypdf",
                str(inputs.get("osampypdf", 4)),
                "--coviscale",
                str(inputs.get("coviscale", 1)),
                "--nis",
                str(inputs.get("nis", 1000)),
                "--scalePrior",
                str(inputs.get("scalePrior", 0.3)),
            ]
        )
        if str(inputs.get("burn_custom", "no") or "no") == "yes":
            nsamp_burn = int(inputs.get("nsampBurnMCMC", -1))
            if nsamp_burn != -1:
                cmd.extend(["--nsampBurnMCMC", str(nsamp_burn)])
            cmd.extend(["--T0BurnMCMC", str(inputs.get("T0BurnMCMC", 100))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        image_format = cls._image_format(inputs)
        cmd = ["baredSC_2d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--output", "output", "--figure", f"baredSC.{image_format}", "--logevidence", "logevidence.txt"])
        commands = [
            _shell_join(cmd),
            "mkdir QC",
            "mv baredSC_convergence.* QC",
            f"mv baredSC_p.{shlex.quote(image_format)} QC",
            "mv baredSC_corner.* QC",
            "mkdir output",
            "mv baredSC_neff.txt output",
            "mv baredSC_pdf2d.txt output",
            "mv baredSC_pdf2d_flat.txt output",
            f"mv baredSC.{shlex.quote(image_format)} baredSC",
        ]
        splity = str(inputs.get("splity", "") or "")
        commands.extend(
            _shell_join(["mv", f"baredSC_split{value}.txt", f"baredSC_split{value}_pdf.txt"])
            for value in splity.split()
        )
        return " && ".join(commands)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("geneXColName", "")).strip():
            return "geneXColName is required"
        if not str(inputs.get("geneYColName", "")).strip():
            return "geneYColName is required"
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "tabular" and not str(inputs.get("input", "")).strip():
            return "input is required when filetype is tabular"
        if filetype not in cls.FILETYPES:
            return f"filetype must be one of: {', '.join(cls.FILETYPES)}"
        if filetype == "anndata" and not str(inputs.get("inputAnnData", "")).strip():
            return "inputAnnData is required when filetype is anndata"
        filter_nb = str(inputs.get("filter_nb", "0") or "0")
        if filter_nb not in cls.FILTER_COUNTS:
            return f"filter_nb must be one of: {', '.join(cls.FILTER_COUNTS)}"
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        if scale not in cls.SCALE_OPTIONS:
            return f"xscale must be one of: {', '.join(cls.SCALE_OPTIONS)}"
        restart = str(inputs.get("automatic_restart", "yes") or "yes")
        if restart not in cls.RESTART_OPTIONS:
            return f"automatic_restart must be one of: {', '.join(cls.RESTART_OPTIONS)}"
        image_format = cls._image_format(inputs)
        if image_format not in cls.IMAGE_FORMATS:
            return f"image_file_format must be one of: {', '.join(cls.IMAGE_FORMATS)}"
        splity = str(inputs.get("splity", "") or "")
        if splity:
            try:
                [float(value) for value in splity.split()]
            except ValueError:
                return "splity must be space-separated numeric thresholds"
        numeric_mins = {
            "nx": (1, int, 100),
            "ny": (1, int, 100),
            "nnorm": (1, int, 2),
            "nsampMCMC": (1, int, 100000),
            "nsampInPlot": (1, int, 100000),
            "osampx": (1, int, 10),
            "osampxpdf": (1, int, 4),
            "osampy": (1, int, 10),
            "osampypdf": (1, int, 4),
        }
        for name, (minimum, caster, default) in numeric_mins.items():
            try:
                value = caster(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "geneXColName": ("STRING", {"description": "Name of the x-axis gene count column"}),
                "geneYColName": ("STRING", {"description": "Name of the y-axis gene count column"}),
            },
            "optional": {
                "filetype": ("STRING", {"default": "tabular", "options": cls.FILETYPES}),
                "input": ("TSV", {"description": "Input count table with one row per cell"}),
                "inputAnnData": ("H5AD", {"description": "AnnData file containing raw counts"}),
                "filter_nb": ("STRING", {"default": "0", "options": cls.FILTER_COUNTS}),
                "metadata1ColName": ("STRING", {"default": ""}),
                "metadata1Values": ("STRING", {"default": ""}),
                "metadata2ColName": ("STRING", {"default": ""}),
                "metadata2Values": ("STRING", {"default": ""}),
                "metadata3ColName": ("STRING", {"default": ""}),
                "metadata3Values": ("STRING", {"default": ""}),
                "xmin": ("FLOAT", {"default": 0}),
                "xmax": ("FLOAT", {"default": 2.5}),
                "nx": ("INT", {"default": 100, "min": 1}),
                "minScalex": ("FLOAT", {"default": 0.1}),
                "ymin": ("FLOAT", {"default": 0}),
                "ymax": ("FLOAT", {"default": 2.5}),
                "ny": ("INT", {"default": 100, "min": 1}),
                "minScaley": ("FLOAT", {"default": 0.1}),
                "xscale": ("STRING", {"default": "Seurat", "options": cls.SCALE_OPTIONS}),
                "targetSum": ("FLOAT", {"default": 10000}),
                "seed": ("INT", {"default": 1}),
                "nnorm": ("INT", {"default": 2, "min": 1}),
                "nsampMCMC": ("INT", {"default": 100000, "min": 1}),
                "automatic_restart": ("STRING", {"default": "yes", "options": cls.RESTART_OPTIONS}),
                "minNeff": ("FLOAT", {"default": 200}),
                "image_file_format": ("STRING", {"default": "png", "options": cls.IMAGE_FORMATS}),
                "title": ("STRING", {"default": ""}),
                "removeFirstSamples": ("INT", {"default": -1}),
                "nsampInPlot": ("INT", {"default": 100000, "min": 1}),
                "prettyBinsx": ("INT", {"default": -1, "min": -1}),
                "prettyBinsy": ("INT", {"default": -1, "min": -1}),
                "log1pColorScale": ("BOOLEAN", {"default": False}),
                "splity": ("STRING", {"default": ""}),
                "osampx": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "osampxpdf": ("INT", {"default": 4, "min": 1, "advanced": True}),
                "osampy": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "osampypdf": ("INT", {"default": 4, "min": 1, "advanced": True}),
                "coviscale": ("FLOAT", {"default": 1, "advanced": True}),
                "nis": ("INT", {"default": 1000, "advanced": True}),
                "scalePrior": ("FLOAT", {"default": 0.3, "advanced": True}),
                "burn_custom": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "nsampBurnMCMC": ("INT", {"default": -1, "advanced": True}),
                "T0BurnMCMC": ("FLOAT", {"default": 100, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BaredscCombine1DNode(Baredsc1DNode):
    """Combine multiple one-dimensional baredSC model archives."""

    NODE_ID = "baredsc_combine_1d"
    DISPLAY_NAME = "Combine multiple 1D Models"
    DESCRIPTION = "Combine multiple one-dimensional baredSC model archives for a single gene."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_combine_1d",
        "Combine multiple 1D Models",
        "combine 1D",
        "model averaging",
        "single gene",
        "Bayesian Approach",
        "MCMC",
    ]
    RETURN_TYPES = ("TSV", "IMAGE", "DIRECTORY")
    RETURN_NAMES = ("pdf", "plot", "other_outputs")
    REQUIRED_EXECUTABLES = ["combineMultipleModels_1d", "ln", "mkdir", "mv", "gunzip"]

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--xscale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(
            [
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScale",
                str(inputs.get("minScalex", 0.1)),
                "--seed",
                str(inputs.get("seed", 1)),
            ]
        )

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output" / "baredSC_pdf.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
        ]

    @classmethod
    def _append_model_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        outputs = _as_list(inputs.get("outputs"))
        cmd.append("--outputs")
        cmd.extend(str(idx) for idx, _ in enumerate(outputs))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        outputs = _as_list(inputs.get("outputs"))
        commands = [_shell_join(["ln", "-s", output, f"{idx}.npz"]) for idx, output in enumerate(outputs)]
        image_format = cls._image_format(inputs)
        cmd = ["combineMultipleModels_1d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_model_outputs(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--figure", f"baredSC.{image_format}"])
        commands.extend(
            [
                _shell_join(cmd),
                "mkdir output",
                "mv baredSC_pdf.txt output",
                f"mv baredSC.{shlex.quote(image_format)} baredSC",
                "gunzip baredSC_means.txt.gz",
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "output").mkdir(parents=True, exist_ok=True)
        (out / "other_outputs").mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("outputs")):
            return "outputs is required"
        result = super().VALIDATE_INPUTS(inputs)
        if result is not True:
            return result
        try:
            pretty_bins = int(inputs.get("prettyBins", -1))
        except (TypeError, ValueError):
            return "prettyBins must be numeric"
        if pretty_bins < -1:
            return "prettyBins must be greater than or equal to -1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        base = super().INPUT_TYPES()
        required = {"outputs": ("FILE", {"is_list": True, "description": "baredSC 1D model archives to combine"})}
        required.update(base["required"])
        base["required"] = required
        return base

class BaredscCombine2DNode(Baredsc2DNode):
    """Combine multiple two-dimensional baredSC model archives."""

    NODE_ID = "baredsc_combine_2d"
    DISPLAY_NAME = "Combine multiple 2D Models"
    DESCRIPTION = "Combine multiple two-dimensional baredSC model archives for a pair of genes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_combine_2d",
        "Combine multiple 2D Models",
        "combine 2D",
        "model averaging",
        "pair of genes",
        "Bayesian Approach",
        "correlation",
        "MCMC",
    ]
    RETURN_TYPES = ("TSV", "TSV", "IMAGE", "DIRECTORY")
    RETURN_NAMES = ("pdf2d", "pdf2d_flat", "plot", "other_outputs")
    REQUIRED_EXECUTABLES = ["combineMultipleModels_2d", "ln", "mkdir", "mv"]

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output" / "baredSC_pdf2d.txt",
            out / "output" / "baredSC_pdf2d_flat.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
        ]

    @classmethod
    def _append_model_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        outputs = _as_list(inputs.get("outputs"))
        cmd.append("--outputs")
        cmd.extend(str(idx) for idx, _ in enumerate(outputs))

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScalex",
                str(inputs.get("minScalex", 0.1)),
                "--ymin",
                str(inputs.get("ymin", 0)),
                "--ymax",
                str(inputs.get("ymax", 2.5)),
                "--ny",
                str(inputs.get("ny", 100)),
                "--minScaley",
                str(inputs.get("minScaley", 0.1)),
                "--scale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(["--seed", str(inputs.get("seed", 1))])

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--osampx",
                str(inputs.get("osampx", 10)),
                "--osampxpdf",
                str(inputs.get("osampxpdf", 4)),
                "--osampy",
                str(inputs.get("osampy", 10)),
                "--osampypdf",
                str(inputs.get("osampypdf", 4)),
                "--coviscale",
                str(inputs.get("coviscale", 1)),
                "--nis",
                str(inputs.get("nis", 1000)),
                "--scalePrior",
                str(inputs.get("scalePrior", 0.3)),
            ]
        )
        if inputs.get("getPVal", False):
            cmd.append("--getPVal")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        outputs = _as_list(inputs.get("outputs"))
        commands = [_shell_join(["ln", "-s", output, f"{idx}.npz"]) for idx, output in enumerate(outputs)]
        image_format = cls._image_format(inputs)
        cmd = ["combineMultipleModels_2d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_model_outputs(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--figure", f"baredSC.{image_format}"])
        commands.extend(
            [
                _shell_join(cmd),
                "mkdir output",
                "mv baredSC_pdf2d.txt output",
                "mv baredSC_pdf2d_flat.txt output",
                f"mv baredSC.{shlex.quote(image_format)} baredSC",
            ]
        )
        splity = str(inputs.get("splity", "") or "")
        commands.extend(
            _shell_join(["mv", f"baredSC_split{value}.txt", f"baredSC_split{value}_pdf.txt"])
            for value in splity.split()
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "output").mkdir(parents=True, exist_ok=True)
        (out / "other_outputs").mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("outputs")):
            return "outputs is required"
        result = super().VALIDATE_INPUTS(inputs)
        if result is not True:
            return result
        for name in ("prettyBinsx", "prettyBinsy"):
            try:
                value = int(inputs.get(name, -1))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < -1:
                return f"{name} must be greater than or equal to -1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        base = super().INPUT_TYPES()
        required = {"outputs": ("FILE", {"is_list": True, "description": "baredSC 2D model archives to combine"})}
        required.update(base["required"])
        base["required"] = required
        optional = dict(base["optional"])
        optional["getPVal"] = (
            "BOOLEAN",
            {"default": False, "advanced": True, "description": "Use fewer samples to estimate the p-value"},
        )
        base["optional"] = optional
        return base

class Bax2BamNode(CommandNode):
    """Convert legacy PacBio bax.h5 basecall files to BAM."""

    NODE_ID = "bax2bam"
    DISPLAY_NAME = "bax2bam"
    REQUIRED_CONDA_PACKAGES = ["bax2bam"]
    CATEGORY = "conversion"
    DESCRIPTION = "Convert PacBio basecall format bax.h5 files into BAM."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bax2bam",
        "PacBio",
        "bax.h5",
        "basecall format",
        "BAM basecall",
        "subreads",
        "hqregion",
        "polymerase read",
        "scraps BAM",
        "pulse features",
        "Pacific Biosciences",
    ]
    RETURN_TYPES = ("BAM", "BAM", "BAM", "BAM", "BAM")
    RETURN_NAMES = (
        "output_scrap",
        "output_subread",
        "output_hqregion",
        "output_lqregion",
        "output_polymeraseread",
    )
    REQUIRED_EXECUTABLES = ["bax2bam"]
    DOCUMENTATION_URL = BAX2BAM_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BAX2BAM_CITATION_URL]
    CITATION_TEXT = BAX2BAM_CITATION_TEXT
    VERSION = "0.0.11+galaxy0"
    SHELL = True

    READTYPE_OPTIONS = ["--hqregion", "--polymeraseread", "--subread"]
    PULSEFEATURE_OPTIONS = [
        "DeletionQV",
        "DeletionTag",
        "InsertionQV",
        "IPD",
        "MergeQV",
        "PulseWidth",
        "SubstitutionQV",
        "SubstitutionTag",
    ]
    DEFAULT_PULSEFEATURES = [
        "DeletionQV",
        "DeletionTag",
        "InsertionQV",
        "IPD",
        "MergeQV",
        "PulseWidth",
        "SubstitutionQV",
    ]

    @classmethod
    def _readtype(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("readtype", "--subread") or "--subread")

    @classmethod
    def _pulsefeatures(cls, inputs: dict[str, Any]) -> list[str]:
        selected = inputs.get("pulsefeatures", cls.DEFAULT_PULSEFEATURES)
        values = _as_list(selected)
        return values if values else []

    @classmethod
    def _output_prefix(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["bax2bam"]
        cmd.extend(_as_list(inputs.get("files")))
        cmd.extend(["-o", cls._output_prefix(inputs), cls._readtype(inputs)])
        pulsefeatures = cls._pulsefeatures(inputs)
        if pulsefeatures:
            cmd.append(f"--pulsefeatures={','.join(pulsefeatures)}")
        if inputs.get("losslessframes"):
            cmd.append("--losslessframes")
        if inputs.get("internal"):
            cmd.append("--internal")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        match cls._readtype(inputs):
            case "--hqregion":
                return [out / "output.hqregions.bam", out / "output.lqregions.bam"]
            case "--polymeraseread":
                return [out / "output.polymerase.bam"]
            case _:
                return [out / "output.scraps.bam", out / "output.subreads.bam"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("files")):
            return "files is required"
        if cls._readtype(inputs) not in cls.READTYPE_OPTIONS:
            return f"readtype must be one of: {', '.join(cls.READTYPE_OPTIONS)}"
        if any(feature not in cls.PULSEFEATURE_OPTIONS for feature in cls._pulsefeatures(inputs)):
            return "pulsefeatures must be selected from supported PacBio pulse features"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "files": (
                    "FILE",
                    {"is_list": True, "description": "PacBio bax.h5 files from the same movie"},
                ),
            },
            "optional": {
                "readtype": (
                    "STRING",
                    {
                        "default": "--subread",
                        "options": cls.READTYPE_OPTIONS,
                        "description": "Output read type to produce",
                    },
                ),
                "pulsefeatures": (
                    "STRING",
                    {
                        "default": cls.DEFAULT_PULSEFEATURES,
                        "options": cls.PULSEFEATURE_OPTIONS,
                        "is_list": True,
                        "description": "Pulse features to include in the output BAM",
                    },
                ),
                "losslessframes": (
                    "BOOLEAN",
                    {"default": False, "description": "Store full 16-bit IPD and PulseWidth data"},
                ),
                "internal": (
                    "BOOLEAN",
                    {"default": False, "description": "Include non-sequencing ZMWs in the scraps BAM when applicable"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BerokkaNode(CommandNode):
    """Trim, circularise, orient, and filter long-read bacterial assemblies."""

    NODE_ID = "berokka"
    DISPLAY_NAME = "Berokka"
    REQUIRED_CONDA_PACKAGES = ["berokka"]
    CATEGORY = "assembly"
    DESCRIPTION = "Trim, circularise, orient and filter long read bacterial genome assemblies."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "berokka",
        "Berokka",
        "trim circularise orient",
        "long read bacterial genome assemblies",
        "completed assemblies",
        "CANU",
        "HGAP",
        "Circlator",
        "PacBio control sequence",
    ]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("trimmed", "results")
    REQUIRED_EXECUTABLES = ["berokka"]
    DOCUMENTATION_URL = BEROKKA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BEROKKA_CITATION_URL]
    CITATION_TEXT = BEROKKA_CITATION_TEXT
    VERSION = "0.2.3"
    SHELL = True

    @classmethod
    def _read_length(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("read_length", 60000) or 60000)

    @classmethod
    def _fuzz(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("fuzz", 5) or 5)

    @classmethod
    def _work_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/default"

    @classmethod
    def _trimmed_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/trimmed.fasta"

    @classmethod
    def _results_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/results.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "berokka",
            "--outdir",
            cls._work_dir(inputs),
            str(inputs.get("input_file", "")),
        ]
        _add_if_value(cmd, "--filter", inputs.get("filter_fasta"))
        cmd.extend(["--readlen", str(cls._read_length(inputs)), "--fuzz", str(cls._fuzz(inputs))])
        if inputs.get("anno", True) is False:
            cmd.append("--noanno")
        cmd.extend(
            [
                "&&",
                "cp",
                f"{cls._work_dir(inputs)}/02.trimmed.fa",
                cls._trimmed_path(inputs),
                "&&",
                "cp",
                f"{cls._work_dir(inputs)}/03.results.tab",
                cls._results_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "trimmed.fasta", out / "results.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        try:
            read_length = cls._read_length(inputs)
        except (TypeError, ValueError):
            return "read_length must be an integer"
        if read_length < 28:
            return "read_length must be at least 28"
        try:
            cls._fuzz(inputs)
        except (TypeError, ValueError):
            return "fuzz must be an integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FASTA",
                    {"description": "Completed long-read assembly FASTA, such as CANU or HGAP contigs"},
                ),
            },
            "optional": {
                "filter_fasta": (
                    "FASTA",
                    {"default": "", "description": "Optional FASTA whose matching contigs are filtered out"},
                ),
                "read_length": (
                    "INT",
                    {
                        "default": 60000,
                        "min": 28,
                        "description": "Approximate maximum read length used for circularisation matching",
                    },
                ),
                "fuzz": (
                    "INT",
                    {"default": 5, "description": "Accept local alignment within this many bp of global alignment"},
                ),
                "anno": (
                    "BOOLEAN",
                    {"default": True, "description": "Annotate trimmed FASTA descriptions"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BamToScidxNode(CommandNode):
    """Convert BAM data to Strand-specific coordinate count ScIdx files."""

    NODE_ID = "bam_to_scidx"
    DISPLAY_NAME = "Convert BAM to ScIdx"
    REQUIRED_CONDA_PACKAGES = ["openjdk"]
    CATEGORY = "chip_seq"
    DESCRIPTION = "Convert BAM alignments to Strand-specific coordinate count ScIdx format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bam_to_scidx",
        "BAM to ScIdx",
        "ScIdx",
        "strand-specific coordinate count",
        "ChIP-exo",
        "GeneTrack",
        "MultiGPS",
        "BAMtoscIDX",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["java"]
    DOCUMENTATION_URL = BAM_TO_SCIDX_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BAM_TO_SCIDX_CITATION_URL]
    CITATION_TEXT = BAM_TO_SCIDX_CITATION_TEXT
    VERSION = "1.0.1"
    SHELL = True

    PROPER_MATE_PAIRING = ["1", "0"]
    READS = ["0", "1", "2"]

    @classmethod
    def _proper_mate_pairing(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("require_proper_mate_pairing", "1") or "1")

    @classmethod
    def _read(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("read", "0") or "0")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.scidx"

    @classmethod
    def _optional_int(cls, inputs: dict[str, Any], key: str) -> int | None:
        value = inputs.get(key)
        if value is None or str(value) == "":
            return None
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "ln",
            "-s",
            str(inputs.get("input_bam", "")),
            "localbam.bam",
            "&&",
            "ln",
            "-f",
            "-s",
            str(inputs.get("bam_index", "")),
            "localbam.bam.bai",
            "&&",
            "java",
            "-jar",
            str(inputs.get("jar_path", "BAMtoscIDX.jar") or "BAMtoscIDX.jar"),
            "-b",
            "localbam.bam",
            "-i",
            "localbam.bam.bai",
            "-p",
            cls._proper_mate_pairing(inputs),
            "-r",
            cls._read(inputs),
        ]
        min_insert_size = cls._optional_int(inputs, "min_insert_size")
        if min_insert_size is not None:
            cmd.extend(["-m", str(min_insert_size)])
        max_insert_size = cls._optional_int(inputs, "max_insert_size")
        if max_insert_size is not None:
            cmd.extend(["-M", str(max_insert_size)])
        cmd.extend(["-o", cls._output_path(inputs), "1>/dev/null"])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.scidx"]

    @classmethod
    def _validate_insert_size(cls, inputs: dict[str, Any], key: str) -> bool | str:
        try:
            value = cls._optional_int(inputs, key)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value is not None and value < 0:
            return f"{key} must be greater than or equal to 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_bam", "")).strip():
            return "input_bam is required"
        if not str(inputs.get("bam_index", "")).strip():
            return "bam_index is required"
        read = cls._read(inputs)
        if read not in cls.READS:
            return f"read must be one of: {', '.join(cls.READS)}"
        proper_mate_pairing = cls._proper_mate_pairing(inputs)
        if proper_mate_pairing not in cls.PROPER_MATE_PAIRING:
            return f"require_proper_mate_pairing must be one of: {', '.join(cls.PROPER_MATE_PAIRING)}"
        for key in ("min_insert_size", "max_insert_size"):
            validation = cls._validate_insert_size(inputs, key)
            if validation is not True:
                return validation
        min_insert_size = cls._optional_int(inputs, "min_insert_size")
        max_insert_size = cls._optional_int(inputs, "max_insert_size")
        if min_insert_size is not None and max_insert_size is not None and max_insert_size < min_insert_size:
            return "max_insert_size must be greater than or equal to min_insert_size"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Input BAM file"}),
                "bam_index": ("BAI", {"description": "BAM index file for the input BAM"}),
            },
            "optional": {
                "require_proper_mate_pairing": (
                    "STRING",
                    {
                        "default": "1",
                        "options": cls.PROPER_MATE_PAIRING,
                        "description": "Require proper mate-pairing when filtering by insert size",
                    },
                ),
                "read": (
                    "STRING",
                    {"default": "0", "options": cls.READS, "description": "Read to output: 0 Read1, 1 Read2, or 2 combined"},
                ),
                "min_insert_size": ("INT", {"default": "", "min": 0, "description": "Minimum insert size to output"}),
                "max_insert_size": ("INT", {"default": "", "min": 0, "description": "Maximum insert size to output"}),
                "jar_path": (
                    "FILE",
                    {"default": "BAMtoscIDX.jar", "advanced": True, "description": "Path to BAMtoscIDX.jar"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FastaRegexFinderNode(CommandNode):
    """Search FASTA sequences for regular-expression matches and emit BED coordinates."""

    NODE_ID = "fasta_regex_finder"
    DISPLAY_NAME = "Fasta regular expression finder"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "sequence"
    DESCRIPTION = "Search FASTA sequences for regular-expression matches and report BED coordinates."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "fasta_regex_finder",
        "fastaRegexFinder",
        "FASTA regex",
        "regular expression finder",
        "motif search",
        "G-quadruplex",
        "BED coordinates",
        "reverse complement",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = FASTA_REGEX_FINDER_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [FASTA_REGEX_FINDER_CITATION_URL]
    CITATION_TEXT = FASTA_REGEX_FINDER_CITATION_TEXT
    VERSION = "0.1.0"
    SHELL = True

    ADVANCED_MODES = ["simple", "advanced"]
    DEFAULT_REGEX = r"([gG]{3,}\w{1,7}){3,}[gG]{3,}"

    @classmethod
    def _advanced(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("advanced", "simple") or "simple")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.bed"

    @classmethod
    def _maxstr(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("maxstr", 10000)
        if value is None or str(value) == "":
            return 10000
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "fastaregexfinder.py") or "fastaregexfinder.py"),
            "--fasta",
            str(inputs.get("input", "")),
            "--regex",
            str(inputs.get("regex", cls.DEFAULT_REGEX) or cls.DEFAULT_REGEX),
        ]
        if cls._advanced(inputs) == "advanced":
            if inputs.get("matchcase"):
                cmd.append("--matchcase")
            if inputs.get("noreverse"):
                cmd.append("--noreverse")
            cmd.extend(["--maxstr", str(cls._maxstr(inputs))])
            _add_if_value(cmd, "--seqnames", inputs.get("seqnames"))
        cmd.extend(["--quiet", ">", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("regex", cls.DEFAULT_REGEX)).strip():
            return "regex is required"
        advanced = cls._advanced(inputs)
        if advanced not in cls.ADVANCED_MODES:
            return f"advanced must be one of: {', '.join(cls.ADVANCED_MODES)}"
        if advanced == "advanced":
            try:
                maxstr = cls._maxstr(inputs)
            except (TypeError, ValueError):
                return "maxstr must be an integer"
            if maxstr < 1:
                return "maxstr must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA sequences to search"}),
            },
            "optional": {
                "regex": (
                    "STRING",
                    {"default": cls.DEFAULT_REGEX, "description": "Regular expression searched in the FASTA input"},
                ),
                "advanced": (
                    "STRING",
                    {"default": "simple", "options": cls.ADVANCED_MODES, "description": "Expose advanced search controls"},
                ),
                "matchcase": ("BOOLEAN", {"default": False, "description": "Match case instead of ignoring case"}),
                "noreverse": ("BOOLEAN", {"default": False, "description": "Do not search the reverse complement"}),
                "maxstr": ("INT", {"default": 10000, "min": 1, "description": "Maximum length of matched sequence to report"}),
                "seqnames": (
                    "STRING",
                    {"default": "", "description": "Space-separated FASTA sequence names to search in advanced mode"},
                ),
                "script_path": (
                    "FILE",
                    {"default": "fastaregexfinder.py", "advanced": True, "description": "Path to the fastaRegexFinder script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CDHitNode(CommandNode):
    """Cluster or compare protein and nucleotide FASTA datasets with CD-HIT."""

    NODE_ID = "cd_hit"
    DISPLAY_NAME = "cd-hit"
    REQUIRED_CONDA_PACKAGES = ["cd-hit"]
    CATEGORY = "clustering"
    DESCRIPTION = "Cluster or compare biological sequence datasets with CD-HIT."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "cd-hit",
        "cd_hit",
        "CD-HIT",
        "cd-hit-est",
        "cd-hit-2d",
        "cd-hit-est-2d",
        "sequence clustering",
        "non-redundant sequences",
        "representative sequences",
    ]
    RETURN_TYPES = ("TXT", "FASTA")
    RETURN_NAMES = ("clusters_out", "fasta_out")
    REQUIRED_EXECUTABLES = ["cd-hit", "cd-hit-est", "cd-hit-2d", "cd-hit-est-2d"]
    DOCUMENTATION_URL = "http://weizhongli-lab.org/cd-hit/"
    CITATION_DOIS = CD_HIT_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CD_HIT_CITATION_DOIS]
    CITATION_TEXT = CD_HIT_CITATION_TEXT
    VERSION = "4.8.1+galaxy0"
    SHELL = True

    SEQUENCE_TYPES = ["protein", "nucleotide"]
    OPERATIONS = ["cluster", "2d"]
    IDENTITY_STYLES = ["global", "local"]

    @classmethod
    def _sequence_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sequence_type", "protein") or "protein")

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("operation", "cluster") or "cluster")

    @classmethod
    def _identity_style(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("identity_style", "global") or "global")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/rep_seq"

    @classmethod
    def _binary(cls, inputs: dict[str, Any]) -> str:
        binary = "cd-hit"
        if cls._sequence_type(inputs) == "nucleotide":
            binary += "-est"
        if cls._operation(inputs) == "2d":
            binary += "-2d"
        return binary

    @classmethod
    def _bool_flag(cls, inputs: dict[str, Any], key: str, default: bool = False) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return "1" if value.lower() in {"true", "1", "yes"} else "0"
        return "1" if bool(value) else "0"

    @classmethod
    def _inram_flag(cls, inputs: dict[str, Any]) -> str:
        value = inputs.get("inram", True)
        if isinstance(value, str):
            inram = value.lower() in {"true", "1", "yes"}
        else:
            inram = bool(value)
        return "0" if inram else "1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = cls._sequence_type(inputs)
        operation = cls._operation(inputs)
        identity_style = cls._identity_style(inputs)
        cmd = [
            cls._binary(inputs),
            "-i",
            str(inputs.get("fasta_in", "")),
            "-o",
            cls._output_path(inputs),
            "-c",
            str(inputs.get("similarity", 0.9)),
            "-n",
            str(inputs.get("nucleotide_wordsize", 10) if sequence_type == "nucleotide" else inputs.get("protein_wordsize", 5)),
        ]
        if sequence_type == "nucleotide":
            cmd.extend(["-r", cls._bool_flag(inputs, "compare_both_strands", False)])
            _add_if_value(cmd, "-mask", inputs.get("mask"))
            cmd.extend(["-match", str(inputs.get("match", 2))])
            cmd.extend(["-mismatch", str(inputs.get("mismatch", -2))])
            cmd.extend(["-gap", str(inputs.get("gap", -6))])
            cmd.extend(["-gap-ext", str(inputs.get("gap_ext", -1))])
        else:
            cmd.extend(["-t", str(inputs.get("redtol", 2))])

        if operation == "2d":
            cmd.extend(["-i2", str(inputs.get("fasta_in2", ""))])
            if identity_style == "local":
                cmd.extend(["-s2", str(inputs.get("cutoff_diff_len2", 1.0))])
                cmd.extend(["-S2", str(inputs.get("aa_cutoff_diff_len2", 0))])

        cmd.extend(["-b", str(inputs.get("band_width", 20))])
        cmd.extend(["-l", str(inputs.get("throw_away_len", 10))])
        if identity_style == "local":
            cmd.extend(["-G", "0"])
            cmd.extend(["-aL", str(inputs.get("align_coverage_long", 0.0))])
            cmd.extend(["-AL", str(inputs.get("align_coverage_long_control", 99999999))])
            cmd.extend(["-aS", str(inputs.get("align_coverage_short", 0.0))])
            cmd.extend(["-AS", str(inputs.get("align_coverage_short_control", 99999999))])
            cmd.extend(["-A", str(inputs.get("align_coverage_min", 0))])
            cmd.extend(["-s", str(inputs.get("cutoff_diff_len", 0.0))])
            cmd.extend(["-S", str(inputs.get("aa_cutoff_diff_len", 999999))])
        cmd.extend(["-uL", str(inputs.get("max_unmatched_per_l", 1.0))])
        cmd.extend(["-uS", str(inputs.get("max_unmatched_per_s", 1.0))])
        cmd.extend(["-U", str(inputs.get("max_unmatched_len", 99999999))])
        cmd.extend(["-g", cls._bool_flag(inputs, "accurate", False)])
        cmd.extend(["-B", cls._inram_flag(inputs)])
        cmd.extend(["-sc", cls._bool_flag(inputs, "sort_cluster", False)])
        cmd.extend(["-sf", cls._bool_flag(inputs, "sort_fasta", False)])
        if inputs.get("print_alignment_overlap"):
            cmd.extend(["-p", "1", "-d", str(inputs.get("desclen", 20))])
        cmd.extend(["-M", "${GALAXY_MEMORY_MB:-0}", "-T", "${GALAXY_SLOTS:-1}"])
        return _shell_join(cmd).replace("'${GALAXY_MEMORY_MB:-0}'", "${GALAXY_MEMORY_MB:-0}").replace(
            "'${GALAXY_SLOTS:-1}'",
            "${GALAXY_SLOTS:-1}",
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "rep_seq.clstr", out / "rep_seq"]

    @classmethod
    def _validate_float_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> bool | str:
        try:
            value = float(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < minimum or value > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def _validate_int_range(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: int,
        minimum: int,
        maximum: int | None = None,
    ) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum or (maximum is not None and value > maximum):
            if maximum is None:
                return f"{key} must be greater than or equal to {minimum}"
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fasta_in", "")).strip():
            return "fasta_in is required"
        sequence_type = cls._sequence_type(inputs)
        if sequence_type not in cls.SEQUENCE_TYPES:
            return f"sequence_type must be one of: {', '.join(cls.SEQUENCE_TYPES)}"
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        if operation == "2d" and not str(inputs.get("fasta_in2", "")).strip():
            return "fasta_in2 is required when operation is 2d"
        style = cls._identity_style(inputs)
        if style not in cls.IDENTITY_STYLES:
            return f"identity_style must be one of: {', '.join(cls.IDENTITY_STYLES)}"
        similarity = inputs.get("similarity", 0.9)
        if sequence_type == "nucleotide":
            validation = cls._validate_float_range({"similarity": similarity}, "similarity", 0.9, 0.8, 1.0)
            if validation is not True:
                return "similarity must be between 0.8 and 1.0 for nucleotide sequences"
            validation = cls._validate_int_range(inputs, "nucleotide_wordsize", 10, 4, 11)
            if validation is not True:
                return validation
        else:
            validation = cls._validate_float_range({"similarity": similarity}, "similarity", 0.9, 0.4, 1.0)
            if validation is not True:
                return "similarity must be between 0.4 and 1.0 for protein sequences"
            validation = cls._validate_int_range(inputs, "protein_wordsize", 5, 2, 5)
            if validation is not True:
                return validation
        for key in ("band_width", "throw_away_len"):
            validation = cls._validate_int_range(inputs, key, 20 if key == "band_width" else 10, 1)
            if validation is not True:
                return validation
        for key in ("max_unmatched_per_l", "max_unmatched_per_s"):
            validation = cls._validate_float_range(inputs, key, 1.0, 0.0, 1.0)
            if validation is not True:
                return validation
        validation = cls._validate_int_range(inputs, "max_unmatched_len", 99999999, 0)
        if validation is not True:
            return validation
        if style == "local":
            for key in ("align_coverage_long", "align_coverage_short", "cutoff_diff_len", "cutoff_diff_len2"):
                validation = cls._validate_float_range(inputs, key, 0.0 if key != "cutoff_diff_len2" else 1.0, 0.0, 1.0)
                if validation is not True:
                    return validation
            for key, default in (
                ("align_coverage_long_control", 99999999),
                ("align_coverage_short_control", 99999999),
                ("align_coverage_min", 0),
                ("aa_cutoff_diff_len", 999999),
                ("aa_cutoff_diff_len2", 0),
            ):
                validation = cls._validate_int_range(inputs, key, default, 0)
                if validation is not True:
                    return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta_in": ("FASTA", {"description": "Primary protein or nucleotide FASTA sequences"}),
            },
            "optional": {
                "operation": (
                    "STRING",
                    {"default": "cluster", "options": cls.OPERATIONS, "description": "Cluster one dataset or compare against a second dataset"},
                ),
                "fasta_in2": ("FASTA", {"default": "", "description": "Second FASTA dataset for cd-hit-2d comparisons"}),
                "sequence_type": (
                    "STRING",
                    {"default": "protein", "options": cls.SEQUENCE_TYPES, "description": "Protein uses cd-hit; nucleotide uses cd-hit-est"},
                ),
                "similarity": ("FLOAT", {"default": 0.9, "min": 0.4, "max": 1.0, "description": "Sequence identity threshold"}),
                "protein_wordsize": ("INT", {"default": 5, "min": 2, "max": 5, "description": "Protein word size"}),
                "nucleotide_wordsize": ("INT", {"default": 10, "min": 4, "max": 11, "description": "Nucleotide word size"}),
                "redtol": ("INT", {"default": 2, "description": "Tolerance for redundancy in protein mode"}),
                "compare_both_strands": ("BOOLEAN", {"default": False, "description": "Compare both strands in nucleotide mode"}),
                "mask": ("STRING", {"default": "", "description": "Masking letters for nucleotide mode, for example NX"}),
                "match": ("INT", {"default": 2, "description": "Nucleotide match score"}),
                "mismatch": ("INT", {"default": -2, "description": "Nucleotide mismatch score"}),
                "gap": ("INT", {"default": -6, "description": "Nucleotide gap opening score"}),
                "gap_ext": ("INT", {"default": -1, "description": "Nucleotide gap extension score"}),
                "band_width": ("INT", {"default": 20, "min": 1, "description": "Alignment band width"}),
                "throw_away_len": ("INT", {"default": 10, "min": 1, "description": "Length threshold for throwing away short sequences"}),
                "identity_style": (
                    "STRING",
                    {"default": "global", "options": cls.IDENTITY_STYLES, "description": "Use global or local sequence identity"},
                ),
                "align_coverage_long": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Local-mode coverage for longer sequence"}),
                "align_coverage_long_control": ("INT", {"default": 99999999, "min": 0, "description": "Maximum uncovered residues for longer sequence"}),
                "align_coverage_short": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Local-mode coverage for shorter sequence"}),
                "align_coverage_short_control": ("INT", {"default": 99999999, "min": 0, "description": "Maximum uncovered residues for shorter sequence"}),
                "align_coverage_min": ("INT", {"default": 0, "min": 0, "description": "Minimum alignment coverage in residues"}),
                "cutoff_diff_len": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "description": "Length difference cutoff"}),
                "aa_cutoff_diff_len": ("INT", {"default": 999999, "min": 0, "description": "Length difference cutoff in residues"}),
                "cutoff_diff_len2": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "2D local-mode length difference cutoff"}),
                "aa_cutoff_diff_len2": ("INT", {"default": 0, "min": 0, "description": "2D local-mode length difference cutoff in residues"}),
                "max_unmatched_per_l": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "Maximum unmatched fraction for longer sequence"}),
                "max_unmatched_per_s": ("FLOAT", {"default": 1.0, "min": 0, "max": 1, "description": "Maximum unmatched fraction for shorter sequence"}),
                "max_unmatched_len": ("INT", {"default": 99999999, "min": 0, "description": "Maximum unmatched length"}),
                "accurate": ("BOOLEAN", {"default": False, "description": "Use accurate but slower clustering"}),
                "inram": ("BOOLEAN", {"default": True, "description": "Store sequences in RAM"}),
                "sort_cluster": ("BOOLEAN", {"default": False, "description": "Sort clusters by size"}),
                "sort_fasta": ("BOOLEAN", {"default": False, "description": "Sort output FASTA by cluster size"}),
                "print_alignment_overlap": (
                    "BOOLEAN",
                    {"default": False, "description": "Print alignment overlap in the .clstr output"},
                ),
                "desclen": ("INT", {"default": 20, "min": 0, "description": "Description length for .clstr output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ClusteringFromDistmatNode(CommandNode):
    """Hierarchically cluster samples from a symmetric distance matrix."""

    NODE_ID = "clustering_from_distmat"
    DISPLAY_NAME = "Distance matrix-based hierarchical clustering"
    REQUIRED_CONDA_PACKAGES = ["python", "scipy"]
    CATEGORY = "clustering"
    DESCRIPTION = "Cluster samples from a symmetric distance matrix with SciPy hierarchical clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "clustering_from_distmat",
        "Distance matrix-based hierarchical clustering",
        "distance matrix",
        "hierarchical clustering",
        "SciPy linkage",
        "UPGMA",
        "WPGMA",
        "dendrogram",
        "newick",
        "cut_tree",
        "cluster assignments",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE", "TSV")
    RETURN_NAMES = ("clustering_dendrogram", "clustering_assignment")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html"
    CITATION_DOIS = [SCIPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{SCIPY_CITATION_DOI}"]
    CITATION_TEXT = SCIPY_CITATION_TEXT
    VERSION = "1.1.1"
    SHELL = True

    METHODS = ["single", "complete", "average", "weighted", "centroid", "median", "ward"]
    MISSING_NAMES_OPTIONS = ["", "--nr", "--nc"]
    CLUSTER_ASSIGNMENT_OPTIONS = ["dendrogram-only", "n-cluster", "height"]

    @staticmethod
    def _bool_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() not in {"", "false", "0", "no", "off"}
        return bool(value)

    @classmethod
    def _cluster_assignment(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("cluster_assignment", "dendrogram-only") or "dendrogram-only")

    @classmethod
    def _dendrogram_requested(cls, inputs: dict[str, Any]) -> bool:
        return cls._cluster_assignment(inputs) == "dendrogram-only" or cls._bool_flag(inputs.get("generate_dendrogram", False))

    @classmethod
    def _assignment_requested(cls, inputs: dict[str, Any]) -> bool:
        return cls._cluster_assignment(inputs) in {"n-cluster", "height"}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        assignment = cls._cluster_assignment(inputs)
        cmd = [
            "python",
            str(inputs.get("script_path", "clustering_from_distmat.py") or "clustering_from_distmat.py"),
            str(inputs.get("distmat", "")),
            "result",
            "--method",
            str(inputs.get("method", "average") or "average"),
        ]
        missing_names = str(inputs.get("missing_names", "") or "")
        if missing_names:
            cmd.append(missing_names)
        if assignment == "n-cluster":
            cmd.extend(["--n-clusters", str(inputs.get("n_cluster", 5))])
        elif assignment == "height":
            cmd.extend(["--height", str(inputs.get("height", 5.0))])
        min_cluster_size = int(inputs.get("min_cluster_size", 2))
        if assignment != "dendrogram-only" and min_cluster_size != 2:
            cmd.extend(["--min-cluster-size", str(min_cluster_size)])
        commands = [_shell_join(["mkdir", "-p", out]), f"cd {shlex.quote(out)}", _shell_join(cmd)]
        if cls._dendrogram_requested(inputs):
            commands.append(_shell_join(["mv", "result.tree.newick", "clustering_dendrogram.newick"]))
        if cls._assignment_requested(inputs):
            commands.append(_shell_join(["mv", "result.cluster_assignments.tsv", "clustering_assignment.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        if cls._dendrogram_requested(inputs):
            outputs.append(out / "clustering_dendrogram.newick")
        if cls._assignment_requested(inputs):
            outputs.append(out / "clustering_assignment.tsv")
        return outputs

    @classmethod
    def _validate_int_min(cls, inputs: dict[str, Any], key: str, default: int, minimum: int) -> bool | str:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value < minimum:
            return f"{key} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("distmat", "")).strip():
            return "distmat is required"
        method = str(inputs.get("method", "average") or "average")
        if method not in cls.METHODS:
            return f"method must be one of: {', '.join(cls.METHODS)}"
        missing_names = str(inputs.get("missing_names", "") or "")
        if missing_names not in cls.MISSING_NAMES_OPTIONS:
            return f"missing_names must be one of: {', '.join(cls.MISSING_NAMES_OPTIONS)}"
        assignment = cls._cluster_assignment(inputs)
        if assignment not in cls.CLUSTER_ASSIGNMENT_OPTIONS:
            return f"cluster_assignment must be one of: {', '.join(cls.CLUSTER_ASSIGNMENT_OPTIONS)}"
        if assignment == "n-cluster":
            result = cls._validate_int_min(inputs, "n_cluster", 5, 1)
            if result is not True:
                return result
        elif assignment == "height":
            try:
                float(inputs.get("height", 5.0))
            except (TypeError, ValueError):
                return "height must be numeric"
        if assignment != "dendrogram-only":
            result = cls._validate_int_min(inputs, "min_cluster_size", 2, 1)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "distmat": ("TSV", {"description": "Symmetric tabular distance matrix with sample names"}),
            },
            "optional": {
                "method": (
                    "STRING",
                    {"default": "average", "options": cls.METHODS, "description": "SciPy linkage clustering method"},
                ),
                "missing_names": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.MISSING_NAMES_OPTIONS,
                        "description": "Input omits row names, column names, or neither",
                    },
                ),
                "cluster_assignment": (
                    "STRING",
                    {
                        "default": "dendrogram-only",
                        "options": cls.CLUSTER_ASSIGNMENT_OPTIONS,
                        "description": "Generate only a dendrogram or also cut the tree into clusters",
                    },
                ),
                "n_cluster": ("INT", {"default": 5, "min": 1}),
                "height": ("FLOAT", {"default": 5.0}),
                "min_cluster_size": ("INT", {"default": 2, "min": 1}),
                "generate_dendrogram": (
                    "BOOLEAN",
                    {"default": False, "description": "Also keep the Newick dendrogram when generating assignments"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "clustering_from_distmat.py",
                        "advanced": True,
                        "description": "Path to the Galaxy clustering_from_distmat.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AddInputNameAsColumnNode(CommandNode):
    """Add the input dataset name as an appended or prepended tabular column."""

    NODE_ID = "add_input_name_as_column"
    DISPLAY_NAME = "Add input name as column"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Add the input dataset name as an appended or prepended tabular column."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Add input name as column",
        "add_input_name_as_column",
        "dataset collection labels",
        "history dataset name",
        "sample label column",
        "tabular label column",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = ADD_INPUT_NAME_AS_COLUMN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ADD_INPUT_NAME_AS_COLUMN_CITATION_URL]
    CITATION_TEXT = ADD_INPUT_NAME_AS_COLUMN_CITATION_TEXT
    VERSION = "0.3.0"
    SHELL = True

    HEADER_OPTIONS = ["yes", "no"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "add_input_name_as_column.py")),
            "--input",
            str(inputs.get("input", "")),
            "--label",
            str(inputs.get("label", "")),
            "--output",
            cls._output_path(inputs),
        ]
        if str(inputs.get("contains_header", "yes") or "yes") == "yes":
            cmd.extend(["--header", str(inputs.get("colname", "sample") or "sample")])
        if inputs.get("prepend"):
            cmd.append("--prepend")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("label", "")).strip():
            return "label is required"
        contains_header = str(inputs.get("contains_header", "yes") or "yes")
        if contains_header not in cls.HEADER_OPTIONS:
            return f"contains_header must be one of: {', '.join(cls.HEADER_OPTIONS)}"
        if contains_header == "yes" and not str(inputs.get("colname", "sample") or "").strip():
            return "colname is required when contains_header is yes"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TXT", {"description": "Text or tabular dataset to annotate with its input label"}),
                "label": ("STRING", {"description": "Dataset label to add, matching Galaxy's input element identifier"}),
            },
            "optional": {
                "contains_header": (
                    "STRING",
                    {
                        "default": "yes",
                        "options": cls.HEADER_OPTIONS,
                        "description": "Whether the first line should receive a column header instead of the dataset label",
                    },
                ),
                "colname": (
                    "STRING",
                    {"default": "sample", "description": "Column name added to the first line when the input has a header"},
                ),
                "prepend": (
                    "BOOLEAN",
                    {"default": False, "description": "Prepend the label column instead of appending it"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "add_input_name_as_column.py",
                        "advanced": True,
                        "description": "Path to the Galaxy add_input_name_as_column.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AddInputNameAsColumnGalaxyNode(AddInputNameAsColumnNode):
    """Galaxy wrapper-ID compatible alias for Add input name as column."""

    NODE_ID = "addName"
    DISPLAY_NAME = "Add input name as column (Galaxy)"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "addName",
        "Add input name as column",
        "add_input_name_as_column",
        "dataset collection labels",
        "history dataset name",
        "sample label column",
        "tabular label column",
    ]

class ColumnRemoveByHeaderNode(CommandNode):
    """Remove or keep tabular columns by matching header names."""

    NODE_ID = "column_remove_by_header"
    DISPLAY_NAME = "Remove columns"
    REQUIRED_CONDA_PACKAGES = ["python"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Remove or keep columns from a tabular file by matching header names."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "column_remove_by_header",
        "Remove columns",
        "remove columns by heading",
        "keep named columns",
        "header names",
        "tabular column filter",
        "unicode escaped columns",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output_tabular",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = COLUMN_REMOVE_BY_HEADER_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLUMN_REMOVE_BY_HEADER_CITATION_URL]
    CITATION_TEXT = COLUMN_REMOVE_BY_HEADER_CITATION_TEXT
    VERSION = "1.0"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_tabular.tsv"

    @classmethod
    def _headers(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("headers")
        if isinstance(raw, str):
            return [header.strip() for header in raw.split(",") if header.strip()]
        return _as_list(raw)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "column_remove_by_header.py") or "column_remove_by_header.py"),
            "-i",
            str(inputs.get("input_tabular", "")),
            "-o",
            cls._output_path(inputs),
            "-d",
            str(inputs.get("delimiter", "\\t") or "\\t"),
        ]
        if inputs.get("keep_columns"):
            cmd.append("--keep")
        cmd.extend(
            [
                "-s",
                str(inputs.get("strip_characters", "#")),
                "--unicode-escaped-cols",
                "--columns",
                *cls._headers(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_tabular.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tabular", "")).strip():
            return "input_tabular is required"
        if not cls._headers(inputs):
            return "at least one header is required"
        delimiter = str(inputs.get("delimiter", "\\t"))
        if delimiter == "":
            return "delimiter is required"
        try:
            delimiter.encode("ascii")
        except UnicodeEncodeError:
            return "delimiter must contain only ASCII characters"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tabular": ("TSV", {"description": "Tabular file with a header row"}),
                "headers": (
                    "STRING",
                    {
                        "is_list": True,
                        "description": "Header names to remove, or to keep when keep_columns is enabled",
                    },
                ),
            },
            "optional": {
                "keep_columns": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Keep named columns and drop all other columns",
                    },
                ),
                "strip_characters": (
                    "STRING",
                    {
                        "default": "#",
                        "description": "Leading characters to strip from the first header before comparison",
                    },
                ),
                "delimiter": ("STRING", {"default": "\\t", "description": "ASCII field delimiter"}),
                "script_path": (
                    "FILE",
                    {
                        "default": "column_remove_by_header.py",
                        "advanced": True,
                        "description": "Path to the Galaxy column_remove_by_header.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ColumnOrderHeaderSortNode(CommandNode):
    """Sort tabular columns by header while optionally preserving an identifier column."""

    NODE_ID = "column_order_header_sort"
    DISPLAY_NAME = "Sort Column Order"
    REQUIRED_CONDA_PACKAGES = ["python", "gawk"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Reorder tabular columns by sorted header values, with an optional identifier column first."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "column_order_header_sort",
        "Sort Column Order",
        "sort column order",
        "sorted header fields",
        "identifier column",
        "tabular column sort",
        "column order by heading",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output_tabular",)
    REQUIRED_EXECUTABLES = ["python", "gawk"]
    DOCUMENTATION_URL = COLUMN_ORDER_HEADER_SORT_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLUMN_ORDER_HEADER_SORT_CITATION_URL]
    CITATION_TEXT = COLUMN_ORDER_HEADER_SORT_CITATION_TEXT
    VERSION = "0.0.1"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_tabular.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "column_order_header_sort.py") or "column_order_header_sort.py"),
            str(inputs.get("input_tabular", "")),
            cls._output_path(inputs),
            str(inputs.get("delimiter", "\\t") or "\\t"),
            str(inputs.get("key_column", 0)),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_tabular.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tabular", "")).strip():
            return "input_tabular is required"
        try:
            key_column = int(inputs.get("key_column", 0))
        except (TypeError, ValueError):
            return "key_column must be an integer"
        if key_column < 0:
            return "key_column must be greater than or equal to 0"
        delimiter = str(inputs.get("delimiter", "\\t"))
        if delimiter == "":
            return "delimiter is required"
        try:
            delimiter.encode("ascii")
        except UnicodeEncodeError:
            return "delimiter must contain only ASCII characters"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tabular": ("TSV", {"description": "Tabular file with unique header values"}),
            },
            "optional": {
                "key_column": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Optional 1-based identifier column to keep leftmost; 0 disables it",
                    },
                ),
                "delimiter": ("STRING", {"default": "\\t", "description": "ASCII field delimiter"}),
                "script_path": (
                    "FILE",
                    {
                        "default": "column_order_header_sort.py",
                        "advanced": True,
                        "description": "Path to the Galaxy column_order_header_sort.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _DatamashBaseNode(CommandNode):
    """Shared metadata and helpers for GNU Datamash Galaxy wrappers."""

    REQUIRED_CONDA_PACKAGES = ["datamash"]
    CATEGORY = "data_transform"
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("out_file",)
    DOCUMENTATION_URL = DATAMASH_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [DATAMASH_CITATION_URL]
    CITATION_TEXT = DATAMASH_CITATION_TEXT
    VERSION = "1.9"
    SHELL = True

    INPUT_EXT_OPTIONS = ["tabular", "tsv", "csv"]

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_ext", "tabular") or "tabular")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_file.tsv"

    @classmethod
    def _separator_args(cls, inputs: dict[str, Any]) -> list[str]:
        return ["-t", ","] if cls._input_ext(inputs) == "csv" else []

    @classmethod
    def _redirect_stdin_stdout(cls, cmd: list[str], inputs: dict[str, Any]) -> str:
        cmd.extend([">", cls._output_path(inputs)])
        input_file = shlex.quote(str(inputs.get("in_file", "")))
        return _shell_join(cmd).replace(" > ", f" < {input_file} > ")

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out_file.tsv"]

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_file", "")).strip():
            return "in_file is required"
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("TSV", {"description": "Input tabular, TSV, or CSV dataset"}),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {"default": "tabular", "options": cls.INPUT_EXT_OPTIONS, "description": "Input file format"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class DatamashOpsNode(_DatamashBaseNode):
    """Perform GNU Datamash statistical operations on tabular data."""

    NODE_ID = "datamash_ops"
    DISPLAY_NAME = "Datamash"
    DESCRIPTION = "Perform statistical and text operations on tabular data, optionally grouped by fields."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Datamash",
        "GNU Datamash",
        "datamash_ops",
        "group by fields",
        "tabular statistics",
        "column operations",
        "sum mean median",
    ]
    REQUIRED_EXECUTABLES = ["datamash"]

    OPERATIONS = [
        "count",
        "sum",
        "min",
        "max",
        "absmin",
        "absmax",
        "mean",
        "pstdev",
        "sstdev",
        "median",
        "q1",
        "q3",
        "iqr",
        "mad",
        "pvar",
        "svar",
        "sskew",
        "pskew",
        "skurt",
        "pkurt",
        "jarque",
        "dpo",
        "mode",
        "antimode",
        "rand",
        "unique",
        "collapse",
        "countunique",
    ]

    @classmethod
    def _operations(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        raw = inputs.get("operations")
        if raw is None or raw == "":
            return [{"op_name": str(inputs.get("op_name", "count") or "count"), "op_column": inputs.get("op_column", 1)}]
        if isinstance(raw, list):
            return [op for op in raw if isinstance(op, dict)]
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["datamash"]
        for key, flag in (
            ("header_in", "--header-in"),
            ("header_out", "--header-out"),
            ("need_sort", "--sort"),
            ("print_full_line", "--full"),
            ("ignore_case", "--ignore-case"),
            ("narm", "--narm"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(cls._separator_args(inputs))
        grouping = str(inputs.get("grouping", "") or "").replace(" ", "")
        if grouping:
            cmd.extend(["--group", grouping])
        for operation in cls._operations(inputs):
            cmd.extend([str(operation.get("op_name", "")), str(operation.get("op_column", ""))])
        return cls._redirect_stdin_stdout(cmd, inputs)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        common = cls._validate_common(inputs)
        if common is not True:
            return common
        grouping = str(inputs.get("grouping", "") or "").replace(" ", "")
        if grouping and not re.fullmatch(r"\d+(,\d+)*", grouping):
            return "grouping must be a comma-separated list of integer fields"
        operations = cls._operations(inputs)
        if not operations:
            return "at least one operation is required"
        for operation in operations:
            op_name = str(operation.get("op_name", "") or "")
            if op_name not in cls.OPERATIONS:
                return f"op_name must be one of: {', '.join(cls.OPERATIONS)}"
            try:
                column = int(operation.get("op_column", ""))
            except (TypeError, ValueError):
                return "op_column must be an integer"
            if column < 1:
                return "op_column must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        spec = super().INPUT_TYPES()
        spec["optional"].update(
            {
                "grouping": (
                    "STRING",
                    {"default": "", "description": "Comma-separated field numbers used to group consecutive rows"},
                ),
                "need_sort": ("BOOLEAN", {"default": False, "description": "Sort input by grouping fields before operation"}),
                "header_in": ("BOOLEAN", {"default": False, "description": "Input file has a header line"}),
                "header_out": ("BOOLEAN", {"default": False, "description": "Print a header line"}),
                "print_full_line": ("BOOLEAN", {"default": False, "description": "Print all fields from input file"}),
                "ignore_case": ("BOOLEAN", {"default": False, "description": "Ignore case while grouping"}),
                "narm": ("BOOLEAN", {"default": False, "description": "Skip NA and NaN values"}),
                "operations": (
                    "JSON",
                    {
                        "default": [{"op_name": "count", "op_column": 1}],
                        "is_list": True,
                        "description": "Datamash operation objects with op_name and op_column",
                    },
                ),
                "op_name": (
                    "STRING",
                    {"default": "count", "options": cls.OPERATIONS, "description": "Operation type for simple forms"},
                ),
                "op_column": ("INT", {"default": 1, "min": 1, "description": "Column number for simple forms"}),
            }
        )
        return spec

class DatamashTransposeNode(_DatamashBaseNode):
    """Transpose rows and columns with GNU Datamash."""

    NODE_ID = "datamash_transpose"
    DISPLAY_NAME = "Transpose"
    REQUIRED_CONDA_PACKAGES = ["datamash", "coreutils"]
    DESCRIPTION = "Transpose rows and columns in a tabular or CSV file with GNU Datamash."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Datamash",
        "GNU Datamash",
        "datamash_transpose",
        "transpose rows columns",
        "matrix transpose",
    ]
    REQUIRED_EXECUTABLES = ["datamash", "split", "paste"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get("in_file", ""))
        output = cls._output_path(inputs)
        if inputs.get("large_file_mode"):
            chunk_count = str(inputs.get("chunk_count", 2) or 2)
            transpose_cmd = _shell_join(["datamash", "transpose", *cls._separator_args(inputs)])
            return (
                f"{_shell_join(['split', '-n', f'l/{chunk_count}', input_file, 'split_input_'])} && "
                f"for chunk in $(ls split_input*); do {transpose_cmd} < $chunk > ${{chunk}}_transposed; done && "
                f"paste split_input_*_transposed > {shlex.quote(output)}"
            )
        cmd = ["datamash", "transpose", *cls._separator_args(inputs)]
        return cls._redirect_stdin_stdout(cmd, inputs)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        common = cls._validate_common(inputs)
        if common is not True:
            return common
        chunk_count = inputs.get("chunk_count", 2)
        if str(chunk_count) != "":
            try:
                value = int(chunk_count)
            except (TypeError, ValueError):
                return "chunk_count must be an integer"
            if value < 1:
                return "chunk_count must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        spec = super().INPUT_TYPES()
        spec["optional"].update(
            {
                "large_file_mode": (
                    "BOOLEAN",
                    {"default": False, "description": "Use split and paste chunking for very large matrices"},
                ),
                "chunk_count": ("INT", {"default": 2, "min": 1, "description": "Number of chunks for large-file transpose"}),
            }
        )
        return spec

class DatamashReverseNode(_DatamashBaseNode):
    """Reverse column order with GNU Datamash."""

    NODE_ID = "datamash_reverse"
    DISPLAY_NAME = "Reverse"
    DESCRIPTION = "Reverse column order in a tabular or CSV file with GNU Datamash."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Datamash",
        "GNU Datamash",
        "datamash_reverse",
        "reverse columns",
        "column order",
    ]
    REQUIRED_EXECUTABLES = ["datamash"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["datamash", "reverse", *cls._separator_args(inputs)]
        return cls._redirect_stdin_stdout(cmd, inputs)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return cls._validate_common(inputs)

class FalcoNode(CommandNode):
    """Run FastQC-compatible read quality control with Falco."""

    NODE_ID = "falco"
    DISPLAY_NAME = "Falco"
    REQUIRED_CONDA_PACKAGES = ["falco"]
    CATEGORY = "qc"
    DESCRIPTION = "Run high-speed FastQC-compatible quality control on FASTQ, SAM, or BAM sequencing reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Falco",
        "falco",
        "FastQC emulation",
        "FASTQ QC",
        "read quality control",
        "sequencing quality report",
    ]
    RETURN_TYPES = ("HTML_REPORT", "TXT", "TXT")
    RETURN_NAMES = ("html_file", "text_file", "summary_file")
    REQUIRED_EXECUTABLES = ["falco"]
    DOCUMENTATION_URL = FALCO_DOCUMENTATION_URL
    CITATION_DOIS = [FALCO_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{FALCO_CITATION_DOI}"]
    CITATION_TEXT = FALCO_CITATION_TEXT
    VERSION = "1.3.2+galaxy0"
    SHELL = True

    INPUT_EXT_OPTIONS = ["fastq", "fastq.gz", "bam", "sam"]

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lower().lstrip(".")
        if explicit:
            return explicit
        suffixes = [suffix.lower() for suffix in Path(str(inputs.get("input_file", ""))).suffixes]
        if ".bam" in suffixes:
            return "bam"
        if ".sam" in suffixes:
            return "sam"
        if ".gz" in suffixes:
            return "fastq.gz"
        return "fastq"

    @staticmethod
    def _input_symlink_name(input_file: Any) -> str:
        return sub(r"[^\w\-]", "_", Path(str(input_file or "")).name) or "input_reads"

    @classmethod
    def _summary_requested(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("generate_summary"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_file = str(inputs.get("input_file", ""))
        input_name = cls._input_symlink_name(input_file)
        cmd = [
            "falco",
            "--outdir",
            out,
        ]
        _add_if_value(cmd, "--contaminants", inputs.get("contaminants"))
        _add_if_value(cmd, "--adapters", inputs.get("adapters"))
        _add_if_value(cmd, "--limits", inputs.get("limits"))
        cmd.extend(["--threads", "${GALAXY_SLOTS:-2}", "--quiet"])
        if inputs.get("nogroup"):
            cmd.append("--nogroup")
        cmd.extend(["-f", cls._input_format(inputs), input_name])
        subsample = inputs.get("subsample", 1)
        if int(subsample) > 1:
            cmd.extend(["-subsample", str(subsample)])
        if inputs.get("bisulfite"):
            cmd.append("-bisulfite")
        if inputs.get("reverse_complement"):
            cmd.append("-reverse-complement")
        if not cls._summary_requested(inputs):
            cmd.append("-skip-summary")
        falco_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-2}'", "${GALAXY_SLOTS:-2}")
        return " && ".join(
            [
                _shell_join(["mkdir", "-p", out]),
                _shell_join(["ln", "-sf", input_file, input_name]),
                falco_cmd,
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "fastqc_report.html", out / "fastqc_data.txt"]
        if cls._summary_requested(inputs):
            outputs.append(out / "summary.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        input_ext = cls._input_format(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        subsample = inputs.get("subsample", 1)
        try:
            subsample_int = int(subsample)
        except (TypeError, ValueError):
            return "subsample must be an integer"
        if subsample_int < 1:
            return "subsample must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTQ", {"description": "FASTQ, FASTQ.GZ, SAM, or BAM reads to inspect"}),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": cls.INPUT_EXT_OPTIONS,
                        "description": "Input format passed to Falco",
                    },
                ),
                "contaminants": (
                    "TSV",
                    {"default": "", "description": "Optional contaminant list with name and sequence columns"},
                ),
                "adapters": (
                    "TSV",
                    {"default": "", "description": "Optional adapter list with name and sequence columns"},
                ),
                "limits": ("TXT", {"default": "", "description": "Optional custom FastQC limits configuration"}),
                "nogroup": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable base grouping for reads longer than 50 bp"},
                ),
                "subsample": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Process only reads whose index is a multiple of this value"},
                ),
                "bisulfite": (
                    "BOOLEAN",
                    {"default": False, "description": "Account for whole-genome bisulfite sequencing base composition"},
                ),
                "reverse_complement": (
                    "BOOLEAN",
                    {"default": False, "description": "Evaluate reads as reverse-complemented"},
                ),
                "generate_summary": ("BOOLEAN", {"default": False, "description": "Emit Falco summary.txt output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
