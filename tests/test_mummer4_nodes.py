from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


MUMMER4_DOI = "10.1371/journal.pcbi.1005944"


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_mummer4_nodes_expose_galaxy_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "mummer4_nucmer": {
            "display_name": "MUMmer4 Nucmer",
            "output": ["FILE", "BAM", "CRAM", "IMAGE"],
            "executables": ["nucmer", "mummerplot", "gnuplot", "samtools"],
            "packages": ["mummer4", "gnuplot", "samtools"],
        },
        "mummer4_dnadiff": {
            "display_name": "MUMmer4 DNAdiff",
            "output": ["STATS_FILE", "DIRECTORY"],
            "executables": ["dnadiff"],
            "packages": ["mummer4"],
        },
        "mummer4_delta_filter": {
            "display_name": "MUMmer4 Delta Filter",
            "output": ["FILE"],
            "executables": ["delta-filter"],
            "packages": ["mummer4"],
        },
        "mummer4_show_coords": {
            "display_name": "MUMmer4 Show Coordinates",
            "output": ["TSV"],
            "executables": ["show-coords"],
            "packages": ["mummer4"],
        },
        "mummer4_mummer": {
            "display_name": "MUMmer4 Mummer",
            "output": ["TSV", "IMAGE"],
            "executables": ["mummer", "mummerplot", "gnuplot"],
            "packages": ["mummer4", "gnuplot"],
        },
        "mummer4_mummerplot": {
            "display_name": "MUMmer4 Mummerplot",
            "output": ["IMAGE", "FILE", "FILE", "FILE", "FILE"],
            "executables": ["mummerplot", "gnuplot"],
            "packages": ["mummer4", "gnuplot"],
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == "genomics"
        assert node_info["description"]
        assert node_info["output"] == metadata["output"]
        assert node_info["required_executables"] == metadata["executables"]
        assert node_info["required_conda_packages"] == metadata["packages"]
        assert node_info["documentation_url"].startswith("https://mummer4.github.io/")
        assert node_info["citation_dois"] == [MUMMER4_DOI]
        assert f"https://doi.org/{MUMMER4_DOI}" in node_info["citation_urls"]
        assert "MUMmer4" in node_info["citation_text"]
        assert "Galaxy" in node_info["search_aliases"]


def test_mummer4_environment_metadata_maps_executables_to_packages() -> None:
    for executable in ("nucmer", "dnadiff", "delta-filter", "show-coords", "mummer", "mummerplot"):
        assert EXECUTABLE_TO_CONDA_PACKAGE[executable] == "mummer4"
    assert EXECUTABLE_TO_CONDA_PACKAGE["gnuplot"] == "gnuplot"
    assert PACKAGE_MIN_VERSIONS["mummer4"] == ">=4.0.1"
    assert PACKAGE_MIN_VERSIONS["gnuplot"] == ">=6.0.4"


def test_mummer4_nucmer_renders_delta_plot_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mummer4_nucmer")

    assert node_class.render_command(
        {
            "reference_sequence": "ref.fa",
            "query_sequence": "query.fa",
            "out_format": "delta",
            "plot": True,
            "anchoring": "--maxmatch",
            "breaklen": 180,
            "mincluster": 70,
            "diagdiff": 6,
            "diagfactor": 0.2,
            "noextend": True,
            "direction": "-f",
            "maxgap": 100,
            "minmatch": 22,
            "minalign": 15,
            "nooptimize": True,
            "nosimplify": True,
            "banded": True,
            "large": True,
            "genome": True,
            "max_chunk": 60000,
            "threads": 4,
            "plot_breaklen": 25,
            "plot_color": "-color",
            "coverage_plot": "-c",
            "filter_plot": True,
            "fat": True,
            "plot_ids": True,
            "ref_id": "chr1",
            "query_id": "contigA",
            "plot_size": "medium",
            "snp": True,
            "title": "Nucmer plot",
            "custom_range": True,
            "min_x": 1,
            "max_x": 1000,
            "min_y": 5,
            "max_y": 900,
            "output": "/work/nucmer",
        }
    ) == [
        "ln",
        "-s",
        "ref.fa",
        "reference.fa",
        "&&",
        "ln",
        "-s",
        "query.fa",
        "query.fa",
        "&&",
        "nucmer",
        "--maxmatch",
        "-b",
        "180",
        "-c",
        "70",
        "-D",
        "6",
        "-d",
        "0.2",
        "--noextend",
        "-f",
        "-g",
        "100",
        "-l",
        "22",
        "-L",
        "15",
        "--nooptimize",
        "--nosimplify",
        "--threads",
        "4",
        "--banded",
        "--large",
        "-G",
        "-M",
        "60000",
        "reference.fa",
        "query.fa",
        "&&",
        "mv",
        "out.delta",
        "/work/nucmer/out.delta",
        "&&",
        "mummerplot",
        "-b",
        "25",
        "-color",
        "-c",
        "--filter",
        "--fat",
        "-IdR",
        "chr1",
        "-IdQ",
        "contigA",
        "-s",
        "medium",
        "-terminal",
        "png",
        "-title",
        "Nucmer plot",
        "--SNP",
        "-x",
        "[1:1000]",
        "-y",
        "[5:900]",
        "/work/nucmer/out.delta",
        "&&",
        "gnuplot",
        "<",
        "out.gp",
        "&&",
        "mv",
        "out.png",
        "/work/nucmer/out.png",
    ]
    assert node_class.PLAN_OUTPUTS({"out_format": "delta", "plot": True}, tmp_path) == [
        tmp_path / "mummer4_nucmer" / "out.delta",
        tmp_path / "mummer4_nucmer" / "out.png",
    ]


def test_mummer4_nucmer_renders_bam_command_and_output(tmp_path: Path) -> None:
    node_class = _node_class("mummer4_nucmer")

    assert node_class.render_command(
        {
            "reference_sequence": "ref.fa",
            "query_sequence": "query.fa",
            "out_format": "bam-long",
            "threads": 8,
            "output": "/work/nucmer",
        }
    ) == [
        "ln",
        "-s",
        "ref.fa",
        "reference.fa",
        "&&",
        "ln",
        "-s",
        "query.fa",
        "query.fa",
        "&&",
        "nucmer",
        "--sam-long=outsam.sam",
        "-b",
        "200",
        "-c",
        "65",
        "-D",
        "5",
        "-d",
        "0.12",
        "-g",
        "90",
        "-l",
        "20",
        "-L",
        "0",
        "--threads",
        "8",
        "reference.fa",
        "query.fa",
        "&&",
        "samtools",
        "dict",
        "reference.fa",
        ">",
        "outsamhead",
        "&&",
        "tail",
        "-n",
        "+3",
        "outsam.sam",
        ">>",
        "outsamhead",
        "&&",
        "samtools",
        "sort",
        "-@",
        "8",
        "-T",
        "${TMPDIR:-.}",
        "outsamhead",
        "|",
        "samtools",
        "calmd",
        "-b",
        "--threads",
        "8",
        "-",
        "reference.fa",
        ">",
        "/work/nucmer/outsam.bam",
    ]
    assert node_class.PLAN_OUTPUTS({"out_format": "bam-long"}, tmp_path) == [
        tmp_path / "mummer4_nucmer" / "outsam.bam",
    ]


def test_mummer4_dnadiff_renders_command_and_mode_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mummer4_dnadiff")

    assert node_class.render_command(
        {"reference_sequence": "ref.fa", "query_sequence": "query.fa", "output": "/work/dnadiff"}
    ) == [
        "ln",
        "-s",
        "ref.fa",
        "reference.fa",
        "&&",
        "ln",
        "-s",
        "query.fa",
        "query.fa",
        "&&",
        "dnadiff",
        "-p",
        "/work/dnadiff/out",
        "reference.fa",
        "query.fa",
    ]
    assert node_class.PLAN_OUTPUTS({"report_only": "yes"}, tmp_path) == [
        tmp_path / "mummer4_dnadiff" / "out.report",
    ]
    assert node_class.PLAN_OUTPUTS({"report_only": "no"}, tmp_path) == [
        tmp_path / "mummer4_dnadiff" / "out.report",
        tmp_path / "mummer4_dnadiff" / "out.delta",
        tmp_path / "mummer4_dnadiff" / "out.1delta",
        tmp_path / "mummer4_dnadiff" / "out.mdelta",
        tmp_path / "mummer4_dnadiff" / "out.1coords",
        tmp_path / "mummer4_dnadiff" / "out.mcoords",
        tmp_path / "mummer4_dnadiff" / "out.snps",
        tmp_path / "mummer4_dnadiff" / "out.rdiff",
        tmp_path / "mummer4_dnadiff" / "out.qdiff",
    ]


def test_mummer4_delta_filter_and_show_coords_render_commands_and_outputs(tmp_path: Path) -> None:
    delta_filter = _node_class("mummer4_delta_filter")
    show_coords = _node_class("mummer4_show_coords")

    assert delta_filter.render_command(
        {
            "delta": "out.delta",
            "alignment": "-1",
            "min_identity": 95.5,
            "min_length": 500,
            "overlap": "-r",
            "min_uniqueness": 80.0,
            "max_overlap": 90.0,
            "output": "/work/delta_filter",
        }
    ) == [
        "delta-filter",
        "-1",
        "-i",
        "95.5",
        "-l",
        "500",
        "-r",
        "-u",
        "80.0",
        "-o",
        "90.0",
        "out.delta",
        ">",
        "/work/delta_filter/delta-filter.txt",
    ]
    assert delta_filter.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mummer4_delta_filter" / "delta-filter.txt"]

    assert show_coords.render_command(
        {
            "delta": "out.delta",
            "merge": True,
            "direction": True,
            "identity": 90.0,
            "min_alignment_length": 250,
            "annotate": True,
            "sort": "-q",
            "output": "/work/show_coords",
        }
    ) == [
        "show-coords",
        "-b",
        "-d",
        "-c",
        "-H",
        "-I",
        "90.0",
        "-l",
        "-L",
        "250",
        "-o",
        "-q",
        "-T",
        "out.delta",
        ">",
        "/work/show_coords/show-coords_extend.tsv",
    ]
    assert show_coords.PLAN_OUTPUTS({"direction": True}, tmp_path) == [
        tmp_path / "mummer4_show_coords" / "show-coords_extend.tsv",
    ]


def test_mummer4_mummer_renders_plot_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mummer4_mummer")

    assert node_class.render_command(
        {
            "reference_sequence": "ref.fa",
            "query_sequence": "query.fa",
            "anchoring": "-mum",
            "min": 30,
            "direction": "-r",
            "force": True,
            "chars": True,
            "print_length": True,
            "substring": True,
            "position": True,
            "threads": 3,
            "advanced": True,
            "suffix": 2,
            "suflink": 1,
            "child": 1,
            "skip": 12,
            "kmer": 2,
            "plot": True,
            "plot_breaklen": 20,
            "plot_size": "large",
            "title": "Mummer plot",
            "output": "/work/mummer",
        }
    ) == [
        "mummer",
        "-mum",
        "-l",
        "30",
        "-r",
        "-F",
        "-n",
        "-L",
        "-s",
        "-c",
        "-threads",
        "3",
        "-qthreads",
        "3",
        "-k",
        "2",
        "-suflink",
        "1",
        "-child",
        "1",
        "-skip",
        "12",
        "-kmer",
        "2",
        "ref.fa",
        "query.fa",
        ">",
        "/work/mummer/mummer.tsv",
        "&&",
        "mummerplot",
        "-b",
        "20",
        "-s",
        "large",
        "-terminal",
        "png",
        "-title",
        "Mummer plot",
        "/work/mummer/mummer.tsv",
        "&&",
        "gnuplot",
        "<",
        "out.gp",
        "&&",
        "mv",
        "out.png",
        "/work/mummer/out.png",
    ]
    assert node_class.PLAN_OUTPUTS({"plot": True}, tmp_path) == [
        tmp_path / "mummer4_mummer" / "mummer.tsv",
        tmp_path / "mummer4_mummer" / "out.png",
    ]


def test_mummer4_mummerplot_renders_all_outputs_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mummer4_mummerplot")

    assert node_class.render_command(
        {
            "delta": "out.delta",
            "reference_sequence": "ref.fa",
            "query_sequence": "query.fa",
            "breaklen": 30,
            "color": "-color",
            "coverage": "-c",
            "filter": True,
            "fat": True,
            "plot_ids": True,
            "ref_id": "chr2",
            "query_id": "contigB",
            "seq_input": True,
            "layout": True,
            "size": "small",
            "title": "Plot",
            "snp": True,
            "custom_range": True,
            "min_x": 10,
            "max_x": 20,
            "min_y": 30,
            "max_y": 40,
            "extra_outs": "all",
            "output": "/work/mummerplot",
        }
    ) == [
        "ln",
        "-s",
        "ref.fa",
        "reference.fa",
        "&&",
        "ln",
        "-s",
        "query.fa",
        "query.fa",
        "&&",
        "mummerplot",
        "-b",
        "30",
        "-color",
        "-c",
        "--filter",
        "--fat",
        "-IdR",
        "chr2",
        "-IdQ",
        "contigB",
        "-R",
        "ref.fa",
        "-Q",
        "query.fa",
        "--layout",
        "-s",
        "small",
        "-terminal",
        "png",
        "-title",
        "Plot",
        "--SNP",
        "-x",
        "[10:20]",
        "-y",
        "[30:40]",
        "out.delta",
        "&&",
        "gnuplot",
        "<",
        "out.gp",
        "&&",
        "mv",
        "out.png",
        "/work/mummerplot/out.png",
        "&&",
        "mv",
        "out.gp",
        "/work/mummerplot/out.gp",
        "&&",
        "mv",
        "out.fplot",
        "/work/mummerplot/out.fplot",
        "&&",
        "mv",
        "out.rplot",
        "/work/mummerplot/out.rplot",
        "&&",
        "mv",
        "out.hplot",
        "/work/mummerplot/out.hplot",
    ]
    assert node_class.PLAN_OUTPUTS({"extra_outs": "all"}, tmp_path) == [
        tmp_path / "mummer4_mummerplot" / "out.png",
        tmp_path / "mummer4_mummerplot" / "out.gp",
        tmp_path / "mummer4_mummerplot" / "out.fplot",
        tmp_path / "mummer4_mummerplot" / "out.rplot",
        tmp_path / "mummer4_mummerplot" / "out.hplot",
    ]
