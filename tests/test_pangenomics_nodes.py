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


def test_vg_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["vg"] == "vg"
    assert PACKAGE_MIN_VERSIONS["vg"] == ">=1.62.0"


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
