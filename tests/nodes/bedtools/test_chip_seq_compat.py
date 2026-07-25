"""Focused coverage for the two canonical ChIP-seq BEDTools IDs."""

from pathlib import Path

import pytest

from bionodulo.nodes.builtin import chip_seq
from bionodulo.nodes.builtin.bedtools_family.coverage_native import BEDToolsCoverageNode
from bionodulo.nodes.builtin.bedtools_family.intersect import BEDToolsIntersectNode
from scripts.gen_node_index import build_index


def test_chip_seq_bedtools_ids_have_focused_source_pinned_owners() -> None:
    index = build_index()
    for node_class in (BEDToolsIntersectNode, BEDToolsCoverageNode):
        assert index[node_class.NODE_ID] == node_class.__module__
        assert getattr(chip_seq, node_class.__name__) is node_class
        assert node_class.VERSION == "2.31.1"
        assert node_class.GIT_COMMIT == "705ccfdf2c9a77d71560c8adcece0663c2f5e18e"
        assert node_class.STDOUT_OUTPUT_INDEX == 0
        assert node_class.SHELL is False


def test_chip_seq_bedtools_commands_and_outputs(tmp_path: Path) -> None:
    intersect_inputs = {"a": "peaks.bed", "b": "blacklist.bed", "wa": True, "f": 0.5, "s": True}
    assert BEDToolsIntersectNode.VALIDATE_INPUTS(intersect_inputs) is True
    assert BEDToolsIntersectNode.render_command(intersect_inputs) == [
        "bedtools",
        "intersect",
        "-a",
        "peaks.bed",
        "-b",
        "blacklist.bed",
        "-wa",
        "-f",
        "0.5",
        "-s",
    ]
    assert BEDToolsIntersectNode.PLAN_OUTPUTS(intersect_inputs, tmp_path) == [
        tmp_path / "bedtools_intersect" / "intersection.bed"
    ]

    coverage_inputs = {"a": "regions.bed", "b": "reads.bam"}
    assert BEDToolsCoverageNode.render_command(coverage_inputs) == [
        "bedtools",
        "coverage",
        "-a",
        "regions.bed",
        "-b",
        "reads.bam",
    ]
    assert BEDToolsCoverageNode.PLAN_OUTPUTS(coverage_inputs, tmp_path) == [
        tmp_path / "bedtools_coverage" / "coverage.bed"
    ]


@pytest.mark.parametrize(
    "inputs",
    [
        {"a": "a.bed", "b": "b.bed", "v": True, "wo": True},
        {"a": "a.bed", "b": "b.bed", "wa": True, "wo": True},
        {"a": "a.bed", "b": "b.bed", "f": 0.0},
        {"a": "a.bed", "b": "b.bed", "f": 2.0},
    ],
)
def test_intersect_incompatible_modes_fail_closed(inputs: dict[str, object]) -> None:
    assert BEDToolsIntersectNode.VALIDATE_INPUTS(inputs) is not True
