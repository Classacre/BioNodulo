"""Independent oracle for the digest-pinned container runs of the SeqFu nodes.

The obvious way to check a SeqFu report is to run SeqFu again, but that would
let the tool mark its own homework. Instead this module parses the fixtures and
the captured stdout with the standard library only, computes the expected
statistics independently, and asserts the receipts agree exactly.

Ground truth is the fixture itself, hand-written in this directory:

* ``fixtures/mini.fasta`` — 4 records, names ``seq1..seq4``, lengths
  10, 20, 4, 30 (total 64). N50/N75/N90, auN, Avg, Min and Max are recomputed
  from those lengths by the helpers below.
* ``fixtures/mini.fastq`` — 3 records, lengths 10, 20, 6 (total 36).

Every assertion is about content, never about exit status alone. Tests skip
cleanly when a receipt is absent, which is different from passing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "nodes" / "seqfu_family" / "fixtures"
FASTA_FIXTURE = FIXTURES / "mini.fasta"
FASTQ_FIXTURE = FIXTURES / "mini.fastq"

RECEIPTS = REPO_ROOT / "reports" / "run-receipts"
STATS_DIR = RECEIPTS / "seqfu-stats"
COUNT_DIR = RECEIPTS / "seqfu-count"
LIST_DIR = RECEIPTS / "seqfu-list"

EXPECTED_IMAGE = "quay.io/biocontainers/seqfu:1.28.0--h41da26b_0"
EXPECTED_DIGEST = "sha256:0c910dd19d749bda7325d9f2738af0aec2a74cd920f345ecf2d244f6534f3e1c"
EXPECTED_VERSION = "1.28.0"

# Hand-written ground truth. ``test_fixtures_match_declared_ground_truth`` ties
# these to the files, so editing a fixture without updating the oracle fails.
FASTA_NAMES = ["seq1", "seq2", "seq3", "seq4"]
FASTA_LENGTHS = {"seq1": 10, "seq2": 20, "seq3": 4, "seq4": 30}
FASTA_TOTAL = 64

FASTQ_NAMES = ["read1", "read2", "read3"]
FASTQ_LENGTHS = {"read1": 10, "read2": 20, "read3": 6}
FASTQ_TOTAL = 36

STATS_HEADER = ["File", "#Seq", "Total bp", "Avg", "N50", "N75", "N90", "auN", "Min", "Max"]


# ── stdlib parsers (no SeqFu involved) ──────────────────────────────────────


def parse_fasta(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name: str | None = None
    chunks: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(chunks)))
            name = line[1:].split()[0]
            chunks = []
        elif line.strip():
            chunks.append(line.strip())
    if name is not None:
        records.append((name, "".join(chunks)))
    return records


def parse_fastq(path: Path) -> list[tuple[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line != ""]
    if len(lines) % 4 != 0:
        raise ValueError(f"FASTQ line count {len(lines)} is not a multiple of 4")
    records: list[tuple[str, str]] = []
    for index in range(0, len(lines), 4):
        header, sequence, plus, quality = lines[index:index + 4]
        if not header.startswith("@") or not plus.startswith("+"):
            raise ValueError(f"malformed FASTQ record at line {index + 1}")
        if len(sequence) != len(quality):
            raise ValueError(f"sequence/quality length mismatch at line {index + 1}")
        records.append((header[1:].split()[0], sequence))
    return records


def nx(lengths: list[int], fraction: float) -> int:
    """Nx: the length at which the cumulative length first reaches fraction*total."""
    ordered = sorted(lengths, reverse=True)
    threshold = fraction * sum(ordered)
    running = 0
    for length in ordered:
        running += length
        if running >= threshold:
            return length
    return 0


def aun(lengths: list[int]) -> float:
    """Area under the Nx curve: sum(L^2) / sum(L)."""
    total = sum(lengths)
    return sum(length * length for length in lengths) / total


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_receipt(receipt_dir: Path) -> dict:
    path = receipt_dir / "receipt.json"
    if not path.is_file():
        pytest.skip(f"pinned-container receipt not present: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_pinned_run(receipt: dict, node_id: str) -> None:
    assert receipt["node_id"] == node_id
    assert receipt["status"] == "completed"
    assert receipt["exit_code"] == 0
    assert receipt["execution"]["kind"] == "digest_pinned_container"
    assert receipt["execution"]["image"] == EXPECTED_IMAGE
    assert receipt["execution"]["image_digest_expected"] == EXPECTED_DIGEST
    # The digest must still resolve to the same value after the run, so the
    # receipt cannot have silently drifted onto a different image.
    assert receipt["execution"]["image_digest_observed_after_run"] == (
        f"{EXPECTED_IMAGE.split(':')[0]}@{EXPECTED_DIGEST}"
    )
    assert receipt["execution"]["digest_stable"] is True
    assert receipt["execution"]["network"] == "none"
    assert EXPECTED_VERSION in receipt["tool_version_stdout"]
    # The staged fixture is the only artifact a stdout-only node writes here.
    assert receipt["artifact_count"] >= 1
    for artifact in receipt["artifacts"]:
        path = (RECEIPTS / node_id.replace("_", "-")) / artifact["path"]
        assert path.is_file(), artifact["path"]
        assert path.stat().st_size == artifact["bytes"], artifact["path"]
        assert sha256_file(path) == artifact["sha256"], artifact["path"]


# ── fixtures are the ground truth the oracle compares against ────────────────


def test_fixtures_match_declared_ground_truth() -> None:
    fasta = parse_fasta(FASTA_FIXTURE)
    assert [name for name, _ in fasta] == FASTA_NAMES
    assert {name: len(seq) for name, seq in fasta} == FASTA_LENGTHS
    assert sum(len(seq) for _, seq in fasta) == FASTA_TOTAL

    fastq = parse_fastq(FASTQ_FIXTURE)
    assert [name for name, _ in fastq] == FASTQ_NAMES
    assert {name: len(seq) for name, seq in fastq} == FASTQ_LENGTHS
    assert sum(len(seq) for _, seq in fastq) == FASTQ_TOTAL


# ── seqfu_stats ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def stats_receipt() -> dict:
    return load_receipt(STATS_DIR)


def test_stats_receipt_is_a_successful_pinned_run(stats_receipt: dict) -> None:
    assert_pinned_run(stats_receipt, "seqfu_stats")
    assert stats_receipt["rendered_command"][:2] == ["seqfu", "stats"]
    assert stats_receipt["rendered_command"][-1] == "/work/mini.fasta"


def test_stats_header_is_the_documented_table(stats_receipt: dict) -> None:
    lines = [line for line in stats_receipt["stdout"].splitlines() if line.strip()]
    assert lines[0].split("\t") == STATS_HEADER


def test_stats_reports_exact_sequence_count_and_total_bases(stats_receipt: dict) -> None:
    lines = [line for line in stats_receipt["stdout"].splitlines() if line.strip()]
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:]]
    assert len(rows) == 1, f"one input file must give one row, got {rows}"
    row = rows[0]
    assert row["File"].endswith("mini.fasta")
    assert int(row["#Seq"]) == len(FASTA_NAMES) == 4
    assert int(row["Total bp"]) == FASTA_TOTAL == 64


def test_stats_length_summary_matches_independently_computed_values(stats_receipt: dict) -> None:
    lengths = list(FASTA_LENGTHS.values())
    lines = [line for line in stats_receipt["stdout"].splitlines() if line.strip()]
    header = lines[0].split("\t")
    row = dict(zip(header, lines[1].split("\t")))

    assert int(row["N50"]) == nx(lengths, 0.50)
    assert int(row["N75"]) == nx(lengths, 0.75)
    assert int(row["N90"]) == nx(lengths, 0.90)
    assert int(row["Min"]) == min(lengths)
    assert int(row["Max"]) == max(lengths)
    assert float(row["Avg"]) == pytest.approx(FASTA_TOTAL / len(lengths), abs=0.01)
    assert float(row["auN"]) == pytest.approx(aun(lengths), abs=0.01)


# ── seqfu_count ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def count_receipt() -> dict:
    return load_receipt(COUNT_DIR)


def test_count_receipt_is_a_successful_pinned_run(count_receipt: dict) -> None:
    assert_pinned_run(count_receipt, "seqfu_count")
    assert count_receipt["rendered_command"][:2] == ["seqfu", "count"]


def test_count_reports_the_exact_number_of_sequences(count_receipt: dict) -> None:
    lines = [line for line in count_receipt["stdout"].splitlines() if line.strip()]
    assert len(lines) == 1, f"expected one row for one input, got {lines}"
    fields = lines[0].split("\t")
    assert fields[0].endswith("mini.fasta")
    assert fields[1] == str(len(FASTA_NAMES))
    assert int(fields[1]) == 4
    # Single-end input, as the fixture is not a paired-end pair.
    assert fields[2] == "SE"


# ── seqfu_list ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def list_receipt() -> dict:
    return load_receipt(LIST_DIR)


def test_list_receipt_is_a_successful_pinned_run(list_receipt: dict) -> None:
    assert_pinned_run(list_receipt, "seqfu_list")
    command = list_receipt["rendered_command"]
    assert command[0:2] == ["seqfu", "list"]
    # Classic mode: <LIST> then the FASTX input.
    assert command[-2:] == ["/work/mini.fasta", "/work/mini.fasta"]


def test_list_emits_exactly_the_fixture_names_in_input_order(list_receipt: dict) -> None:
    output = parse_fasta_from_text(list_receipt["stdout"])
    assert [name for name, _ in output] == FASTA_NAMES
    assert len(output) == len(FASTA_NAMES)


def test_list_sequences_are_byte_identical_to_the_fixture(list_receipt: dict) -> None:
    output = dict(parse_fasta_from_text(list_receipt["stdout"]))
    fixture = dict(parse_fasta(FASTA_FIXTURE))
    assert output == fixture


def parse_fasta_from_text(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(chunks)))
            name = line[1:].split()[0]
            chunks = []
        elif line.strip():
            chunks.append(line.strip())
    if name is not None:
        records.append((name, "".join(chunks)))
    return records
