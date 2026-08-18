from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.ml_design_family import TrainingLeakageCheckNode

TRAINING_SEQ = "ACGTACGTACGTACGTACGTACGTACGTACGTACG"
CONTAINED_SEQ = TRAINING_SEQ[:33] + "TT"
NOVEL_SEQ = "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT"


def _context(tmp_path: Path, name: str = "run") -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


def _candidates_fasta(tmp_path: Path) -> str:
    path = tmp_path / "candidates.fasta"
    path.write_text(
        f">E1 exact copy\n{TRAINING_SEQ}\n>E2 sixty percent\n{CONTAINED_SEQ}\n>E3 novel\n{NOVEL_SEQ}\n",
        encoding="utf-8",
    )
    return str(path)


def _training_tsv(tmp_path: Path, column: str = "RNA.sequence") -> str:
    path = tmp_path / "training.tsv"
    path.write_text(
        f"name\t{column}\ntrain_1\t{TRAINING_SEQ}\ntrain_2\tGGGGCCCCGGGGCCCCGGGGCCCCGGGGCCCCGGGG\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.mark.asyncio
async def test_one_exact_one_contained_one_novel(tmp_path: Path) -> None:
    node = TrainingLeakageCheckNode()
    summary_path, per_candidate_path = await node.run(
        candidates=_candidates_fasta(tmp_path),
        training=_training_tsv(tmp_path),
        context=_context(tmp_path),
    )

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["n_candidates"] == 3
    assert summary["n_training"] == 2
    assert summary["exact_duplicates"] == 1
    assert summary["ids_exact"] == ["E1"]
    assert summary["max_kmer_containment"] == pytest.approx(1.0)
    assert summary["frac_seqs_over_50pct"] == pytest.approx(2 / 3)
    assert summary["kmer_length"] == 31

    with Path(per_candidate_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    by_id = {row["id"]: row for row in rows}
    assert by_id["E1"]["exact_duplicate"] == "True"
    assert float(by_id["E2"]["containment"]) == pytest.approx(0.6)
    assert by_id["E2"]["n_kmers"] == "5" and by_id["E2"]["n_shared"] == "3"
    assert float(by_id["E3"]["containment"]) == pytest.approx(0.0)
    assert by_id["E3"]["exact_duplicate"] == "False"


@pytest.mark.asyncio
async def test_inline_candidates_and_custom_column(tmp_path: Path) -> None:
    inline = f">E1\n{TRAINING_SEQ}\n>E3\n{NOVEL_SEQ}\n"
    training = _training_tsv(tmp_path, column="seq")
    node = TrainingLeakageCheckNode()
    summary_path, _ = await node.run(
        candidates=inline,
        training=training,
        training_seq_column="seq",
        context=_context(tmp_path),
    )
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["n_candidates"] == 2
    assert summary["exact_duplicates"] == 1
    assert summary["frac_seqs_over_50pct"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_training_fasta_input(tmp_path: Path) -> None:
    training_fasta = tmp_path / "training.fasta"
    training_fasta.write_text(f">train_1\n{TRAINING_SEQ}\n", encoding="utf-8")
    node = TrainingLeakageCheckNode()
    summary_path, _ = await node.run(
        candidates=_candidates_fasta(tmp_path),
        training=str(training_fasta),
        context=_context(tmp_path),
    )
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["n_training"] == 1
    assert summary["exact_duplicates"] == 1
    assert summary["max_kmer_containment"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_missing_column_error(tmp_path: Path) -> None:
    node = TrainingLeakageCheckNode()
    with pytest.raises(ValueError, match="no 'design_seq' column"):
        await node.run(
            candidates=_candidates_fasta(tmp_path),
            training=_training_tsv(tmp_path),
            training_seq_column="design_seq",
            context=_context(tmp_path),
        )
    with pytest.raises(ValueError, match="not an existing file"):
        await node.run(
            candidates=_candidates_fasta(tmp_path),
            training=str(tmp_path / "missing.tsv"),
            context=_context(tmp_path, "missing"),
        )
