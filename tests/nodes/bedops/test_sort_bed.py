"""Focused contract checks for BEDOPS 2.4.42 sort-bed."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.bedops_family.sort_bed import BEDOPSSortBedNode
from bionodulo.nodes.builtin.bedops_family.sort_bed_alias import BEDOPSSortBedGalaxyNode
from bionodulo.nodes.registry import NodeRegistry


@pytest.mark.parametrize("node_class", [BEDOPSSortBedNode, BEDOPSSortBedGalaxyNode])
def test_bedops_sort_bed_is_source_pinned_and_captures_stdout(node_class: type) -> None:
    assert node_class.VERSION == "2.4.42"
    assert node_class.GIT_COMMIT == "51d2adac6a3aaae73268cf07d0c4127387d335fa"
    assert node_class.SOURCE_URL.endswith(
        "/docs/content/reference/file-management/sorting/sort-bed.rst"
    )
    assert node_class.REQUIRED_EXECUTABLES == ["sort-bed"]
    assert node_class.REQUIRED_CONDA_PACKAGES == ["bedops"]
    assert node_class.SHELL is False
    assert node_class.STDOUT_OUTPUT_INDEX == 0


def test_bedops_sort_bed_validates_native_argv_and_outputs(tmp_path: Path) -> None:
    inputs = {
        "inputs": ["a.bed", "b.bed"],
        "memory_mb": 512,
        "tmpdir": "/scratch",
        "duplicates": True,
    }
    assert BEDOPSSortBedNode.VALIDATE_INPUTS(inputs) is True
    assert BEDOPSSortBedNode.render_command(inputs) == [
        "sort-bed",
        "--max-mem",
        "512M",
        "--tmpdir",
        "/scratch",
        "--duplicates",
        "a.bed",
        "b.bed",
    ]
    assert BEDOPSSortBedNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "bedops_sort_bed" / "sorted.bed"
    ]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"inputs": []}, "at least one BED input is required"),
        ({"inputs": ["a.bed"], "memory_mb": 0}, "memory_mb must be a positive integer"),
        (
            {"inputs": ["a.bed"], "unique": True, "duplicates": True},
            "unique and duplicates modes are mutually exclusive",
        ),
    ],
)
def test_bedops_sort_bed_fails_closed(inputs: dict[str, object], message: str) -> None:
    assert BEDOPSSortBedNode.VALIDATE_INPUTS(inputs) == message


def test_bedops_registry_has_one_focused_owner_per_stable_id() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    assert registry.get("bedops_sort_bed") is BEDOPSSortBedNode
    assert registry.get("bedops-sort-bed") is BEDOPSSortBedGalaxyNode
