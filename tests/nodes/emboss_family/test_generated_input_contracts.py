"""Generated EMBOSS file ports follow the source ACD declarations."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = json.loads(
    (ROOT / "reports/node-expansion/emboss-generated.json").read_text(encoding="utf-8")
)
GENERATED = [record for record in MANIFEST["records"] if record["status"] == "generated"]


def node_class(node_id: str):
    module_name = f"bionodulo.nodes.builtin.emboss_family.{node_id}"
    module = importlib.import_module(module_name)
    return next(
        value for value in vars(module).values()
        if isinstance(value, type)
        and value.__module__ == module_name
        and getattr(value, "NODE_ID", None) == node_id
    )


@pytest.mark.parametrize("record", GENERATED, ids=lambda record: record["node_id"])
def test_all_acd_file_inputs_are_exposed_with_requiredness(record: dict) -> None:
    node = node_class(record["node_id"])
    spec = node.INPUT_TYPES()
    exposed = set(spec["required"]) | set(spec["optional"])
    source_inputs = set(record["input_files"])
    source_required = source_inputs & set(record["required_params"])

    assert set(node.PATH_INPUTS) == source_inputs
    assert source_inputs <= exposed
    assert source_required <= set(spec["required"])
    assert set(node.REQUIRED_PATH_INPUTS) <= set(spec["required"])
    assert (source_inputs - set(node.REQUIRED_PATH_INPUTS)) <= set(spec["optional"])


@pytest.mark.parametrize("node_id", ["emboss_water", "emboss_needle"])
def test_alignment_requires_two_sequences_but_not_default_matrix(node_id: str) -> None:
    node = node_class(node_id)
    inputs = {"asequence": "first.fa", "bsequence": "second.fa", "output": "out"}

    assert node.VALIDATE_INPUTS(inputs) is True
    command = node.render_command(inputs)
    assert command[command.index("-asequence") + 1] == "first.fa"
    assert command[command.index("-bsequence") + 1] == "second.fa"
    assert "-datafile" not in command
    assert node.VALIDATE_INPUTS({"asequence": "first.fa"}) == (
        "Required input 'bsequence' is missing"
    )

    command_with_matrix = node.render_command({**inputs, "datafile": "matrix.txt"})
    assert command_with_matrix[command_with_matrix.index("-datafile") + 1] == "matrix.txt"


def test_primersearch_exposes_and_renders_both_required_file_inputs() -> None:
    node = node_class("emboss_primersearch")
    inputs = {
        "seqall": "sequences.fa",
        "infile": "primers.txt",
        "mismatchpercent": 0,
        "output": "out",
    }

    assert node.VALIDATE_INPUTS(inputs) is True
    command = node.render_command(inputs)
    assert command[command.index("-seqall") + 1] == "sequences.fa"
    assert command[command.index("-infile") + 1] == "primers.txt"
    assert node.VALIDATE_INPUTS({"seqall": "sequences.fa", "mismatchpercent": 0}) == (
        "Required input 'infile' is missing"
    )


def test_water_preserves_computed_acd_defaults_and_explicit_false() -> None:
    node = node_class("emboss_water")
    optional = node.INPUT_TYPES()["optional"]
    assert "default" not in optional["gapopen"][1]
    assert "default" not in optional["gapextend"][1]
    assert optional["brief"][1]["default"] is True

    inputs = {"asequence": "a.fa", "bsequence": "b.fa", "output": "out"}
    command = node.render_command(inputs)
    assert "-gapopen" not in command and "-gapextend" not in command
    assert "-brief" not in command

    explicit = node.render_command({**inputs, "gapopen": 7.5, "brief": False})
    assert explicit[explicit.index("-gapopen") + 1] == "7.5"
    assert explicit[explicit.index("-brief") + 1] == "N"
    enabled = node.render_command({**inputs, "brief": True})
    assert enabled[enabled.index("-brief") + 1] == "Y"


def test_split_bracket_inforesidue_acd_exposes_real_contract() -> None:
    node = node_class("emboss_inforesidue")
    assert node.DESCRIPTION == "Return information on a given amino acid residue"
    assert "code" in node.INPUT_TYPES()["required"]
    assert node.RETURN_NAMES == ("outfile",)
    assert node.OUTPUT_FILENAMES == ("outfile.out",)
    command = node.render_command({
        "code": "A", "aadata": "amino.dat", "output": "out",
    })
    assert command[command.index("-code") + 1] == "A"
    assert command[command.index("-outfile") + 1].endswith("outfile.out")
