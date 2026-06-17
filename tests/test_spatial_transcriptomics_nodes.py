from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_spaceranger_count_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["spaceranger_count"]
    assert node_info["display_name"] == "Space Ranger Count"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Process 10x Genomics Visium")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["spaceranger_out"]
    assert node_info["required_executables"] == ["spaceranger"]
    assert node_info["required_conda_packages"] == ["spaceranger"]
    assert node_info["experimental"] is True
    assert "spaceranger" in node_info["search_aliases"]
    assert "10x visium" in node_info["search_aliases"]
    assert "spatial transcriptomics" in node_info["search_aliases"]
    assert "visium" in node_info["search_aliases"]
    assert info["spaceranger"]["display_name"] == "Space Ranger"
    assert info["spaceranger"]["category"] == "spatial_transcriptomics"
    assert info["spaceranger"]["output"] == ["DIRECTORY"]
    assert info["spaceranger"]["output_name"] == ["spaceranger_out"]
    assert info["spaceranger"]["required_executables"] == ["spaceranger"]
    assert info["spaceranger"]["required_conda_packages"] == ["spaceranger"]
    assert info["spaceranger"]["experimental"] is True
    assert issubclass(registry.get("spaceranger"), registry.get("spaceranger_count"))

    inputs = node_info["input"]
    assert set(inputs["required"]) == {
        "sample_id",
        "transcriptome",
        "fastqs_dir",
        "sample_prefix",
        "he_image",
        "slide",
        "area",
        "threads",
        "memory",
    }
    assert set(inputs["optional"]) == {"create_bam"}


def test_spaceranger_count_renders_full_count_command() -> None:
    node_class = _node_class("spaceranger_count")

    cmd = node_class.render_command({
        "sample_id": "visium_sample",
        "transcriptome": "/refs/spaceranger_GRCh38",
        "fastqs_dir": "/data/fastqs",
        "sample_prefix": "sampleA",
        "he_image": "/data/tissue.tif",
        "slide": "V19L01-041",
        "area": "A1",
        "threads": 12,
        "memory": 48,
        "create_bam": True,
        "output": "/tmp/run/spaceranger_count",
    })

    assert cmd == [
        "spaceranger",
        "count",
        "--id",
        "visium_sample",
        "--transcriptome",
        "/refs/spaceranger_GRCh38",
        "--fastqs",
        "/data/fastqs",
        "--sample",
        "sampleA",
        "--image",
        "/data/tissue.tif",
        "--slide",
        "V19L01-041",
        "--area",
        "A1",
        "--localcores",
        "12",
        "--localmem",
        "48",
        "--output-dir",
        "/tmp/run/spaceranger_count",
        "--create-bam=true",
    ]


def test_spaceranger_count_omits_create_bam_when_disabled() -> None:
    node_class = _node_class("spaceranger_count")

    cmd = node_class.render_command({
        "sample_id": "visium_sample",
        "transcriptome": "/refs/spaceranger_GRCh38",
        "fastqs_dir": "/data/fastqs",
        "sample_prefix": "sampleA",
        "he_image": "/data/tissue.tif",
        "slide": "V19L01-041",
        "area": "A1",
        "threads": 8,
        "memory": 32,
        "create_bam": False,
        "output": "/tmp/run/spaceranger_count",
    })

    assert "--create-bam=true" not in cmd
    assert cmd[-2:] == ["--output-dir", "/tmp/run/spaceranger_count"]


def test_spaceranger_count_plans_output_directory() -> None:
    node_class = _node_class("spaceranger_count")

    outputs = node_class.PLAN_OUTPUTS({"sample_id": "visium_sample"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/spaceranger_count/visium_sample",
    ]


def test_spaceranger_count_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["spaceranger"] == "spaceranger"
    assert PACKAGE_MIN_VERSIONS["spaceranger"] == ">=3.1"


def test_squidpy_qc_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["squidpy_qc"]
    assert node_info["display_name"] == "Squidpy QC"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Visium QC")
    assert node_info["output"] == ["H5AD", "IMAGE"]
    assert node_info["output_name"] == ["adata", "spatial_plot"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["squidpy", "scanpy", "anndata", "matplotlib"]
    assert "squidpy" in node_info["search_aliases"]
    assert "quality control" in node_info["search_aliases"]
    assert "spatial analysis" in node_info["search_aliases"]
    assert info["squidpy"]["display_name"] == "Squidpy"
    assert info["squidpy"]["category"] == "spatial_transcriptomics"
    assert info["squidpy"]["output"] == ["H5AD", "IMAGE"]
    assert info["squidpy"]["output_name"] == ["adata", "spatial_plot"]
    assert info["squidpy"]["required_executables"] == ["python"]
    assert info["squidpy"]["required_conda_packages"] == ["squidpy", "scanpy", "anndata", "matplotlib"]
    assert issubclass(registry.get("squidpy"), registry.get("squidpy_qc"))

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"visium_path"}
    assert set(inputs["optional"]) == {
        "min_counts",
        "min_cells",
        "max_mt_pct",
        "n_hvg",
        "n_pcs",
        "resolution",
    }


def test_squidpy_qc_writes_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("squidpy_qc")
    output_dir = tmp_path / "squidpy_qc"

    cmd = node_class.render_command({
        "visium_path": "/data/spaceranger/outs",
        "min_counts": 750,
        "min_cells": 5,
        "max_mt_pct": 15.5,
        "n_hvg": 1500,
        "n_pcs": 20,
        "resolution": 1.2,
        "output": str(output_dir),
    })

    script_file = output_dir / "squidpy_run.py"
    assert cmd == ["python", str(script_file)]
    script = script_file.read_text()
    assert "import squidpy as sq" in script
    assert "import scanpy as sc" in script
    assert "matplotlib.use('Agg')" in script
    assert "adata = sc.read_visium('/data/spaceranger/outs')" in script
    assert "sc.pp.filter_cells(adata, min_counts=750)" in script
    assert "sc.pp.filter_genes(adata, min_cells=5)" in script
    assert 'adata = adata[adata.obs["pct_counts_mt"] < 15.5]' in script
    assert "sc.pp.highly_variable_genes(adata, n_top_genes=1500)" in script
    assert "sc.pp.pca(adata, n_comps=20)" in script
    assert "sc.tl.leiden(adata, resolution=1.2)" in script
    assert "sq.gr.spatial_neighbors(adata)" in script
    assert f"adata.write('{output_dir}/adata.h5ad')" in script
    assert f"plt.savefig('{output_dir}/spatial_plot.png', dpi=150)" in script


def test_squidpy_qc_plans_outputs() -> None:
    node_class = _node_class("squidpy_qc")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/squidpy_qc/adata.h5ad",
        "/tmp/run/squidpy_qc/spatial_plot.png",
    ]


def test_squidpy_qc_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["python"] == "python"
    assert PACKAGE_MIN_VERSIONS["squidpy"] == ">=1.6"
    assert PACKAGE_MIN_VERSIONS["scanpy"] == ">=1.10"
    assert PACKAGE_MIN_VERSIONS["anndata"] == ">=0.10"
    assert PACKAGE_MIN_VERSIONS["matplotlib"] == ">=3.8"


def test_scanpy_spatial_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["scanpy_spatial"]
    assert node_info["display_name"] == "Scanpy Spatial"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Cluster spatial transcriptomics")
    assert node_info["output"] == ["CSV", "IMAGE"]
    assert node_info["output_name"] == ["clusters", "umap"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["scanpy", "anndata", "pandas", "matplotlib"]
    assert "scanpy" in node_info["search_aliases"]
    assert "spatial transcriptomics" in node_info["search_aliases"]

    inputs = node_info["input"]
    # All inputs optional now: visium_path (real .h5) OR count_matrix+coordinates CSV.
    assert set(inputs["required"]) == set()
    assert {"visium_path", "count_matrix", "coordinates"}.issubset(set(inputs["optional"]))


def test_scanpy_spatial_writes_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("scanpy_spatial")
    output_dir = tmp_path / "scanpy_spatial"

    cmd = node_class.render_command({
        "count_matrix": "/data/counts.tsv",
        "coordinates": "/data/spatial.csv",
        "sample_name": "sampleA",
        "delimiter": "tab",
        "min_cells": 4,
        "min_genes": 250,
        "n_hvg": 1200,
        "n_pcs": 18,
        "resolution": 0.7,
        "output": str(output_dir),
    })

    script_file = output_dir / "scanpy_spatial_run.py"
    assert cmd == ["python", str(script_file)]
    script = script_file.read_text()
    assert "import scanpy as sc" in script
    assert "import pandas as pd" in script
    assert "matplotlib.use('Agg')" in script
    assert "counts = pd.read_csv('/data/counts.tsv', sep='\\t', index_col=0)" in script
    assert "coordinates = pd.read_csv('/data/spatial.csv')" in script
    assert "adata = sc.AnnData(counts.T)" in script
    assert "sc.pp.filter_cells(adata, min_genes=250)" in script
    assert "sc.pp.filter_genes(adata, min_cells=4)" in script
    assert "sc.pp.highly_variable_genes(adata, n_top_genes=1200)" in script
    assert "sc.pp.pca(adata, n_comps=18)" in script
    assert "sc.tl.leiden(adata, resolution=0.7)" in script
    assert f"adata.obs[['sample', 'leiden']].to_csv('{output_dir}/clusters.csv')" in script
    assert f"plt.savefig('{output_dir}/umap.png', dpi=150)" in script


def test_scanpy_spatial_plans_outputs() -> None:
    node_class = _node_class("scanpy_spatial")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/scanpy_spatial/clusters.csv",
        "/tmp/run/scanpy_spatial/umap.png",
    ]


def test_scanpy_spatial_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["python"] == "python"
    assert PACKAGE_MIN_VERSIONS["scanpy"] == ">=1.10"
    assert PACKAGE_MIN_VERSIONS["anndata"] == ">=0.10"
    assert PACKAGE_MIN_VERSIONS["pandas"] == ">=2.2"
    assert PACKAGE_MIN_VERSIONS["matplotlib"] == ">=3.8"


def test_seurat_spatial_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["seurat_spatial"]
    assert node_info["display_name"] == "Seurat Spatial"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Cluster spatial transcriptomics")
    assert node_info["output"] == ["CSV", "CSV", "IMAGE"]
    assert node_info["output_name"] == ["clusters", "markers", "spatial_plot"]
    assert node_info["required_executables"] == ["Rscript"]
    assert node_info["required_conda_packages"] == ["r-base", "r-seurat", "r-ggplot2", "r-patchwork"]
    assert "seurat" in node_info["search_aliases"]
    assert "spatial transcriptomics" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"count_matrix", "image"}
    assert set(inputs["optional"]) == {
        "sample_name",
        "min_features",
        "normalization_method",
        "dims",
        "resolution",
    }


def test_seurat_spatial_writes_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("seurat_spatial")
    output_dir = tmp_path / "seurat_spatial"

    cmd = node_class.render_command({
        "count_matrix": "/data/filtered_feature_bc_matrix",
        "image": "/data/tissue.png",
        "sample_name": "sampleA",
        "min_features": 300,
        "normalization_method": "SCT",
        "dims": 20,
        "resolution": 0.9,
        "output": str(output_dir),
    })

    script_file = output_dir / "seurat_spatial_run.R"
    assert cmd == ["Rscript", str(script_file)]
    script = script_file.read_text()
    assert "library(Seurat)" in script
    assert "library(ggplot2)" in script
    assert "counts <- Read10X(data.dir = '/data/filtered_feature_bc_matrix')" in script
    assert "object <- CreateSeuratObject(counts = counts, project = 'sampleA', min.features = 300)" in script
    assert "object <- SCTransform(object, verbose = FALSE)" in script
    assert "object <- RunPCA(object, verbose = FALSE)" in script
    assert "object <- FindNeighbors(object, dims = 1:20)" in script
    assert "object <- FindClusters(object, resolution = 0.9)" in script
    assert "markers <- FindAllMarkers(object, only.pos = TRUE)" in script
    assert f"write.csv(cluster_table, '{output_dir}/clusters.csv', row.names = FALSE)" in script
    assert f"write.csv(markers, '{output_dir}/markers.csv', row.names = FALSE)" in script
    assert f"ggsave('{output_dir}/spatial_plot.png'" in script


def test_seurat_spatial_plans_outputs() -> None:
    node_class = _node_class("seurat_spatial")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/seurat_spatial/clusters.csv",
        "/tmp/run/seurat_spatial/markers.csv",
        "/tmp/run/seurat_spatial/spatial_plot.png",
    ]


def test_seurat_spatial_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["Rscript"] == "r-base"
    assert PACKAGE_MIN_VERSIONS["r-base"] == ">=4.3.0"
    assert PACKAGE_MIN_VERSIONS["r-seurat"] == ">=5.0"
    assert PACKAGE_MIN_VERSIONS["r-ggplot2"] == ">=3.5"
    assert PACKAGE_MIN_VERSIONS["r-patchwork"] == ">=1.2"


def test_cell2location_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cell2location"]
    assert node_info["display_name"] == "Cell2location"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Deconvolute spatial transcriptomics")
    assert node_info["output"] == ["H5AD", "IMAGE"]
    assert node_info["output_name"] == ["spatial_deconv", "celltype_map"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["cell2location", "torch", "scanpy", "anndata"]
    assert node_info["experimental"] is True
    assert "cell2location" in node_info["search_aliases"]
    assert "spatial deconvolution" in node_info["search_aliases"]
    assert "cell type mapping" in node_info["search_aliases"]
    assert "cell2loc" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"visium_adata", "scrna_adata", "cell_type_key"}
    assert set(inputs["optional"]) == {"ref_epochs", "deconv_epochs", "n_cells_per_spot"}


def test_cell2location_writes_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("cell2location")
    output_dir = tmp_path / "cell2location"

    cmd = node_class.render_command({
        "visium_adata": "visium.h5ad",
        "scrna_adata": "reference.h5ad",
        "cell_type_key": "annotation",
        "ref_epochs": 100,
        "deconv_epochs": 2000,
        "n_cells_per_spot": 25,
        "output": str(output_dir),
    })

    script_file = output_dir / "cell2location_run.py"
    assert cmd == ["python", str(script_file)]
    script = script_file.read_text()
    assert "import cell2location" in script
    assert "import scanpy as sc" in script
    assert "matplotlib.use('Agg')" in script
    assert "adata_vis = sc.read_h5ad('visium.h5ad')" in script
    assert "adata_ref = sc.read_h5ad('reference.h5ad')" in script
    assert "RegressionModel.setup_anndata(adata_ref, labels_key='annotation')" in script
    assert "mod.train(max_epochs=100)" in script
    assert "from cell2location.models import Cell2location" in script
    assert "N_cells_per_location=25" in script
    assert "mod.train(max_epochs=2000)" in script
    assert f"adata_vis.write('{output_dir}/spatial_deconv.h5ad')" in script
    assert f"adata_vis.obsm['q05_cell_abundance_w_sf'].to_csv('{output_dir}/celltype_map.csv')" in script


def test_cell2location_plans_outputs() -> None:
    node_class = _node_class("cell2location")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cell2location/spatial_deconv.h5ad",
        "/tmp/run/cell2location/celltype_map.csv",
    ]


def test_cell2location_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["python"] == "python"
    assert PACKAGE_MIN_VERSIONS["cell2location"] == ">=0.1"
    assert PACKAGE_MIN_VERSIONS["torch"] == ">=2.0"
    assert PACKAGE_MIN_VERSIONS["scanpy"] == ">=1.10"
    assert PACKAGE_MIN_VERSIONS["anndata"] == ">=0.10"


def test_baysor_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["baysor"]
    assert node_info["display_name"] == "Baysor Segmentation"
    assert node_info["category"] == "spatial_transcriptomics"
    assert node_info["description"].startswith("Cell segmentation for MERFISH")
    assert node_info["output"] == ["CSV"]
    assert node_info["output_name"] == ["cell_segmentation"]
    assert node_info["required_executables"] == ["baysor"]
    assert node_info["required_conda_packages"] == ["baysor"]
    assert "baysor" in node_info["search_aliases"]
    assert "segmentation" in node_info["search_aliases"]
    assert "merfish" in node_info["search_aliases"]
    assert "xenium" in node_info["search_aliases"]
    assert "molecular spatial" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"transcript_data", "x_col", "y_col", "gene_col", "min_molecules"}
    assert set(inputs["optional"]) == {"z_col", "scale", "iters"}


def test_baysor_renders_command_with_optional_3d_and_tuning_flags() -> None:
    node_class = _node_class("baysor")

    cmd = node_class.render_command({
        "transcript_data": "transcripts.csv",
        "x_col": "x_location",
        "y_col": "y_location",
        "gene_col": "feature_name",
        "min_molecules": 45,
        "z_col": "z_location",
        "scale": "12.5",
        "iters": 750,
        "output": "/tmp/run/baysor",
    })

    assert cmd == [
        "baysor",
        "run",
        "transcripts.csv",
        "-x",
        "x_location",
        "-y",
        "y_location",
        "-g",
        "feature_name",
        "-m",
        "45",
        "-o",
        "/tmp/run/baysor",
        "-z",
        "z_location",
        "--scale",
        "12.5",
        "--iters",
        "750",
    ]


def test_baysor_omits_empty_optional_flags() -> None:
    node_class = _node_class("baysor")

    cmd = node_class.render_command({
        "transcript_data": "transcripts.csv",
        "x_col": "x",
        "y_col": "y",
        "gene_col": "gene",
        "min_molecules": 30,
        "z_col": "",
        "scale": "",
        "iters": 0,
        "output": "/tmp/run/baysor",
    })

    assert cmd == [
        "baysor",
        "run",
        "transcripts.csv",
        "-x",
        "x",
        "-y",
        "y",
        "-g",
        "gene",
        "-m",
        "30",
        "-o",
        "/tmp/run/baysor",
    ]


def test_baysor_plans_segmentation_output() -> None:
    node_class = _node_class("baysor")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/baysor/cell_segmentation.csv",
    ]


def test_baysor_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["baysor"] == "baysor"
    assert PACKAGE_MIN_VERSIONS["baysor"] == ">=0.7"
