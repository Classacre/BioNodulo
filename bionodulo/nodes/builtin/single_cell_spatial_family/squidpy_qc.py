"""Squidpy 1.8.2 Visium QC and spatial-neighborhood workflow."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import PythonScriptNode, SCANPY_COMMIT, SQUIDPY_COMMIT, path_value, validate_int, validate_number


class SquidpyQCNode(PythonScriptNode):
    """Read a complete Space Ranger outs directory and run spatial QC."""

    NODE_ID = "squidpy_qc"
    DISPLAY_NAME = "Squidpy QC"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Run Visium QC, clustering, and grid-neighborhood enrichment with Squidpy."
    SEARCH_ALIASES = ["BioNodulo builtin", "Squidpy", "spatial", "Visium", "quality control", "spatial analysis"]
    RETURN_TYPES = ("H5AD", "IMAGE")
    RETURN_NAMES = ("adata", "spatial_plot")
    REQUIRED_CONDA_PACKAGES = ["squidpy", "scanpy", "python-igraph", "matplotlib"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "squidpy": "1.8.2",
        "scanpy": "1.12.2",
        "python-igraph": "1.0.0",
        "matplotlib": "3.10.9",
    }
    VERSION = "1.8.2"
    GIT_URL = "https://github.com/scverse/squidpy.git"
    GIT_COMMIT = SQUIDPY_COMMIT
    SCANPY_GIT_COMMIT = SCANPY_COMMIT
    DOCUMENTATION_URL = "https://squidpy.readthedocs.io/en/stable/notebooks/tutorials/tutorial_visium_hne.html"
    UPSTREAM_SOURCE = (
        "src/squidpy/read/_read.py; src/squidpy/gr/_build.py:spatial_neighbors_grid; "
        "src/squidpy/gr/_nhood.py; src/squidpy/pl/_spatial.py"
    )
    REQUIRED_PATH_INPUTS = ("visium_path",)
    OUTPUT_FILENAMES = ("adata.h5ad", "spatial_plot.png")
    SCRIPT_FILENAME = "squidpy_qc.py"
    PREVIEW_LABELS = (None, "Squidpy spatial QC")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "visium_path": (
                    "DIRECTORY",
                    {"description": "Complete Space Ranger outs directory with matrix and spatial files"},
                )
            },
            "optional": {
                "min_counts": ("INT", {"default": 500, "min": 0}),
                "min_cells": ("INT", {"default": 3, "min": 1}),
                "max_mt_pct": ("FLOAT", {"default": 20.0, "min": 0.0, "max": 100.0}),
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
        for key, default, minimum, maximum in (
            ("min_counts", 500, 0, None),
            ("min_cells", 3, 1, None),
            ("n_hvg", 2000, 100, None),
            ("n_pcs", 15, 2, 50),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        validation = validate_number(inputs.get("max_mt_pct", 20.0), "max_mt_pct", minimum=0, maximum=100)
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
            import squidpy as sq

            adata = sq.read.visium({path_value(inputs.get('visium_path'))!r}, load_images=True)
            adata.var_names_make_unique()
            adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
            sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True)
            sc.pp.filter_cells(adata, min_counts={int(inputs.get('min_counts', 500))})
            sc.pp.filter_genes(adata, min_cells={int(inputs.get('min_cells', 3))})
            adata = adata[adata.obs["pct_counts_mt"] < {float(inputs.get('max_mt_pct', 20.0))}].copy()
            if adata.n_obs < 2 or adata.n_vars < 2:
                raise SystemExit("Too few spots or genes after filtering for Squidpy QC.")
            adata.raw = adata.copy()
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
            sq.gr.spatial_neighbors_grid(adata, n_neighs=6, n_rings=1)
            sq.gr.nhood_enrichment(adata, cluster_key="leiden", seed=0)
            adata.write_h5ad({str(outputs[0])!r})

            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            sq.pl.spatial_scatter(adata, color="leiden", ax=axes[0])
            sc.pl.umap(adata, color="leiden", ax=axes[1], show=False)
            plt.tight_layout()
            plt.savefig({str(outputs[1])!r}, dpi=150, bbox_inches="tight")
            plt.close("all")
            """
        )
