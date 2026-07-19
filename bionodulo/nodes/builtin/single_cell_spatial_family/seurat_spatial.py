"""Seurat 5.3.1 Visium spatial clustering contract."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.r_family.adapter import PreparedRScriptNode, path_value, r_string

from .adapter import validate_int, validate_number


class SeuratSpatialNode(PreparedRScriptNode):
    """Load a complete Space Ranger ``outs`` directory and cluster its spots."""

    NODE_ID = "seurat_spatial"
    DISPLAY_NAME = "Seurat Spatial"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Load complete Space Ranger output and cluster Visium spots with Seurat 5.3.1."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seurat", "Visium", "spatial clustering", "markers"]
    RETURN_TYPES = ("CSV", "CSV", "IMAGE")
    RETURN_NAMES = ("clusters", "markers", "spatial_plot")
    REQUIRED_CONDA_PACKAGES = ["r-base", "r-seurat", "r-ggplot2"]
    CONDA_PACKAGE_CONSTRAINTS = {"r-base": "4.5.3", "r-seurat": "5.3.1", "r-ggplot2": "4.0.3"}
    VERSION = "5.3.1"
    GIT_URL = "https://github.com/satijalab/seurat.git"
    GIT_COMMIT = "ca0ab0f9dd6863fac4a6af87280d48c8f9cc9b95"
    SOURCE_TAG = "v5.3.1"
    DOCUMENTATION_URL = "https://satijalab.org/seurat/articles/spatial_vignette.html"
    UPSTREAM_SOURCE = "R/preprocessing.R:Load10X_Spatial; vignettes/seurat5_spatial_vignette.Rmd"
    PACKAGE_CONSTRAINT = "conda-forge r-seurat=5.3.1"
    OUTPUT_FILENAMES = ("clusters.csv", "markers.csv", "spatial_plot.png")
    SCRIPT_FILENAME = "seurat_spatial.R"
    REQUIRED_PATH_INPUTS = ("visium_path",)
    PREVIEW_LABELS = (None, None, "Seurat spatial clusters")
    EXIT_SEMANTICS = (
        "Rscript exit code 0 plus clusters.csv, markers.csv, and spatial_plot.png is success; "
        "incomplete Space Ranger data or missing outputs fail the node."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "visium_path": (
                    "DIRECTORY",
                    {
                        "description": "Complete Space Ranger outs directory with matrix, spatial coordinates, and images"
                    },
                )
            },
            "optional": {
                "sample_name": ("STRING", {"default": "sample"}),
                "min_features": ("INT", {"default": 200, "min": 0}),
                "normalization_method": ("STRING", {"default": "SCT", "options": ["SCT", "LogNormalize"]}),
                "dims": ("INT", {"default": 30, "min": 2, "max": 100}),
                "resolution": ("FLOAT", {"default": 0.8, "min": 0.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("sample_name", "sample") or "").strip():
            return "Input 'sample_name' must not be empty"
        if str(inputs.get("normalization_method", "SCT")) not in {"SCT", "LogNormalize"}:
            return "Input 'normalization_method' must be one of: SCT, LogNormalize"
        validation = validate_int(inputs.get("min_features", 200), "min_features", minimum=0)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("dims", 30), "dims", minimum=2, maximum=100)
        if validation is not True:
            return validation
        return validate_number(inputs.get("resolution", 0.8), "resolution", minimum=0.0)

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        normalization = str(inputs.get("normalization_method", "SCT"))
        dims = int(inputs.get("dims", 30))
        if normalization == "SCT":
            normalize = textwrap.dedent(
                f"""\
                object <- SCTransform(object, assay = "Spatial", verbose = FALSE)
                object <- RunPCA(object, assay = "SCT", npcs = {dims}, verbose = FALSE)
                DefaultAssay(object) <- "SCT"
                """
            ).strip()
        else:
            normalize = textwrap.dedent(
                f"""\
                object <- NormalizeData(object, assay = "Spatial", verbose = FALSE)
                object <- FindVariableFeatures(object, assay = "Spatial", verbose = FALSE)
                object <- ScaleData(object, assay = "Spatial", verbose = FALSE)
                object <- RunPCA(object, assay = "Spatial", npcs = {dims}, verbose = FALSE)
                DefaultAssay(object) <- "Spatial"
                """
            ).strip()
        return textwrap.dedent(
            f"""\
            suppressPackageStartupMessages(library(Seurat))

            object <- Load10X_Spatial(
              data.dir = {r_string(path_value(inputs.get("visium_path")))},
              assay = "Spatial",
              slice = {r_string(inputs.get("sample_name", "sample"))},
              filter.matrix = TRUE
            )
            object$sample <- {r_string(inputs.get("sample_name", "sample"))}
            keep <- colnames(object)[object$nFeature_Spatial >= {int(inputs.get("min_features", 200))}]
            if (length(keep) < 2) {{
              stop("Too few Visium spots remain after min_features filtering")
            }}
            object <- subset(object, cells = keep)

            {normalize}
            dims_use <- seq_len(min({dims}, ncol(Embeddings(object[["pca"]]))) )
            if (length(dims_use) < 2) {{
              stop("PCA produced fewer than two usable dimensions")
            }}
            object <- FindNeighbors(object, reduction = "pca", dims = dims_use, verbose = FALSE)
            object <- FindClusters(object, resolution = {float(inputs.get("resolution", 0.8))}, verbose = FALSE)
            object <- RunUMAP(object, reduction = "pca", dims = dims_use, seed.use = 0, verbose = FALSE)

            cluster_table <- data.frame(
              barcode = colnames(object),
              cluster = as.character(Idents(object)),
              stringsAsFactors = FALSE
            )
            markers <- FindAllMarkers(object, only.pos = TRUE, verbose = FALSE)
            spatial_plot <- SpatialDimPlot(object, label = TRUE, label.size = 3)

            write.csv(cluster_table, {r_string(outputs[0])}, row.names = FALSE)
            write.csv(markers, {r_string(outputs[1])}, row.names = FALSE)
            ggplot2::ggsave({r_string(outputs[2])}, plot = spatial_plot, width = 8, height = 6, dpi = 150)
            """
        )
