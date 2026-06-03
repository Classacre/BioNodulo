from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.types import BioType, file_extension_for, is_compatible


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_pangenome_graph_types_are_file_compatible() -> None:
    assert BioType.GFA.value == "GFA"
    assert BioType.ODGI.value == "ODGI"
    assert is_compatible("GFA", "FILE")
    assert is_compatible("GFA", "STRING")
    assert is_compatible("ODGI", "FILE")
    assert is_compatible("ODGI", "STRING")
    assert file_extension_for("GFA") == ".gfa"
    assert file_extension_for("ODGI") == ".odgi"


def test_executor_resolves_pangenome_graph_file_inputs(tmp_path: Path) -> None:
    class PangenomeInputNode:
        @classmethod
        def INPUT_TYPES(cls) -> dict[str, dict[str, object]]:
            return {
                "required": {
                    "gfa_graph": ("GFA", {}),
                    "odgi_graph": ("ODGI", {}),
                },
            }

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    graph_dir = tmp_path / "graphs"
    graph_dir.mkdir()
    (graph_dir / "pan.gfa").write_text("H\tVN:Z:1.0\n", encoding="utf-8")
    (graph_dir / "pan.odgi").write_text("", encoding="utf-8")

    resolved = executor._resolve_file_paths(
        PangenomeInputNode,
        {"gfa_graph": "graphs/pan.gfa", "odgi_graph": "graphs/pan.odgi"},
    )

    assert resolved == {
        "gfa_graph": str(tmp_path / "graphs/pan.gfa"),
        "odgi_graph": str(tmp_path / "graphs/pan.odgi"),
    }


def test_odgi_visualize_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["odgi_visualize"]
    assert node_info["display_name"] == "odgi Visualize"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Visualize pangenome graphs")
    assert node_info["output"] == ["IMAGE", "IMAGE"]
    assert node_info["output_name"] == ["graph_1d", "graph_2d"]
    assert node_info["required_executables"] == ["odgi"]
    assert node_info["required_conda_packages"] == ["odgi"]
    assert "pangenome" in node_info["search_aliases"]
    assert "graph layout" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"gfa_graph"}
    assert set(inputs["optional"]) == {"width", "height", "draw_width", "draw_height", "show_path_names"}
    assert inputs["required"]["gfa_graph"][0] == "GFA"
    assert _node_class("odgi_visualize").INPUT_TYPES()["required"]["gfa_graph"][0] == "GFA"


def test_odgi_visualize_renders_1d_and_2d_graph_command() -> None:
    node_class = _node_class("odgi_visualize")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "width": 1600,
        "height": 240,
        "draw_width": 1400,
        "draw_height": 700,
        "show_path_names": True,
        "output": "/tmp/run/odgi_visualize",
    })

    assert cmd == [
        "odgi",
        "build",
        "-g",
        "pan.gfa",
        "-o",
        "/tmp/run/odgi_visualize/graph.og",
        "&&",
        "odgi",
        "viz",
        "-i",
        "/tmp/run/odgi_visualize/graph.og",
        "-o",
        "/tmp/run/odgi_visualize/graph_1d.png",
        "-x",
        "1600",
        "-y",
        "240",
        "-p",
        "&&",
        "odgi",
        "sort",
        "-i",
        "/tmp/run/odgi_visualize/graph.og",
        "-o",
        "/tmp/run/odgi_visualize/sorted.og",
        "-Y",
        "&&",
        "odgi",
        "draw",
        "-i",
        "/tmp/run/odgi_visualize/sorted.og",
        "-c",
        "/tmp/run/odgi_visualize/graph_2d.png",
        "-H",
        "700",
        "-C",
        "1400",
    ]


def test_odgi_visualize_omits_path_names_flag() -> None:
    node_class = _node_class("odgi_visualize")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "width": 1200,
        "height": 200,
        "draw_width": 1200,
        "draw_height": 600,
        "show_path_names": False,
        "output": "/tmp/run/odgi_visualize",
    })

    assert "-p" not in cmd


def test_odgi_visualize_plans_outputs() -> None:
    node_class = _node_class("odgi_visualize")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/odgi_visualize/graph_1d.png",
        "/tmp/run/odgi_visualize/graph_2d.png",
    ]


def test_odgi_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["odgi"] == "odgi"
    assert PACKAGE_MIN_VERSIONS["odgi"] == ">=0.9.0"
