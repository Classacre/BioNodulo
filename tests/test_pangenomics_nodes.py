"""Small compatibility checks shared by all pangenomics operation families."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.scripts.pangenome_stats_summary import summarize_table
from bionodulo.nodes.types import BioType, file_extension_for, is_compatible


def test_pangenome_graph_types_remain_file_compatible() -> None:
    expected = {
        "GFA": ".gfa",
        "ODGI": ".odgi",
        "GBZ": ".gbz",
        "HAL": ".hal",
        "MAF": ".maf",
        "VG": ".vg",
        "TAR": ".tar",
    }
    for type_name, extension in expected.items():
        assert getattr(BioType, type_name).value == type_name
        assert is_compatible(type_name, "FILE")
        assert is_compatible(type_name, "STRING")
        assert file_extension_for(type_name) == extension


def test_executor_resolves_pangenome_graph_paths(tmp_path: Path) -> None:
    class PangenomeInputNode:
        @classmethod
        def INPUT_TYPES(cls) -> dict[str, dict[str, object]]:
            return {"required": {"gfa_graph": ("GFA", {}), "odgi_graph": ("ODGI", {})}}

    graph_dir = tmp_path / "graphs"
    graph_dir.mkdir()
    (graph_dir / "pan.gfa").write_text("H\tVN:Z:1.0\n", encoding="utf-8")
    (graph_dir / "pan.odgi").write_text("graph\n", encoding="utf-8")

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    assert executor._resolve_file_paths(
        PangenomeInputNode,
        {"gfa_graph": "graphs/pan.gfa", "odgi_graph": "graphs/pan.odgi"},
    ) == {
        "gfa_graph": str(graph_dir / "pan.gfa"),
        "odgi_graph": str(graph_dir / "pan.odgi"),
    }


def test_all_nineteen_pangenomics_ids_remain_discoverable() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    expected = {
        "cactus_cactus",
        "cactus_export",
        "minigraph",
        "minigraph_cactus",
        "odgi_build",
        "odgi_stats",
        "odgi_view",
        "odgi_visualize",
        "odgi_viz",
        "pangenome_gene",
        "pangenome_stats",
        "pangenome_sv",
        "pggb",
        "pggb_build",
        "vcf_decompose",
        "vg_call",
        "vg_construct",
        "vg_index",
        "vg_map",
    }
    assert all(registry.get(node_id) is not None for node_id in expected)


def test_pangenome_stats_summary_remains_deterministic() -> None:
    summary = summarize_table(
        StringIO("feature\t1\t2\t3\ncore\t10\t10\t10\nshell\t1\t5\t5\ncloud\t1\t1\t1\n"),
        core_threshold=0.9,
        shell_threshold=0.2,
    )
    assert summary["core_features"] == 1
    assert summary["shell_features"] == 1
    assert summary["cloud_features"] == 1
    assert summary["max_observed"] == 10.0
