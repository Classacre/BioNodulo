"""Scanpy 1.12.2 spatial H5AD clustering and UMAP export."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import PythonScriptNode, SCANPY_COMMIT, path_value, validate_int, validate_number


class ScanpySpatialNode(PythonScriptNode):
    """Cluster a spatial H5AD object and export barcode-level assignments."""

    NODE_ID = "scanpy_spatial"
    DISPLAY_NAME = "Scanpy Spatial"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Cluster a spatial AnnData object and export Leiden assignments plus a UMAP."
    SEARCH_ALIASES = ["BioNodulo builtin", "Scanpy", "spatial transcriptomics", "spatial clustering", "UMAP", "Leiden"]
    RETURN_TYPES = ("CSV", "IMAGE")
    RETURN_NAMES = ("clusters", "umap")
    REQUIRED_CONDA_PACKAGES = ["scanpy", "python-igraph", "matplotlib"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "scanpy": "1.12.2",
        "python-igraph": "1.0.0",
        "matplotlib": "3.10.9",
    }
    VERSION = "1.12.2"
    GIT_URL = "https://github.com/scverse/scanpy.git"
    GIT_COMMIT = SCANPY_COMMIT
    DOCUMENTATION_URL = "https://scanpy.readthedocs.io/en/stable/tutorials/basics/clustering.html"
    UPSTREAM_SOURCE = (
        "src/scanpy/readwrite.py:read_h5ad; src/scanpy/preprocessing; "
        "src/scanpy/tools/_leiden.py; src/scanpy/tools/_umap.py"
    )
    REQUIRED_PATH_INPUTS = ("adata",)
    OUTPUT_FILENAMES = ("clusters.csv", "umap.png")
    SCRIPT_FILENAME = "scanpy_spatial.py"
    PREVIEW_LABELS = (None, "Scanpy spatial UMAP")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"adata": ("H5AD", {"description": "Spatial AnnData with raw counts or .raw counts"})},
            "optional": {
                "sample_name": ("STRING", {"default": "sample"}),
                "min_cells": ("INT", {"default": 3, "min": 1}),
                "min_genes": ("INT", {"default": 200, "min": 0}),
                "n_hvg": ("INT", {"default": 2000, "min": 100}),
                "n_pcs": ("INT", {"default": 15, "min": 2, "max": 50}),
                "resolution": ("FLOAT", {"default": 0.8, "min": 0.1, "max": 2.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("sample_name", "sample") or "").strip():
            return "Input 'sample_name' must be non-empty"
        for key, default, minimum, maximum in (
            ("min_cells", 3, 1, None),
            ("min_genes", 200, 0, None),
            ("n_hvg", 2000, 100, None),
            ("n_pcs", 15, 2, 50),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        return validate_number(inputs.get("resolution", 0.8), "resolution", minimum=0.1, maximum=2.0)

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        return textwrap.dedent(
            f"""\
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import scanpy as sc

            adata = sc.read_h5ad({path_value(inputs.get('adata'))!r})
            if adata.raw is not None:
                adata = adata.raw.to_adata()
            adata.var_names_make_unique()
            adata.obs["sample"] = {str(inputs.get('sample_name', 'sample'))!r}
            sc.pp.filter_cells(adata, min_genes={int(inputs.get('min_genes', 200))})
            sc.pp.filter_genes(adata, min_cells={int(inputs.get('min_cells', 3))})
            if adata.n_obs < 2 or adata.n_vars < 2:
                raise SystemExit("Too few spots or genes after filtering for Scanpy spatial clustering.")
            sc.pp.normalize_total(adata, target_sum=1e4)
            sc.pp.log1p(adata)
            sc.pp.highly_variable_genes(
                adata,
                n_top_genes=min({int(inputs.get('n_hvg', 2000))}, adata.n_vars),
                subset=True,
            )
            sc.pp.scale(adata, max_value=10)
            n_pcs = max(1, min({int(inputs.get('n_pcs', 15))}, adata.n_obs - 1, adata.n_vars - 1))
            sc.pp.pca(adata, n_comps=n_pcs, random_state=0)
            sc.pp.neighbors(adata, n_neighbors=min(15, adata.n_obs - 1), n_pcs=n_pcs, random_state=0)
            sc.tl.umap(adata, random_state=0)
            sc.tl.leiden(
                adata,
                resolution={float(inputs.get('resolution', 0.8))},
                random_state=0,
                flavor="igraph",
                n_iterations=2,
                directed=False,
            )
            adata.obs[["sample", "leiden"]].to_csv({str(outputs[0])!r}, index_label="barcode")
            sc.pl.umap(adata, color="leiden", show=False)
            plt.savefig({str(outputs[1])!r}, dpi=150, bbox_inches="tight")
            plt.close("all")
            """
        )
