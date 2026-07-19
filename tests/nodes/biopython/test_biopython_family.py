from __future__ import annotations

import json
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
    context.register_preview = lambda path, label="": previews.append({"path": str(path), "label": label})
    return context


def test_biopython_and_blast_authorities_are_exact() -> None:
    for node in (SeqIOReadNode, SeqIOWriteNode, SequenceTranslateNode, SequenceStatsNode, MSAViewNode):
        assert node.VERSION == "1.87"
        assert node.GIT_COMMIT == "7a9c76cce8c6a58db791be2b12a135af210cedf2"
        assert node.REQUIRED_CONDA_PACKAGES[0] == "biopython"
    assert BLASTSearchNode.VERSION == "2.17.0"
    assert BLASTSearchNode.SOURCE_SHA256 == "898be99790d620053991c7761797f5328281fffc6ed2ca0c95504e619be8f68a"
    assert BLASTSearchNode.REQUIRED_EXECUTABLES == ["blastn", "blastp", "blastx", "tblastn", "tblastx"]


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
async def test_translation_and_stats_use_declared_sequence_types(tmp_path: Path) -> None:
    source = tmp_path / "coding.fasta"
    source.write_text(">gene\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG\n", encoding="utf-8")
    translated = await SequenceTranslateNode().run(
        input_file=str(source),
        table="Standard",
        to_stop=True,
        context=_context(tmp_path),
    )
    assert "MAIVMGR" in Path(translated[0]).read_text(encoding="utf-8")

    stats = await SequenceStatsNode().run(
        input_file=str(source),
        format="fasta",
        sequence_type="DNA",
        context=_context(tmp_path),
    )
    payload = json.loads(Path(stats[0]).read_text(encoding="utf-8"))
    assert payload[0]["length"] == 39
    assert payload[0]["gc_content"] is not None


@pytest.mark.asyncio
async def test_blast_uses_direct_documented_argv_without_a_real_binary(tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    async def run_command(command: list[str], cwd: str) -> dict[str, object]:
        calls.append((command, cwd))
        Path(command[-1]).write_text("<not-a-real-blast-document/>\n", encoding="utf-8")
        return {"returncode": 0}

    context = _context(tmp_path)
    context.run_command = run_command
    output = await BLASTSearchNode().run(
        query="query.fa",
        subject="subject.fa",
        program="blastn",
        evalue=1e-5,
        max_hits=25,
        outfmt="5",
        context=context,
    )

    assert Path(output[0]).name == "blast_result.xml"
    assert calls[0][0] == [
        "blastn",
        "-query",
        "query.fa",
        "-subject",
        "subject.fa",
        "-evalue",
        "1e-05",
        "-max_target_seqs",
        "25",
        "-outfmt",
        "5",
        "-out",
        output[0],
    ]


@pytest.mark.asyncio
async def test_msa_view_emits_real_consensus_and_png(tmp_path: Path) -> None:
    alignment = tmp_path / "alignment.fasta"
    alignment.write_text(">a\nACGT\n>b\nACGA\n", encoding="utf-8")
    summary, consensus, image = await MSAViewNode().run(
        alignment_file=str(alignment),
        format="fasta",
        context=_context(tmp_path),
    )

    assert json.loads(Path(summary).read_text(encoding="utf-8"))["alignment_length"] == 4
    assert "ACGT" in Path(consensus).read_text(encoding="utf-8")
    assert Path(image).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


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


def test_legacy_facade_reexports_the_focused_owners() -> None:
    from bionodulo.nodes.builtin import biopython_nodes

    assert biopython_nodes.SeqIOReadNode is SeqIOReadNode
    assert biopython_nodes.SeqIOWriteNode is SeqIOWriteNode
    assert biopython_nodes.SequenceTranslateNode is SequenceTranslateNode
    assert biopython_nodes.SequenceStatsNode is SequenceStatsNode
    assert biopython_nodes.BLASTSearchNode is BLASTSearchNode
    assert biopython_nodes.MSAViewNode is MSAViewNode
