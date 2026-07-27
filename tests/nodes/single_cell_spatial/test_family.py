from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.single_cell_spatial_family.adapter import SCANPY_COMMIT, SQUIDPY_COMMIT
from bionodulo.nodes.builtin.single_cell_spatial_family.cellranger_count import CellRangerCountNode
from bionodulo.nodes.builtin.single_cell_spatial_family.scanpy_spatial import ScanpySpatialNode
from bionodulo.nodes.builtin.single_cell_spatial_family.scanpy_umap import ScanpyUmapNode
from bionodulo.nodes.builtin.single_cell_spatial_family.squidpy_qc import SquidpyQCNode


WAVE_NODES = (CellRangerCountNode, ScanpyUmapNode, SquidpyQCNode, ScanpySpatialNode)


def test_wave_has_four_stable_source_backed_ids() -> None:
    assert {node.NODE_ID for node in WAVE_NODES} == {
        "cellranger_count",
        "scanpy_umap",
        "squidpy_qc",
        "scanpy_spatial",
    }
    assert ScanpyUmapNode.GIT_COMMIT == SCANPY_COMMIT
    assert ScanpySpatialNode.GIT_COMMIT == SCANPY_COMMIT
    assert SquidpyQCNode.GIT_COMMIT == SQUIDPY_COMMIT
    for node in WAVE_NODES:
        assert node.UPSTREAM_SOURCE
        assert node.EXIT_SEMANTICS
        assert node.SHELL is False


def test_environment_contracts_distinguish_licensed_binary_from_conda_tools() -> None:
    assert CellRangerCountNode.VERSION == "9.0.1"
    assert CellRangerCountNode.GIT_COMMIT == "6ebad209b8354353b4a9ee3eed1cb248d102af88"
    assert CellRangerCountNode.REQUIRED_EXECUTABLES == ["cellranger"]
    assert CellRangerCountNode.REQUIRED_CONDA_PACKAGES == []
    assert "BYOL only" in CellRangerCountNode.DISTRIBUTION
    assert CellRangerCountNode.ENVIRONMENT["access"] == "BYOL"
    assert CellRangerCountNode.QUARANTINE_STATUS == "byol-evidence-only-no-binary-execution"
    assert CellRangerCountNode.EXPERIMENTAL is True
    assert "complete compatible Cell Ranger reference" in CellRangerCountNode.ACCESS_CONSTRAINTS[1]
    assert CellRangerCountNode.ENV_VARS == {"TENX_DISABLE_TELEMETRY": "1"}
    assert "build_metrics_summary_csv" in CellRangerCountNode.SOURCE_AUTHORITIES["metrics_summary_layout"]
    assert ScanpyUmapNode.CONDA_PACKAGE_CONSTRAINTS == {
        "scanpy": "1.12.2",
        "python-igraph": "1.0.0",
        "matplotlib": "3.10.9",
    }
    assert SquidpyQCNode.CONDA_PACKAGE_CONSTRAINTS["squidpy"] == "1.8.2"


def test_cellranger_count_renders_official_count_subset_and_native_outputs(tmp_path: Path) -> None:
    inputs = {
        "fastq_dir": "/data/fastqs",
        "transcriptome": "/refs/refdata-gex-GRCh38-2024-A",
        "threads": 12,
        "memory": 48,
        "run_id": "tinygex",
        "sample": "tinygex",
        "expect_cells": 100,
        "create_bam": False,
    }
    assert CellRangerCountNode.render_command(inputs) == [
        "cellranger",
        "count",
        "--id",
        "tinygex",
        "--transcriptome",
        "/refs/refdata-gex-GRCh38-2024-A",
        "--fastqs",
        "/data/fastqs",
        "--localcores",
        "12",
        "--localmem",
        "48",
        "--sample",
        "tinygex",
        "--expect-cells",
        "100",
        "--create-bam=false",
        "--disable-ui",
    ]
    run_dir = tmp_path / "cellranger_count" / "tinygex"
    assert CellRangerCountNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        run_dir,
        run_dir / "outs" / "web_summary.html",
        run_dir / "outs" / "metrics_summary.csv",
        run_dir / "outs" / "filtered_feature_bc_matrix",
        run_dir / "outs" / "filtered_feature_bc_matrix.h5",
        run_dir / "outs" / "raw_feature_bc_matrix",
        run_dir / "outs" / "raw_feature_bc_matrix.h5",
    ]
    assert CellRangerCountNode.RETURN_NAMES[-2:] == (
        "possorted_bam",
        "possorted_bam_index",
    )
    assert CellRangerCountNode.RETURN_TYPES[-2:] == ("BAM", "FILE")
    with_bam = {**inputs, "create_bam": True}
    assert CellRangerCountNode.PLAN_OUTPUTS(with_bam, tmp_path)[-1] == (
        run_dir / "outs" / "possorted_genome_bam.bam"
    )
    assert CellRangerCountNode.RUN_IN_NODE_OUTPUT_DIR is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"run_id": "bad/id"}, "letters, numbers"),
        ({"threads": 0}, "at least 1"),
        ({"expect_cells": 0}, "at least 1"),
    ],
)
def test_cellranger_count_rejects_invalid_release_contracts(overrides: dict[str, Any], message: str) -> None:
    inputs = {
        "fastq_dir": "fastqs",
        "transcriptome": "reference",
        "threads": 8,
        "memory": 32,
        "run_id": "sample",
        **overrides,
    }
    assert message in str(CellRangerCountNode.VALIDATE_INPUTS(inputs))


@pytest.mark.asyncio
@pytest.mark.parametrize("index_suffix", [None, ".bai", ".csi"])
async def test_cellranger_count_maps_conditional_bam_and_exactly_one_native_index(
    index_suffix: str | None,
    tmp_path: Path,
) -> None:
    create_bam = index_suffix is not None
    inputs = {
        "fastq_dir": "/data/fastqs",
        "transcriptome": "/refs/refdata-gex-GRCh38-2024-A",
        "threads": 8,
        "memory": 32,
        "run_id": "sample",
        "create_bam": create_bam,
    }
    planned = CellRangerCountNode.PLAN_OUTPUTS(inputs, tmp_path)

    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            assert f"--create-bam={'true' if create_bam else 'false'}" in command
            for path in planned:
                if path.suffix in {".html", ".csv", ".h5", ".bam"}:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic")
                else:
                    path.mkdir(parents=True, exist_ok=True)
            if index_suffix is not None:
                Path(f"{planned[-1]}{index_suffix}").write_bytes(b"index")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await CellRangerCountNode().run(
        **inputs,
        context=Context(),
        output_dir=tmp_path,
    )
    expected_names = set(CellRangerCountNode.RETURN_NAMES[:7])
    if create_bam:
        expected_names.update({"possorted_bam", "possorted_bam_index"})
    assert set(result["outputs"]) == expected_names
    if index_suffix is not None:
        assert result["outputs"]["possorted_bam_index"].endswith(index_suffix)


def test_cellranger_count_rejects_missing_or_ambiguous_bam_sidecar(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outs = run_dir / "outs"
    outs.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="found none"):
        CellRangerCountNode.RESOLVE_BAM_INDEX(run_dir)
    for suffix in (".bai", ".csi"):
        (outs / f"possorted_genome_bam.bam{suffix}").write_bytes(b"index")
    with pytest.raises(RuntimeError, match="found possorted_genome_bam.bam.bai, possorted_genome_bam.bam.csi"):
        CellRangerCountNode.RESOLVE_BAM_INDEX(run_dir)


def test_scanpy_umap_writes_pinned_pipeline_with_explicit_determinism(tmp_path: Path) -> None:
    output = tmp_path / "scanpy_umap"
    command = ScanpyUmapNode.render_command(
        {
            "matrix_h5": "/data/filtered_feature_bc_matrix.h5",
            "min_genes": 250,
            "min_cells": 4,
            "n_pcs": 25,
            "n_neighbors": 12,
            "resolution": 0.7,
            "output": output,
        }
    )
    script_path = output / "scanpy_umap.py"
    script = script_path.read_text(encoding="utf-8")
    assert command == ["python", str(script_path)]
    assert "sc.read_10x_h5('/data/filtered_feature_bc_matrix.h5', gex_only=True)" in script
    assert "sc.pp.filter_cells(adata, min_genes=250)" in script
    assert "sc.pp.filter_genes(adata, min_cells=4)" in script
    assert "flavor=\"igraph\"" in script
    assert "n_iterations=2" in script
    assert "random_state=0" in script
    assert "scanpy_n_neighbors = min(12, adata.n_obs)" in script
    assert "n_neighbors=scanpy_n_neighbors" in script


def test_squidpy_qc_loads_complete_visium_spatial_data_and_new_grid_api(tmp_path: Path) -> None:
    output = tmp_path / "squidpy_qc"
    command = SquidpyQCNode.render_command(
        {
            "visium_path": "/data/visium/outs",
            "min_counts": 750,
            "min_cells": 5,
            "max_mt_pct": 15.5,
            "n_hvg": 1500,
            "n_pcs": 20,
            "resolution": 1.2,
            "output": output,
        }
    )
    script_path = output / "squidpy_qc.py"
    script = script_path.read_text(encoding="utf-8")
    assert command == ["python", str(script_path)]
    assert "sq.read.visium('/data/visium/outs', load_images=True)" in script
    assert "load_images=False" not in script
    assert "grid_n_neighs = min(6, adata.n_obs - 1)" in script
    assert (
        "sq.gr.spatial_neighbors_grid(adata, n_neighs=grid_n_neighs, n_rings=1)"
        in script
    )
    # Squidpy's default 1000 permutations fan across forkserver workers that
    # die with ConnectionResetError on a modest box; run single-process.
    assert "sq.gr.nhood_enrichment(" in script
    assert 'cluster_key="leiden"' in script
    assert "n_jobs=1" in script
    assert "n_perms=100" in script
    assert "scanpy_n_neighbors = min(15, adata.n_obs)" in script
    assert "n_neighbors=scanpy_n_neighbors" in script
    assert "adata.raw = adata.copy()" in script
    assert SquidpyQCNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "squidpy_qc" / "adata.h5ad",
        tmp_path / "squidpy_qc" / "spatial_plot.png",
    ]


def test_scanpy_spatial_consumes_explicit_h5ad_and_returns_only_declared_outputs(tmp_path: Path) -> None:
    output = tmp_path / "scanpy_spatial"
    command = ScanpySpatialNode.render_command(
        {
            "adata": "/data/squidpy_qc/adata.h5ad",
            "sample_name": "sampleA",
            "min_cells": 4,
            "min_genes": 250,
            "n_hvg": 1200,
            "n_pcs": 18,
            "resolution": 0.7,
            "output": output,
        }
    )
    script_path = output / "scanpy_spatial.py"
    script = script_path.read_text(encoding="utf-8")
    assert command == ["python", str(script_path)]
    assert "sc.read_h5ad('/data/squidpy_qc/adata.h5ad')" in script
    assert "adata.raw.to_adata()" in script
    assert "adata.obs[[\"sample\", \"leiden\"]].to_csv" in script
    assert "scanpy_n_neighbors = min(15, adata.n_obs)" in script
    assert "n_neighbors=scanpy_n_neighbors" in script
    assert ScanpySpatialNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "scanpy_spatial" / "clusters.csv",
        tmp_path / "scanpy_spatial" / "umap.png",
    ]
    assert len(ScanpySpatialNode.RETURN_NAMES) == len(ScanpySpatialNode.PLAN_OUTPUTS({}, tmp_path))


class _FailingContext:
    def __init__(self, node_dir: Path) -> None:
        self.node_dir = node_dir

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 17, "stdout": "", "stderr": "synthetic failure"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node", "inputs"),
    [
        (
            CellRangerCountNode(),
            {"fastq_dir": "fastqs", "transcriptome": "ref", "threads": 8, "memory": 32, "run_id": "run"},
        ),
        (ScanpyUmapNode(), {"matrix_h5": "matrix.h5"}),
        (SquidpyQCNode(), {"visium_path": "outs"}),
        (ScanpySpatialNode(), {"adata": "adata.h5ad"}),
    ],
)
async def test_wave_nodes_fail_closed_on_nonzero_exit(node: Any, inputs: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"exit 17.*synthetic failure"):
        await node.run(context=_FailingContext(tmp_path), **inputs)
