"""Independent oracle for the digest-pinned container runs of the EMBOSS nodes.

Independence matters here. The obvious way to check an EMBOSS translation is to
run EMBOSS again, which would let the tool under test mark its own homework.
Instead this module re-derives every expected value from external ground truth
using only the Python standard library:

* the standard genetic code is re-implemented here as a codon table, so the
  protein is translated from the fixture nucleotide independently of EMBOSS;
* the reverse complement is computed with a plain base-complement table;
* the pepstats residue counts are recomputed from the fixture protein, and the
  nine physicochemical property groups are the standard EDAM/EMBOSS groupings,
  encoded here rather than read back out of the report.

It asserts biological content, not exit status. It also pins the run itself:
the image must be the digest-pinned EMBOSS image requested, and that digest must
still resolve to the same value afterwards.

Each node's assertions skip cleanly when its receipt is absent from the
checkout, which is different from passing.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "nodes" / "emboss_family" / "fixtures"
RECEIPTS = REPO_ROOT / "reports" / "run-receipts"

EXPECTED_IMAGE = "quay.io/biocontainers/emboss:6.6.0--h0f19ade_14"
EXPECTED_DIGEST = "sha256:a9bf499a690de7950a3f553793ea45daa947c63946a43edaefdbcfb0e9960a97"
EXPECTED_REPO_DIGEST = f"{EXPECTED_IMAGE.split(':')[0]}@{EXPECTED_DIGEST}"
EXPECTED_TOOL_VERSION = "EMBOSS:6.6.0.0"

TRANSEQ_RECEIPT = RECEIPTS / "emboss-transeq" / "receipt.json"
REVSEQ_RECEIPT = RECEIPTS / "emboss-revseq" / "receipt.json"
PEPSTATS_RECEIPT = RECEIPTS / "emboss-pepstats" / "receipt.json"

# Ground truth for the hand-written fixtures.
EXPECTED_PROTEIN = "MAKAFGRNDEVLSKGIE"
EXPECTED_REVERSE_COMPLEMENT = "CGTTTACGTAAACCCGGGTTTCAT"
EXPECTED_RESIDUES = 17

# The standard genetic code, written out here so the translation is derived
# independently of EMBOSS. Table 0 (EMBOSS "Standard").
CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}
COMPLEMENT = str.maketrans("ACGT", "TGCA")

# EMBOSS pepstats property groups, from the EMBOSS documentation. Encoded here
# rather than parsed from the report so the comparison is independent.
PROPERTY_GROUPS = {
    "Tiny": "ACGT" + "S",
    "Small": "ABCDGNPS" + "TV",
    "Aliphatic": "AILV",
    "Aromatic": "FHWY",
    "Non-polar": "ACFGILMPVWY",
    "Polar": "DEHKNQRSTZ",
    "Charged": "BDEHKRZ",
    "Basic": "HKR",
    "Acidic": "BDEZ",
}

_RESIDUE_ROW = re.compile(r"^([A-Z]) = \S+\s+(\d+)")
_PROPERTY_ROW = re.compile(
    r"^(Tiny|Small|Aliphatic|Aromatic|Non-polar|Polar|Charged|Basic|Acidic)"
    r"\s+\(([^)]*)\)\s+(\d+)"
)
_RESIDUE_TOTAL = re.compile(r"Residues\s*=\s*(\d+)")
_STANDARD_RESIDUES = set("ACDEFGHIKLMNPQRSTVWY")


def _load_receipt(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"pinned-container run receipt not present: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_fasta(path: Path) -> dict[str, str]:
    """Minimal stdlib FASTA reader: header id -> concatenated sequence."""
    records: dict[str, str] = {}
    name: str | None = None
    chunks: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if name is not None:
                records[name] = "".join(chunks)
            name = line[1:].split()[0]
            chunks = []
        elif line.strip():
            chunks.append(line.strip())
    if name is not None:
        records[name] = "".join(chunks)
    return records


def translate(nucleotides: str) -> str:
    return "".join(CODON_TABLE[nucleotides[i:i + 3]] for i in range(0, len(nucleotides) - 2, 3))


def reverse_complement(nucleotides: str) -> str:
    return nucleotides.translate(COMPLEMENT)[::-1]


def _assert_pinned_run(receipt: dict, node_id: str) -> None:
    assert receipt["node_id"] == node_id
    assert receipt["status"] == "completed"
    assert receipt["exit_code"] == 0
    assert receipt["execution"]["kind"] == "digest_pinned_container"
    assert receipt["execution"]["image"] == EXPECTED_IMAGE
    assert receipt["execution"]["image_digest_expected"] == EXPECTED_DIGEST
    assert receipt["execution"]["image_digest_observed_after_run"] == EXPECTED_REPO_DIGEST
    assert receipt["execution"]["digest_stable"] is True
    assert receipt["execution"]["network"] == "none"
    assert EXPECTED_TOOL_VERSION in receipt["tool_version_stdout"]


def _assert_artifact_hashes(receipt: dict, receipt_dir: Path) -> None:
    assert receipt["artifact_count"] >= 1
    for artifact in receipt["artifacts"]:
        path = receipt_dir / artifact["path"]
        assert path.is_file(), artifact["path"]
        assert path.stat().st_size == artifact["bytes"], artifact["path"]
        assert _sha256(path) == artifact["sha256"], artifact["path"]


# ── emboss_transeq ──────────────────────────────────────────────────────────

def test_transeq_receipt_is_a_successful_pinned_run() -> None:
    receipt = _load_receipt(TRANSEQ_RECEIPT)
    _assert_pinned_run(receipt, "emboss_transeq")
    _assert_artifact_hashes(receipt, TRANSEQ_RECEIPT.parent)


def test_transeq_renders_the_expected_outseq_argv() -> None:
    receipt = _load_receipt(TRANSEQ_RECEIPT)
    argv = receipt["rendered_command"]
    assert argv[0] == "transeq"
    assert argv[1:3] == ["-sequence", "/work/cds_nucleotide.fasta"]
    assert argv[3:5] == ["-outseq", "/work/out/translated.fasta"]


def test_transeq_translation_matches_independent_codon_table() -> None:
    _load_receipt(TRANSEQ_RECEIPT)
    cds = read_fasta(FIXTURES / "cds_nucleotide.fasta")
    (nucleotide,) = cds.values()

    translated = read_fasta(TRANSEQ_RECEIPT.parent / "work" / "out" / "translated.fasta")
    assert len(translated) == 1, f"expected exactly one translation record, got {list(translated)}"
    (protein,) = translated.values()

    # External ground truth, derived here without EMBOSS.
    assert translate(nucleotide) == EXPECTED_PROTEIN
    assert protein == EXPECTED_PROTEIN
    assert protein == translate(nucleotide)
    # A 51 nt CDS with no stop codon translates to exactly 17 residues.
    assert len(protein) == 17


# ── emboss_revseq ───────────────────────────────────────────────────────────

def test_revseq_receipt_is_a_successful_pinned_run() -> None:
    receipt = _load_receipt(REVSEQ_RECEIPT)
    _assert_pinned_run(receipt, "emboss_revseq")
    _assert_artifact_hashes(receipt, REVSEQ_RECEIPT.parent)


def test_revseq_renders_the_expected_outseq_argv() -> None:
    receipt = _load_receipt(REVSEQ_RECEIPT)
    argv = receipt["rendered_command"]
    assert argv[0] == "revseq"
    assert argv[1:3] == ["-sequence", "/work/nucleotide.fasta"]
    assert argv[3:5] == ["-outseq", "/work/out/reverse_complement.fasta"]


def test_revseq_output_is_the_exact_reverse_complement() -> None:
    _load_receipt(REVSEQ_RECEIPT)
    nucleotides = read_fasta(FIXTURES / "nucleotide.fasta")
    (sequence,) = nucleotides.values()

    produced = read_fasta(REVSEQ_RECEIPT.parent / "work" / "out" / "reverse_complement.fasta")
    assert len(produced) == 1, f"expected exactly one record, got {list(produced)}"
    (revcomp,) = produced.values()

    # The fixture is deliberately non-palindromic, so a plain reverse or a plain
    # complement would both fail this assertion.
    assert reverse_complement(sequence) == EXPECTED_REVERSE_COMPLEMENT
    assert revcomp == EXPECTED_REVERSE_COMPLEMENT
    assert revcomp == reverse_complement(sequence)
    assert revcomp != sequence
    assert revcomp != sequence[::-1]
    assert revcomp != sequence.translate(COMPLEMENT)


# ── emboss_pepstats ─────────────────────────────────────────────────────────

def test_pepstats_receipt_is_a_successful_pinned_run() -> None:
    receipt = _load_receipt(PEPSTATS_RECEIPT)
    _assert_pinned_run(receipt, "emboss_pepstats")


def test_pepstats_renders_the_expected_stdout_argv() -> None:
    receipt = _load_receipt(PEPSTATS_RECEIPT)
    argv = receipt["rendered_command"]
    assert argv[0] == "pepstats"
    assert argv[1:3] == ["-sequence", "/work/protein.fasta"]
    # pepstats requires -outfile; `stdout` is the documented stdout sentinel.
    assert argv[3:5] == ["-outfile", "stdout"]
    assert receipt["stdout"].strip(), "pepstats report must be captured from stdout"


def test_pepstats_reports_the_expected_residue_count() -> None:
    receipt = _load_receipt(PEPSTATS_RECEIPT)
    report = receipt["stdout"]

    proteins = read_fasta(FIXTURES / "protein.fasta")
    (protein,) = proteins.values()
    assert len(protein) == EXPECTED_RESIDUES

    match = _RESIDUE_TOTAL.search(report)
    assert match is not None, "pepstats report did not contain a Residues line"
    assert int(match.group(1)) == EXPECTED_RESIDUES
    assert int(match.group(1)) == len(protein)
    assert f"PEPSTATS of {next(iter(proteins))} from 1 to {EXPECTED_RESIDUES}" in report


def test_pepstats_residue_composition_matches_the_fixture() -> None:
    receipt = _load_receipt(PEPSTATS_RECEIPT)
    report = receipt["stdout"]
    (protein,) = read_fasta(FIXTURES / "protein.fasta").values()

    counted: dict[str, int] = {}
    for line in report.splitlines():
        row = _RESIDUE_ROW.match(line)
        if row is not None:
            counted[row.group(1)] = int(row.group(2))

    assert counted, "pepstats report contained no residue table"
    # Every residue in the fixture is accounted for, and the pseudo-residues
    # (B/J/O/U/X/Z) are empty because the fixture uses only the 20 standard ones.
    assert sum(counted.values()) == EXPECTED_RESIDUES
    expected = Counter(protein)
    for residue in sorted(_STANDARD_RESIDUES):
        assert counted.get(residue, 0) == expected.get(residue, 0), residue
    for pseudo in "BJOUXZ":
        assert counted.get(pseudo, 0) == 0, pseudo


def test_pepstats_property_groups_match_independent_groupings() -> None:
    receipt = _load_receipt(PEPSTATS_RECEIPT)
    report = receipt["stdout"]
    (protein,) = read_fasta(FIXTURES / "protein.fasta").values()
    composition = Counter(protein)

    reported: dict[str, int] = {}
    for line in report.splitlines():
        row = _PROPERTY_ROW.match(line)
        if row is not None:
            reported[row.group(1)] = int(row.group(3))

    assert reported, "pepstats report contained no property table"
    for group, members in PROPERTY_GROUPS.items():
        expected = sum(composition[residue] for residue in members)
        assert reported[group] == expected, f"{group}: {reported[group]} != {expected}"


def test_pepstats_input_is_the_independent_translation_of_the_cds() -> None:
    """Cross-node check: the pepstats fixture is the transeq fixture's translation."""
    (cds,) = read_fasta(FIXTURES / "cds_nucleotide.fasta").values()
    (protein,) = read_fasta(FIXTURES / "protein.fasta").values()
    assert translate(cds) == protein
