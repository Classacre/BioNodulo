from pathlib import Path

from bionodulo.nodes.builtin.single_cell import CellRangerCountNode


def test_cellranger_count_exposes_web_summary_metrics_and_filtered_matrix_outputs() -> None:
    outputs = CellRangerCountNode.PLAN_OUTPUTS({"run_id": "tinygex"}, "/tmp/run")

    assert CellRangerCountNode.RETURN_NAMES == (
        "output_dir",
        "web_summary",
        "metrics_summary",
        "filtered_feature_bc_matrix",
        "filtered_feature_bc_matrix_h5",
        "raw_feature_bc_matrix",
        "raw_feature_bc_matrix_h5",
    )
    assert CellRangerCountNode.RETURN_TYPES == (
        "CELL_RANGER_OUT",
        "FILE",
        "CSV",
        "DIRECTORY",
        "FILE",
        "DIRECTORY",
        "FILE",
    )
    assert outputs == [
        Path("/tmp/run/cellranger_count/tinygex"),
        Path("/tmp/run/cellranger_count/tinygex/outs/web_summary.html"),
        Path("/tmp/run/cellranger_count/tinygex/outs/metrics_summary.csv"),
        Path("/tmp/run/cellranger_count/tinygex/outs/filtered_feature_bc_matrix"),
        Path("/tmp/run/cellranger_count/tinygex/outs/filtered_feature_bc_matrix.h5"),
        Path("/tmp/run/cellranger_count/tinygex/outs/raw_feature_bc_matrix"),
        Path("/tmp/run/cellranger_count/tinygex/outs/raw_feature_bc_matrix.h5"),
    ]
