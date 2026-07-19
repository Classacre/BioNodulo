from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.mummer4_family.delta_filter import Mummer4DeltaFilterNode
from bionodulo.nodes.builtin.mummer4_family.dnadiff import Mummer4DnadiffNode
from bionodulo.nodes.builtin.mummer4_family.mummer import Mummer4MummerNode
from bionodulo.nodes.builtin.mummer4_family.mummerplot import Mummer4MummerplotNode
from bionodulo.nodes.builtin.mummer4_family.nucmer import Mummer4NucmerNode
from bionodulo.nodes.builtin.mummer4_family.show_coords import Mummer4ShowCoordsNode
from bionodulo.nodes.registry import NodeRegistry


MUMMER4_CLASSES = (
    Mummer4NucmerNode,
    Mummer4DnadiffNode,
    Mummer4DeltaFilterNode,
    Mummer4ShowCoordsNode,
    Mummer4MummerNode,
    Mummer4MummerplotNode,
)


def test_mummer4_family_is_source_pinned_and_discoverable() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    for node_class in MUMMER4_CLASSES:
        assert registry.get(node_class.NODE_ID) is node_class
        assert node_class.VERSION == "4.0.1"
        assert node_class.GIT_COMMIT == "eb734606f2d516f42a0e0dce7a116bfb88ec1ebf"
        assert node_class.GIT_URL == "https://github.com/mummer4/mummer.git"
        assert node_class.UPSTREAM_SOURCE
        assert node_class.CITATION_DOIS == ["10.1371/journal.pcbi.1005944"]
        assert "BioNodulo builtin" in node_class.SEARCH_ALIASES


def test_mummer4_environment_is_exactly_pinned() -> None:
    for executable in (
        "nucmer",
        "dnadiff",
        "delta-filter",
        "show-coords",
        "show-snps",
        "mummer",
        "mummerplot",
    ):
        assert EXECUTABLE_TO_CONDA_PACKAGE[executable] == "mummer4"
    assert PACKAGE_MIN_VERSIONS["mummer4"] == "4.0.1"


def test_nucmer_renders_native_output_modes_and_query_list(tmp_path: Path) -> None:
    inputs = {
        "reference_sequence": "ref.fa",
        "query_sequence": ["query-a.fa", "query-b.fa"],
        "output_format": "sam_long",
        "match_mode": "maxmatch",
        "breaklen": 180,
        "mincluster": 70,
        "diagdiff": 6,
        "diagfactor": 0.2,
        "noextend": True,
        "strand": "forward",
        "maxgap": 100,
        "minmatch": 22,
        "minalign": 15,
        "nooptimize": True,
        "nosimplify": True,
        "threads": 4,
        "banded": True,
        "large": True,
        "genome": True,
        "max_chunk": 60000,
        "output": "/work/nucmer",
    }
    assert Mummer4NucmerNode.render_command(inputs) == [
        "nucmer",
        "--maxmatch",
        "--sam-long",
        "/work/nucmer/alignment.sam",
        "--breaklen",
        "180",
        "--mincluster",
        "70",
        "--diagdiff",
        "6",
        "--diagfactor",
        "0.2",
        "--noextend",
        "--forward",
        "--maxgap",
        "100",
        "--minmatch",
        "22",
        "--minalign",
        "15",
        "--nooptimize",
        "--nosimplify",
        "--threads",
        "4",
        "--banded",
        "--large",
        "--genome",
        "--max-chunk",
        "60000",
        "ref.fa",
        "query-a.fa",
        "query-b.fa",
    ]
    assert Mummer4NucmerNode.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / "mummer4_nucmer" / "alignment.sam"]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"reference_sequence": "ref.fa", "query_sequence": []}, "at least one"),
        (
            {"reference_sequence": "ref.fa", "query_sequence": ["q.fa"], "output_format": "bam"},
            "output_format",
        ),
        (
            {"reference_sequence": "ref.fa", "query_sequence": ["q.fa"], "threads": 0},
            "at least 1",
        ),
    ],
)
def test_nucmer_rejects_invalid_source_contracts(inputs: dict[str, Any], message: str) -> None:
    assert message in str(Mummer4NucmerNode.VALIDATE_INPUTS(inputs))


def test_dnadiff_stages_stable_fasta_names_and_plans_native_outputs(tmp_path: Path) -> None:
    reference = tmp_path / "input-ref.fa"
    query = tmp_path / "input-query.fa"
    reference.write_text(">ref\nACGT\n", encoding="ascii")
    query.write_text(">query\nACGA\n", encoding="ascii")
    outputs = Mummer4DnadiffNode.PLAN_OUTPUTS({}, tmp_path / "results")

    Mummer4DnadiffNode.PREPARE_EXECUTION(
        {"reference_sequence": reference, "query_sequence": query},
        outputs,
    )

    assert [path.name for path in outputs] == list(Mummer4DnadiffNode.OUTPUT_FILENAMES)
    assert (outputs[0].parent / "reference.fa").read_bytes() == reference.read_bytes()
    assert (outputs[0].parent / "query.fa").read_bytes() == query.read_bytes()
    assert Mummer4DnadiffNode.render_command({"reference_sequence": reference, "query_sequence": query}) == [
        "dnadiff",
        "-p",
        "out",
        "reference.fa",
        "query.fa",
    ]


def test_delta_filter_renders_source_order_and_validates_ranges(tmp_path: Path) -> None:
    inputs = {
        "delta": "alignments.delta",
        "epsilon": 0.01,
        "min_identity": 95.5,
        "min_length": 100,
        "min_uniqueness": 80.0,
        "mode": "one_to_one",
        "max_overlap": 10.0,
    }
    assert Mummer4DeltaFilterNode.render_command(inputs) == [
        "delta-filter",
        "-e",
        "0.01",
        "-i",
        "95.5",
        "-l",
        "100",
        "-u",
        "80.0",
        "-1",
        "-o",
        "10.0",
        "alignments.delta",
    ]
    assert Mummer4DeltaFilterNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "mummer4_delta_filter" / "filtered.delta"
    ]
    assert "at most 100" in str(Mummer4DeltaFilterNode.VALIDATE_INPUTS({"delta": "a.delta", "min_identity": 101.0}))


def test_show_coords_emits_parseable_tabular_output() -> None:
    assert Mummer4ShowCoordsNode.render_command(
        {
            "delta": "alignments.delta",
            "brief": True,
            "coverage": True,
            "direction": True,
            "include_header": False,
            "min_identity": 90.0,
            "knockout": True,
            "sequence_lengths": True,
            "min_alignment_length": 75,
            "annotation": "overlaps",
            "sort": "reference",
        }
    ) == [
        "show-coords",
        "-b",
        "-c",
        "-d",
        "-H",
        "-I",
        "90.0",
        "-k",
        "-l",
        "-L",
        "75",
        "-o",
        "-r",
        "-T",
        "alignments.delta",
    ]


def test_mummer_renders_source_flags_without_plot_side_effects(tmp_path: Path) -> None:
    inputs = {
        "reference_sequence": "ref.fa",
        "query_sequence": ["q1.fa", "q2.fa"],
        "match_mode": "maxmatch",
        "min_length": 31,
        "strand": "both",
        "force_four_column": True,
        "nucleotides_only": True,
        "print_query_length": True,
        "print_substring": True,
        "reverse_positions": True,
        "sparse_index": 3,
        "threads": 4,
        "query_threads": 2,
        "max_chunk": 64000,
    }
    assert Mummer4MummerNode.render_command(inputs) == [
        "mummer",
        "-maxmatch",
        "-l",
        "31",
        "-b",
        "-F",
        "-n",
        "-L",
        "-s",
        "-c",
        "-k",
        "3",
        "-threads",
        "4",
        "-qthreads",
        "2",
        "-max-chunk",
        "64000",
        "ref.fa",
        "q1.fa",
        "q2.fa",
    ]
    assert Mummer4MummerNode.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / "mummer4_mummer" / "matches.tsv"]


def test_mummer_enforces_the_source_sparse_index_mode_rule() -> None:
    validation = Mummer4MummerNode.VALIDATE_INPUTS(
        {
            "reference_sequence": "ref.fa",
            "query_sequence": ["query.fa"],
            "match_mode": "mum",
            "sparse_index": 2,
        }
    )
    assert validation == "Input 'sparse_index' may differ from 1 only when 'match_mode' is 'maxmatch'"


def test_mummerplot_renders_and_groups_only_source_generated_files(tmp_path: Path) -> None:
    inputs = {
        "delta": "alignments.delta",
        "breaklen": 20,
        "color_mode": "identity",
        "coverage": True,
        "filter": True,
        "layout": True,
        "fat": True,
        "ref_id": "chr1",
        "query_id": "contig1",
        "reference_sequence": "ref.fa",
        "query_sequence": "query.fa",
        "size": "medium",
        "snp": True,
        "terminal": "postscript",
        "title": "Assembly comparison",
        "xrange": "[0:1000]",
        "yrange": "[5,900]",
    }
    assert Mummer4MummerplotNode.render_command(inputs) == [
        "mummerplot",
        "-p",
        "out",
        "-t",
        "postscript",
        "-b",
        "20",
        "--color",
        "--coverage",
        "--filter",
        "--layout",
        "--fat",
        "-r",
        "chr1",
        "-q",
        "contig1",
        "-R",
        "ref.fa",
        "-Q",
        "query.fa",
        "-s",
        "medium",
        "--SNP",
        "--title",
        "Assembly comparison",
        "-x",
        "[0:1000]",
        "-y",
        "[5,900]",
        "alignments.delta",
    ]
    planned = Mummer4MummerplotNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert [path.name for path in planned] == [
        "out.ps",
        "out.gp",
        "out.fplot",
        "out.rplot",
        "out.hplot",
        "out.filter",
    ]
    assert Mummer4MummerplotNode.MAP_PLANNED_OUTPUTS(planned) == {
        "plot": planned[0],
        "plot_artifacts": planned[1:],
    }


@pytest.mark.parametrize("key", ["xrange", "yrange"])
def test_mummerplot_rejects_ranges_the_source_parser_rejects(key: str) -> None:
    validation = Mummer4MummerplotNode.VALIDATE_INPUTS({"delta": "alignments.delta", key: "0:100"})
    assert "source format" in str(validation)


class _FakeContext:
    def __init__(self, *, mummerplot: bool = False) -> None:
        self.mummerplot = mummerplot
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((command, kwargs))
        if stdout_path := kwargs.get("stdout_path"):
            Path(stdout_path).write_text("matches\n", encoding="ascii")
        if self.mummerplot:
            cwd = Path(kwargs["cwd"])
            for name in ("out.png", "out.gp", "out.fplot", "out.rplot"):
                (cwd / name).write_text(name, encoding="ascii")
        return {"returncode": 0, "stdout": "", "stderr": ""}


@pytest.mark.asyncio
async def test_stdout_and_dynamic_plot_outputs_use_runtime_capture(tmp_path: Path) -> None:
    match_context = _FakeContext()
    match_result = await Mummer4MummerNode().run(
        context=match_context,
        output_dir=tmp_path,
        reference_sequence="ref.fa",
        query_sequence=["query.fa"],
    )
    assert match_result == (str(tmp_path / "mummer4_mummer" / "matches.tsv"),)
    assert match_context.calls[0][1]["stdout_path"] == tmp_path / "mummer4_mummer" / "matches.tsv"

    plot_context = _FakeContext(mummerplot=True)
    plot_result = await Mummer4MummerplotNode().run(
        context=plot_context,
        output_dir=tmp_path,
        delta="alignments.delta",
    )
    assert plot_result == {
        "outputs": {
            "plot": str(tmp_path / "mummer4_mummerplot" / "out.png"),
            "plot_artifacts": [
                str(tmp_path / "mummer4_mummerplot" / "out.gp"),
                str(tmp_path / "mummer4_mummerplot" / "out.fplot"),
                str(tmp_path / "mummer4_mummerplot" / "out.rplot"),
            ],
        }
    }
