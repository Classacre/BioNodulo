"""Compact contract coverage for the focused BEDTools 2.31.1 family."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.bedtools_family.annotate import BEDToolsAnnotateNode
from bionodulo.nodes.builtin.bedtools_family.bamtobed import BEDToolsBamToBedNode
from bionodulo.nodes.builtin.bedtools_family.bed12tobed6 import BEDToolsBed12ToBed6Node
from bionodulo.nodes.builtin.bedtools_family.bedpetobam import BEDToolsBedpeToBamNode
from bionodulo.nodes.builtin.bedtools_family.bedtobam import BEDToolsBedToBamNode
from bionodulo.nodes.builtin.bedtools_family.bedtoigv import BEDToolsBedToIgvNode
from bionodulo.nodes.builtin.bedtools_family.closestbed import BEDToolsClosestBedNode
from bionodulo.nodes.builtin.bedtools_family.cluster import BEDToolsClusterNode
from bionodulo.nodes.builtin.bedtools_family.complement import BEDToolsComplementNode
from bionodulo.nodes.builtin.bedtools_family.coverage import BEDToolsCoverageNode
from bionodulo.nodes.builtin.bedtools_family.expand import BEDToolsExpandNode
from bionodulo.nodes.builtin.bedtools_family.fisher import BEDToolsFisherNode
from bionodulo.nodes.builtin.bedtools_family.flank import BEDToolsFlankNode
from bionodulo.nodes.builtin.bedtools_family.genomecov import BEDToolsGenomeCoverageNode
from bionodulo.nodes.builtin.bedtools_family.getfasta import BEDToolsGetFastaNode
from bionodulo.nodes.builtin.bedtools_family.groupby import BEDToolsGroupByNode
from bionodulo.nodes.builtin.bedtools_family.intersectbed import BEDToolsIntersectBedNode
from bionodulo.nodes.builtin.bedtools_family.jaccard import BEDToolsJaccardNode
from bionodulo.nodes.builtin.bedtools_family.links import BEDToolsLinksNode
from bionodulo.nodes.builtin.bedtools_family.makewindows import BEDToolsMakeWindowsNode
from bionodulo.nodes.builtin.bedtools_family.map import BEDToolsMapNode
from bionodulo.nodes.builtin.bedtools_family.maskfasta import BEDToolsMaskFastaNode
from bionodulo.nodes.builtin.bedtools_family.merge import BEDToolsMergeNode
from bionodulo.nodes.builtin.bedtools_family.multicov import BEDToolsMultiCovNode
from bionodulo.nodes.builtin.bedtools_family.multiinter import BEDToolsMultiIntersectNode
from bionodulo.nodes.builtin.bedtools_family.nuc import BEDToolsNucNode
from bionodulo.nodes.builtin.bedtools_family.overlap import BEDToolsOverlapBedNode
from bionodulo.nodes.builtin.bedtools_family.random import BEDToolsRandomNode
from bionodulo.nodes.builtin.bedtools_family.reldist import BEDToolsRelativeDistanceNode
from bionodulo.nodes.builtin.bedtools_family.shuffle import BEDToolsShuffleNode
from bionodulo.nodes.builtin.bedtools_family.slop import BEDToolsSlopNode
from bionodulo.nodes.builtin.bedtools_family.sort import BEDToolsSortNode
from bionodulo.nodes.builtin.bedtools_family.spacing import BEDToolsSpacingNode
from bionodulo.nodes.builtin.bedtools_family.subtract import BEDToolsSubtractNode
from bionodulo.nodes.builtin.bedtools_family.tag import BEDToolsTagBedNode
from bionodulo.nodes.builtin.bedtools_family.unionbedg import BEDToolsUnionBedGraphNode
from bionodulo.nodes.builtin.bedtools_family.window import BEDToolsWindowNode
from bionodulo.nodes.builtin.bedtools_family.closest import BEDToolsClosestNode
from bionodulo.nodes.builtin.bedtools_family.getfasta import BEDToolsGetFastaNode as FocusedGetFasta
from bionodulo.nodes.registry import NodeRegistry, _to_frontend_input_spec


CASES = [
    (BEDToolsCoverageNode, {"inputA": "a.bed", "inputB": ["b.bed"], "report": "counts"}, ["bedtools", "coverage", "-counts", "-a", "a.bed", "-b", "b.bed"]),
    (BEDToolsGenomeCoverageNode, {"input_type": "bed", "input": "a.bed", "report": "bg", "genome": "genome.sizes"}, ["bedtools", "genomecov", "-i", "a.bed", "-g", "genome.sizes", "-bg"]),
    (BEDToolsSubtractNode, {"inputA": "a.bed", "inputB": "b.bed", "overlap": 0.5, "remove_if_overlap": "remove_feature"}, ["bedtools", "subtract", "-a", "a.bed", "-b", "b.bed", "-f", "0.5", "-A"]),
    (BEDToolsMergeNode, {"input": "a.bed", "distance": 10, "strand": "same", "columns": "4", "operations": "distinct"}, ["bedtools", "merge", "-i", "a.bed", "-d", "10", "-s", "-c", "4", "-o", "distinct", "-delim", ";"]),
    (BEDToolsSortNode, {"input": "a.bed", "sort_by": "-sizeD"}, ["bedtools", "sort", "-i", "a.bed", "-sizeD"]),
    (BEDToolsGetFastaNode, {"input": "a.bed", "fasta": "ref.fa", "tab": True, "name_only": True, "output": "/work/getfasta"}, ["bedtools", "getfasta", "-nameOnly", "-tab", "-fi", "ref.fa", "-bed", "a.bed", "-fo", "/work/getfasta/extracted.tsv"]),
    (BEDToolsComplementNode, {"input": "a.bed", "genome": "genome.sizes", "limit": True}, ["bedtools", "complement", "-i", "a.bed", "-g", "genome.sizes", "-L"]),
    (BEDToolsFlankNode, {"input": "a.bed", "genome": "genome.sizes", "addition_mode": "lr", "left": 10, "right": 20, "strand": True}, ["bedtools", "flank", "-i", "a.bed", "-g", "genome.sizes", "-l", "10", "-r", "20", "-s"]),
    (BEDToolsSlopNode, {"inputA": "a.bed", "genome": "genome.sizes", "both": 25, "header": True}, ["bedtools", "slop", "-i", "a.bed", "-g", "genome.sizes", "-b", "25", "-header"]),
    (BEDToolsWindowNode, {"inputA": "a.bed", "inputB": "b.bed", "window": 50, "report": "u", "strand": "same"}, ["bedtools", "window", "-a", "a.bed", "-b", "b.bed", "-w", "50", "-sm", "-u"]),
    (BEDToolsMapNode, {"inputA": "a.bed", "inputB": "b.bed", "columns": "5", "operations": "mean", "overlap": 0.5}, ["bedtools", "map", "-a", "a.bed", "-b", "b.bed", "-c", "5", "-o", "mean", "-f", "0.5"]),
    (BEDToolsMultiIntersectNode, {"inputs": ["a.bed", "b.bed"], "names": ["a", "b"], "header": True}, ["bedtools", "multiinter", "-header", "-filler", "0", "-i", "a.bed", "b.bed", "-names", "a", "b"]),
    (BEDToolsClusterNode, {"inputA": "a.bed", "distance": 5, "strand": True}, ["bedtools", "cluster", "-i", "a.bed", "-s", "-d", "5"]),
    (BEDToolsJaccardNode, {"inputA": "a.bed", "inputB": "b.bed", "strand": "same", "overlap": 0.25}, ["bedtools", "jaccard", "-a", "a.bed", "-b", "b.bed", "-s", "-f", "0.25"]),
    (BEDToolsFisherNode, {"inputA": "a.bed", "inputB": "b.bed", "genome": "genome.sizes", "merge": True}, ["bedtools", "fisher", "-a", "a.bed", "-b", "b.bed", "-g", "genome.sizes", "-m"]),
    (BEDToolsRelativeDistanceNode, {"inputA": "a.bed", "inputB": "b.bed", "detail": True}, ["bedtools", "reldist", "-a", "a.bed", "-b", "b.bed", "-detail"]),
    (BEDToolsSpacingNode, {"input": "a.bed"}, ["bedtools", "spacing", "-i", "a.bed"]),
    (BEDToolsGroupByNode, {"inputA": "a.tsv", "group": "1,2", "columns": "4,5", "operation": "sum,mean"}, ["bedtools", "groupby", "-i", "a.tsv", "-g", "1,2", "-c", "4,5", "-o", "sum,mean"]),
    (BEDToolsBamToBedNode, {"input": "a.bam", "option": "bed12", "split": True}, ["bedtools", "bamtobed", "-bed12", "-split", "-i", "a.bam"]),
    (BEDToolsBed12ToBed6Node, {"input": "a.bed12", "block_number": True}, ["bedtools", "bed12tobed6", "-n", "-i", "a.bed12"]),
    (BEDToolsBedToBamNode, {"input": "a.bed", "genome": "genome.sizes", "bed12": True, "mapq": 60}, ["bedtools", "bedtobam", "-i", "a.bed", "-g", "genome.sizes", "-bed12", "-mapq", "60"]),
    (BEDToolsBedpeToBamNode, {"input": "a.bedpe", "genome": "genome.sizes", "mapq": 30}, ["bedtools", "bedpetobam", "-i", "a.bedpe", "-g", "genome.sizes", "-mapq", "30"]),
    (BEDToolsMakeWindowsNode, {"type": "genome", "action": "windowsize", "genome": "genome.sizes", "windowsize": 100, "step_size": 50, "sourcename": "src"}, ["bedtools", "makewindows", "-g", "genome.sizes", "-w", "100", "-s", "50", "-i", "src"]),
    (BEDToolsAnnotateNode, {"inputA": "a.bed", "beds": ["b.bed"], "names": ["b"], "counts": True}, ["bedtools", "annotate", "-i", "a.bed", "-files", "b.bed", "-names", "b", "-counts"]),
    (BEDToolsExpandNode, {"input": "a.tsv", "columns": "4,5"}, ["bedtools", "expand", "-i", "a.tsv", "-c", "4,5"]),
    (BEDToolsMaskFastaNode, {"input": "mask.bed", "fasta": "ref.fa", "soft": True, "full_header": True, "output": "/work/mask"}, ["bedtools", "maskfasta", "-soft", "-fi", "ref.fa", "-bed", "mask.bed", "-fo", "/work/mask/masked.fasta", "-fullHeader"]),
    (BEDToolsMultiCovNode, {"input": "targets.bed", "bams": ["a.bam", "b.bam"], "bam_indexes": ["a.bam.bai", "b.bam.bai"], "q": 20, "proper": True}, ["bedtools", "multicov", "-bed", "targets.bed", "-bams", "a.bam", "b.bam", "-q", "20", "-p"]),
    (BEDToolsNucNode, {"input": "a.bed", "fasta": "ref.fa", "pattern": "AT", "ignore_case": True}, ["bedtools", "nuc", "-pattern", "AT", "-C", "-fi", "ref.fa", "-bed", "a.bed"]),
    (BEDToolsRandomNode, {"genome": "genome.sizes", "length": 100, "intervals": 10, "seed": 7}, ["bedtools", "random", "-g", "genome.sizes", "-l", "100", "-n", "10", "-seed", "7"]),
    (BEDToolsShuffleNode, {"inputA": "a.bed", "genome": "genome.sizes", "exclude": "gaps.bed", "overlap": 0.2, "seed": 7, "maxtries": 20}, ["bedtools", "shuffle", "-i", "a.bed", "-g", "genome.sizes", "-seed", "7", "-excl", "gaps.bed", "-f", "0.2", "-maxTries", "20"]),
    (BEDToolsUnionBedGraphNode, {"inputs": ["a.bg", "b.bg"], "names": ["a", "b"], "header": True}, ["bedtools", "unionbedg", "-header", "-filler", "0", "-i", "a.bg", "b.bg", "-names", "a", "b"]),
    (BEDToolsClosestBedNode, {"inputA": "a.bed", "inputB": ["b.bed"], "distance_mode": "a", "first_upstream": True, "k": 2}, ["bedtools", "closest", "-D", "a", "-fu", "-mdb", "each", "-t", "all", "-k", "2", "-a", "a.bed", "-b", "b.bed"]),
    (BEDToolsIntersectBedNode, {"inputA": "a.bed", "inputB": ["b.bed"], "report": "wo", "sorted": True, "genome": "genome.sizes"}, ["bedtools", "intersect", "-a", "a.bed", "-b", "b.bed", "-wo", "-sorted", "-g", "genome.sizes"]),
    (BEDToolsBedToIgvNode, {"input": "a.bed", "session": "session.xml", "path": "/work/igv", "img": "svg"}, ["bedtools", "igv", "-i", "a.bed", "-path", "/work/igv", "-sess", "session.xml", "-slop", "0", "-img", "svg"]),
    (BEDToolsLinksNode, {"input": "a.bed"}, ["bedtools", "links", "-base", "http://genome.ucsc.edu", "-org", "human", "-db", "hg18", "-i", "a.bed"]),
    (BEDToolsOverlapBedNode, {"input": "a.tsv", "cols": "2,3,6,7"}, ["bedtools", "overlap", "-i", "a.tsv", "-cols", "2,3,6,7"]),
    (BEDToolsTagBedNode, {"inputA": "a.bam", "inputB": ["genes.bed"], "labels": ["genes"], "field": "labels", "intervals": True, "tag": "ZG"}, ["bedtools", "tag", "-i", "a.bam", "-files", "genes.bed", "-labels", "genes", "-intervals", "-tag", "ZG"]),
]


@pytest.mark.parametrize("node_class,inputs,expected", CASES, ids=[case[0].NODE_ID for case in CASES])
def test_bedtools_contract_renders_native_argv(node_class: type, inputs: dict[str, object], expected: list[str]) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is True
    assert node_class.render_command(inputs) == expected
    assert all(token not in {">", "|", "&&", "ln"} for token in expected)


@pytest.mark.parametrize("node_class,_,__", CASES, ids=[case[0].NODE_ID for case in CASES])
def test_bedtools_family_metadata_and_planned_outputs(node_class: type, _: dict[str, object], __: list[str], tmp_path: Path) -> None:
    assert node_class.VERSION == "2.31.1"
    assert node_class.GIT_COMMIT == "705ccfdf2c9a77d71560c8adcece0663c2f5e18e"
    assert node_class.REQUIRED_EXECUTABLES == ["bedtools"]
    assert node_class.REQUIRED_CONDA_PACKAGES == ["bedtools"]
    assert node_class.PACKAGE_CONSTRAINTS == ("bedtools==2.31.1",)
    assert node_class.SOURCE_REVISION == "705ccfdf2c9a77d71560c8adcece0663c2f5e18e"
    assert node_class.DOCUMENTATION_URL.startswith("https://")
    outputs = node_class.PLAN_OUTPUTS({}, tmp_path)
    assert outputs
    assert outputs[0].parent.name == node_class.NODE_ID


def test_bedtools_stdout_and_native_file_contracts() -> None:
    native_file_nodes = {BEDToolsGetFastaNode, BEDToolsMaskFastaNode}
    for node_class, _, _ in CASES:
        if node_class in native_file_nodes:
            assert node_class.STDOUT_OUTPUT_INDEX is None
        else:
            assert node_class.STDOUT_OUTPUT_INDEX == 0
        assert node_class.SHELL is False


def test_chip_seq_sort_dependency_is_pinned_to_the_documented_coordinate_sort() -> None:
    assert BEDToolsSortNode.PACKAGE_CONSTRAINTS == ("bedtools==2.31.1",)
    assert BEDToolsSortNode.SOURCE_SHA256 == "d69117e1b2d24caae92fe6e84034a1f7e6f16877e94eaca6466528f8b4e0ee02"
    assert BEDToolsSortNode.UPSTREAM_SOURCE_SHA256 == (
        "c72bb170d3397693c2ceae5d7556c451f32c9edb427e5db586a7da0af32ba7ef"
    )
    assert BEDToolsSortNode.render_command({"input": "peaks.bed"}) == [
        "bedtools",
        "sort",
        "-i",
        "peaks.bed",
    ]


def test_closest_accepts_generic_sorted_interval_artifacts_in_the_editor() -> None:
    required = BEDToolsClosestNode.INPUT_TYPES()["required"]
    assert required["variants"][0] == "FILE"
    assert required["annotations"][0] == "FILE"
    assert _to_frontend_input_spec(required["variants"])[0] == "FILE"
    assert _to_frontend_input_spec(required["annotations"])[0] == "FILE"


@pytest.mark.parametrize(
    ("node_class", "inputs"),
    [
        (BEDToolsCoverageNode, {"inputA": "a.bed", "inputB": ["b.bed"], "d": True}),
        (BEDToolsGenomeCoverageNode, {"input_type": "bed", "input": "a.bed", "report": "bg"}),
        (BEDToolsMultiCovNode, {"input": "a.bed", "bams": ["a.bam"], "bam_indexes": ["wrong.bai"]}),
        (BEDToolsTagBedNode, {"inputA": "a.bam", "inputB": ["a.bed"], "field": "labels"}),
        (BEDToolsClosestBedNode, {"inputA": "a.bed", "inputB": ["b.bed"], "first_upstream": True}),
        (BEDToolsOverlapBedNode, {"input": "a.tsv", "cols": "1,2,3"}),
    ],
)
def test_bedtools_contracts_fail_closed_for_stale_or_missing_sidecars(node_class: type, inputs: dict[str, object]) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is not True


@pytest.mark.parametrize(
    ("node_class", "inputs"),
    [
        (
            BEDToolsIntersectBedNode,
            {
                "inputA": "a.bed",
                "inputB": ["b.bed"],
                "overlap": 0.5,
                "overlap_b": 0.25,
                "reciprocal": True,
            },
        ),
        (
            BEDToolsCoverageNode,
            {
                "inputA": "a.bed",
                "inputB": ["b.bed"],
                "overlap_a": 0.5,
                "overlap_b": 0.25,
                "reciprocal_overlap": True,
            },
        ),
        (
            BEDToolsIntersectBedNode,
            {"inputA": "a.bam", "inputB": ["b.bed"], "report": "wo"},
        ),
        (
            BEDToolsIntersectBedNode,
            {
                "inputA": "a.bed",
                "inputB": ["b.bed"],
                "report": "c",
                "names": ["annotations"],
            },
        ),
        (
            BEDToolsWindowNode,
            {"inputA": "a.bed", "inputB": "b.bed", "left": 50},
        ),
        (
            BEDToolsWindowNode,
            {
                "inputA": "a.bed",
                "inputB": "b.bed",
                "addition_mode": "lr",
                "window": 50,
            },
        ),
        (
            BEDToolsWindowNode,
            {"inputA": "a.bam", "inputB": "b.bed", "header": True},
        ),
        (
            BEDToolsWindowNode,
            {"inputA": "a.bam", "inputB": "b.bed", "report": "c"},
        ),
        (
            BEDToolsBamToBedNode,
            {"input": "a.bam", "option": "bedpe", "split": True},
        ),
        (
            BEDToolsGenomeCoverageNode,
            {
                "input_type": "bam",
                "input": "a.bam",
                "report": "bg",
                "split": True,
                "five": True,
            },
        ),
        (
            BEDToolsFlankNode,
            {"input": "a.bed", "genome": "genome.sizes", "left": 10},
        ),
        (
            BEDToolsSlopNode,
            {
                "inputA": "a.bed",
                "genome": "genome.sizes",
                "addition_mode": "lr",
                "both": 10,
            },
        ),
        (
            BEDToolsMakeWindowsNode,
            {
                "type": "genome",
                "action": "number",
                "genome": "genome.sizes",
                "windowsize": 10,
            },
        ),
        (
            BEDToolsMakeWindowsNode,
            {
                "type": "genome",
                "action": "number",
                "genome": "genome.sizes",
                "reverse": True,
            },
        ),
        (
            BEDToolsMaskFastaNode,
            {"input": "a.bed", "fasta": "ref.fa", "soft": True, "mask_character": "X"},
        ),
        (
            BEDToolsTagBedNode,
            {
                "inputA": "a.bam",
                "inputB": ["genes.bed"],
                "labels": ["genes"],
                "tag": "Z",
            },
        ),
        (
            BEDToolsMapNode,
            {"inputA": "a.bed", "inputB": "b.bed", "columns": "5", "operations": "bogus"},
        ),
        (
            BEDToolsMergeNode,
            {"input": "a.bed", "distance": "ten"},
        ),
        (
            BEDToolsMergeNode,
            {"input": "a.bed", "distance": 0, "delimiter": "|"},
        ),
    ],
)
def test_bedtools_contracts_reject_invalid_or_ignored_upstream_modes(
    node_class: type,
    inputs: dict[str, object],
) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is not True


@pytest.mark.parametrize(
    ("node_class", "inputs", "expected_tail"),
    [
        (
            BEDToolsMapNode,
            {"inputA": "a.bed", "inputB": "b.bed", "columns": "5", "operations": "min,max"},
            ["-c", "5", "-o", "min,max"],
        ),
        (
            BEDToolsMergeNode,
            {"input": "a.bed", "distance": 0, "columns": "5", "operations": "min,max"},
            ["-c", "5", "-o", "min,max", "-delim", ";"],
        ),
        (
            BEDToolsGroupByNode,
            {"inputA": "a.tsv", "group": "1-4", "columns": "5", "operation": "min,max"},
            ["-g", "1-4", "-c", "5", "-o", "min,max"],
        ),
    ],
)
def test_bedtools_column_operations_allow_one_column_with_multiple_operations(
    node_class: type,
    inputs: dict[str, object],
    expected_tail: list[str],
) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is True
    command = node_class.render_command(inputs)
    start = command.index(expected_tail[0])
    assert command[start : start + len(expected_tail)] == expected_tail


def test_bedtools_fasta_staging_preserves_siblings(tmp_path: Path) -> None:
    source = tmp_path / "source.fa"
    source.write_text(">chr1\nACGT\n")
    (tmp_path / "source.fa.fai").write_text("chr1\t4\t6\t4\t5\n")
    outputs = FocusedGetFasta.PLAN_OUTPUTS({"tab": False}, tmp_path / "out")
    inputs: dict[str, object] = {"input": "regions.bed", "fasta": str(source)}
    FocusedGetFasta.PREPARE_EXECUTION(inputs, outputs)
    staged = Path(str(inputs["fasta"]))
    assert staged.parent == outputs[0].parent
    assert staged.exists()
    assert Path(f"{staged}.fai").exists()
    assert staged.read_text() == source.read_text()


def test_bedtools_registry_owns_compatibility_ids_once() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    expected = {node_class.NODE_ID for node_class, _, _ in CASES}
    assert expected.issubset(registry.all())
    for node_id in expected:
        assert registry.get(node_id).__module__.startswith("bionodulo.nodes.builtin.bedtools_family")
    assert not {
        node_id
        for node_id, node_class in registry.all().items()
        if node_class.__module__.endswith("wrapped_bedtools")
    }
