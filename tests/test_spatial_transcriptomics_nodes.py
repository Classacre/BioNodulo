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
