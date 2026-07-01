from __future__ import annotations

from pathlib import Path
from io import StringIO

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.scripts.pangenome_stats_summary import summarize_table
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
    assert BioType.GBZ.value == "GBZ"
    assert BioType.HAL.value == "HAL"
    assert BioType.MAF.value == "MAF"
    assert BioType.VG.value == "VG"
    assert BioType.TAR.value == "TAR"
    assert is_compatible("GFA", "FILE")
    assert is_compatible("GFA", "STRING")
    assert is_compatible("ODGI", "FILE")
    assert is_compatible("ODGI", "STRING")
    assert is_compatible("GBZ", "FILE")
    assert is_compatible("GBZ", "STRING")
    assert is_compatible("HAL", "FILE")
    assert is_compatible("HAL", "STRING")
    assert is_compatible("MAF", "FILE")
    assert is_compatible("MAF", "STRING")
    assert is_compatible("VG", "FILE")
    assert is_compatible("VG", "STRING")
    assert is_compatible("TAR", "FILE")
    assert is_compatible("TAR", "STRING")
    assert file_extension_for("GFA") == ".gfa"
    assert file_extension_for("ODGI") == ".odgi"
    assert file_extension_for("GBZ") == ".gbz"
    assert file_extension_for("HAL") == ".hal"
    assert file_extension_for("MAF") == ".maf"
    assert file_extension_for("VG") == ".vg"
    assert file_extension_for("TAR") == ".tar"


def test_embedding_type_is_file_compatible() -> None:
    assert BioType.EMBEDDING.value == "EMBEDDING"
    assert is_compatible("EMBEDDING", "FILE")
    assert is_compatible("EMBEDDING", "STRING")
    assert file_extension_for("EMBEDDING") == ".npy"


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


def test_odgi_viz_is_registered_for_workflow_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["odgi_viz"]
    assert node_info["display_name"] == "ODGI Viz"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Render a pangenome graph")
    assert node_info["output"] == ["IMAGE"]
    assert node_info["output_name"] == ["viz_image"]
    assert node_info["required_executables"] == ["odgi"]
    assert node_info["required_conda_packages"] == ["odgi"]
    assert "odgi viz" in node_info["search_aliases"]
    assert "graph visualization" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"gfa_graph"}
    assert set(inputs["optional"]) == {"width", "height", "show_paths", "viz_mode", "threads"}
    assert inputs["required"]["gfa_graph"][0] == "GFA"
    assert _node_class("odgi_viz").INPUT_TYPES()["required"]["gfa_graph"][0] == "GFA"


def test_odgi_viz_renders_gfa_visualization_command() -> None:
    node_class = _node_class("odgi_viz")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "width": 1600,
        "height": 260,
        "show_paths": True,
        "viz_mode": "gradient",
        "threads": 6,
        "output": "/tmp/run/odgi_viz",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "odgi",
        "build",
        "-g",
        "pan.gfa",
        "-o",
        "/tmp/run/odgi_viz/graph.og",
        "-t",
        "6",
        "&&",
        "odgi",
        "viz",
        "-i",
        "/tmp/run/odgi_viz/graph.og",
        "-o",
        "/tmp/run/odgi_viz/viz_image.png",
        "-x",
        "1600",
        "-y",
        "260",
        "-p",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/odgi_viz/viz_image.png"]


def test_odgi_viz_omits_optional_flags_and_rejects_bad_inputs() -> None:
    node_class = _node_class("odgi_viz")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "width": 1200,
        "height": 200,
        "show_paths": False,
        "viz_mode": "plain",
        "threads": 0,
        "output": "/tmp/run/odgi_viz",
    })

    assert "-p" not in cmd
    assert "-t" not in cmd
    assert node_class.VALIDATE_INPUTS({
        "gfa_graph": "pan.gfa",
        "viz_mode": "heatmap",
        "threads": 1,
    }) == "Unsupported ODGI Viz mode: heatmap"
    assert node_class.VALIDATE_INPUTS({
        "gfa_graph": "pan.gfa",
        "viz_mode": "plain",
        "threads": -1,
    }) == "ODGI Viz threads must be zero or greater."


def test_odgi_stats_is_registered_for_workflow_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["odgi_stats"]
    assert node_info["display_name"] == "ODGI Stats"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Compute JSON graph statistics")
    assert node_info["output"] == ["JSON"]
    assert node_info["output_name"] == ["stats_json"]
    assert node_info["required_executables"] == ["odgi"]
    assert node_info["required_conda_packages"] == ["odgi"]
    assert "odgi stats" in node_info["search_aliases"]
    assert "graph statistics" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"gfa_graph"}
    assert set(inputs["optional"]) == {"threads"}
    assert inputs["required"]["gfa_graph"][0] == "GFA"


def test_odgi_stats_renders_json_stats_command() -> None:
    node_class = _node_class("odgi_stats")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "threads": 4,
        "output": "/tmp/run/odgi_stats",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "odgi",
        "build",
        "-g",
        "pan.gfa",
        "-o",
        "/tmp/run/odgi_stats/graph.og",
        "-t",
        "4",
        "&&",
        "odgi",
        "stats",
        "-i",
        "/tmp/run/odgi_stats/graph.og",
        "-j",
        ">",
        "/tmp/run/odgi_stats/stats.json",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/odgi_stats/stats.json"]


def test_odgi_stats_omits_threads_and_rejects_negative_threads() -> None:
    node_class = _node_class("odgi_stats")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "threads": 0,
        "output": "/tmp/run/odgi_stats",
    })

    assert "-t" not in cmd
    assert node_class.VALIDATE_INPUTS({
        "gfa_graph": "pan.gfa",
        "threads": -1,
    }) == "ODGI Stats threads must be zero or greater."


def test_odgi_view_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["odgi_view"]
    assert node_info["display_name"] == "ODGI View"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Visualize and extract information")
    assert node_info["output"] == ["FILE", "JSON"]
    assert node_info["output_name"] == ["view", "stats"]
    assert node_info["required_executables"] == ["odgi"]
    assert node_info["required_conda_packages"] == ["odgi"]
    assert "odgi stats" in node_info["search_aliases"]
    assert "pangenome graph" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"graph", "mode"}
    assert set(inputs["optional"]) == {"width", "height", "show_path_names"}
    assert inputs["required"]["graph"][0] == "ODGI"
    assert inputs["required"]["mode"][0] == "STRING"


def test_odgi_view_renders_png_view_and_stats_command() -> None:
    node_class = _node_class("odgi_view")

    cmd = node_class.render_command({
        "graph": "pan.odgi",
        "mode": "png",
        "width": 1600,
        "height": 260,
        "show_path_names": True,
        "output": "/tmp/run/odgi_view",
    })
    outputs = node_class.PLAN_OUTPUTS({"mode": "png"}, "/tmp/run")

    assert cmd == [
        "odgi",
        "viz",
        "-i",
        "pan.odgi",
        "-o",
        "/tmp/run/odgi_view/view.png",
        "-x",
        "1600",
        "-y",
        "260",
        "-p",
        "&&",
        "odgi",
        "stats",
        "-i",
        "pan.odgi",
        "-j",
        ">",
        "/tmp/run/odgi_view/stats.json",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/odgi_view/view.png",
        "/tmp/run/odgi_view/stats.json",
    ]


def test_odgi_view_renders_text_view_and_omits_optional_flags() -> None:
    node_class = _node_class("odgi_view")

    cmd = node_class.render_command({
        "graph": "pan.odgi",
        "mode": "paths",
        "width": 0,
        "height": 0,
        "show_path_names": False,
        "output": "/tmp/run/odgi_view",
    })
    outputs = node_class.PLAN_OUTPUTS({"mode": "paths"}, "/tmp/run")

    assert "-x" not in cmd
    assert "-y" not in cmd
    assert "-p" not in cmd
    assert cmd == [
        "odgi",
        "paths",
        "-i",
        "pan.odgi",
        "-L",
        ">",
        "/tmp/run/odgi_view/view.txt",
        "&&",
        "odgi",
        "stats",
        "-i",
        "pan.odgi",
        "-j",
        ">",
        "/tmp/run/odgi_view/stats.json",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/odgi_view/view.txt",
        "/tmp/run/odgi_view/stats.json",
    ]


def test_odgi_view_rejects_unsupported_mode() -> None:
    node_class = _node_class("odgi_view")

    assert node_class.VALIDATE_INPUTS({
        "graph": "pan.odgi",
        "mode": "heatmap",
    }) == "Unsupported ODGI view mode: heatmap"


def test_odgi_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["odgi"] == "odgi"
    assert PACKAGE_MIN_VERSIONS["odgi"] == ">=0.9.0"


def test_odgi_build_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["odgi_build"]
    assert node_info["display_name"] == "odgi Build"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Build an ODGI pangenome graph")
    assert node_info["output"] == ["ODGI", "JSON"]
    assert node_info["output_name"] == ["graph_odgi", "stats"]
    assert node_info["required_executables"] == ["odgi"]
    assert node_info["required_conda_packages"] == ["odgi"]
    assert "odgi build" in node_info["search_aliases"]
    assert "gfa to odgi" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"gfa_graph"}
    assert set(inputs["optional"]) == {"threads", "compact_ids", "validate", "output_name"}
    assert inputs["required"]["gfa_graph"][0] == "GFA"
    assert _node_class("odgi_build").INPUT_TYPES()["required"]["gfa_graph"][0] == "GFA"


def test_odgi_build_renders_build_and_stats_command() -> None:
    node_class = _node_class("odgi_build")

    cmd = node_class.render_command({
        "gfa_graph": "pan.gfa",
        "threads": 8,
        "compact_ids": True,
        "validate": True,
        "output_name": "study graph",
        "output": "/tmp/run/odgi_build",
    })

    assert cmd == [
        "odgi",
        "build",
        "-g",
        "pan.gfa",
        "-o",
        "/tmp/run/odgi_build/study_graph.odgi",
        "-t",
        "8",
        "-c",
        "-v",
        "&&",
        "odgi",
        "stats",
        "-i",
        "/tmp/run/odgi_build/study_graph.odgi",
        "-j",
        ">",
        "/tmp/run/odgi_build/study_graph.stats.json",
    ]


def test_odgi_build_omits_optional_flags_and_uses_input_stem() -> None:
    node_class = _node_class("odgi_build")

    cmd = node_class.render_command({
        "gfa_graph": "/data/pan.gfa",
        "threads": 0,
        "compact_ids": False,
        "validate": False,
        "output_name": "",
        "output": "/tmp/run/odgi_build",
    })

    assert "-t" not in cmd
    assert "-c" not in cmd
    assert "-v" not in cmd
    assert cmd == [
        "odgi",
        "build",
        "-g",
        "/data/pan.gfa",
        "-o",
        "/tmp/run/odgi_build/pan.odgi",
        "&&",
        "odgi",
        "stats",
        "-i",
        "/tmp/run/odgi_build/pan.odgi",
        "-j",
        ">",
        "/tmp/run/odgi_build/pan.stats.json",
    ]


def test_odgi_build_plans_outputs() -> None:
    node_class = _node_class("odgi_build")

    outputs = node_class.PLAN_OUTPUTS(
        {"gfa_graph": "pan.gfa", "output_name": "study graph"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/odgi_build/study_graph.odgi",
        "/tmp/run/odgi_build/study_graph.stats.json",
    ]


def test_odgi_build_rejects_negative_threads() -> None:
    node_class = _node_class("odgi_build")

    assert node_class.VALIDATE_INPUTS({
        "gfa_graph": "pan.gfa",
        "threads": -1,
    }) == "odgi Build threads must be zero or greater."


def test_vg_construct_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vg_construct"]
    assert node_info["display_name"] == "vg Construct"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Construct a variation graph")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["vg_graph"]
    assert node_info["required_executables"] == ["vg"]
    assert node_info["required_conda_packages"] == ["vg"]
    assert "variation graph" in node_info["search_aliases"]
    assert "graph genome" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reference", "vcf"}
    assert set(inputs["optional"]) == {"region", "max_node_size", "progress"}
    assert inputs["required"]["reference"][0] == "FASTA"
    assert inputs["required"]["vcf"][0] == "VCF_GZ"
    assert _node_class("vg_construct").INPUT_TYPES()["required"]["vcf"][0] == "VCF_GZ"


def test_vg_construct_renders_graph_command_for_compressed_vcf() -> None:
    node_class = _node_class("vg_construct")

    cmd = node_class.render_command({
        "reference": "ref.fa",
        "vcf": "variants.vcf.gz",
        "region": "chr1:1-1000000",
        "max_node_size": 64,
        "progress": True,
        "output": "/tmp/run/vg_construct",
    })

    assert cmd == [
        "vg",
        "construct",
        "-r",
        "ref.fa",
        "-a",
        "-f",
        "-S",
        "-v",
        "variants.vcf.gz",
        "-R",
        "chr1:1-1000000",
        "-m",
        "64",
        "-p",
        ">",
        "/tmp/run/vg_construct/vg_graph.vg",
    ]


def test_vg_construct_uses_plain_vcf_flag_and_omits_empty_options() -> None:
    node_class = _node_class("vg_construct")

    cmd = node_class.render_command({
        "reference": "ref.fa",
        "vcf": "variants.vcf",
        "region": "",
        "max_node_size": 0,
        "progress": False,
        "output": "/tmp/run/vg_construct",
    })

    assert "-R" not in cmd
    assert "-m" not in cmd
    assert "-p" not in cmd
    assert cmd == [
        "vg",
        "construct",
        "-r",
        "ref.fa",
        "-a",
        "-f",
        "-S",
        "-V",
        "variants.vcf",
        ">",
        "/tmp/run/vg_construct/vg_graph.vg",
    ]


def test_vg_construct_plans_outputs() -> None:
    node_class = _node_class("vg_construct")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/vg_construct/vg_graph.vg"]


def test_vg_index_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vg_index"]
    assert node_info["display_name"] == "vg Autoindex"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Build vg autoindex files")
    assert node_info["output"] == ["FILE", "FILE", "FILE", "FILE", "FILE"]
    assert node_info["output_name"] == [
        "gbz_index",
        "minimizer_index",
        "zipcode_index",
        "distance_index",
        "xg_index",
    ]
    assert node_info["required_executables"] == ["vg"]
    assert node_info["required_conda_packages"] == ["vg"]
    assert "autoindex" in node_info["search_aliases"]
    assert "giraffe" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"graph_gfa"}
    assert set(inputs["optional"]) == {"workflow", "threads", "output_prefix", "reference", "tmp_dir", "target_mem"}
    assert inputs["required"]["graph_gfa"][0] == "GFA"
    assert inputs["optional"]["reference"][0] == "FASTA"
    assert _node_class("vg_index").INPUT_TYPES()["required"]["graph_gfa"][0] == "GFA"


def test_vg_index_renders_autoindex_and_xg_conversion_command() -> None:
    node_class = _node_class("vg_index")

    cmd = node_class.render_command({
        "graph_gfa": "pan.gfa",
        "workflow": "giraffe",
        "threads": 12,
        "output_prefix": "study graph",
        "reference": "ref.fa",
        "tmp_dir": "/scratch/vg",
        "target_mem": "64G",
        "output": "/tmp/run/vg_index",
    })

    assert cmd == [
        "vg",
        "autoindex",
        "--workflow",
        "giraffe",
        "--gfa",
        "pan.gfa",
        "--ref-fasta",
        "ref.fa",
        "--prefix",
        "/tmp/run/vg_index/study_graph",
        "--threads",
        "12",
        "--tmp-dir",
        "/scratch/vg",
        "--target-mem",
        "64G",
        "&&",
        "vg",
        "convert",
        "-x",
        "--drop-haplotypes",
        "/tmp/run/vg_index/study_graph.giraffe.gbz",
        ">",
        "/tmp/run/vg_index/study_graph.xg",
    ]


def test_vg_index_omits_empty_optional_arguments() -> None:
    node_class = _node_class("vg_index")

    cmd = node_class.render_command({
        "graph_gfa": "/data/pan.gfa",
        "workflow": "giraffe",
        "threads": 8,
        "output_prefix": "",
        "reference": "",
        "tmp_dir": "",
        "target_mem": "",
        "output": "/tmp/run/vg_index",
    })

    assert "--ref-fasta" not in cmd
    assert "--tmp-dir" not in cmd
    assert "--target-mem" not in cmd
    assert cmd == [
        "vg",
        "autoindex",
        "--workflow",
        "giraffe",
        "--gfa",
        "/data/pan.gfa",
        "--prefix",
        "/tmp/run/vg_index/pan",
        "--threads",
        "8",
        "&&",
        "vg",
        "convert",
        "-x",
        "--drop-haplotypes",
        "/tmp/run/vg_index/pan.giraffe.gbz",
        ">",
        "/tmp/run/vg_index/pan.xg",
    ]


def test_vg_index_plans_outputs() -> None:
    node_class = _node_class("vg_index")

    outputs = node_class.PLAN_OUTPUTS(
        {"graph_gfa": "pan.gfa", "output_prefix": "study graph"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/vg_index/study_graph.giraffe.gbz",
        "/tmp/run/vg_index/study_graph.shortread.withzip.min",
        "/tmp/run/vg_index/study_graph.shortread.zipcodes",
        "/tmp/run/vg_index/study_graph.dist",
        "/tmp/run/vg_index/study_graph.xg",
    ]


def test_vg_index_rejects_unsupported_workflow() -> None:
    node_class = _node_class("vg_index")

    assert node_class.VALIDATE_INPUTS({
        "graph_gfa": "pan.gfa",
        "workflow": "mpmap",
        "threads": 8,
    }) == "Unsupported vg Autoindex workflow: mpmap"


def test_vg_index_rejects_non_positive_threads() -> None:
    node_class = _node_class("vg_index")

    assert node_class.VALIDATE_INPUTS({
        "graph_gfa": "pan.gfa",
        "workflow": "giraffe",
        "threads": 0,
    }) == "vg Autoindex threads must be greater than zero."


def test_vcf_decompose_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vcf_decompose"]
    assert node_info["display_name"] == "VCF Decompose"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Decompose complex variants")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["decomposed_vcf"]
    assert node_info["required_executables"] == ["vcfdecompose", "bgzip", "tabix"]
    assert node_info["required_conda_packages"] == ["vcflib", "htslib"]
    assert "pangenome vcf" in node_info["search_aliases"]
    assert "primitive variants" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "reference"}
    assert set(inputs["optional"]) == {"mode", "keep_info", "threads"}


def test_vcf_decompose_renders_normalize_and_index_command() -> None:
    node_class = _node_class("vcf_decompose")

    cmd = node_class.render_command({
        "vcf": "graph.vcf.gz",
        "reference": "ref.fa",
        "mode": "normalize",
        "keep_info": True,
        "threads": 4,
        "output": "/tmp/run/vcf_decompose",
    })

    assert cmd == [
        "vcfdecompose",
        "-k",
        "graph.vcf.gz",
        "|",
        "vcfallelicprimitives",
        "-kg",
        "-t",
        "DECOMPOSED",
        "-f",
        "ref.fa",
        "|",
        "bgzip",
        "--threads",
        "4",
        "-c",
        ">",
        "/tmp/run/vcf_decompose/decomposed_vcf.vcf.gz",
        "&&",
        "tabix",
        "-f",
        "-p",
        "vcf",
        "/tmp/run/vcf_decompose/decomposed_vcf.vcf.gz",
    ]


def test_vcf_decompose_supports_decompose_only_without_keep_info() -> None:
    node_class = _node_class("vcf_decompose")

    cmd = node_class.render_command({
        "vcf": "graph.vcf",
        "reference": "ref.fa",
        "mode": "decompose",
        "keep_info": False,
        "threads": 0,
        "output": "/tmp/run/vcf_decompose",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "vcfdecompose",
        "graph.vcf",
        "|",
        "bgzip",
        "-c",
        ">",
        "/tmp/run/vcf_decompose/decomposed_vcf.vcf.gz",
        "&&",
        "tabix",
        "-f",
        "-p",
        "vcf",
        "/tmp/run/vcf_decompose/decomposed_vcf.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/vcf_decompose/decomposed_vcf.vcf.gz"]


def test_vcf_decompose_rejects_unsupported_mode() -> None:
    node_class = _node_class("vcf_decompose")

    assert node_class.VALIDATE_INPUTS({
        "vcf": "graph.vcf.gz",
        "reference": "ref.fa",
        "mode": "explode",
    }) == "Unsupported VCF decompose mode: explode"


def test_pangenome_sv_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["pangenome_sv"]
    assert node_info["display_name"] == "Pangenome SV"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Call structural variants from a pangenome graph")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["vg", "bcftools", "bgzip", "tabix"]
    assert node_info["required_conda_packages"] == ["vg", "bcftools", "htslib"]
    assert "structural variants" in node_info["search_aliases"]
    assert "pangenome graph" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"graph_gfa", "reference"}
    assert set(inputs["optional"]) == {"sample_name", "threads", "ref_path", "min_sv_length"}
    assert inputs["required"]["graph_gfa"][0] == "GFA"
    assert inputs["required"]["reference"][0] == "FASTA"


def test_pangenome_sv_renders_graph_vcf_pipeline() -> None:
    node_class = _node_class("pangenome_sv")

    cmd = node_class.render_command({
        "graph_gfa": "pan.gfa",
        "reference": "ref.fa",
        "sample_name": "sample-a",
        "threads": 8,
        "ref_path": "chr1",
        "min_sv_length": 50,
        "output": "/tmp/run/pangenome_sv",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "printf",
        "'sample-a\\n'",
        ">",
        "/tmp/run/pangenome_sv/samples.txt",
        "&&",
        "vg",
        "autoindex",
        "--workflow",
        "giraffe",
        "--gfa",
        "pan.gfa",
        "--ref-fasta",
        "ref.fa",
        "--prefix",
        "/tmp/run/pangenome_sv/graph",
        "--threads",
        "8",
        "&&",
        "vg",
        "deconstruct",
        "/tmp/run/pangenome_sv/graph.xg",
        "-P",
        "chr1",
        "-a",
        "-e",
        "-t",
        "8",
        "|",
        "bcftools",
        "view",
        "-i",
        "ABS(ILEN)>=50 || ABS(strlen(ALT)-strlen(REF))>=50",
        "|",
        "bcftools",
        "reheader",
        "-s",
        "/tmp/run/pangenome_sv/samples.txt",
        "|",
        "bgzip",
        "--threads",
        "8",
        "-c",
        ">",
        "/tmp/run/pangenome_sv/sv_vcf.vcf.gz",
        "&&",
        "tabix",
        "-f",
        "-p",
        "vcf",
        "/tmp/run/pangenome_sv/sv_vcf.vcf.gz",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/pangenome_sv/sv_vcf.vcf.gz"]


def test_pangenome_sv_omits_optional_filters_and_reheader() -> None:
    node_class = _node_class("pangenome_sv")

    cmd = node_class.render_command({
        "graph_gfa": "pan.gfa",
        "reference": "ref.fa",
        "sample_name": "",
        "threads": 0,
        "ref_path": "",
        "min_sv_length": 0,
        "output": "/tmp/run/pangenome_sv",
    })

    assert "-P" not in cmd
    assert "bcftools" not in cmd
    assert "--threads" not in cmd
    assert cmd == [
        "vg",
        "autoindex",
        "--workflow",
        "giraffe",
        "--gfa",
        "pan.gfa",
        "--ref-fasta",
        "ref.fa",
        "--prefix",
        "/tmp/run/pangenome_sv/graph",
        "&&",
        "vg",
        "deconstruct",
        "/tmp/run/pangenome_sv/graph.xg",
        "-a",
        "-e",
        "|",
        "bgzip",
        "-c",
        ">",
        "/tmp/run/pangenome_sv/sv_vcf.vcf.gz",
        "&&",
        "tabix",
        "-f",
        "-p",
        "vcf",
        "/tmp/run/pangenome_sv/sv_vcf.vcf.gz",
    ]


def test_pangenome_sv_rejects_negative_min_sv_length() -> None:
    node_class = _node_class("pangenome_sv")

    assert node_class.VALIDATE_INPUTS({
        "graph_gfa": "pan.gfa",
        "reference": "ref.fa",
        "min_sv_length": -1,
    }) == "Minimum SV length must be non-negative"


def test_pangenome_stats_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["pangenome_stats"]
    assert node_info["display_name"] == "Pangenome Stats"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Compute core, shell, and cloud pangenome statistics")
    assert node_info["output"] == ["JSON", "FILE"]
    assert node_info["output_name"] == ["stats", "rarefaction"]
    assert node_info["required_executables"] == ["panacus"]
    assert node_info["required_conda_packages"] == ["panacus"]
    assert "core genes" in node_info["search_aliases"]
    assert "rarefaction" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"graph", "annotations"}
    assert set(inputs["optional"]) == {"core_threshold", "shell_threshold", "groupby", "threads", "include_html"}
    assert inputs["required"]["graph"][0] == "GFA"
    assert inputs["required"]["annotations"][0] == "GFF"


def test_pangenome_stats_renders_histgrowth_and_summary_command() -> None:
    node_class = _node_class("pangenome_stats")

    cmd = node_class.render_command({
        "graph": "pan.gfa",
        "annotations": "genes.gff",
        "groupby": "sample-groups.tsv",
        "core_threshold": 0.95,
        "shell_threshold": 0.15,
        "threads": 6,
        "include_html": True,
        "output": "/tmp/run/pangenome_stats",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "panacus",
        "histgrowth",
        "pan.gfa",
        "--gff",
        "genes.gff",
        "--groupby",
        "sample-groups.tsv",
        "--threads",
        "6",
        "--html",
        "/tmp/run/pangenome_stats/rarefaction.html",
        ">",
        "/tmp/run/pangenome_stats/rarefaction.tsv",
        "&&",
        "python",
        "-m",
        "bionodulo.nodes.scripts.pangenome_stats_summary",
        "--input",
        "/tmp/run/pangenome_stats/rarefaction.tsv",
        "--output",
        "/tmp/run/pangenome_stats/stats.json",
        "--core-threshold",
        "0.95",
        "--shell-threshold",
        "0.15",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/pangenome_stats/stats.json",
        "/tmp/run/pangenome_stats/rarefaction.tsv",
    ]


def test_pangenome_stats_omits_optional_arguments() -> None:
    node_class = _node_class("pangenome_stats")

    cmd = node_class.render_command({
        "graph": "pan.gfa",
        "annotations": "genes.gff",
        "groupby": "",
        "core_threshold": 0.9,
        "shell_threshold": 0.1,
        "threads": 0,
        "include_html": False,
        "output": "/tmp/run/pangenome_stats",
    })

    assert "--groupby" not in cmd
    assert "--threads" not in cmd
    assert "--html" not in cmd
    assert cmd == [
        "panacus",
        "histgrowth",
        "pan.gfa",
        "--gff",
        "genes.gff",
        ">",
        "/tmp/run/pangenome_stats/rarefaction.tsv",
        "&&",
        "python",
        "-m",
        "bionodulo.nodes.scripts.pangenome_stats_summary",
        "--input",
        "/tmp/run/pangenome_stats/rarefaction.tsv",
        "--output",
        "/tmp/run/pangenome_stats/stats.json",
        "--core-threshold",
        "0.9",
        "--shell-threshold",
        "0.1",
    ]


def test_pangenome_stats_rejects_invalid_threshold_order() -> None:
    node_class = _node_class("pangenome_stats")

    assert node_class.VALIDATE_INPUTS({
        "graph": "pan.gfa",
        "annotations": "genes.gff",
        "core_threshold": 0.1,
        "shell_threshold": 0.2,
    }) == "Core threshold must be greater than shell threshold"


def test_pangenome_gene_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["pangenome_gene"]
    assert node_info["display_name"] == "Pangenome Gene"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Extract gene presence/absence")
    assert node_info["output"] == ["FILE", "IMAGE"]
    assert node_info["output_name"] == ["presence_matrix", "pan_genome_plot"]
    assert node_info["required_executables"] == ["panaroo"]
    assert node_info["required_conda_packages"] == ["panaroo"]
    assert "presence absence" in node_info["search_aliases"]
    assert "orthologs" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"annotations", "orthologs"}
    assert set(inputs["optional"]) == {
        "clean_mode",
        "threads",
        "core_threshold",
        "remove_invalid_genes",
        "merge_paralogs",
    }
    assert inputs["required"]["annotations"][0] == "GFF"
    assert inputs["required"]["orthologs"][0] == "FILE"


def test_pangenome_gene_renders_panaroo_matrix_and_plot_command() -> None:
    node_class = _node_class("pangenome_gene")

    cmd = node_class.render_command({
        "annotations": ["sample-a.gff", "sample-b.gff"],
        "orthologs": "orthologs.tsv",
        "clean_mode": "strict",
        "threads": 8,
        "core_threshold": 0.95,
        "remove_invalid_genes": True,
        "merge_paralogs": True,
        "output": "/tmp/run/pangenome_gene",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "panaroo",
        "-i",
        "sample-a.gff",
        "sample-b.gff",
        "-o",
        "/tmp/run/pangenome_gene",
        "--clean-mode",
        "strict",
        "-t",
        "8",
        "--core_threshold",
        "0.95",
        "--remove-invalid-genes",
        "--merge_paralogs",
        "&&",
        "cp",
        "/tmp/run/pangenome_gene/gene_presence_absence.Rtab",
        "/tmp/run/pangenome_gene/presence_matrix.tsv",
        "&&",
        "cp",
        "orthologs.tsv",
        "/tmp/run/pangenome_gene/orthologs.tsv",
        "&&",
        "python",
        "-m",
        "bionodulo.nodes.scripts.pangenome_gene_plot",
        "--input",
        "/tmp/run/pangenome_gene/presence_matrix.tsv",
        "--output",
        "/tmp/run/pangenome_gene/pan_genome_plot.svg",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/pangenome_gene/presence_matrix.tsv",
        "/tmp/run/pangenome_gene/pan_genome_plot.svg",
    ]


def test_pangenome_gene_accepts_delimited_annotation_paths_and_omits_optional_flags() -> None:
    node_class = _node_class("pangenome_gene")

    cmd = node_class.render_command({
        "annotations": "sample-a.gff, sample-b.gff\nsample-c.gff",
        "orthologs": "orthologs.tsv",
        "clean_mode": "sensitive",
        "threads": 0,
        "core_threshold": 0,
        "remove_invalid_genes": False,
        "merge_paralogs": False,
        "output": "/tmp/run/pangenome_gene",
    })

    assert "-t" not in cmd
    assert "--core_threshold" not in cmd
    assert "--remove-invalid-genes" not in cmd
    assert "--merge_paralogs" not in cmd
    assert cmd == [
        "panaroo",
        "-i",
        "sample-a.gff",
        "sample-b.gff",
        "sample-c.gff",
        "-o",
        "/tmp/run/pangenome_gene",
        "--clean-mode",
        "sensitive",
        "&&",
        "cp",
        "/tmp/run/pangenome_gene/gene_presence_absence.Rtab",
        "/tmp/run/pangenome_gene/presence_matrix.tsv",
        "&&",
        "cp",
        "orthologs.tsv",
        "/tmp/run/pangenome_gene/orthologs.tsv",
        "&&",
        "python",
        "-m",
        "bionodulo.nodes.scripts.pangenome_gene_plot",
        "--input",
        "/tmp/run/pangenome_gene/presence_matrix.tsv",
        "--output",
        "/tmp/run/pangenome_gene/pan_genome_plot.svg",
    ]


def test_pangenome_gene_rejects_empty_annotations_and_invalid_clean_mode() -> None:
    node_class = _node_class("pangenome_gene")

    assert node_class.VALIDATE_INPUTS({
        "annotations": [],
        "orthologs": "orthologs.tsv",
        "clean_mode": "strict",
    }) == "At least one GFF annotation is required"
    assert node_class.VALIDATE_INPUTS({
        "annotations": ["sample-a.gff"],
        "orthologs": "orthologs.tsv",
        "clean_mode": "loose",
    }) == "Unsupported Panaroo clean mode: loose"


def test_pangenome_stats_summary_counts_core_shell_and_cloud_features() -> None:
    summary = summarize_table(
        StringIO("feature\t1\t2\t3\ncore\t10\t10\t10\nshell\t1\t5\t5\ncloud\t1\t1\t1\n"),
        core_threshold=0.9,
        shell_threshold=0.2,
    )

    assert summary == {
        "rows": 3,
        "core_threshold": 0.9,
        "shell_threshold": 0.2,
        "core_features": 1,
        "shell_features": 1,
        "cloud_features": 1,
        "max_observed": 10.0,
    }


def test_vcflib_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["vcfdecompose"] == "vcflib"
    assert EXECUTABLE_TO_CONDA_PACKAGE["vcfallelicprimitives"] == "vcflib"
    assert EXECUTABLE_TO_CONDA_PACKAGE["bgzip"] == "htslib"
    assert EXECUTABLE_TO_CONDA_PACKAGE["tabix"] == "htslib"
    assert PACKAGE_MIN_VERSIONS["vcflib"] == ">=1.0.9"
    assert PACKAGE_MIN_VERSIONS["htslib"] == ">=1.15"


def test_vg_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["vg"] == "vg"
    assert PACKAGE_MIN_VERSIONS["vg"] == ">=1.62.0"


def test_panacus_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["panacus"] == "panacus"
    assert PACKAGE_MIN_VERSIONS["panacus"] == ">=0.3.3"


def test_panaroo_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["panaroo"] == "panaroo"
    assert PACKAGE_MIN_VERSIONS["panaroo"] == ">=1.5.0"


def test_vg_map_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vg_map"]
    assert node_info["display_name"] == "vg Map/Giraffe"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Map reads to a variation graph")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["gam_alignment"]
    assert node_info["required_executables"] == ["vg"]
    assert node_info["required_conda_packages"] == ["vg"]
    assert "giraffe" in node_info["search_aliases"]
    assert "graph alignment" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "mapper", "threads"}
    assert set(inputs["optional"]) == {
        "reads2",
        "gbz_index",
        "minimizer_index",
        "zipcode_index",
        "distance_index",
        "xg_index",
        "gcsa_index",
        "min_identity",
    }
    assert inputs["required"]["reads"][0] == "FASTQ"
    assert inputs["required"]["mapper"][0] == "STRING"
    assert _node_class("vg_map").INPUT_TYPES()["optional"]["gbz_index"][0] == "FILE"


def test_vg_map_renders_giraffe_command_with_paired_reads() -> None:
    node_class = _node_class("vg_map")

    cmd = node_class.render_command({
        "reads": "reads_R1.fastq.gz",
        "reads2": "reads_R2.fastq.gz",
        "mapper": "giraffe",
        "gbz_index": "graph.gbz",
        "minimizer_index": "graph.min",
        "zipcode_index": "graph.zipcodes",
        "distance_index": "graph.dist",
        "threads": 12,
        "output": "/tmp/run/vg_map",
    })

    assert cmd == [
        "vg",
        "giraffe",
        "-Z",
        "graph.gbz",
        "-m",
        "graph.min",
        "-z",
        "graph.zipcodes",
        "-d",
        "graph.dist",
        "-f",
        "reads_R1.fastq.gz",
        "-p",
        "-t",
        "12",
        "-f",
        "reads_R2.fastq.gz",
        ">",
        "/tmp/run/vg_map/gam_alignment.gam",
    ]


def test_vg_map_renders_classic_map_command_with_min_identity() -> None:
    node_class = _node_class("vg_map")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "reads2": "",
        "mapper": "map",
        "xg_index": "graph.xg",
        "gcsa_index": "graph.gcsa",
        "min_identity": 0.82,
        "threads": 8,
        "output": "/tmp/run/vg_map",
    })

    assert cmd == [
        "vg",
        "map",
        "-x",
        "graph.xg",
        "-g",
        "graph.gcsa",
        "-f",
        "reads.fastq.gz",
        "-t",
        "8",
        "-p",
        "--min-ident",
        "0.82",
        ">",
        "/tmp/run/vg_map/gam_alignment.gam",
    ]


def test_vg_map_omits_empty_optional_flags() -> None:
    node_class = _node_class("vg_map")

    cmd = node_class.render_command({
        "reads": "reads.fastq.gz",
        "reads2": "",
        "mapper": "map",
        "xg_index": "graph.xg",
        "gcsa_index": "graph.gcsa",
        "min_identity": 0,
        "threads": 4,
        "output": "/tmp/run/vg_map",
    })

    assert "--min-ident" not in cmd
    assert cmd.count("-f") == 1


def test_vg_map_plans_outputs() -> None:
    node_class = _node_class("vg_map")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/vg_map/gam_alignment.gam"]


def test_vg_call_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vg_call"]
    assert node_info["display_name"] == "vg Call Variants"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Call variants from graph alignments")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["calls_vcf"]
    assert node_info["required_executables"] == ["vg"]
    assert node_info["required_conda_packages"] == ["vg"]
    assert "variant calling" in node_info["search_aliases"]
    assert "graph caller" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"xg_graph", "gam", "threads"}
    assert set(inputs["optional"]) == {"ref_path", "sample"}
    assert inputs["required"]["xg_graph"][0] == "FILE"
    assert inputs["required"]["gam"][0] == "FILE"


def test_vg_call_renders_pack_and_call_command_with_options() -> None:
    node_class = _node_class("vg_call")

    cmd = node_class.render_command({
        "xg_graph": "graph.xg",
        "gam": "mapped.gam",
        "threads": 8,
        "ref_path": "GRCh38#chr1",
        "sample": "HG002",
        "output": "/tmp/run/vg_call",
    })

    assert cmd == [
        "vg",
        "pack",
        "-x",
        "graph.xg",
        "-g",
        "mapped.gam",
        "-o",
        "/tmp/run/vg_call/aln.pack",
        "-t",
        "8",
        "&&",
        "vg",
        "call",
        "graph.xg",
        "-k",
        "/tmp/run/vg_call/aln.pack",
        "-t",
        "8",
        "-v",
        "-p",
        "GRCh38#chr1",
        "-s",
        "HG002",
        ">",
        "/tmp/run/vg_call/calls_vcf.vcf",
    ]


def test_vg_call_omits_empty_optional_flags() -> None:
    node_class = _node_class("vg_call")

    cmd = node_class.render_command({
        "xg_graph": "graph.xg",
        "gam": "mapped.gam",
        "threads": 4,
        "ref_path": "",
        "sample": "",
        "output": "/tmp/run/vg_call",
    })

    assert "-p" not in cmd
    assert "-s" not in cmd
    assert cmd == [
        "vg",
        "pack",
        "-x",
        "graph.xg",
        "-g",
        "mapped.gam",
        "-o",
        "/tmp/run/vg_call/aln.pack",
        "-t",
        "4",
        "&&",
        "vg",
        "call",
        "graph.xg",
        "-k",
        "/tmp/run/vg_call/aln.pack",
        "-t",
        "4",
        "-v",
        ">",
        "/tmp/run/vg_call/calls_vcf.vcf",
    ]


def test_vg_call_plans_outputs() -> None:
    node_class = _node_class("vg_call")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/vg_call/calls_vcf.vcf"]


def test_minigraph_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["minigraph"]
    assert node_info["display_name"] == "Minigraph"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Fast sequence-to-graph aligner")
    assert node_info["output"] == ["GFA"]
    assert node_info["output_name"] == ["output_gfa"]
    assert node_info["required_executables"] == ["minigraph"]
    assert node_info["required_conda_packages"] == ["minigraph"]
    assert "sequence to graph" in node_info["search_aliases"]
    assert "sv graph" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"mode", "threads"}
    assert set(inputs["optional"]) == {"assemblies", "graph_gfa", "query_fasta", "preset"}
    assert inputs["optional"]["assemblies"][0] == "FASTA"
    assert inputs["optional"]["graph_gfa"][0] == "GFA"


def test_minigraph_renders_construct_command_with_assemblies_and_preset() -> None:
    node_class = _node_class("minigraph")

    cmd = node_class.render_command({
        "mode": "construct",
        "threads": 16,
        "preset": "asm",
        "assemblies": ["ref.fa", "sample1.fa", "sample2.fa"],
        "output": "/tmp/run/minigraph",
    })

    assert cmd == [
        "minigraph",
        "-cxggs",
        "-t",
        "16",
        "-x",
        "asm",
        "ref.fa",
        "sample1.fa",
        "sample2.fa",
        ">",
        "/tmp/run/minigraph/output_gfa.gfa",
    ]


def test_minigraph_renders_align_command() -> None:
    node_class = _node_class("minigraph")

    cmd = node_class.render_command({
        "mode": "align",
        "threads": 8,
        "preset": "ggs",
        "graph_gfa": "graph.gfa",
        "query_fasta": "query.fa",
        "output": "/tmp/run/minigraph",
    })

    assert cmd == [
        "minigraph",
        "-cx",
        "ggs",
        "-t",
        "8",
        "graph.gfa",
        "query.fa",
        ">",
        "/tmp/run/minigraph/output_gfa.gfa",
    ]


def test_minigraph_omits_construct_preset_when_empty() -> None:
    node_class = _node_class("minigraph")

    cmd = node_class.render_command({
        "mode": "construct",
        "threads": 4,
        "preset": "",
        "assemblies": "ref.fa",
        "output": "/tmp/run/minigraph",
    })

    assert "-x" not in cmd
    assert cmd == [
        "minigraph",
        "-cxggs",
        "-t",
        "4",
        "ref.fa",
        ">",
        "/tmp/run/minigraph/output_gfa.gfa",
    ]


def test_minigraph_plans_outputs() -> None:
    node_class = _node_class("minigraph")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/minigraph/output_gfa.gfa"]


def test_pggb_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["pggb"]
    assert node_info["display_name"] == "PGGB Build"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Reference-free pangenome graph builder")
    assert node_info["output"] == ["GFA", "FASTA"]
    assert node_info["output_name"] == ["smooth_gfa", "consensus_fasta"]
    assert node_info["required_executables"] == ["pggb"]
    assert node_info["required_conda_packages"] == ["pggb"]
    assert "all-vs-all" in node_info["search_aliases"]
    assert "graph construction" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_fasta", "num_haplotypes", "threads"}
    assert set(inputs["optional"]) == {
        "map_pct_id",
        "segment_length",
        "min_match_length",
        "graph_poas",
        "consensus_spec",
        "do_viz",
        "do_layout",
    }
    assert inputs["required"]["input_fasta"][0] == "FASTA"


def test_pggb_renders_build_command_with_optional_flags() -> None:
    node_class = _node_class("pggb")

    cmd = node_class.render_command({
        "input_fasta": "haplotypes.fa",
        "num_haplotypes": 6,
        "threads": 32,
        "map_pct_id": 95,
        "segment_length": 10000,
        "min_match_length": 29,
        "graph_poas": 3,
        "consensus_spec": "100,1000,10000",
        "do_viz": True,
        "do_layout": True,
        "output": "/tmp/run/pggb",
    })

    assert cmd == [
        "pggb",
        "-i",
        "haplotypes.fa",
        "-o",
        "/tmp/run/pggb",
        "-n",
        "6",
        "-t",
        "32",
        "-p",
        "95",
        "-s",
        "10000",
        "-k",
        "29",
        "-G",
        "3",
        "--do-viz",
        "--do-layout",
        "-C",
        "100,1000,10000",
    ]


def test_pggb_omits_empty_optional_flags() -> None:
    node_class = _node_class("pggb")

    cmd = node_class.render_command({
        "input_fasta": "haplotypes.fa",
        "num_haplotypes": 2,
        "threads": 16,
        "map_pct_id": 90,
        "segment_length": 5000,
        "min_match_length": 19,
        "graph_poas": 2,
        "consensus_spec": "",
        "do_viz": False,
        "do_layout": False,
        "output": "/tmp/run/pggb",
    })

    assert "--do-viz" not in cmd
    assert "--do-layout" not in cmd
    assert "-C" not in cmd
    assert cmd == [
        "pggb",
        "-i",
        "haplotypes.fa",
        "-o",
        "/tmp/run/pggb",
        "-n",
        "2",
        "-t",
        "16",
        "-p",
        "90",
        "-s",
        "5000",
        "-k",
        "19",
        "-G",
        "2",
    ]


def test_pggb_plans_outputs() -> None:
    node_class = _node_class("pggb")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/pggb/smooth_gfa.gfa",
        "/tmp/run/pggb/consensus_fasta.fa",
    ]


def test_pggb_build_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["pggb_build"]
    assert node_info["display_name"] == "PGGB Build"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Construct pangenome graph")
    assert node_info["output"] == ["GFA", "ODGI"]
    assert node_info["output_name"] == ["graph_gfa", "graph_odgi"]
    assert node_info["required_executables"] == ["pggb"]
    assert node_info["required_conda_packages"] == ["pggb"]
    assert "haplotypes" in node_info["search_aliases"]
    assert "pggb" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_fasta", "threads"}
    assert set(inputs["optional"]) == {"map_pct_id", "segment_length", "min_match_length", "graph_poas"}
    assert inputs["required"]["input_fasta"][0] == "FASTA"
    assert inputs["required"]["threads"][0] == "INT"


def test_pggb_build_renders_graph_build_command() -> None:
    node_class = _node_class("pggb_build")

    cmd = node_class.render_command({
        "input_fasta": ["hap1.fa", "hap2.fa", "hap3.fa"],
        "threads": 12,
        "map_pct_id": 94,
        "segment_length": 7000,
        "min_match_length": 25,
        "graph_poas": 4,
        "output": "/tmp/run/pggb_build",
    })

    assert cmd == [
        "cat",
        "hap1.fa",
        "hap2.fa",
        "hap3.fa",
        ">",
        "/tmp/run/pggb_build/haplotypes.fa",
        "&&",
        "pggb",
        "-i",
        "/tmp/run/pggb_build/haplotypes.fa",
        "-o",
        "/tmp/run/pggb_build/pggb",
        "-n",
        "3",
        "-t",
        "12",
        "-p",
        "94",
        "-s",
        "7000",
        "-k",
        "25",
        "-G",
        "4",
        "&&",
        "find",
        "/tmp/run/pggb_build/pggb",
        "-name",
        "*.smooth.final.gfa",
        "-print",
        "-quit",
        "|",
        "xargs",
        "-r",
        "-I{}",
        "cp",
        "-f",
        "{}",
        "/tmp/run/pggb_build/graph_gfa.gfa",
        "&&",
        "find",
        "/tmp/run/pggb_build/pggb",
        "-name",
        "*.smooth.final.og",
        "-print",
        "-quit",
        "|",
        "xargs",
        "-r",
        "-I{}",
        "cp",
        "-f",
        "{}",
        "/tmp/run/pggb_build/graph_odgi.odgi",
    ]


def test_pggb_build_renders_string_fasta_list() -> None:
    node_class = _node_class("pggb_build")

    cmd = node_class.render_command({
        "input_fasta": "hap1.fa,hap2.fa hap3.fa",
        "threads": 8,
        "output": "/tmp/run/pggb_build",
    })

    assert cmd[:7] == [
        "cat",
        "hap1.fa",
        "hap2.fa",
        "hap3.fa",
        ">",
        "/tmp/run/pggb_build/haplotypes.fa",
        "&&",
    ]
    haplotype_count_index = cmd.index("-n")
    assert cmd[haplotype_count_index:haplotype_count_index + 2] == ["-n", "3"]


def test_pggb_build_plans_outputs() -> None:
    node_class = _node_class("pggb_build")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/pggb_build/graph_gfa.gfa",
        "/tmp/run/pggb_build/graph_odgi.odgi",
    ]


def test_pggb_build_requires_multiple_haplotypes() -> None:
    node_class = _node_class("pggb_build")

    assert node_class.VALIDATE_INPUTS({"input_fasta": "hap1.fa", "threads": 4}) == (
        "PGGB Build requires at least two haplotype FASTA files."
    )


def test_pggb_build_requires_positive_threads() -> None:
    node_class = _node_class("pggb_build")

    assert node_class.VALIDATE_INPUTS({"input_fasta": ["hap1.fa", "hap2.fa"], "threads": 0}) == (
        "PGGB Build threads must be greater than zero."
    )


def test_pggb_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["pggb"] == "pggb"
    assert PACKAGE_MIN_VERSIONS["pggb"] == ">=0.7.3"


def test_minigraph_cactus_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["minigraph_cactus"]
    assert node_info["display_name"] == "Minigraph-Cactus"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"].startswith("Build pangenome graphs from assemblies")
    assert node_info["output"] == ["GBZ", "VCF_GZ", "GFA", "ODGI"]
    assert node_info["output_name"] == ["graph_gbz", "variants_vcf", "graph_gfa", "graph_odgi"]
    assert node_info["required_executables"] == ["cactus-pangenome"]
    assert node_info["required_conda_packages"] == ["cactus"]
    assert "HPRC" in node_info["search_aliases"]
    assert "cactus-pangenome" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"seq_file", "reference"}
    assert set(inputs["optional"]) == {
        "out_name",
        "work_dir",
        "threads",
        "max_cores",
        "cons_batch_size",
        "gbz",
        "giraffe",
        "vcf",
        "gfa",
        "odgi",
        "viz",
        "chrom_vg",
    }
    assert inputs["required"]["seq_file"][0] == "FILE"
    assert inputs["required"]["reference"][0] == "STRING"


def test_minigraph_cactus_renders_pangenome_command_with_optional_outputs() -> None:
    node_class = _node_class("minigraph_cactus")

    cmd = node_class.render_command({
        "seq_file": "seqFile.txt",
        "reference": "GRCh38",
        "out_name": "hprc_pg",
        "work_dir": "/scratch/cactus",
        "threads": 48,
        "max_cores": 12,
        "cons_batch_size": 4,
        "gbz": True,
        "giraffe": True,
        "vcf": True,
        "gfa": True,
        "odgi": True,
        "viz": True,
        "chrom_vg": True,
        "output": "/tmp/run/minigraph_cactus",
    })

    assert cmd == [
        "cactus-pangenome",
        "/scratch/cactus",
        "seqFile.txt",
        "--outDir",
        "/tmp/run/minigraph_cactus",
        "--outName",
        "hprc_pg",
        "--reference",
        "GRCh38",
        "--maxCores",
        "12",
        "--batchSize",
        "4",
        "--gbz",
        "--giraffe",
        "--vcf",
        "--gfa",
        "--odgi",
        "--viz",
        "--chrom-vg",
    ]
    assert "--threads" not in cmd


def test_minigraph_cactus_defaults_work_dir_and_output_flags() -> None:
    node_class = _node_class("minigraph_cactus")

    cmd = node_class.render_command({
        "seq_file": "assemblies.tsv",
        "reference": "sample_ref",
        "out_name": "",
        "work_dir": "",
        "threads": 16,
        "max_cores": 0,
        "cons_batch_size": 0,
        "gbz": True,
        "giraffe": False,
        "vcf": False,
        "gfa": True,
        "odgi": False,
        "viz": False,
        "chrom_vg": False,
        "output": "/tmp/run/minigraph_cactus",
    })

    assert cmd == [
        "cactus-pangenome",
        "/tmp/run/minigraph_cactus/work",
        "assemblies.tsv",
        "--outDir",
        "/tmp/run/minigraph_cactus",
        "--outName",
        "pangenome",
        "--reference",
        "sample_ref",
        "--maxCores",
        "16",
        "--gbz",
        "--gfa",
    ]
    assert "--giraffe" not in cmd
    assert "--vcf" not in cmd
    assert "--odgi" not in cmd
    assert "--viz" not in cmd
    assert "--chrom-vg" not in cmd


def test_minigraph_cactus_plans_requested_outputs() -> None:
    node_class = _node_class("minigraph_cactus")

    outputs = node_class.PLAN_OUTPUTS({
        "out_name": "study_pg",
        "gbz": True,
        "vcf": True,
        "gfa": True,
        "odgi": True,
    }, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/minigraph_cactus/study_pg.gbz",
        "/tmp/run/minigraph_cactus/study_pg.vcf.gz",
        "/tmp/run/minigraph_cactus/study_pg.gfa.gz",
        "/tmp/run/minigraph_cactus/study_pg.og",
    ]


def test_minigraph_cactus_rejects_missing_output_flags_and_non_positive_threads() -> None:
    node_class = _node_class("minigraph_cactus")

    assert node_class.VALIDATE_INPUTS({
        "seq_file": "seqFile.txt",
        "reference": "GRCh38",
        "threads": 4,
        "gbz": False,
        "vcf": False,
        "gfa": False,
        "odgi": False,
    }) == "Minigraph-Cactus requires at least one graph or variant output flag."
    assert node_class.VALIDATE_INPUTS({
        "seq_file": "seqFile.txt",
        "reference": "GRCh38",
        "threads": 0,
        "gbz": True,
    }) == "Minigraph-Cactus threads must be greater than zero."


def test_minigraph_cactus_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["cactus-pangenome"] == "cactus"
    assert PACKAGE_MIN_VERSIONS["cactus"] == ">=2.9.0"


def test_bionodulo_builtin_cactus_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cactus_cactus"]
    assert node_info["display_name"] == "Cactus"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"] == "Whole-genome multiple sequence alignment with Progressive Cactus or Minigraph-Cactus."
    assert node_info["output"] == ["FILE", "GFA"]
    assert node_info["output_name"] == ["out_hal", "out_gfa"]
    assert node_info["required_executables"] == ["cactus", "cactus-pangenome"]
    assert node_info["required_conda_packages"] == ["cactus"]
    assert node_info["documentation_url"] == "https://github.com/ComparativeGenomicsToolkit/cactus"
    assert node_info["citation_dois"] == ["10.1038/s41586-020-2871-y"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1038/s41586-020-2871-y"]
    assert "Progressive Cactus is a multiple-genome aligner" in node_info["citation_text"]
    assert "BioNodulo builtin" in node_info["search_aliases"]
    assert "whole-genome multiple alignment" in node_info["search_aliases"]
    assert node_info["version"] == "2.7.1+galaxy0"

    inputs = node_info["input"]
    assert inputs["required"]["in_seqs"][0] == "STRING"
    assert inputs["required"]["in_seqs"][1]["multiple"] is True
    assert inputs["required"]["labels"][0] == "STRING"
    assert inputs["optional"]["aln_mode_select"][1]["default"] == "interspecies"
    assert inputs["optional"]["aln_mode_select"][1]["options"] == ["interspecies", "intraspecies"]
    assert inputs["optional"]["in_tree"][0] == "FILE"
    assert inputs["optional"]["ref_level"][0] == "STRING"
    assert inputs["optional"]["max_cores"][1]["default"] == 4
    assert inputs["optional"]["max_memory_mb"][1]["default"] == 16384
    assert _node_class("cactus_cactus").INPUT_TYPES()["required"]["in_seqs"][0] == "FASTA_LIST"
    assert _node_class("cactus_cactus").INPUT_TYPES()["required"]["labels"][0] == "STRING_LIST"


def test_bionodulo_builtin_cactus_renders_interspecies_command_and_outputs() -> None:
    node_class = _node_class("cactus_cactus")

    cmd = node_class.render_command({
        "aln_mode_select": "interspecies",
        "in_tree": "guide tree.nhx",
        "in_seqs": ["cow.fa", "dog genome.fa"],
        "labels": ["simCow_chr6", "simDog_chr6"],
        "max_cores": 8,
        "max_memory_mb": 32768,
        "output": "/tmp/run/cactus_cactus",
    })

    assert cmd == [
        "mkdir",
        "-p",
        "/tmp/run/cactus_cactus",
        "&&",
        "cat",
        "guide tree.nhx",
        ">",
        "/tmp/run/cactus_cactus/seqfile.txt",
        "&&",
        "ln",
        "-s",
        "cow.fa",
        "/tmp/run/cactus_cactus/simCow_chr6.fa",
        "&&",
        "printf",
        "%s %s\n",
        "simCow_chr6",
        "simCow_chr6.fa",
        ">>",
        "/tmp/run/cactus_cactus/seqfile.txt",
        "&&",
        "ln",
        "-s",
        "dog genome.fa",
        "/tmp/run/cactus_cactus/simDog_chr6.fa",
        "&&",
        "printf",
        "%s %s\n",
        "simDog_chr6",
        "simDog_chr6.fa",
        ">>",
        "/tmp/run/cactus_cactus/seqfile.txt",
        "&&",
        "cd",
        "/tmp/run/cactus_cactus",
        "&&",
        "cactus",
        "--binariesMode",
        "local",
        "--maxCores",
        "8",
        "--maxMemory",
        "32768M",
        "--workDir",
        "./",
        "jobStore",
        "seqfile.txt",
        "alignment.full.hal",
    ]

    assert [str(path) for path in node_class.PLAN_OUTPUTS({"aln_mode_select": "interspecies"}, "/tmp/run")] == [
        "/tmp/run/cactus_cactus/alignment.full.hal",
    ]


def test_bionodulo_builtin_cactus_renders_intraspecies_command_outputs_and_validation() -> None:
    node_class = _node_class("cactus_cactus")

    cmd = node_class.render_command({
        "aln_mode_select": "intraspecies",
        "ref_level": "simCow_chr6",
        "in_seqs": ["cow.fa", "dog.fa"],
        "labels": ["simCow_chr6", "simDog_chr6"],
        "max_cores": 16,
        "max_memory_mb": 64000,
        "output": "/tmp/run/cactus_cactus",
    })

    assert cmd[-15:] == [
        "cactus-pangenome",
        "--reference",
        "simCow_chr6",
        "--binariesMode",
        "local",
        "--maxCores",
        "16",
        "--maxMemory",
        "64000M",
        "--outDir",
        "./",
        "--outName",
        "alignment",
        "jobStore",
        "seqfile.txt",
    ]
    assert [str(path) for path in node_class.PLAN_OUTPUTS({"aln_mode_select": "intraspecies"}, "/tmp/run")] == [
        "/tmp/run/cactus_cactus/alignment.full.hal",
        "/tmp/run/cactus_cactus/alignment.gfa.gz",
    ]

    assert node_class.VALIDATE_INPUTS({}) == "at least one input genome FASTA is required"
    assert node_class.VALIDATE_INPUTS({"in_seqs": ["cow.fa"], "labels": []}) == "labels must match in_seqs length"
    assert node_class.VALIDATE_INPUTS({"in_seqs": ["cow.fa"], "labels": ["bad label"]}) == (
        "labels may contain only letters, digits, and underscores"
    )
    assert node_class.VALIDATE_INPUTS({"in_seqs": ["cow.fa"], "labels": ["cow"], "aln_mode_select": "bad"}) == (
        "aln_mode_select must be one of: interspecies, intraspecies"
    )
    assert node_class.VALIDATE_INPUTS({"in_seqs": ["cow.fa"], "labels": ["cow"], "aln_mode_select": "interspecies"}) == (
        "in_tree is required for interspecies mode"
    )
    assert node_class.VALIDATE_INPUTS({"in_seqs": ["cow.fa"], "labels": ["cow"], "aln_mode_select": "intraspecies"}) == (
        "ref_level is required for intraspecies mode"
    )
    assert node_class.VALIDATE_INPUTS({
        "in_seqs": ["cow.fa"],
        "labels": ["cow"],
        "aln_mode_select": "intraspecies",
        "ref_level": "dog",
    }) == "ref_level must match one of the labels"
    assert node_class.VALIDATE_INPUTS({
        "in_seqs": ["cow.fa"],
        "labels": ["cow"],
        "aln_mode_select": "intraspecies",
        "ref_level": "cow",
        "max_cores": 0,
    }) == "max_cores must be greater than zero"
    assert node_class.VALIDATE_INPUTS({
        "in_seqs": ["cow.fa"],
        "labels": ["cow"],
        "aln_mode_select": "intraspecies",
        "ref_level": "cow",
        "max_memory_mb": 0,
    }) == "max_memory_mb must be greater than zero"
    assert node_class.VALIDATE_INPUTS({
        "in_seqs": ["cow.fa"],
        "labels": ["cow"],
        "aln_mode_select": "intraspecies",
        "ref_level": "cow",
    }) is True


def test_bionodulo_builtin_cactus_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["cactus"] == "cactus"
    assert EXECUTABLE_TO_CONDA_PACKAGE["cactus-pangenome"] == "cactus"
    assert PACKAGE_MIN_VERSIONS["cactus"] == ">=2.9.0"


def test_cactus_export_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cactus_export"]
    assert node_info["display_name"] == "Cactus Export"
    assert node_info["category"] == "pangenomics"
    assert node_info["description"] == "Convert Cactus HAL whole-genome alignments to MAF, VG, or UCSC Assembly Hub archives."
    assert node_info["output"] == ["MAF", "VG", "TAR"]
    assert node_info["output_name"] == ["out_maf", "out_vg", "out_ah"]
    assert node_info["required_executables"] == ["hal2maf", "hal2vg", "hal2assemblyHub.py", "tar"]
    assert node_info["required_conda_packages"] == ["cactus", "tar"]
    assert node_info["documentation_url"] == "https://github.com/ComparativeGenomicsToolkit/cactus#using-the-output"
    assert node_info["citation_dois"] == ["10.1038/s41586-020-2871-y"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1038/s41586-020-2871-y"]
    assert "Progressive Cactus" in node_info["citation_text"]
    assert "BioNodulo builtin" in node_info["search_aliases"]
    assert "hal2maf" in node_info["search_aliases"]
    assert node_info["version"] == "2.7.1+galaxy0"

    inputs = node_info["input"]
    assert inputs["required"]["hal_file"][0] == "HAL"
    assert inputs["optional"]["format"][1]["default"] == "maf_selector"
    assert inputs["optional"]["format"][1]["options"] == ["maf_selector", "vg_selector", "ah_selector"]
    assert inputs["optional"]["ref_level"][0] == "STRING"
    assert inputs["optional"]["max_cores"][1]["default"] == 4
    assert inputs["optional"]["max_memory_mb"][1]["default"] == 8196


def test_cactus_export_renders_maf_vg_and_assembly_hub_commands_and_outputs() -> None:
    node_class = _node_class("cactus_export")

    assert node_class.render_command({
        "hal_file": "alignment results.hal",
        "format": "maf_selector",
        "ref_level": "simMouse_chr6",
        "output": "/tmp/run/cactus_export",
    }) == [
        "ln",
        "-s",
        "alignment results.hal",
        "/tmp/run/cactus_export/alignment.hal",
        "&&",
        "cd",
        "/tmp/run/cactus_export",
        "&&",
        "hal2maf",
        "--refGenome",
        "simMouse_chr6",
        "alignment.hal",
        "alignment.maf",
    ]
    assert [str(path) for path in node_class.PLAN_OUTPUTS({"format": "maf_selector"}, "/tmp/run")] == [
        "/tmp/run/cactus_export/alignment.maf",
    ]

    assert node_class.render_command({
        "hal_file": "alignment.hal",
        "format": "vg_selector",
        "ref_level": "simCow_chr6",
        "output": "/tmp/run/cactus_export",
    })[-5:] == [
        "hal2vg",
        "alignment.hal",
        "--progress",
        ">",
        "alignment.pg",
    ]
    assert [str(path) for path in node_class.PLAN_OUTPUTS({"format": "vg_selector"}, "/tmp/run")] == [
        "/tmp/run/cactus_export/alignment.pg",
    ]

    assert node_class.render_command({
        "hal_file": "alignment.hal",
        "format": "ah_selector",
        "max_cores": 12,
        "max_memory_mb": 24000,
        "output": "/tmp/run/cactus_export",
    })[-14:] == [
        "hal2assemblyHub.py",
        "--maxCores",
        "12",
        "--maxMemory",
        "24000M",
        "./jobStore",
        "alignment.hal",
        "assemblyhub",
        "&&",
        "tar",
        "-cv",
        "assemblyhub",
        ">",
        "assemblyhub.tar",
    ]
    assert [str(path) for path in node_class.PLAN_OUTPUTS({"format": "ah_selector"}, "/tmp/run")] == [
        "/tmp/run/cactus_export/assemblyhub.tar",
    ]


def test_cactus_export_validates_required_and_mode_specific_inputs() -> None:
    node_class = _node_class("cactus_export")

    assert node_class.VALIDATE_INPUTS({}) == "hal_file is required"
    assert node_class.VALIDATE_INPUTS({"hal_file": "alignment.hal", "format": "bad"}) == (
        "format must be one of: maf_selector, vg_selector, ah_selector"
    )
    assert node_class.VALIDATE_INPUTS({"hal_file": "alignment.hal", "format": "maf_selector"}) == (
        "ref_level is required for MAF and VG export"
    )
    assert node_class.VALIDATE_INPUTS({"hal_file": "alignment.hal", "format": "vg_selector"}) == (
        "ref_level is required for MAF and VG export"
    )
    assert node_class.VALIDATE_INPUTS({
        "hal_file": "alignment.hal",
        "format": "ah_selector",
        "max_cores": 0,
    }) == "max_cores must be greater than zero"
    assert node_class.VALIDATE_INPUTS({
        "hal_file": "alignment.hal",
        "format": "ah_selector",
        "max_memory_mb": 0,
    }) == "max_memory_mb must be greater than zero"
    assert node_class.VALIDATE_INPUTS({
        "hal_file": "alignment.hal",
        "format": "maf_selector",
        "ref_level": "simMouse_chr6",
    }) is True
    assert node_class.VALIDATE_INPUTS({"hal_file": "alignment.hal", "format": "ah_selector"}) is True
