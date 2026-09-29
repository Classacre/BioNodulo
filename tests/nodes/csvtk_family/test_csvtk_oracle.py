"""Independent oracle for the digest-pinned container runs of the csvtk family.

Independence matters here. The obvious way to check csvtk's output would be to run
csvtk again, but that lets the tool under test mark its own homework. Instead this
module reads the receipts' captured stdout and the fixture with the Python stdlib
only (``csv`` / ``json``) and recomputes the expected values itself.

It asserts real content, not exit status:

* ``csvtk_headers`` returns exactly the fixture's column names, in order;
* ``csvtk_cut`` returns exactly the requested columns in the requested order with
  values unchanged (and in an order that differs from the fixture, so a node that
  silently ignored ``-f`` would fail);
* ``csvtk_stats`` reports the exact row count and the exact min/max/mean that this
  module computes from the fixture.

Each test skips cleanly when its receipt is absent, which is different from
passing. It also pins the run: the image digest must be the one requested and must
still resolve to the same value afterwards.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPT_ROOT = REPO_ROOT / "reports" / "run-receipts"
FIXTURE = REPO_ROOT / "tests" / "nodes" / "csvtk_family" / "fixtures" / "mini_table.tsv"

EXPECTED_IMAGE = "quay.io/biocontainers/csvtk:0.31.0--h9ee0642_0"
EXPECTED_DIGEST = "sha256:e73ae7d1626058e06af6023e70945664ee08f55edf2f41fb9aa151b9a6a3f954"

STATS_RECEIPT = RECEIPT_ROOT / "csvtk-stats" / "receipt.json"
HEADERS_RECEIPT = RECEIPT_ROOT / "csvtk-headers" / "receipt.json"
CUT_RECEIPT = RECEIPT_ROOT / "csvtk-cut" / "receipt.json"


def load_receipt(path: Path) -> dict:
    """Return the receipt, or skip the test when the pinned run is absent."""
    if not path.is_file():
        pytest.skip(f"pinned-container run receipt not present: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_table() -> tuple[list[str], list[dict[str, str]]]:
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def parse_tsv(text: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    rows = [row for row in reader if row]
    return (rows[0], rows[1:]) if rows else ([], [])


@pytest.mark.parametrize(
    "receipt_path,node_id",
    [
        (STATS_RECEIPT, "csvtk_stats"),
        (HEADERS_RECEIPT, "csvtk_headers"),
        (CUT_RECEIPT, "csvtk_cut"),
    ],
)
def test_each_receipt_is_a_completed_digest_pinned_run(receipt_path: Path, node_id: str) -> None:
    receipt = load_receipt(receipt_path)
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
    assert receipt["fixture"]["sha256"]
    assert receipt["stdout"] != ""


def test_headers_receipt_returns_exactly_the_fixture_column_names() -> None:
    receipt = load_receipt(HEADERS_RECEIPT)
    fieldnames, _ = fixture_table()

    lines = [line for line in receipt["stdout"].splitlines() if line]
    assert lines == fieldnames == ["sample", "gene", "length", "gc"]


def test_cut_receipt_returns_requested_columns_in_order_with_unchanged_values() -> None:
    receipt = load_receipt(CUT_RECEIPT)
    fieldnames, rows = fixture_table()

    header, body = parse_tsv(receipt["stdout"])
    # The node was asked for gene,sample — a reorder, not the fixture order.
    assert header == ["gene", "sample"]
    assert header != fieldnames[:2]

    expected = [[row["gene"], row["sample"]] for row in rows]
    assert body == expected
    assert len(body) == len(rows) == 5


def test_stats_receipt_reports_exact_row_count_and_statistics() -> None:
    receipt = load_receipt(STATS_RECEIPT)
    _, rows = fixture_table()

    header, body = parse_tsv(receipt["stdout"])
    assert len(body) == 1, "csvtk summary must emit exactly one result row"
    values = dict(zip(header, body[0], strict=True))

    # Exact row count, independently derived from the fixture.
    row_count = len(rows)
    assert row_count == 5
    assert float(values["length:count"]) == row_count
    assert float(values["gc:count"]) == row_count

    # Exact min/max/mean recomputed here from the fixture, never read back from csvtk.
    for column in ("length", "gc"):
        numbers = [float(row[column]) for row in rows]
        assert float(values[f"{column}:countn"]) == len(numbers)
        assert float(values[f"{column}:min"]) == min(numbers)
        assert float(values[f"{column}:max"]) == max(numbers)
        assert float(values[f"{column}:mean"]) == sum(numbers) / len(numbers)

    # Pin the concrete numbers the fixture was chosen to produce.
    assert values["length:min"] == "10.00"
    assert values["length:max"] == "50.00"
    assert values["length:mean"] == "30.00"
    assert values["gc:min"] == "40.00"
    assert values["gc:max"] == "60.00"
    assert values["gc:mean"] == "50.00"


def test_stats_receipt_argv_is_the_nodes_own_rendered_command() -> None:
    receipt = load_receipt(STATS_RECEIPT)
    argv = receipt["rendered_command"]
    assert argv[:2] == ["csvtk", "summary"]
    assert "-f" in argv
    assert argv[argv.index("-f") + 1] == (
        "length:count,length:countn,length:min,length:max,length:mean,"
        "gc:count,gc:countn,gc:min,gc:max,gc:mean"
    )
    assert argv[-1].endswith("mini_table.tsv")
