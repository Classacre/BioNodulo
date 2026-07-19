"""Focused anndata io node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

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

pin_contract(AnnDataExportNode)
pin_contract(AnnDataImportNode)

__all__ = ['AnnDataExportNode', 'AnnDataImportNode']
