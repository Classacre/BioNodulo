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
    assert StringTieNode.PACKAGE_CONSTRAINTS == ("stringtie=3.0.3",)
    assert StringTieNode.SOURCE_AUTHORITIES["cli_contract"] == "stringtie.cpp:processOptions"
    assert StringTieNode.AUDIT_STATUS == "contract-checked-no-binary-execution"


def test_stringtie_renders_documented_outputs_and_flags(tmp_path: Path) -> None:
    bam = tmp_path / "aligned.bam"
    gtf = tmp_path / "genes.gtf"
    bam.write_bytes(b"BAM")
    gtf.write_text("##gtf-version 3\n", encoding="utf-8")
    inputs = {
        "bam": str(bam),
        "gtf": str(gtf),
        "threads": 4,
        "fr": True,
        "min_isoform_fraction": 0.05,
        "output": "/work/stringtie",
    }
    assert StringTieNode.VALIDATE_INPUTS(inputs) is True
    assert StringTieNode.render_command(inputs) == [
        "stringtie",
        str(bam),
        "-G",
        str(gtf),
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


def test_stringtie_renders_cram_reference_without_invented_thread_cap(tmp_path: Path) -> None:
    cram = tmp_path / "aligned.cram"
    reference = tmp_path / "reference.fa"
    cram.write_bytes(b"CRAM")
    reference.write_text(">chr1\nACGT\n", encoding="utf-8")
    inputs = {
        "bam": cram,
        "cram_reference": reference,
        "threads": 128,
        "output": str(tmp_path / "out"),
    }
    assert StringTieNode.VALIDATE_INPUTS(inputs) is True
    assert StringTieNode.render_command(inputs) == [
        "stringtie",
        str(cram),
        "--ref",
        str(reference),
        "-o",
        str(tmp_path / "out" / "transcripts.gtf"),
        "-A",
        str(tmp_path / "out" / "gene_abundance.tsv"),
        "-p",
        "128",
        "-f",
        "0.01",
    ]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"bam": "aligned.bam", "threads": 0}, "threads must be a positive integer"),
        ({"bam": "aligned.bam", "threads": 1, "fr": True, "rf": True}, "mutually exclusive"),
        (
            {"bam": "aligned.bam", "threads": 1, "min_isoform_fraction": 1.0},
            "less than 1",
        ),
    ],
)
def test_stringtie_fails_closed(inputs: dict[str, object], message: str) -> None:
    assert message in str(StringTieNode.VALIDATE_INPUTS(inputs))


def test_stringtie_rejects_unmaterialized_alignment(tmp_path: Path) -> None:
    missing = tmp_path / "missing.bam"
    assert StringTieNode.VALIDATE_INPUTS({"bam": missing, "threads": 1}) == (
        f"bam is not a materialized file: {missing}"
    )


@pytest.mark.asyncio
async def test_stringtie_rejects_incomplete_gene_abundance_output(tmp_path: Path) -> None:
    bam = tmp_path / "aligned.bam"
    bam.write_bytes(b"BAM")

    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str] | str, **kwargs: object) -> dict[str, object]:
            output = tmp_path / "stringtie"
            output.mkdir(parents=True, exist_ok=True)
            (output / "transcripts.gtf").write_text(
                "# StringTie version 3.0.3\n", encoding="utf-8"
            )
            (output / "gene_abundance.tsv").write_text("partial\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="unexpected header"):
        await StringTieNode().run(bam=bam, threads=1, context=Context(), output_dir=tmp_path)
