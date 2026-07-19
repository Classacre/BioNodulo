from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.wrapped_protein_taxonomy_family.hmmer import (
    HMMERAlimaskNode,
    HMMERHmmalignNode,
    HMMERHmmbuildNode,
    HMMERHmmconvertNode,
    HMMERHmmemitNode,
    HMMERHmmfetchNode,
)

COMMIT = "9acd8b6758a0ca5d21db6d167e0277484341929b"
FIRST_WAVE = (
    (HMMERAlimaskNode, "alimask"),
    (HMMERHmmalignNode, "hmmalign"),
    (HMMERHmmbuildNode, "hmmbuild"),
    (HMMERHmmconvertNode, "hmmconvert"),
    (HMMERHmmemitNode, "hmmemit"),
    (HMMERHmmfetchNode, "hmmfetch"),
)


@pytest.mark.parametrize(("node_class", "command"), FIRST_WAVE)
def test_first_wave_has_operation_local_hmmer_34_authority(node_class: type, command: str) -> None:
    assert node_class.VERSION == "3.4"
    assert node_class.GIT_COMMIT == COMMIT
    assert node_class.DOCUMENTATION_URL == (
        f"https://github.com/EddyRivasLab/hmmer/blob/{COMMIT}/documentation/man/{command}.man.in"
    )
    assert node_class.SOURCE_URL == f"https://github.com/EddyRivasLab/hmmer/blob/{COMMIT}/src/{command}.c"
    assert node_class.SOURCE_PATHS == (f"documentation/man/{command}.man.in", f"src/{command}.c")
    assert f"src/{command}.c::main" in node_class.UPSTREAM_SOURCE
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert all(".hmmer.adapter" not in base.__module__ for base in inspect.getmro(node_class))


def test_hmmbuild_renders_documented_exclusive_modes_and_worker_count() -> None:
    command = HMMERHmmbuildNode.render_command(
        {
            "msafile": "globins.sto",
            "effective_weighting": "eent",
            "ere": 0.59,
            "single_sequence_scoring": "singlemx",
            "threads": 6,
            "output": "/work/hmmbuild",
        }
    )
    assert "--eent" in command
    assert "--eset" not in command
    assert "--singlemx" in command
    assert command[command.index("--cpu") + 1] == "6"
    assert HMMERHmmbuildNode.VALIDATE_INPUTS(
        {"msafile": "globins.sto", "effective_weighting": "eent", "eset": 2.5}
    ) == "Input 'eset' is only valid when effective_weighting is eset"
    assert HMMERHmmbuildNode.VALIDATE_INPUTS(
        {"msafile": "globins.sto", "effective_weighting": "eset"}
    ) == "Input 'eset' is required when effective_weighting is eset"


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"single_sequence_scoring": "singlemx", "popen": 0.5}, "less than 0.5"),
        ({"single_sequence_scoring": "singlemx", "pextend": 1.0}, "less than 1"),
        ({"eft": 0.0}, "greater than 0 and less than 1"),
    ],
)
def test_hmmbuild_enforces_exclusive_upstream_numeric_bounds(updates: dict[str, object], message: str) -> None:
    validation = HMMERHmmbuildNode.VALIDATE_INPUTS({"msafile": "globins.sto", **updates})
    assert validation is not True
    assert message in str(validation)


def test_hmmemit_uses_hmmer_34_defaults_and_direct_output_option() -> None:
    optional = HMMERHmmemitNode.INPUT_TYPES()["optional"]
    assert optional["seed"][1]["default"] == 0
    assert optional["minl"][1]["default"] == 0.0
    assert optional["minu"][1]["default"] == 0.0
    assert optional["length"][1]["default"] == 400
    assert HMMERHmmemitNode.render_command(
        {"hmmfile": "model.hmm", "output_mode": "fasta", "output": "/work/hmmemit"}
    ) == [
        "hmmemit",
        "-o",
        "/work/hmmemit/emitted.fasta",
        "-N",
        "1",
        "--seed",
        "0",
        "model.hmm",
    ]


def test_direct_output_and_stdout_collection_match_each_command_contract(tmp_path: Path) -> None:
    assert HMMERHmmalignNode.render_command(
        {
            "seq": "seq.fa",
            "hmmfile": "model.hmm",
            "input_format_select": "--amino",
            "output": "/work/hmmalign",
        }
    )[:3] == ["hmmalign", "-o", "/work/hmmalign/alignment.sto"]
    assert HMMERHmmfetchNode.render_command(
        {"hmmfile": "db.hmm", "keyfile": "keys.txt", "output": "/work/hmmfetch"}
    )[:4] == ["hmmfetch", "-f", "-o", "/work/hmmfetch/selected.hmm"]
    assert HMMERHmmconvertNode.STDOUT_OUTPUT_INDEX == 0
    assert HMMERHmmconvertNode.render_command(
        {"hmmfile": "model.hmm", "format": "-a", "outfmt": "3/e", "output": "/work/hmmconvert"}
    ) == ["hmmconvert", "-a", "--outfmt", "3/e", "model.hmm"]
    assert HMMERHmmconvertNode.PLAN_OUTPUTS({"format": "-a"}, tmp_path) == [
        tmp_path / "hmmer_hmmconvert" / "converted.hmm3"
    ]
    assert "-b" not in HMMERHmmconvertNode.INPUT_TYPES()["required"]["format"][1]["options"]
    assert "binary-safe" in HMMERHmmconvertNode.AUDIT_CAVEATS[0]


@pytest.mark.parametrize("ranges", [[], ["0-10"], ["20-10"], ["one-ten"]])
def test_alimask_rejects_invalid_documented_range_syntax(ranges: list[str]) -> None:
    validation = HMMERAlimaskNode.VALIDATE_INPUTS(
        {"msafile": "alignment.sto", "range_type": "model", "ranges": ranges}
    )
    assert validation is not True
    assert "range" in str(validation)
