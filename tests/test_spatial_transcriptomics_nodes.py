from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def _node_class(node_id: str) -> type:
    node_class = _registry().get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_spatial_wave_resolves_to_focused_modules() -> None:
    from bionodulo.nodes.builtin.single_cell_spatial_family.cell2location import Cell2LocationNode

    registry = _registry()
    expected_modules = {
        "baysor": "bionodulo.nodes.builtin.single_cell_spatial_family.baysor",
        "cell2location": "bionodulo.nodes.builtin.single_cell_spatial_family.cell2location",
        "seurat_spatial": "bionodulo.nodes.builtin.single_cell_spatial_family.seurat_spatial",
        "spaceranger": "bionodulo.nodes.builtin.single_cell_spatial_family.spaceranger",
        "spaceranger_count": "bionodulo.nodes.builtin.single_cell_spatial_family.spaceranger_count",
        "squidpy": "bionodulo.nodes.builtin.single_cell_spatial_family.squidpy",
    }
    assert {node_id: registry.get(node_id).__module__ for node_id in expected_modules} == expected_modules
    assert issubclass(registry.get("spaceranger"), registry.get("spaceranger_count"))
    assert issubclass(registry.get("squidpy"), registry.get("squidpy_qc"))
    assert Cell2LocationNode is registry.get("cell2location")


def test_spaceranger_contract_is_external_and_source_pinned() -> None:
    node_class = _node_class("spaceranger_count")
    assert node_class.VERSION == "3.1.3"
    assert node_class.REQUIRED_EXECUTABLES == ["spaceranger"]
    assert node_class.REQUIRED_CONDA_PACKAGES == []
    assert node_class.RETURN_TYPES == ("DIRECTORY", "BAM", "FILE")
    assert node_class.RETURN_NAMES == ("spaceranger_out", "possorted_bam", "possorted_bam_index")
    assert node_class.ENVIRONMENT["provisioning"] == "external_worker_binary"
    assert node_class.ENV_VARS == {"TENX_DISABLE_TELEMETRY": "1"}


@pytest.mark.parametrize("create_bam", [True, False])
def test_spaceranger_renders_documented_count_flags(create_bam: bool) -> None:
    node_class = _node_class("spaceranger_count")
    command = node_class.render_command(
        {
            "sample_id": "visium_A1",
            "transcriptome": "/refs/GRCh38",
            "fastqs_dir": "/reads",
            "he_image": "/images/tissue.tif",
            "slide": "V19L01-041",
            "area": "A1",
            "sample_prefix": "sampleA",
            "slidefile": "/slides/design.gpr",
            "threads": 12,
            "memory": 48,
            "create_bam": create_bam,
            "output": "/tmp/run/spaceranger_count",
        }
    )
    assert command[:4] == ["spaceranger", "count", "--id", "visium_A1"]
    output_index = command.index("--output-dir")
    assert ["--output-dir", "/tmp/run/spaceranger_count"] == command[output_index : output_index + 2]
    assert f"--create-bam={'true' if create_bam else 'false'}" in command
    assert command[-4:] == ["--sample", "sampleA", "--slidefile", "/slides/design.gpr"]
    assert "--disable-ui" in command


@pytest.mark.parametrize("node_id", ["spaceranger_count", "spaceranger"])
@pytest.mark.parametrize("create_bam", [True, False])
def test_spaceranger_aliases_map_conditional_native_bam_sidecars(
    node_id: str,
    create_bam: bool,
    tmp_path: Path,
) -> None:
    node_class = _node_class(node_id)
    outs = tmp_path / node_id / "outs"
    expected = [outs]
    expected_names = {"spaceranger_out"}
    if create_bam:
        expected.append(outs / "possorted_genome_bam.bam")
        expected_names.add("possorted_bam")
    planned = node_class.PLAN_OUTPUTS({"create_bam": create_bam}, tmp_path)
    assert planned == expected
    assert set(node_class.MAP_PLANNED_OUTPUTS(planned)) == expected_names


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("create_bam", "index_suffix"),
    [(True, ".bai"), (True, ".csi"), (False, None)],
)
async def test_spaceranger_fake_execution_returns_only_enabled_outputs(
    create_bam: bool,
    index_suffix: str | None,
    tmp_path: Path,
) -> None:
    node_class = _node_class("spaceranger_count")
    inputs = {
        "sample_id": "visium_A1",
        "transcriptome": "/refs/GRCh38",
        "fastqs_dir": "/reads",
        "he_image": "/images/tissue.tif",
        "slide": "V19L01-041",
        "area": "A1",
        "create_bam": create_bam,
    }

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: list[str], **_kwargs: object) -> dict[str, object]:
            for path in node_class.PLAN_OUTPUTS(inputs, self.node_dir):
                if path.name == "outs":
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic")
            if index_suffix is not None:
                bam = self.node_dir / "spaceranger_count" / "outs" / "possorted_genome_bam.bam"
                Path(f"{bam}{index_suffix}").write_bytes(b"synthetic index")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await node_class().run(context=Context(), **inputs)
    assert set(result["outputs"]) == (
        {"spaceranger_out", "possorted_bam", "possorted_bam_index"} if create_bam else {"spaceranger_out"}
    )
    if index_suffix is not None:
        assert result["outputs"]["possorted_bam_index"].endswith(index_suffix)


def test_spaceranger_rejects_missing_or_ambiguous_bam_indexes(tmp_path: Path) -> None:
    node_class = _node_class("spaceranger_count")
    outs = tmp_path / "outs"
    outs.mkdir()
    with pytest.raises(RuntimeError, match="exactly one BAM index"):
        node_class.RESOLVE_BAM_INDEX(outs)
    (outs / "possorted_genome_bam.bam.bai").write_bytes(b"bai")
    (outs / "possorted_genome_bam.bam.csi").write_bytes(b"csi")
    with pytest.raises(RuntimeError, match="exactly one BAM index"):
        node_class.RESOLVE_BAM_INDEX(outs)


def test_spaceranger_rejects_unsafe_run_ids() -> None:
    node_class = _node_class("spaceranger_count")
    validation = node_class.VALIDATE_INPUTS(
        {
            "sample_id": "sample with spaces",
            "transcriptome": "/refs/GRCh38",
            "fastqs_dir": "/reads",
            "he_image": "/images/tissue.tif",
            "slide": "V19L01-041",
            "area": "A1",
        }
    )
    assert validation == "Input 'sample_id' may only contain letters, numbers, underscores, and hyphens"


def test_seurat_spatial_uses_complete_visium_outs_and_sct(tmp_path: Path) -> None:
    node_class = _node_class("seurat_spatial")
    output_dir = tmp_path / "seurat_spatial"
    command = node_class.render_command(
        {
            "visium_path": "/data/spaceranger/outs",
            "sample_name": "sampleA",
            "min_features": 300,
            "normalization_method": "SCT",
            "dims": 20,
            "resolution": 0.9,
            "output": str(output_dir),
        }
    )
    script_path = output_dir / "seurat_spatial.R"
    script = script_path.read_text()
    assert command == ["Rscript", "--vanilla", str(script_path)]
    assert "object <- Load10X_Spatial(" in script
    assert 'data.dir = "/data/spaceranger/outs"' in script
    assert 'object <- SCTransform(object, assay = "Spatial", verbose = FALSE)' in script
    assert 'object <- RunPCA(object, assay = "SCT", npcs = 20' in script
    assert "SpatialDimPlot(object" in script


def test_seurat_spatial_log_normalize_branch_is_complete(tmp_path: Path) -> None:
    node_class = _node_class("seurat_spatial")
    output_dir = tmp_path / "seurat_spatial"
    node_class.render_command(
        {
            "visium_path": "/data/spaceranger/outs",
            "normalization_method": "LogNormalize",
            "output": str(output_dir),
        }
    )
    script = (output_dir / "seurat_spatial.R").read_text()
    assert 'NormalizeData(object, assay = "Spatial"' in script
    assert 'FindVariableFeatures(object, assay = "Spatial"' in script
    assert 'ScaleData(object, assay = "Spatial"' in script
    assert 'DefaultAssay(object) <- "Spatial"' in script
    assert "SCTransform" not in script


def test_seurat_spatial_plans_all_declared_outputs(tmp_path: Path) -> None:
    outputs = _node_class("seurat_spatial").PLAN_OUTPUTS({}, tmp_path)
    assert outputs == [
        tmp_path / "seurat_spatial" / "clusters.csv",
        tmp_path / "seurat_spatial" / "markers.csv",
        tmp_path / "seurat_spatial" / "spatial_plot.png",
    ]


def test_cell2location_contract_is_external_pypi_and_csv_output() -> None:
    node_class = _node_class("cell2location")
    assert node_class.VERSION == "0.1.5"
    assert node_class.GIT_COMMIT == "20afdf2ddbd651434e664129547adb8a204044fc"
    assert node_class.REQUIRED_CONDA_PACKAGES == []
    assert node_class.RETURN_TYPES == ("H5AD", "CSV")
    assert node_class.ENVIRONMENT["packages"]["cell2location"] == "0.1.5"
    assert node_class.ENVIRONMENT["packages"]["scvi-tools"] == ">=1.3.0"


def test_cell2location_script_handles_both_signature_layouts_and_seeds(tmp_path: Path) -> None:
    node_class = _node_class("cell2location")
    output_dir = tmp_path / "cell2location"
    command = node_class.render_command(
        {
            "visium_adata": "/data/visium.h5ad",
            "scrna_adata": "/data/reference.h5ad",
            "cell_type_key": "annotation",
            "ref_epochs": 100,
            "deconv_epochs": 2000,
            "n_cells_per_spot": 25,
            "detection_alpha": 200.0,
            "seed": 7,
            "output": str(output_dir),
        }
    )
    script_path = output_dir / "cell2location_run.py"
    script = script_path.read_text()
    compile(script, str(script_path), "exec")
    assert command == ["python", str(script_path)]
    assert "scvi.settings.seed = seed" in script
    assert "if signature_key in adata_ref.varm:" in script
    assert "elif all(name in adata_ref.var.columns for name in signature_columns):" in script
    assert "if not shared_genes:" in script
    assert "detection_alpha=200.0" in script
    assert "abundance.columns = factor_names" in script
    assert 'abundance_key = "q05_cell_abundance_w_sf"' in script


def test_cell2location_rejects_nonpositive_detection_alpha() -> None:
    validation = _node_class("cell2location").VALIDATE_INPUTS(
        {
            "visium_adata": "visium.h5ad",
            "scrna_adata": "reference.h5ad",
            "cell_type_key": "annotation",
            "detection_alpha": 0.0,
        }
    )
    assert validation == "Input 'detection_alpha' must be greater than 0"


def test_baysor_renders_supported_config_and_prior_column_flags() -> None:
    node_class = _node_class("baysor")
    command = node_class.render_command(
        {
            "transcript_data": "transcripts.csv",
            "x_col": "x_location",
            "y_col": "y_location",
            "gene_col": "feature_name",
            "prior_segmentation_column": "cell_id",
            "min_molecules": 45,
            "n_clusters": 6,
            "iters": 750,
            "count_matrix_format": "tsv",
            "polygon_format": "none",
            "output": "/tmp/run/baysor",
        }
    )
    assert command[:2] == ["baysor", "run"]
    assert "--config.segmentation.iters=750" in command
    count_index = command.index("--count-matrix-format")
    output_index = command.index("-o")
    assert ["--count-matrix-format", "tsv"] == command[count_index : count_index + 2]
    assert ["-o", "/tmp/run/baysor/segmentation.csv"] == command[output_index : output_index + 2]
    assert command[-2:] == ["transcripts.csv", ":cell_id"]


def test_baysor_requires_scale_or_prior_and_plans_native_outputs(tmp_path: Path) -> None:
    node_class = _node_class("baysor")
    validation = node_class.VALIDATE_INPUTS(
        {"transcript_data": "transcripts.csv", "x_col": "x", "y_col": "y", "gene_col": "gene"}
    )
    assert validation == "Baysor requires a positive 'scale' or prior segmentation"
    assert node_class.PLAN_OUTPUTS({"count_matrix_format": "loom"}, tmp_path) == [
        tmp_path / "baysor" / "segmentation.csv",
        tmp_path / "baysor" / "segmentation_cell_stats.csv",
        tmp_path / "baysor" / "segmentation_counts.loom",
        tmp_path / "baysor" / "segmentation_polygons_2d.json",
    ]


def test_baysor_exposes_parquet_input_and_conditional_polygon_outputs(tmp_path: Path) -> None:
    node_class = _node_class("baysor")
    assert node_class.INPUT_TYPES()["required"]["transcript_data"][0] == "FILE"
    assert node_class.RETURN_NAMES == (
        "cell_segmentation",
        "cell_stats",
        "count_matrix",
        "polygons_2d",
        "polygons_3d",
    )
    assert node_class.PLAN_OUTPUTS({"polygon_format": "none"}, tmp_path) == [
        tmp_path / "baysor" / "segmentation.csv",
        tmp_path / "baysor" / "segmentation_cell_stats.csv",
        tmp_path / "baysor" / "segmentation_counts.loom",
    ]
    assert node_class.PLAN_OUTPUTS({"z_col": "z"}, tmp_path)[-2:] == [
        tmp_path / "baysor" / "segmentation_polygons_2d.json",
        tmp_path / "baysor" / "segmentation_polygons_3d.json",
    ]


def test_squidpy_alias_preserves_id_specific_outputs(tmp_path: Path) -> None:
    node_class = _node_class("squidpy")
    assert node_class.VERSION == "1.8.2"
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "squidpy" / "adata.h5ad",
        tmp_path / "squidpy" / "spatial_plot.png",
    ]
