"""Spatial transcriptomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

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


class SquidpyQCNode(CommandNode):
    """Run Visium QC and spatial neighborhood analysis with Squidpy."""
    NODE_ID = "squidpy_qc"
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

adata = sc.read_visium('{visium_path}')
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
