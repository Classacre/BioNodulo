from pathlib import Path

from bionodulo.nodes.builtin.single_cell import CellRangerCountNode


def test_cellranger_count_exposes_web_summary_and_metrics_summary_outputs() -> None:
    outputs = CellRangerCountNode.PLAN_OUTPUTS({"run_id": "tinygex"}, "/tmp/run")

    assert CellRangerCountNode.RETURN_NAMES == ("output_dir", "web_summary", "metrics_summary")
    assert CellRangerCountNode.RETURN_TYPES == ("CELL_RANGER_OUT", "FILE", "CSV")
    assert outputs == [
        Path("/tmp/run/cellranger_count/tinygex"),
        Path("/tmp/run/cellranger_count/tinygex/outs/web_summary.html"),
        Path("/tmp/run/cellranger_count/tinygex/outs/metrics_summary.csv"),
    ]
