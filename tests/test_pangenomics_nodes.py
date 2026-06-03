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


def test_pggb_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["pggb"] == "pggb"
    assert PACKAGE_MIN_VERSIONS["pggb"] == ">=0.7.3"
