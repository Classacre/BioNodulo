"""Source-contract tests for the focused official Seqtk v1.4 family."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.seqtk_family.adapter import SeqtkCommandNode
from bionodulo.nodes.builtin.seqtk_family.comp import SeqTKCompNode
from bionodulo.nodes.builtin.seqtk_family.cutn import SeqTKCutNNode
from bionodulo.nodes.builtin.seqtk_family.dropse import SeqTKDropSENode
from bionodulo.nodes.builtin.seqtk_family.fqchk import SeqTKFqchkNode
from bionodulo.nodes.builtin.seqtk_family.hety import SeqTKHetyNode
from bionodulo.nodes.builtin.seqtk_family.listhet import SeqTKListHetNode
from bionodulo.nodes.builtin.seqtk_family.mergefa import SeqTKMergeFANode
from bionodulo.nodes.builtin.seqtk_family.mergepe import SeqTKMergePENode
from bionodulo.nodes.builtin.seqtk_family.mutfa import SeqTKMutFANode
from bionodulo.nodes.builtin.seqtk_family.randbase import SeqTKRandBaseNode
from bionodulo.nodes.builtin.seqtk_family.sample import SeqTKSampleNode
from bionodulo.nodes.builtin.seqtk_family.seq import SeqTKSeqNode
from bionodulo.nodes.builtin.seqtk_family.subseq import SeqTKSubseqNode
from bionodulo.nodes.builtin.seqtk_family.telo import SeqTKTeloNode
from bionodulo.nodes.builtin.seqtk_family.trimfq import SeqTKTrimFQNode


SEQTK_CLASSES = (
    SeqTKCompNode,
    SeqTKCutNNode,
    SeqTKDropSENode,
    SeqTKFqchkNode,
    SeqTKHetyNode,
    SeqTKListHetNode,
    SeqTKMergeFANode,
    SeqTKMergePENode,
    SeqTKMutFANode,
    SeqTKRandBaseNode,
    SeqTKSampleNode,
    SeqTKSeqNode,
    SeqTKSubseqNode,
    SeqTKTeloNode,
    SeqTKTrimFQNode,
)


def test_seqtk_family_uses_pinned_official_v14_authority() -> None:
    assert SeqtkCommandNode.VERSION == "1.4"
    assert SeqtkCommandNode.GIT_TAG == "v1.4"
    assert SeqtkCommandNode.GIT_COMMIT == "ae7defa8bead3ef77d241f12194dc66acdd40fca"
    assert SeqtkCommandNode.UPSTREAM_SOURCE_SHA256 == "411bbc5882c4f848ff7a0e46c7ea428ea68bf509dec7903cc4337c523326bb1d"
    assert all(node.SHELL is False for node in SEQTK_CLASSES)
    assert all(node.REQUIRED_EXECUTABLES == ["seqtk"] for node in SEQTK_CLASSES)


def test_seqtk_family_preserves_all_stable_ids_and_class_names() -> None:
    assert {node.__name__: node.NODE_ID for node in SEQTK_CLASSES} == {
        "SeqTKCompNode": "seqtk_comp",
        "SeqTKCutNNode": "seqtk_cutN",
        "SeqTKDropSENode": "seqtk_dropse",
        "SeqTKFqchkNode": "seqtk_fqchk",
        "SeqTKHetyNode": "seqtk_hety",
        "SeqTKListHetNode": "seqtk_listhet",
        "SeqTKMergeFANode": "seqtk_mergefa",
        "SeqTKMergePENode": "seqtk_mergepe",
        "SeqTKMutFANode": "seqtk_mutfa",
        "SeqTKRandBaseNode": "seqtk_randbase",
        "SeqTKSampleNode": "seqtk_sample",
        "SeqTKSeqNode": "seqtk_seq",
        "SeqTKSubseqNode": "seqtk_subseq",
        "SeqTKTeloNode": "seqtk_telo",
        "SeqTKTrimFQNode": "seqtk_trimfq",
    }


@pytest.mark.parametrize(
    ("node", "inputs", "expected"),
    (
        (SeqTKCompNode, {"in_file": "reads.fa"}, ["seqtk", "comp", "reads.fa"]),
        (
            SeqTKCutNNode,
            {"in_file": "reads.fa"},
            ["seqtk", "cutN", "-n", "1000", "-p", "10", "reads.fa"],
        ),
        (SeqTKDropSENode, {"in_file": "reads.fq"}, ["seqtk", "dropse", "reads.fq"]),
        (
            SeqTKFqchkNode,
            {"in_file": "reads.fq"},
            ["seqtk", "fqchk", "-q", "20", "reads.fq"],
        ),
        (
            SeqTKHetyNode,
            {"in_file": "reads.fa"},
            ["seqtk", "hety", "-w", "50000", "-t", "5", "reads.fa"],
        ),
        (SeqTKListHetNode, {"in_file": "reads.fa"}, ["seqtk", "listhet", "reads.fa"]),
        (
            SeqTKMergeFANode,
            {"in_fa1": "a.fa", "in_fa2": "b.fa"},
            ["seqtk", "mergefa", "-q", "0", "a.fa", "b.fa"],
        ),
        (
            SeqTKMergePENode,
            {"in_fq1": "r1.fq", "in_fq2": "r2.fq"},
            ["seqtk", "mergepe", "r1.fq", "r2.fq"],
        ),
        (
            SeqTKMutFANode,
            {"in_file": "reads.fa", "in_snp": "changes.tsv"},
            ["seqtk", "mutfa", "reads.fa", "changes.tsv"],
        ),
        (SeqTKRandBaseNode, {"in_file": "reads.fa"}, ["seqtk", "randbase", "reads.fa"]),
        (
            SeqTKSampleNode,
            {"in_file": "reads.fq", "subsample_size": 100},
            ["seqtk", "sample", "-s", "11", "reads.fq", "100"],
        ),
        (
            SeqTKSeqNode,
            {"in_file": "reads.fq"},
            [
                "seqtk",
                "seq",
                "-q",
                "0",
                "-X",
                "255",
                "-l",
                "0",
                "-Q",
                "33",
                "-s",
                "11",
                "-f",
                "1.0",
                "-L",
                "0",
                "reads.fq",
            ],
        ),
        (
            SeqTKSubseqNode,
            {"in_file": "reads.fa", "regions": "regions.bed"},
            ["seqtk", "subseq", "-l", "0", "reads.fa", "regions.bed"],
        ),
        (
            SeqTKTeloNode,
            {"in_file": "reads.fa"},
            [
                "seqtk",
                "telo",
                "-m",
                "CCCTAA",
                "-p",
                "1",
                "-d",
                "2000",
                "-s",
                "300",
                "reads.fa",
            ],
        ),
        (
            SeqTKTrimFQNode,
            {"in_file": "reads.fq"},
            [
                "seqtk",
                "trimfq",
                "-l",
                "30",
                "-q",
                "0.05",
                "-b",
                "0",
                "-e",
                "0",
                "-L",
                "0",
                "reads.fq",
            ],
        ),
    ),
)
def test_seqtk_default_argv_matches_seqtk_c(
    node: type[SeqtkCommandNode],
    inputs: dict[str, Any],
    expected: list[str],
) -> None:
    assert node.render_command(inputs) == expected
    assert all(token not in {">", "|", "awk", "pigz"} for token in expected)


def test_seqtk_optional_flags_follow_native_order() -> None:
    assert SeqTKCompNode.render_command({"in_file": "reads.fa", "u": True, "in_bed": "regions.bed"}) == [
        "seqtk",
        "comp",
        "-u",
        "-r",
        "regions.bed",
        "reads.fa",
    ]
    assert SeqTKCutNNode.render_command({"in_file": "reads.fa", "n": 50, "p": 2, "g": True}) == [
        "seqtk",
        "cutN",
        "-n",
        "50",
        "-p",
        "2",
        "-g",
        "reads.fa",
    ]
    assert SeqTKHetyNode.render_command({"in_file": "reads.fa", "w": 1000, "t": 4, "m": True}) == [
        "seqtk",
        "hety",
        "-w",
        "1000",
        "-t",
        "4",
        "-m",
        "reads.fa",
    ]
    assert SeqTKMergeFANode.render_command(
        {
            "in_fa1": "a.fa",
            "in_fa2": "b.fa",
            "q": 20,
            "i": True,
            "r": True,
            "h": True,
        }
    ) == ["seqtk", "mergefa", "-q", "20", "-i", "-r", "-h", "a.fa", "b.fa"]
    assert SeqTKSampleNode.render_command({"in_file": "reads.fq", "subsample_size": 0.1, "two_pass": True, "s": 7}) == [
        "seqtk",
        "sample",
        "-2",
        "-s",
        "7",
        "reads.fq",
        "0.1",
    ]
    assert SeqTKSubseqNode.render_command(
        {"in_file": "reads.fa", "regions": "regions.bed", "t": True, "l": 60, "s": True}
    ) == ["seqtk", "subseq", "-t", "-l", "60", "-s", "reads.fa", "regions.bed"]
    assert SeqTKTrimFQNode.render_command({"in_file": "reads.fq", "l": 25, "q": 0.01, "b": 5, "e": 10, "L": 80}) == [
        "seqtk",
        "trimfq",
        "-l",
        "25",
        "-q",
        "0.01",
        "-b",
        "5",
        "-e",
        "10",
        "-L",
        "80",
        "reads.fq",
    ]


def test_seqtk_seq_exposes_v14_flags_without_legacy_direction_selector() -> None:
    inputs = {
        "in_file": "reads.fq",
        "q": 20,
        "X": 70,
        "n": "N",
        "l": 60,
        "Q": 64,
        "s": 7,
        "f": 0.5,
        "M": "mask.bed",
        "L": 100,
        "F": "I",
        "c": True,
        "r": True,
        "A": True,
        "C": True,
        "N": True,
        "x1": True,
        "V": True,
        "U": True,
        "x": True,
        "S": True,
    }
    assert SeqTKSeqNode.render_command(inputs) == [
        "seqtk",
        "seq",
        "-q",
        "20",
        "-X",
        "70",
        "-n",
        "N",
        "-l",
        "60",
        "-Q",
        "64",
        "-s",
        "7",
        "-f",
        "0.5",
        "-M",
        "mask.bed",
        "-L",
        "100",
        "-F",
        "I",
        "-c",
        "-r",
        "-A",
        "-C",
        "-N",
        "-1",
        "-V",
        "-U",
        "-x",
        "-S",
        "reads.fq",
    ]


@pytest.mark.parametrize(
    ("inputs", "expected_tail"),
    (
        ({"in_file": "reads.fa", "c": True}, ["-c", "reads.fa"]),
        ({"in_file": "reads.fa", "x": True}, ["-x", "reads.fa"]),
        ({"in_file": "reads.fa", "x1": True, "x2": True}, ["-1", "-2", "reads.fa"]),
    ),
)
def test_seqtk_seq_preserves_source_accepted_flag_combinations(
    inputs: dict[str, Any],
    expected_tail: list[str],
) -> None:
    assert SeqTKSeqNode.VALIDATE_INPUTS(inputs) is True
    assert SeqTKSeqNode.render_command(inputs)[-len(expected_tail) :] == expected_tail


def test_seqtk_stdout_and_meaningful_stderr_artifacts_are_planned(tmp_path: Path) -> None:
    assert SeqTKCompNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "seqtk_comp" / "composition.tsv"]
    assert SeqTKMergeFANode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "seqtk_mergefa" / "merged.fasta",
        tmp_path / "seqtk_mergefa" / "mergefa.stats.txt",
    ]
    assert SeqTKMergeFANode.STDOUT_OUTPUT_INDEX == 0
    assert SeqTKMergeFANode.STDERR_OUTPUT_INDEX == 1
    assert SeqTKTeloNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "seqtk_telo" / "telomeres.bed",
        tmp_path / "seqtk_telo" / "telomere_counts.txt",
    ]
    assert SeqTKTeloNode.STDOUT_OUTPUT_INDEX == 0
    assert SeqTKTeloNode.STDERR_OUTPUT_INDEX == 1


def test_seqtk_native_output_names_drop_input_compression(tmp_path: Path) -> None:
    assert SeqTKCutNNode.PLAN_OUTPUTS({"in_file": "reads.fa.gz"}, tmp_path)[0].name == "cutN.fasta"
    assert SeqTKCutNNode.PLAN_OUTPUTS({"in_file": "reads.fa.gz", "g": True}, tmp_path)[0].name == "gaps.bed"
    assert SeqTKDropSENode.PLAN_OUTPUTS({"in_file": "reads.fq.gz"}, tmp_path)[0].name == "paired.fastq"
    assert SeqTKMergePENode.PLAN_OUTPUTS({"in_fq1": "r1.fq.gz"}, tmp_path)[0].name == "interleaved.fastq"
    assert SeqTKSampleNode.PLAN_OUTPUTS({"in_file": "reads.fq.gz"}, tmp_path)[0].name == "subsampled.fastq"
    assert SeqTKSeqNode.PLAN_OUTPUTS({"in_file": "reads.fq.gz", "A": True}, tmp_path)[0].name == "transformed.fasta"
    assert SeqTKSeqNode.PLAN_OUTPUTS({"in_file": "reads.fa.gz", "F": "I"}, tmp_path)[0].name == "transformed.fastq"
    assert SeqTKSubseqNode.PLAN_OUTPUTS({"in_file": "reads.fa.gz", "t": True}, tmp_path)[0].name == "selected.tsv"
    assert SeqTKTrimFQNode.PLAN_OUTPUTS({"in_file": "reads.fq.gz"}, tmp_path)[0].name == "trimmed.fastq"


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    (
        (SeqTKMergeFANode, {"in_fa1": "a.fa", "in_fa2": "b.fa", "i": True, "m": True}, "mutually exclusive"),
        (SeqTKSampleNode, {"in_file": "a.fa", "subsample_size": 10, "single_pass_mode": True}, "Legacy"),
        (SeqTKSeqNode, {"in_file": "a.fa", "direction": "-R"}, "Legacy"),
        (SeqTKSeqNode, {"in_file": "a.fa", "n": "NN"}, "exactly one character"),
        (SeqTKSubseqNode, {"in_file": "a.fa", "regions": "r.bed", "source_type": "bed"}, "Legacy"),
        (SeqTKTeloNode, {"in_file": "a.fa", "P": True}, "Legacy"),
        (SeqTKTrimFQNode, {"in_file": "a.fq", "mode_select": "quality"}, "Legacy"),
        (SeqTKCompNode, {"in_file": "-"}, "stdin"),
    ),
)
def test_seqtk_rejects_source_incompatible_or_stale_inputs(
    node: type[SeqtkCommandNode],
    inputs: dict[str, Any],
    message: str,
) -> None:
    validation = node.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)
