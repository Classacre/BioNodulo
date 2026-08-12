from __future__ import annotations

import csv
import json
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.biopython_family import (
    BLASTSearchNode,
    MSAViewNode,
    SeqIOReadNode,
    SeqIOWriteNode,
    SequenceStatsNode,
    SequenceTranslateNode,
)


def _context(tmp_path: Path) -> SimpleNamespace:
    previews: list[dict[str, str]] = []
    context = SimpleNamespace(node_dir=tmp_path, previews=previews)
    context.register_preview = lambda path, label="": previews.append(
        {"path": str(path), "label": label}
    )
    return context


def _fasta_sequence(path: str) -> str:
    return "".join(
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if not line.startswith(">")
    )


def _png_dimensions_and_pixels(path: str) -> tuple[int, int, bytes]:
    data = Path(path).read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    compressed = bytearray()
    width = height = 0
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"IDAT":
            compressed.extend(payload)
        offset += length + 12
    return width, height, zlib.decompress(bytes(compressed))


def test_authorities_hashes_and_focused_ownership_are_exact() -> None:
    owners = {
        SeqIOReadNode: "seqio_read",
        SeqIOWriteNode: "seqio_write",
        SequenceTranslateNode: "translate",
        SequenceStatsNode: "sequence_stats",
        MSAViewNode: "msa_view",
    }
    for node, owner in owners.items():
        assert node.__module__.endswith(f".{owner}")
        assert node.VERSION == "1.87"
        assert node.GIT_COMMIT == "7a9c76cce8c6a58db791be2b12a135af210cedf2"
        assert node.CONDA_PACKAGE_CONSTRAINTS == {"biopython": "1.87"}
        assert set(node.SOURCE_PATHS) <= set(node.SOURCE_FILE_SHA256)

    assert BLASTSearchNode.__module__.endswith(".blast")
    assert BLASTSearchNode.VERSION == "2.17.0"
    assert BLASTSearchNode.GIT_COMMIT == "db5563aefe2290e580da9a841950832ea3e89274"
    assert BLASTSearchNode.SOURCE_FILE_SHA256 == {
        "src/algo/blast/core/blast_engine.c": (
            "d4d27cd407135aab77bf14d0d185e2f1bad4b3f295a0cc5d0c8ff8eeca680238"
        ),
        "src/algo/blast/blastinput/blast_args.cpp": (
            "54ac1dcbfd6f06011f600ec59113a1f03fa2cdb3a9eb59c782cdff137575c676"
        ),
        "src/app/blast/blast_app_util.hpp": (
            "ef49a86de6066ec104fc9bc0ccdf237bcaef0fe798f846da52d90ef069148cba"
        ),
    }


@pytest.mark.asyncio
async def test_seqio_read_handles_lowercase_gc_and_protein_gc(tmp_path: Path) -> None:
    source = tmp_path / "source.fasta"
    source.write_text(">seq1\nacgtNN\n", encoding="utf-8")

    _, nucleotide_stats = await SeqIOReadNode().run(
        input_file=str(source),
        format="fasta",
        sequence_type="DNA",
        context=_context(tmp_path / "dna"),
    )
    assert json.loads(Path(nucleotide_stats).read_text(encoding="utf-8"))["average_gc"] == 50.0

    _, protein_stats = await SeqIOReadNode().run(
        input_file=str(source),
        format="fasta",
        sequence_type="protein",
        context=_context(tmp_path / "protein"),
    )
    assert json.loads(Path(protein_stats).read_text(encoding="utf-8"))["average_gc"] is None


@pytest.mark.asyncio
async def test_seqio_read_write_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.fasta"
    source.write_text(">seq1 example\nATGGCC\n>seq2\nGCGCGC\n", encoding="utf-8")
    read_outputs = await SeqIOReadNode().run(
        input_file=str(source),
        format="fasta",
        context=_context(tmp_path),
    )
    records = json.loads(Path(read_outputs[0]).read_text(encoding="utf-8"))
    assert [record["id"] for record in records] == ["seq1", "seq2"]

    write_outputs = await SeqIOWriteNode().run(
        sequences_json=read_outputs[0],
        output_format="genbank",
        output_name="sequences.gb",
        molecule_type="DNA",
        context=_context(tmp_path),
    )
    text = Path(write_outputs[0]).read_text(encoding="utf-8")
    assert "LOCUS" in text
    assert "ORIGIN" in text


@pytest.mark.asyncio
async def test_seqio_write_removes_partial_artifact_on_writer_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Bio import SeqIO

    records = tmp_path / "records.json"
    records.write_text(
        json.dumps([{"id": "seq1", "description": "", "seq_full": "ACGT"}]),
        encoding="utf-8",
    )

    def fail_after_partial_write(_records: object, path: str, _format: str) -> int:
        Path(path).write_text(">partial\nAC", encoding="utf-8")
        raise ValueError("synthetic writer failure")

    monkeypatch.setattr(SeqIO, "write", fail_after_partial_write)
    with pytest.raises(ValueError, match="synthetic writer failure"):
        await SeqIOWriteNode().run(
            sequences_json=str(records),
            output_format="fasta",
            output_name="output.fasta",
            context=_context(tmp_path),
        )

    output_dir = tmp_path / SeqIOWriteNode.NODE_ID
    assert not (output_dir / "output.fasta").exists()
    assert not (output_dir / ".output.fasta.tmp").exists()


@pytest.mark.asyncio
async def test_translation_uses_exact_ncbi_table_ids(tmp_path: Path) -> None:
    source = tmp_path / "coding.fasta"
    source.write_text(">gene\nATGAGA\n", encoding="utf-8")

    standard = await SequenceTranslateNode().run(
        input_file=str(source),
        table="Standard",
        to_stop=False,
        context=_context(tmp_path / "standard"),
    )
    mitochondrial = await SequenceTranslateNode().run(
        input_file=str(source),
        table="Vertebrate Mitochondrial",
        to_stop=False,
        context=_context(tmp_path / "mitochondrial"),
    )

    assert SequenceTranslateNode.TABLE_IDS["Standard"] == 1
    assert SequenceTranslateNode.TABLE_IDS["Vertebrate Mitochondrial"] == 2
    assert _fasta_sequence(standard[0]) == "MR"
    assert _fasta_sequence(mitochondrial[0]) == "M*"


@pytest.mark.asyncio
async def test_stats_explains_ambiguous_weight_and_quotes_csv(tmp_path: Path) -> None:
    source = tmp_path / "ambiguous.fasta"
    source.write_text(">seq,one\nacgtN\n", encoding="utf-8")
    stats_json, _, stats_csv = await SequenceStatsNode().run(
        input_file=str(source),
        format="fasta",
        sequence_type="DNA",
        context=_context(tmp_path),
    )

    payload = json.loads(Path(stats_json).read_text(encoding="utf-8"))
    assert payload[0]["gc_content"] == 50.0
    assert payload[0]["molecular_weight"] is None
    assert "not a valid unambiguous letter for DNA" in payload[0]["molecular_weight_error"]
    assert '"seq,one"' in Path(stats_csv).read_text(encoding="utf-8")
    with Path(stats_csv).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["id"] == "seq,one"
    assert rows[0]["molecular_weight_error"] == payload[0]["molecular_weight_error"]


@pytest.mark.asyncio
async def test_stats_does_not_swallow_unexpected_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Bio import SeqUtils

    source = tmp_path / "source.fasta"
    source.write_text(">seq1\nACGT\n", encoding="utf-8")

    def unexpected_failure(*_args: object, **_kwargs: object) -> float:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(SeqUtils, "molecular_weight", unexpected_failure)
    with pytest.raises(RuntimeError, match="unexpected failure"):
        await SequenceStatsNode().run(
            input_file=str(source),
            format="fasta",
            sequence_type="DNA",
            context=_context(tmp_path),
        )


@pytest.mark.asyncio
async def test_blast_uses_documented_argv_and_source_valid_limits(tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    async def run_command(command: list[str], cwd: str) -> dict[str, object]:
        calls.append((command, cwd))
        Path(command[-1]).write_text("<not-a-real-blast-document/>\n", encoding="utf-8")
        return {"returncode": 0}

    assert (
        BLASTSearchNode.VALIDATE_INPUTS(
            {
                "query": "query.fa",
                "subject": "subject.fa",
                "program": "blastn",
                "max_hits": 10_000,
            }
        )
        is True
    )
    context = _context(tmp_path)
    context.run_command = run_command
    output = await BLASTSearchNode().run(
        query="query.fa",
        subject="subject.fa",
        program="blastn",
        evalue=1e-5,
        max_hits=10_000,
        outfmt="5",
        context=context,
    )

    assert calls[0][0] == [
        "blastn",
        "-query",
        "query.fa",
        "-subject",
        "subject.fa",
        "-evalue",
        "1e-05",
        "-max_target_seqs",
        "10000",
        "-outfmt",
        "5",
        "-out",
        output[0],
    ]


@pytest.mark.asyncio
async def test_blast_failure_removes_stale_and_partial_xml(tmp_path: Path) -> None:
    output_path = tmp_path / BLASTSearchNode.NODE_ID / "blast_result.xml"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("stale", encoding="utf-8")

    async def run_command(command: list[str], cwd: str) -> dict[str, object]:
        del cwd
        Path(command[-1]).write_text("partial", encoding="utf-8")
        return {"returncode": 2, "stderr": "subject rejected"}

    context = _context(tmp_path)
    context.run_command = run_command
    with pytest.raises(RuntimeError, match=r"exit code 2 .*subject rejected"):
        await BLASTSearchNode().run(
            query="query.fa",
            subject="subject.fa",
            program="blastn",
            context=context,
        )
    assert not output_path.exists()


@pytest.mark.asyncio
async def test_msa_ties_are_deterministic_strict_majorities(tmp_path: Path) -> None:
    first = tmp_path / "first.fasta"
    second = tmp_path / "second.fasta"
    first.write_text(">a\nACGT\n>b\nACGA\n", encoding="utf-8")
    second.write_text(">b\nACGA\n>a\nACGT\n", encoding="utf-8")

    first_outputs = await MSAViewNode().run(
        alignment_file=str(first),
        format="fasta",
        context=_context(tmp_path / "first"),
    )
    second_outputs = await MSAViewNode().run(
        alignment_file=str(second),
        format="fasta",
        context=_context(tmp_path / "second"),
    )

    assert _fasta_sequence(first_outputs[1]) == "ACGN"
    assert _fasta_sequence(second_outputs[1]) == "ACGN"


@pytest.mark.asyncio
async def test_msa_protein_render_is_visible_and_bounded(tmp_path: Path) -> None:
    alignment = tmp_path / "proteins.fasta"
    sequence = "ARNDCQEGHILKMFPSTWYV" * 11
    alignment.write_text(
        "".join(f">protein_{index}\n{sequence}\n" for index in range(101)),
        encoding="utf-8",
    )
    summary_path, consensus_path, image_path = await MSAViewNode().run(
        alignment_file=str(alignment),
        format="fasta",
        context=_context(tmp_path),
    )

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["sequence_type"] == "protein"
    assert summary["rendered_sequences"] == 100
    assert summary["rendered_columns"] == 200
    assert summary["render_truncated"] is True
    assert "X" not in _fasta_sequence(consensus_path)

    width, height, pixels = _png_dimensions_and_pixels(image_path)
    assert (width, height) == (800, 800)
    assert any(channel != 255 for channel in pixels)


def test_contract_validation_rejects_unrepresentable_modes() -> None:
    assert "filename without directory" in str(
        SeqIOWriteNode.VALIDATE_INPUTS(
            {
                "sequences_json": "records.json",
                "output_format": "fasta",
                "output_name": "../escape.fa",
            }
        )
    )
    assert "exposes BLAST XML" in str(
        BLASTSearchNode.VALIDATE_INPUTS(
            {"query": "q.fa", "subject": "s.fa", "program": "blastn", "outfmt": "6"}
        )
    )


def test_family_package_reexports_the_focused_owners() -> None:
    from bionodulo.nodes.builtin.biopython_family import nodes

    for facade in (nodes,):
        assert facade.SeqIOReadNode is SeqIOReadNode
        assert facade.SeqIOWriteNode is SeqIOWriteNode
        assert facade.SequenceTranslateNode is SequenceTranslateNode
        assert facade.SequenceStatsNode is SequenceStatsNode
        assert facade.BLASTSearchNode is BLASTSearchNode
        assert facade.MSAViewNode is MSAViewNode
