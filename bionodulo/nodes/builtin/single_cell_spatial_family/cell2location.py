"""Cell2location 0.1.5 spatial deconvolution contract."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from .adapter import PythonScriptNode, validate_int, validate_number


class Cell2LocationNode(PythonScriptNode):
    """Map source-pinned single-cell signatures onto spatial observations."""

    NODE_ID = "cell2location"
    DISPLAY_NAME = "Cell2location"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Deconvolute spatial transcriptomics spots with Cell2location 0.1.5."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "cell2location",
        "spatial deconvolution",
        "cell type mapping",
        "cell2loc",
    ]
    RETURN_TYPES = ("H5AD", "CSV")
    RETURN_NAMES = ("spatial_deconv", "celltype_map")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRES_GPU = True
    VERSION = "0.1.5"
    GIT_URL = "https://github.com/BayraktarLab/cell2location.git"
    GIT_COMMIT = "20afdf2ddbd651434e664129547adb8a204044fc"
    SOURCE_TAG = "v0.1.5"
    DOCUMENTATION_URL = "https://cell2location.readthedocs.io/en/latest/cell2location_tutorial.html"
    UPSTREAM_SOURCE = (
        "docs/notebooks/cell2location_tutorial.ipynb; "
        "cell2location/models/reference/_reference_model.py; "
        "cell2location/models/_cell2location_model.py"
    )
    PACKAGE_CONSTRAINT = (
        "external Python environment with PyPI cell2location==0.1.5, Python>=3.10, scvi-tools>=1.3.0, and torch>=1.9.0"
    )
    ENVIRONMENT = {
        "provisioning": "external_pypi_environment",
        "python": ">=3.10",
        "packages": {
            "cell2location": "0.1.5",
            "scvi-tools": ">=1.3.0",
            "torch": ">=1.9.0",
            "scanpy": ">=1.5.1",
        },
        "gpu": "optional; seeded CUDA kernels may still be platform-dependent",
    }
    OUTPUT_FILENAMES = ("spatial_deconv.h5ad", "celltype_map.csv")
    SCRIPT_FILENAME = "cell2location_run.py"
    REQUIRED_PATH_INPUTS = ("visium_adata", "scrna_adata")
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "Python exit code 0 plus the deconvolved H5AD and q05 abundance CSV is success; "
        "missing signatures, no shared genes, training errors, or missing outputs fail the node."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "visium_adata": ("H5AD", {"description": "Spatial count AnnData object"}),
                "scrna_adata": ("H5AD", {"description": "Single-cell reference AnnData object"}),
                "cell_type_key": ("STRING", {"default": "cell_type"}),
            },
            "optional": {
                "ref_epochs": ("INT", {"default": 250, "min": 1}),
                "deconv_epochs": ("INT", {"default": 30000, "min": 1}),
                "n_cells_per_spot": ("INT", {"default": 30, "min": 1}),
                "detection_alpha": (
                    "FLOAT",
                    {
                        "default": 20.0,
                        "min": 0.0,
                        "description": "Detection-sensitivity regularisation; upstream recommends testing 20 and 200",
                    },
                ),
                "seed": ("INT", {"default": 0, "min": 0, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("cell_type_key", "cell_type") or "").strip():
            return "Input 'cell_type_key' must not be empty"
        for key, default in (("ref_epochs", 250), ("deconv_epochs", 30000), ("n_cells_per_spot", 30)):
            validation = validate_int(inputs.get(key, default), key, minimum=1)
            if validation is not True:
                return validation
        validation = validate_number(inputs.get("detection_alpha", 20.0), "detection_alpha", minimum=0.0)
        if validation is not True:
            return validation
        if float(inputs.get("detection_alpha", 20.0)) <= 0:
            return "Input 'detection_alpha' must be greater than 0"
        return validate_int(inputs.get("seed", 0), "seed", minimum=0)

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        visium = json.dumps(str(inputs.get("visium_adata", "")), ensure_ascii=True)
        reference = json.dumps(str(inputs.get("scrna_adata", "")), ensure_ascii=True)
        cell_type_key = json.dumps(str(inputs.get("cell_type_key", "cell_type")), ensure_ascii=True)
        output_h5ad = json.dumps(str(outputs[0]), ensure_ascii=True)
        output_csv = json.dumps(str(outputs[1]), ensure_ascii=True)
        return textwrap.dedent(
            f"""\
            import os
            import random

            seed = {int(inputs.get("seed", 0))}
            os.environ["PYTHONHASHSEED"] = str(seed)

            import numpy as np
            import pandas as pd
            import scanpy as sc
            import scvi
            import torch
            from cell2location.models import Cell2location, RegressionModel

            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            scvi.settings.seed = seed

            adata_vis = sc.read_h5ad({visium})
            adata_ref = sc.read_h5ad({reference})
            cell_type_key = {cell_type_key}
            if cell_type_key not in adata_ref.obs:
                raise KeyError(f"Reference AnnData is missing obs column {{cell_type_key!r}}")
            if adata_ref.var_names.has_duplicates or adata_vis.var_names.has_duplicates:
                raise ValueError("Cell2location requires unique reference and spatial gene names")

            RegressionModel.setup_anndata(adata=adata_ref, labels_key=cell_type_key)
            reference_model = RegressionModel(adata_ref)
            reference_model.train(max_epochs={int(inputs.get("ref_epochs", 250))})
            adata_ref = reference_model.export_posterior(adata_ref)

            factor_names = [str(name) for name in adata_ref.uns["mod"]["factor_names"]]
            signature_key = "means_per_cluster_mu_fg"
            signature_columns = [f"{{signature_key}}_{{name}}" for name in factor_names]
            if signature_key in adata_ref.varm:
                inf_aver = pd.DataFrame(adata_ref.varm[signature_key], index=adata_ref.var_names).copy()
                if all(name in inf_aver.columns for name in signature_columns):
                    inf_aver = inf_aver.loc[:, signature_columns]
                elif inf_aver.shape[1] != len(factor_names):
                    raise ValueError("Reference varm signature columns do not match exported factor names")
            elif all(name in adata_ref.var.columns for name in signature_columns):
                inf_aver = adata_ref.var.loc[:, signature_columns].copy()
            else:
                raise KeyError("Reference posterior lacks means_per_cluster_mu_fg signatures in varm or var")
            inf_aver.columns = factor_names

            reference_genes = set(inf_aver.index)
            shared_genes = [gene for gene in adata_vis.var_names if gene in reference_genes]
            if not shared_genes:
                raise ValueError("Spatial and reference AnnData objects have no genes in common")
            adata_vis = adata_vis[:, shared_genes].copy()
            inf_aver = inf_aver.loc[shared_genes, :]

            Cell2location.setup_anndata(adata=adata_vis)
            spatial_model = Cell2location(
                adata_vis,
                cell_state_df=inf_aver,
                N_cells_per_location={int(inputs.get("n_cells_per_spot", 30))},
                detection_alpha={float(inputs.get("detection_alpha", 20.0))},
            )
            spatial_model.train(max_epochs={int(inputs.get("deconv_epochs", 30000))})
            adata_vis = spatial_model.export_posterior(adata_vis)

            abundance_key = "q05_cell_abundance_w_sf"
            if abundance_key in adata_vis.obsm:
                abundance = pd.DataFrame(adata_vis.obsm[abundance_key], index=adata_vis.obs_names).copy()
            else:
                abundance_columns = [f"q05cell_abundance_w_sf_{{name}}" for name in factor_names]
                if not all(name in adata_vis.obs for name in abundance_columns):
                    raise KeyError("Cell2location posterior lacks q05 cell-abundance estimates")
                abundance = adata_vis.obs.loc[:, abundance_columns].copy()
            if abundance.shape[1] != len(factor_names):
                raise ValueError("q05 cell-abundance columns do not match exported factor names")
            abundance.columns = factor_names
            abundance.index.name = "spot"
            adata_vis.obsm[abundance_key] = abundance
            adata_vis.write_h5ad({output_h5ad})
            abundance.to_csv({output_csv})
            """
        )
