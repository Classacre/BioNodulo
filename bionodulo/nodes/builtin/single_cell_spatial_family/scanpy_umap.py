"""Scanpy 1.12.2 Cell Ranger matrix QC and UMAP workflow."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import PythonScriptNode, SCANPY_COMMIT, path_value, validate_int, validate_number


class ScanpyUmapNode(PythonScriptNode):
    """Create QC violin and UMAP plots from a Cell Ranger HDF5 matrix."""

    NODE_ID = "scanpy_umap"
    DISPLAY_NAME = "Scanpy UMAP + QC"
    CATEGORY = "single_cell"
    DESCRIPTION = "Run a source-pinned Scanpy QC, PCA, neighbors, Leiden, and UMAP workflow."
    SEARCH_ALIASES = ["BioNodulo builtin", "Scanpy", "UMAP", "single cell", "Leiden", "QC violin"]
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("umap_png", "qc_violin_png")
    OUTPUT_NODE = True
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
        "src/scanpy/readwrite.py; src/scanpy/preprocessing; src/scanpy/tools/_leiden.py; "
        "src/scanpy/tools/_umap.py"
    )
    REQUIRED_PATH_INPUTS = ("matrix_h5",)
    OUTPUT_FILENAMES = ("umap.png", "qc_violin.png")
    SCRIPT_FILENAME = "scanpy_umap.py"
    PREVIEW_LABELS = ("UMAP (Leiden clusters)", "QC violin")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"matrix_h5": ("FILE", {"description": "Cell Ranger feature-barcode matrix HDF5"})},
            "optional": {
                "min_genes": ("INT", {"default": 200, "min": 0, "max": 5000}),
                "min_cells": ("INT", {"default": 3, "min": 1, "max": 1000}),
                "n_pcs": ("INT", {"default": 30, "min": 2, "max": 100}),
                "n_neighbors": ("INT", {"default": 15, "min": 2, "max": 100}),
                "resolution": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 3.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("min_genes", 200, 0, 5000),
            ("min_cells", 3, 1, 1000),
            ("n_pcs", 30, 2, 100),
            ("n_neighbors", 15, 2, 100),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        return validate_number(inputs.get("resolution", 1.0), "resolution", minimum=0.1, maximum=3.0)

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        return cls._build_script(
            h5=path_value(inputs.get("matrix_h5")),
            min_genes=int(inputs.get("min_genes", 200)),
            min_cells=int(inputs.get("min_cells", 3)),
            n_pcs=int(inputs.get("n_pcs", 30)),
            n_neighbors=int(inputs.get("n_neighbors", 15)),
            resolution=float(inputs.get("resolution", 1.0)),
            umap_png=str(outputs[0]),
            violin_png=str(outputs[1]),
        )

    @staticmethod
    def _build_script(
        *,
        h5: str,
        min_genes: int,
        min_cells: int,
        n_pcs: int,
        n_neighbors: int,
        resolution: float,
        umap_png: str,
        violin_png: str,
    ) -> str:
        return textwrap.dedent(
            f"""\
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import scanpy as sc

            adata = sc.read_10x_h5({h5!r}, gex_only=True)
            adata.var_names_make_unique()
            sc.pp.filter_cells(adata, min_genes={min_genes})
            sc.pp.filter_genes(adata, min_cells={min_cells})
            if adata.n_obs < 2 or adata.n_vars < 2:
                raise SystemExit("Too few cells or genes after filtering for Scanpy UMAP.")
            adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
            sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True)

            sc.pl.violin(
                adata,
                ["n_genes_by_counts", "total_counts", "pct_counts_mt"],
                jitter=0.4,
                multi_panel=True,
                show=False,
            )
            plt.savefig({violin_png!r}, dpi=150, bbox_inches="tight")
            plt.close("all")

            sc.pp.normalize_total(adata, target_sum=1e4)
            sc.pp.log1p(adata)
            sc.pp.highly_variable_genes(adata, n_top_genes=min(2000, adata.n_vars), subset=True)
            sc.pp.scale(adata, max_value=10)
            n_pcs = max(1, min({n_pcs}, adata.n_vars - 1, adata.n_obs - 1))
            sc.pp.pca(adata, n_comps=n_pcs, random_state=0)
            sc.pp.neighbors(adata, n_neighbors=min({n_neighbors}, adata.n_obs - 1), n_pcs=n_pcs, random_state=0)
            sc.tl.umap(adata, random_state=0)
            sc.tl.leiden(
                adata,
                resolution={resolution},
                random_state=0,
                flavor="igraph",
                n_iterations=2,
                directed=False,
            )
            sc.pl.umap(adata, color="leiden", show=False)
            plt.savefig({umap_png!r}, dpi=150, bbox_inches="tight")
            plt.close("all")
            """
        )
