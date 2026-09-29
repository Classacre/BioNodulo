"""Independent oracle for the pinned-container samtools chain.

Covers all seven typed samtools catalog operations in one composition:

    sort -> index
    sort -> flagstat
    sort -> view
    collate -> fixmate -> sort -> markdup

Two things are being checked, and they are different:

1. **Output honesty** — every file the node's ``PLAN_OUTPUTS`` promises actually
   exists after the run. A node that exits 0 while never writing a promised output
   would fail the real executor's G2 gate; here it is asserted directly.

2. **Biological content** — the flagstat report must describe the three reads in
   the fixture, and the derived BAMs must still parse and still contain them. Like
   the single-node oracle, this decompresses BGZF with stdlib ``gzip`` and parses
   the BAM layout itself, so htslib never marks its own homework.

A note on scope: this harness reproduces the executor's contract (PLAN_OUTPUTS,
PREPARE_EXECUTION, STDOUT_OUTPUT_INDEX) around a container run. It does not run
the project's own pixi-provisioned worker, so it is evidence about the nodes and
their commands, not about the cloud provisioning path.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CHAIN_DIR = REPO_ROOT / "reports" / "run-receipts" / "samtools-chain"
RECEIPT_PATH = CHAIN_DIR / "receipt.json"

EXPECTED_DIGEST = "sha256:23cda33a3a42125872766df9aaf1d2db67cdb8c85314b793465188435af31ba6"
FIXTURE_READ_COUNT = 3

pytestmark = pytest.mark.skipif(
    not RECEIPT_PATH.is_file(),
    reason="pinned-container chain receipt not present in this checkout",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_bam_read_names(path: Path) -> tuple[str, list[str]]:
    """Parse a BAM's header text and read names without htslib."""
    with gzip.open(path, "rb") as handle:
        raw = handle.read()
    assert raw[:4] == b"BAM\x01", f"not a BAM: {path}"
    offset = 4
    (l_text,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    header_text = raw[offset:offset + l_text].decode("utf-8", errors="replace")
    offset += l_text
    (n_ref,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    for _ in range(n_ref):
        (l_name,) = struct.unpack_from("<i", raw, offset)
        offset += 4 + l_name + 4
    names: list[str] = []
    while offset < len(raw):
        (block_size,) = struct.unpack_from("<i", raw, offset)
        if block_size <= 0 or offset + 4 + block_size > len(raw):
            break
        body = offset + 4
        (l_read_name,) = struct.unpack_from("<B", raw, body + 8)
        names.append(raw[body + 32:body + 32 + l_read_name - 1].decode("ascii"))
        offset += 4 + block_size
    return header_text, names


@pytest.fixture(scope="module")
def receipt() -> dict:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def test_every_step_completed_in_the_pinned_image(receipt: dict) -> None:
    assert receipt["image_digest"] == EXPECTED_DIGEST
    assert receipt["network"] == "none"
    assert "samtools 1.23.1" in receipt["tool_version"]
    assert receipt["summary"]["steps"] == 8
    assert receipt["summary"]["failed"] == 0, receipt["summary"]
    for step in receipt["steps"]:
        assert step["exit_code"] == 0, (step["step_label"], step["stderr"][:300])


def test_every_step_is_output_honest(receipt: dict) -> None:
    """Each promised output must exist. This is the executor's G2 gate."""
    dishonest = receipt["summary"]["output_dishonest"]
    assert dishonest == [], f"nodes promising outputs they never wrote: {dishonest}"
    for step in receipt["steps"]:
        assert step["planned_outputs_missing_after_run"] == [], step["step_label"]


def test_stdout_captured_outputs_are_recorded(receipt: dict) -> None:
    """flagstat writes to stdout; the receipt must show where that was captured."""
    flagstat = next(s for s in receipt["steps"] if s["node_id"] == "samtools_flagstat")
    assert flagstat["stdout_captured_to"] is not None
    assert flagstat["stdout_captured_to"].endswith("stats.stats.txt")


def test_all_recorded_artifacts_match_disk(receipt: dict) -> None:
    assert receipt["artifacts"]
    for artifact in receipt["artifacts"]:
        path = CHAIN_DIR / "work" / artifact["path"]
        assert path.is_file(), artifact["path"]
        assert _sha256(path) == artifact["sha256"], artifact["path"]


def test_flagstat_report_describes_the_actual_fixture(receipt: dict) -> None:
    stats = CHAIN_DIR / "work" / "out" / "03_flagstat" / "stats.stats.txt"
    text = stats.read_text(encoding="utf-8")
    assert f"{FIXTURE_READ_COUNT} + 0 in total" in text
    assert f"{FIXTURE_READ_COUNT} + 0 primary" in text
    assert f"{FIXTURE_READ_COUNT} + 0 mapped (100.00%" in text
    assert "0 + 0 duplicates" in text


def test_derived_bams_parse_and_keep_every_read(receipt: dict) -> None:
    expected = {"readA", "readB", "readC"}
    for label, relative in [
        ("01_sort", "out/01_sort/sorted_bam.bam"),
        ("04_view", "out/04_view/bam.bam"),
        ("05_collate", "out/05_collate/name_collated_bam.bam"),
        ("07_sort_after_fixmate", "out/07_sort_after_fixmate/sorted_bam.bam"),
        ("08_markdup", "out/08_markdup/marked_bam.bam"),
    ]:
        header_text, names = read_bam_read_names(CHAIN_DIR / "work" / relative)
        assert set(names) == expected, label
        assert len(names) == FIXTURE_READ_COUNT, label
        if label in {"01_sort", "07_sort_after_fixmate", "08_markdup"}:
            assert "SO:coordinate" in header_text, label


def test_index_is_colocated_with_its_bam(receipt: dict) -> None:
    """samtools_index hard-links the BAM beside the .bai in PREPARE_EXECUTION."""
    index_dir = CHAIN_DIR / "work" / "out" / "02_index"
    bam = index_dir / "indexed_bam.bam"
    bai = index_dir / "indexed_bam.bam.bai"
    assert bam.is_file() and bai.is_file()
    # The staged BAM must be byte-identical to the sorted input it indexes.
    sorted_bam = CHAIN_DIR / "work" / "out" / "01_sort" / "sorted_bam.bam"
    assert _sha256(bam) == _sha256(sorted_bam)
    # A BAI starts with the BAM\1 magic and carries a non-trivial index body.
    assert bai.read_bytes()[:4] == b"BAI\x01"
    assert bai.stat().st_size > 8


def test_markdup_duplicate_stats_were_written(receipt: dict) -> None:
    stats = CHAIN_DIR / "work" / "out" / "08_markdup" / "duplicate_stats.stats.txt"
    assert stats.is_file()
    assert stats.stat().st_size > 0
