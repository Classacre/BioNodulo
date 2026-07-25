"""Focused anndata inspect node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

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

pin_contract(AnnDataInspectNode)

__all__ = ['AnnDataInspectNode']
