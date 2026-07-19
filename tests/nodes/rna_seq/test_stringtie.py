"""Focused StringTie 3.0.3 contract checks."""

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.rna_seq import StringTieNode as LegacyStringTieNode
from bionodulo.nodes.builtin.rna_seq_family.stringtie import StringTieNode
from scripts.gen_node_index import build_index


def test_stringtie_has_one_source_pinned_owner() -> None:
    assert LegacyStringTieNode is StringTieNode
    assert build_index()["stringtie"] == StringTieNode.__module__
    assert StringTieNode.VERSION == "3.0.3"
    assert StringTieNode.GIT_COMMIT == "3436ad6dfd0ffc806a94086cf747ac6ff2b0dc19"


def test_stringtie_renders_documented_outputs_and_flags(tmp_path: Path) -> None:
    inputs = {
        "bam": "aligned.bam",
        "gtf": "genes.gtf",
        "threads": 4,
        "fr": True,
        "min_isoform_fraction": 0.05,
        "output": "/work/stringtie",
    }
    assert StringTieNode.VALIDATE_INPUTS(inputs) is True
    assert StringTieNode.render_command(inputs) == [
        "stringtie",
        "aligned.bam",
        "-G",
        "genes.gtf",
        "-o",
        "/work/stringtie/transcripts.gtf",
        "-A",
        "/work/stringtie/gene_abundance.tsv",
        "-p",
        "4",
        "--fr",
        "-f",
        "0.05",
    ]
    assert StringTieNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "stringtie" / "transcripts.gtf",
        tmp_path / "stringtie" / "gene_abundance.tsv",
    ]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"bam": "aligned.bam", "threads": 0}, "threads must be an integer between"),
        ({"bam": "aligned.bam", "threads": 1, "fr": True, "rf": True}, "mutually exclusive"),
        (
            {"bam": "aligned.bam", "threads": 1, "min_isoform_fraction": 1.0},
            "less than 1",
        ),
    ],
)
def test_stringtie_fails_closed(inputs: dict[str, object], message: str) -> None:
    assert message in str(StringTieNode.VALIDATE_INPUTS(inputs))
