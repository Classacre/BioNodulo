"""Independent oracle for the digest-pinned container run of ``samtools_sort``.

Independence matters here. The obvious way to check a BAM is to ask samtools, but
that would let the tool under test mark its own homework. Instead this module
decompresses the BGZF container with Python's stdlib ``gzip`` (BGZF is a valid
multi-member gzip stream) and parses the BAM binary layout directly. No htslib, no
pysam, no samtools process is involved in the assertions.

It asserts biological content, not exit status:

* every read in the fixture survives the sort, by name;
* base sequences are byte-identical to the fixture;
* the header declares coordinate sort;
* records are ordered by reference then position, with references ordered as the
  header declares them.

It also pins the run itself: the image digest must be the one requested and must
still resolve to the same value afterwards.

Skips when the receipt is absent, which is different from passing.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPT_DIR = REPO_ROOT / "reports" / "run-receipts" / "samtools-sort"
RECEIPT_PATH = RECEIPT_DIR / "receipt.json"
FIXTURE = REPO_ROOT / "tests" / "nodes" / "samtools" / "fixtures" / "mini_unsorted.sam"

EXPECTED_IMAGE = "quay.io/biocontainers/samtools:1.23.1--ha83d96e_0"
EXPECTED_DIGEST = "sha256:23cda33a3a42125872766df9aaf1d2db67cdb8c85314b793465188435af31ba6"
# The fixture is deliberately out of order: readB (chr2:200), readC (chr1:300),
# readA (chr1:100). Coordinate sort must yield readA, readC, readB.
EXPECTED_ORDER = ["readA", "readC", "readB"]

pytestmark = pytest.mark.skipif(
    not RECEIPT_PATH.is_file(),
    reason="pinned-container run receipt not present in this checkout",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_bam(path: Path) -> tuple[str, list[str], list[dict]]:
    """Parse a BAM without htslib. BGZF is concatenated gzip members."""
    with gzip.open(path, "rb") as handle:
        raw = handle.read()

    if raw[:4] != b"BAM\x01":
        raise ValueError(f"not a BAM file: magic {raw[:4]!r}")
    offset = 4
    (l_text,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    header_text = raw[offset:offset + l_text].decode("utf-8", errors="replace")
    offset += l_text
    (n_ref,) = struct.unpack_from("<i", raw, offset)
    offset += 4

    refs: list[str] = []
    for _ in range(n_ref):
        (l_name,) = struct.unpack_from("<i", raw, offset)
        offset += 4
        refs.append(raw[offset:offset + l_name - 1].decode("ascii"))
        offset += l_name
        offset += 4  # l_ref

    records: list[dict] = []
    while offset < len(raw):
        (block_size,) = struct.unpack_from("<i", raw, offset)
        if block_size <= 0 or offset + 4 + block_size > len(raw):
            break
        body = offset + 4
        ref_id, pos = struct.unpack_from("<ii", raw, body)
        (l_read_name,) = struct.unpack_from("<B", raw, body + 8)
        (flag,) = struct.unpack_from("<H", raw, body + 14)
        (l_seq,) = struct.unpack_from("<i", raw, body + 16)
        read_name = raw[body + 32:body + 32 + l_read_name - 1].decode("ascii")
        seq_offset = body + 32 + l_read_name + 4 * struct.unpack_from(
            "<H", raw, body + 12)[0]
        packed = raw[seq_offset:seq_offset + (l_seq + 1) // 2]
        bases = "".join("=ACMGRSVTWYHKDBN"[nibble]
                        for byte in packed for nibble in (byte >> 4, byte & 0xF))[:l_seq]
        records.append({"name": read_name, "ref_id": ref_id, "pos": pos,
                        "flag": flag, "seq": bases})
        offset += 4 + block_size
    return header_text, refs, records


def read_fixture_records() -> dict[str, str]:
    rows = FIXTURE.read_text(encoding="utf-8").splitlines()
    out: dict[str, str] = {}
    for line in rows:
        if line.startswith("@"):
            continue
        fields = line.split("\t")
        out[fields[0]] = fields[9]
    return out


@pytest.fixture(scope="module")
def receipt() -> dict:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def test_receipt_records_a_successful_digest_pinned_run(receipt: dict) -> None:
    assert receipt["node_id"] == "samtools_sort"
    assert receipt["status"] == "completed"
    assert receipt["exit_code"] == 0
    assert receipt["execution"]["kind"] == "digest_pinned_container"
    assert receipt["execution"]["image"] == EXPECTED_IMAGE
    assert receipt["execution"]["image_digest_expected"] == EXPECTED_DIGEST
    # The digest must still resolve to the same value after the run, so the receipt
    # cannot have silently drifted onto a different image.
    assert receipt["execution"]["image_digest_observed_after_run"] == f"{EXPECTED_IMAGE.split(':')[0]}@{EXPECTED_DIGEST}"
    assert receipt["execution"]["digest_stable"] is True
    assert receipt["execution"]["network"] == "none"
    assert "samtools 1.23.1" in receipt["tool_version_stdout"]


def test_rendered_command_is_the_nodes_own_argv(receipt: dict) -> None:
    argv = receipt["rendered_command"]
    assert argv[0] == "samtools" and argv[1] == "sort"
    assert "-o" in argv and "/work/out/sorted_bam.bam" in argv
    # The host renders Windows separators; that difference must be recorded, not hidden.
    assert receipt["platform_path_rewrites"], "expected recorded path rewrites on a Windows host"
    for rewrite in receipt["platform_path_rewrites"]:
        assert "\\" in rewrite["rendered_on_host"]
        assert "\\" not in rewrite["used_in_container"]


def test_every_recorded_artifact_hash_matches_disk(receipt: dict) -> None:
    assert receipt["artifact_count"] >= 2
    for artifact in receipt["artifacts"]:
        path = RECEIPT_DIR / artifact["path"]
        assert path.is_file(), artifact["path"]
        assert path.stat().st_size == artifact["bytes"], artifact["path"]
        assert _sha256(path) == artifact["sha256"], artifact["path"]


def test_sorted_bam_is_coordinate_sorted_and_loses_nothing(receipt: dict) -> None:
    bam = RECEIPT_DIR / "work" / "out" / "sorted_bam.bam"
    header_text, refs, records = read_bam(bam)

    # Header must declare coordinate sort.
    assert "SO:coordinate" in header_text
    assert refs == ["chr1", "chr2"]

    # Every fixture read survives, by name.
    fixture_records = read_fixture_records()
    assert {record["name"] for record in records} == set(fixture_records)
    assert len(records) == len(fixture_records)

    # Ordering: reference index ascending, then 0-based position ascending.
    keys = [(record["ref_id"], record["pos"]) for record in records]
    assert keys == sorted(keys), f"records are not coordinate sorted: {keys}"

    # And specifically the order this fixture must produce.
    assert [record["name"] for record in records] == EXPECTED_ORDER


def test_sequences_are_byte_identical_to_the_fixture(receipt: dict) -> None:
    bam = RECEIPT_DIR / "work" / "out" / "sorted_bam.bam"
    _, _, records = read_bam(bam)
    fixture_records = read_fixture_records()
    for record in records:
        assert record["seq"] == fixture_records[record["name"]], record["name"]
    # 0-based positions must match the fixture's 1-based coordinates minus one.
    positions = {record["name"]: record["pos"] for record in records}
    assert positions == {"readA": 99, "readC": 299, "readB": 199}


INVALID_RECEIPT = REPO_ROOT / "reports" / "run-receipts" / "samtools-sort-invalid" / "receipt.json"


@pytest.mark.skipif(not INVALID_RECEIPT.is_file(),
                    reason="invalid-input run receipt not present in this checkout")
def test_invalid_input_fails_loudly_rather_than_silently() -> None:
    """A CIGAR/SEQ length mismatch must fail, not produce a plausible BAM.

    This is the failure mode that matters: a node that quietly emitted a truncated
    or empty alignment file on malformed input would be worse than one that stops.
    """
    invalid = json.loads(INVALID_RECEIPT.read_text(encoding="utf-8"))
    assert invalid["status"] == "failed"
    assert invalid["exit_code"] != 0
    assert "CIGAR and query sequence are of different length" in invalid["stderr"]

    # No output alignment may be published from a failed run.
    output = RECEIPT_DIR.parent / "samtools-sort-invalid" / "work" / "out" / "sorted_bam.bam"
    assert not output.is_file() or output.stat().st_size == 0
