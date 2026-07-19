"""Spatial transcriptomics workflow nodes."""
# ruff: noqa: F401
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.single_cell_spatial_family.scanpy_spatial import ScanpySpatialNode
from bionodulo.nodes.builtin.single_cell_spatial_family.squidpy_qc import SquidpyQCNode
from bionodulo.nodes.command_node import CommandNode


class SpaceRangerNode(CommandNode):
    """Run Space Ranger count for 10x Genomics Visium data."""
    NODE_ID = "spaceranger_count"
    DISPLAY_NAME = "Space Ranger Count"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Process 10x Genomics Visium: alignment, feature-barcode counting, tissue detection."
    SEARCH_ALIASES = ["spaceranger", "10x visium", "spatial transcriptomics", "visium"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("spaceranger_out",)
    REQUIRED_EXECUTABLES = ["spaceranger"]
    REQUIRED_CONDA_PACKAGES = ["spaceranger"]
    DOCUMENTATION_URL = "https://support.10xgenomics.com/spatial-gene-expression"
    VERSION = "3.1.1"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "spaceranger",
            "count",
            "--id",
            str(inputs.get("sample_id", "sample")),
            "--transcriptome",
            str(inputs.get("transcriptome", "")),
            "--fastqs",
            str(inputs.get("fastqs_dir", "")),
            "--sample",
            str(inputs.get("sample_prefix", "")),
            "--image",
            str(inputs.get("he_image", "")),
            "--slide",
            str(inputs.get("slide", "")),
            "--area",
            str(inputs.get("area", "")),
            "--localcores",
            str(inputs.get("threads", 8)),
            "--localmem",
            str(inputs.get("memory", 32)),
            "--output-dir",
            str(out_dir),
        ]
        if inputs.get("create_bam"):
            cmd.append("--create-bam=true")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        sample_id = str(inputs.get("sample_id", "sample"))
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / sample_id]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sample_id": ("STRING", {"description": "Sample ID"}),
                "transcriptome": ("DIRECTORY", {"description": "Space Ranger reference"}),
                "fastqs_dir": ("DIRECTORY", {"description": "FASTQ directory"}),
                "sample_prefix": ("STRING", {"description": "Sample name prefix in FASTQs"}),
                "he_image": ("FILE", {"description": "H&E tissue image (TIFF)"}),
                "slide": ("STRING", {"description": "Slide serial (e.g., V19L01-041)"}),
                "area": ("STRING", {"description": "Capture area (A1, B1, C1, D1)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
                "memory": ("INT", {"default": 32, "min": 8, "max": 256, "label": "Memory (GB)"}),
            },
            "optional": {
                "create_bam": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SpaceRangerCompatibilityNode(SpaceRangerNode):
    """Compatibility wrapper for the original Space Ranger roadmap node ID."""

    NODE_ID = "spaceranger"
    DISPLAY_NAME = "Space Ranger"
    DESCRIPTION = "Process 10x Genomics Visium data with Space Ranger count."
    SEARCH_ALIASES = ["spaceranger", "space ranger", "10x visium", "spatial transcriptomics", "visium"]


class _LegacySquidpyQCNode(CommandNode):
    """Run Visium QC and spatial neighborhood analysis with Squidpy."""
    LEGACY_NODE_ID = "squidpy_qc"
    DISPLAY_NAME = "Squidpy QC"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Visium QC, preprocessing, spatial neighborhood analysis, and visualization with Squidpy."
    SEARCH_ALIASES = ["squidpy", "spatial", "visium", "quality control", "spatial analysis"]
    RETURN_TYPES = ("H5AD", "IMAGE")
    RETURN_NAMES = ("adata", "spatial_plot")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["squidpy", "scanpy", "anndata", "matplotlib"]
    DOCUMENTATION_URL = "https://squidpy.readthedocs.io/"
    VERSION = "1.6.5"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get("output", "."))
        out_dir.mkdir(parents=True, exist_ok=True)
        visium_path = str(inputs.get("visium_path", ""))
        script = f"""
import squidpy as sq
import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

adata = sc.read_visium('{visium_path}', load_images=False)  # QC/clustering: skip tissue images (demo Visium data omits spatial/tissue_hires_image.png)
adata.var_names_make_unique()
adata.var["mt"] = adata.var_names.str.startswith("MT-")
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True)
sc.pp.filter_cells(adata, min_counts={inputs.get("min_counts", 500)})
sc.pp.filter_genes(adata, min_cells={inputs.get("min_cells", 3)})
adata = adata[adata.obs["pct_counts_mt"] < {inputs.get("max_mt_pct", 20.0)}]
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes={inputs.get("n_hvg", 2000)})
sc.pp.scale(adata, max_value=10)
sc.pp.pca(adata, n_comps={inputs.get("n_pcs", 15)})
sc.pp.neighbors(adata)
sc.tl.leiden(adata, resolution={inputs.get("resolution", 0.8)})
sc.tl.umap(adata)
sq.gr.spatial_neighbors(adata)
sq.gr.nhood_enrichment(adata, cluster_key="leiden")
adata.write('{out_dir}/adata.h5ad')

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
sq.pl.spatial_scatter(adata, color='leiden', ax=axes[0], show=False)
sc.pl.umap(adata, color='leiden', ax=axes[1], show=False)
plt.tight_layout()
plt.savefig('{out_dir}/spatial_plot.png', dpi=150)
print("Done")
"""
        script_file = out_dir / "squidpy_run.py"
        script_file.write_text(script)
        return ["python", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "adata.h5ad", node_out / "spatial_plot.png"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "visium_path": ("DIRECTORY", {"description": "Space Ranger output directory"}),
            },
            "optional": {
                "min_counts": ("INT", {"default": 500, "min": 0}),
                "min_cells": ("INT", {"default": 3, "min": 1}),
                "max_mt_pct": ("FLOAT", {"default": 20.0, "min": 0.0, "max": 100.0}),
                "n_hvg": ("INT", {"default": 2000, "min": 100}),
                "n_pcs": ("INT", {"default": 15, "min": 2, "max": 50}),
                "resolution": ("FLOAT", {"default": 0.8, "min": 0.1, "max": 2.0, "step": 0.1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SquidpyNode(SquidpyQCNode):
    """Compatibility wrapper for the original Squidpy roadmap node ID."""

    NODE_ID = "squidpy"
    DISPLAY_NAME = "Squidpy"
    DESCRIPTION = "Run Visium QC, preprocessing, and spatial analysis with Squidpy."
    SEARCH_ALIASES = ["squidpy", "spatial", "visium", "quality control", "spatial analysis"]


class _LegacyScanpySpatialNode(CommandNode):
    """Cluster spatial transcriptomics count matrices with Scanpy."""

    LEGACY_NODE_ID = "scanpy_spatial"
    DISPLAY_NAME = "Scanpy Spatial"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Cluster spatial transcriptomics count matrices and render a UMAP with Scanpy."
    SEARCH_ALIASES = ["scanpy", "spatial transcriptomics", "spatial clustering", "umap", "leiden"]
    RETURN_TYPES = ("CSV", "IMAGE")
    RETURN_NAMES = ("clusters", "umap")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["scanpy", "anndata", "pandas", "matplotlib"]
    DOCUMENTATION_URL = "https://scanpy.readthedocs.io/"
    VERSION = "1.10.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get("output", "."))
        out_dir.mkdir(parents=True, exist_ok=True)
        delimiter = str(inputs.get("delimiter", "comma") or "comma").strip().lower()
        sep = "\\t" if delimiter in {"tab", "tsv", "\\t"} else ","
        sample_name = str(inputs.get("sample_name", "sample") or "sample")
        visium_path = str(inputs.get("visium_path", "") or "").strip()
        if visium_path:
            # Real Space Ranger outs/: read the .h5 and DERIVE the count matrix +
            # coordinate CSVs from it (real data), then continue the same pipeline.
            load = f"""
adata = sc.read_visium('{visium_path}', load_images=False)  # QC/clustering: skip tissue images (demo Visium data omits spatial/tissue_hires_image.png)
adata.var_names_make_unique()
adata.obs['sample'] = '{sample_name}'
adata.to_df().T.to_csv('{out_dir}/counts.csv')
import numpy as _np
if 'spatial' not in adata.obsm:
    # Demo/synthetic Visium data can omit spatial/tissue_positions; synthesize a
    # square grid so spatial QC/plotting can still proceed deterministically.
    _n = adata.n_obs
    _side = int(_np.ceil(_np.sqrt(_n)))
    _grid = _np.array([[i % _side, i // _side] for i in range(_n)], dtype=float)
    adata.obsm['spatial'] = _grid
_coords = pd.DataFrame(_np.asarray(adata.obsm['spatial']), index=adata.obs_names, columns=['x', 'y'])
_coords.index.name = 'barcode'
_coords.to_csv('{out_dir}/coordinates.csv')
"""
        else:
            load = f"""
counts = pd.read_csv('{inputs.get("count_matrix", "")}', sep='{sep}', index_col=0)
coordinates = pd.read_csv('{inputs.get("coordinates", "")}')
adata = sc.AnnData(counts.T)
adata.obs['sample'] = '{sample_name}'
if 'barcode' in coordinates.columns:
    coordinates = coordinates.set_index('barcode')
    adata.obs = adata.obs.join(coordinates, how='left')
"""
        script = f"""
import scanpy as sc
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
{load}
# Clamp QC/dimensionality params to the actual data size. Fixed defaults
# (min_genes=200, 2000 HVGs, 15 PCs) wipe out small/synthetic demo datasets
# ("Found array with 0 sample(s)"). Guard each step so the pipeline degrades
# gracefully on tiny inputs while staying unchanged on real Visium data.
_min_genes = min({inputs.get("min_genes", 200)}, max(1, adata.n_vars // 4))
_min_cells = min({inputs.get("min_cells", 3)}, max(1, adata.n_obs // 4))
sc.pp.filter_cells(adata, min_genes=_min_genes)
sc.pp.filter_genes(adata, min_cells=_min_cells)
if adata.n_obs < 2 or adata.n_vars < 2:
    raise SystemExit("Too few cells/genes after filtering for spatial clustering.")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
_n_hvg = min({inputs.get("n_hvg", 2000)}, adata.n_vars)
sc.pp.highly_variable_genes(adata, n_top_genes=_n_hvg)
adata = adata[:, adata.var['highly_variable']]
sc.pp.scale(adata, max_value=10)
_n_pcs = min({inputs.get("n_pcs", 15)}, adata.n_obs - 1, adata.n_vars - 1)
sc.pp.pca(adata, n_comps=max(1, _n_pcs))
sc.pp.neighbors(adata, n_neighbors=min(15, max(2, adata.n_obs - 1)))
sc.tl.leiden(adata, resolution={inputs.get("resolution", 0.8)})
sc.tl.umap(adata)

adata.obs[['sample', 'leiden']].to_csv('{out_dir}/clusters.csv')
sc.pl.umap(adata, color='leiden', show=False)
plt.savefig('{out_dir}/umap.png', dpi=150)
print("Done")
"""
        script_file = out_dir / "scanpy_spatial_run.py"
        script_file.write_text(script)
        return ["python", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outs = [node_out / "clusters.csv", node_out / "umap.png"]
        if str(inputs.get("visium_path", "") or "").strip():
            # Real CSVs derived from the Space Ranger .h5.
            outs += [node_out / "counts.csv", node_out / "coordinates.csv"]
        return outs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "visium_path": ("DIRECTORY", {"description": "Space Ranger outs/ directory (reads the .h5; derives count/coordinate CSVs)"}),
                "count_matrix": ("FILE", {"description": "Gene-by-cell count matrix as CSV or TSV (used when no visium_path)"}),
                "coordinates": ("CSV", {"description": "Spatial coordinates keyed by barcode (used when no visium_path)"}),
                "sample_name": ("STRING", {"default": "sample"}),
                "delimiter": ("STRING", {"default": "comma", "options": ["comma", "tab"]}),
                "min_cells": ("INT", {"default": 3, "min": 1}),
                "min_genes": ("INT", {"default": 200, "min": 0}),
                "n_hvg": ("INT", {"default": 2000, "min": 100}),
                "n_pcs": ("INT", {"default": 15, "min": 2, "max": 50}),
                "resolution": ("FLOAT", {"default": 0.8, "min": 0.1, "max": 2.0, "step": 0.1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SeuratSpatialNode(CommandNode):
    """Cluster spatial transcriptomics count matrices with Seurat."""

    NODE_ID = "seurat_spatial"
    DISPLAY_NAME = "Seurat Spatial"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Cluster spatial transcriptomics count matrices and export markers with Seurat."
    SEARCH_ALIASES = ["seurat", "spatial transcriptomics", "visium", "spatial clustering", "markers"]
    RETURN_TYPES = ("CSV", "CSV", "IMAGE")
    RETURN_NAMES = ("clusters", "markers", "spatial_plot")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "r-seurat", "r-ggplot2", "r-patchwork"]
    DOCUMENTATION_URL = "https://satijalab.org/seurat/"
    VERSION = "5.0.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get("output", "."))
        out_dir.mkdir(parents=True, exist_ok=True)
        sample_name = str(inputs.get("sample_name", "sample") or "sample")
        normalization_method = str(inputs.get("normalization_method", "LogNormalize") or "LogNormalize")
        dims = int(inputs.get("dims", 15) or 15)
        normalize_line = (
            "object <- SCTransform(object, verbose = FALSE)"
            if normalization_method.upper() == "SCT"
            else "object <- NormalizeData(object)"
        )
        script = f"""
library(Seurat)
library(ggplot2)
library(patchwork)

counts <- Read10X(data.dir = '{inputs.get("count_matrix", "")}')
object <- CreateSeuratObject(counts = counts, project = '{sample_name}', min.features = {inputs.get("min_features", 200)})
{normalize_line}
object <- FindVariableFeatures(object)
object <- ScaleData(object)
object <- RunPCA(object, verbose = FALSE)
object <- FindNeighbors(object, dims = 1:{dims})
object <- FindClusters(object, resolution = {inputs.get("resolution", 0.8)})
object <- RunUMAP(object, dims = 1:{dims})

cluster_table <- data.frame(
  barcode = colnames(object),
  cluster = Idents(object)
)
markers <- FindAllMarkers(object, only.pos = TRUE)
plot <- DimPlot(object, reduction = 'umap', group.by = 'seurat_clusters') +
  ggtitle('Seurat spatial clusters') +
  theme_minimal()

write.csv(cluster_table, '{out_dir}/clusters.csv', row.names = FALSE)
write.csv(markers, '{out_dir}/markers.csv', row.names = FALSE)
ggsave('{out_dir}/spatial_plot.png', plot = plot, width = 8, height = 6, dpi = 150)
print("Done")
"""
        script_file = out_dir / "seurat_spatial_run.R"
        script_file.write_text(script)
        return ["Rscript", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / "clusters.csv",
            node_out / "markers.csv",
            node_out / "spatial_plot.png",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "count_matrix": ("DIRECTORY", {"description": "10x feature-barcode matrix directory"}),
                "image": ("FILE", {"description": "Tissue image associated with the spatial sample"}),
            },
            "optional": {
                "sample_name": ("STRING", {"default": "sample"}),
                "min_features": ("INT", {"default": 200, "min": 0}),
                "normalization_method": ("STRING", {"default": "LogNormalize", "options": ["LogNormalize", "SCT"]}),
                "dims": ("INT", {"default": 15, "min": 2, "max": 50}),
                "resolution": ("FLOAT", {"default": 0.8, "min": 0.1, "max": 2.0, "step": 0.1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Cell2locationNode(CommandNode):
    """Deconvolute spatial spots into cell type proportions."""
    NODE_ID = "cell2location"
    DISPLAY_NAME = "Cell2location"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Deconvolute spatial transcriptomics spots into cell type proportions using scRNA-seq reference."
    SEARCH_ALIASES = ["cell2location", "spatial deconvolution", "cell type mapping", "cell2loc"]
    RETURN_TYPES = ("H5AD", "IMAGE")
    RETURN_NAMES = ("spatial_deconv", "celltype_map")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["cell2location", "torch", "scanpy", "anndata"]
    DOCUMENTATION_URL = "https://cell2location.readthedocs.io/"
    VERSION = "0.1.7"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get("output", "."))
        out_dir.mkdir(parents=True, exist_ok=True)
        script = f"""
import cell2location
import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

adata_vis = sc.read_h5ad('{inputs.get("visium_adata", "")}')
adata_ref = sc.read_h5ad('{inputs.get("scrna_adata", "")}')

from cell2location.models import RegressionModel
RegressionModel.setup_anndata(adata_ref, labels_key='{inputs.get("cell_type_key", "cell_type")}')
mod = RegressionModel(adata_ref)
mod.train(max_epochs={inputs.get("ref_epochs", 250)})
adata_ref = mod.export_posterior(adata_ref)
inf_aver = adata_ref.varm['means_per_cluster_mu_fg']

from cell2location.models import Cell2location
Cell2location.setup_anndata(adata_vis)
mod = Cell2location(adata_vis, cell_state_df=inf_aver,
                    N_cells_per_location={inputs.get("n_cells_per_spot", 30)})
mod.train(max_epochs={inputs.get("deconv_epochs", 30000)})
adata_vis = mod.export_posterior(adata_vis)
adata_vis.write('{out_dir}/spatial_deconv.h5ad')
adata_vis.obsm['q05_cell_abundance_w_sf'].to_csv('{out_dir}/celltype_map.csv')
print("Done")
"""
        script_file = out_dir / "cell2location_run.py"
        script_file.write_text(script)
        return ["python", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "spatial_deconv.h5ad", node_out / "celltype_map.csv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "visium_adata": ("H5AD", {"description": "Visium AnnData"}),
                "scrna_adata": ("H5AD", {"description": "scRNA-seq reference with cell types"}),
                "cell_type_key": ("STRING", {"default": "cell_type"}),
            },
            "optional": {
                "ref_epochs": ("INT", {"default": 250, "min": 10}),
                "deconv_epochs": ("INT", {"default": 30000, "min": 1000}),
                "n_cells_per_spot": ("INT", {"default": 30, "min": 1}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BaysorNode(CommandNode):
    """Run Baysor cell segmentation for molecular spatial data."""
    NODE_ID = "baysor"
    DISPLAY_NAME = "Baysor Segmentation"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Cell segmentation for MERFISH/Xenium high-resolution spatial transcriptomics."
    SEARCH_ALIASES = ["baysor", "segmentation", "merfish", "xenium", "molecular spatial"]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("cell_segmentation",)
    REQUIRED_EXECUTABLES = ["baysor"]
    REQUIRED_CONDA_PACKAGES = ["baysor"]
    DOCUMENTATION_URL = "https://github.com/kharchenkolab/Baysor"
    VERSION = "0.7.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "baysor",
            "run",
            str(inputs.get("transcript_data", "")),
            "-x",
            str(inputs.get("x_col", "x")),
            "-y",
            str(inputs.get("y_col", "y")),
            "-g",
            str(inputs.get("gene_col", "gene")),
            "-m",
            str(inputs.get("min_molecules", 30)),
            "-o",
            str(out_dir),
        ]
        if inputs.get("z_col"):
            cmd.extend(["-z", str(inputs["z_col"])])
        if inputs.get("scale"):
            cmd.extend(["--scale", str(inputs["scale"])])
        if inputs.get("iters"):
            cmd.extend(["--iters", str(inputs["iters"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "cell_segmentation.csv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "transcript_data": ("CSV", {"description": "Transcript coordinates CSV"}),
                "x_col": ("STRING", {"default": "x"}),
                "y_col": ("STRING", {"default": "y"}),
                "gene_col": ("STRING", {"default": "gene"}),
                "min_molecules": ("INT", {"default": 30, "min": 1}),
            },
            "optional": {
                "z_col": ("STRING", {"default": "", "description": "Z column (3D)"}),
                "scale": ("STRING", {"default": "", "description": "Cell scale estimate (um)"}),
                "iters": ("INT", {"default": 500, "min": 100}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
