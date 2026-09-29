"""Independent oracle for the htslib bgzip/tabix nodes.

Two layers, both asserted here:

1. **Contract tests** (always run, no container needed) — the node's own
   ``render_command``, fail-closed ``VALIDATE_INPUTS``, and the
   ``PLAN_OUTPUTS``/``PREPARE_EXECUTION`` path contract that makes the command
   write exactly the files it promises.

2. **Receipt oracle** (skipped when the receipt is absent) — asserts real
   content, never exit status alone. Independence matters: the obvious way to
   check bgzip/tabix output is to ask bgzip/tabix, but that lets the tool mark
   its own homework. Instead this module uses only the Python standard library:
   BGZF is a valid multi-member gzip stream, so ``gzip`` decompresses it; the
   ``.tbi`` magic is read from the decompressed index; and the region query is
   checked against the exact VCF records the fixture contains.

Fixture: ``mini.vcf`` has four data lines on two contigs. ``chr1:100-200`` must
return the records at chr1:100 and chr1:150 and exclude chr1:300 and chr2:120.

Skips when a receipt is absent, which is different from passing.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "nodes" / "htslib_tabix_family" / "fixtures"
RECEIPTS = REPO_ROOT / "reports" / "run-receipts"

EXPECTED_IMAGE = "quay.io/biocontainers/tabix:0.2.5--ha92aebf_2"
EXPECTED_DIGEST = "sha256:6af2484cb77ae4ee86e51b3e9a0e84f3d0242b11980cbbc7bfd5be250180d9b8"

FIXTURE_VCF = FIXTURES / "mini.vcf"
FIXTURE_GZ = FIXTURES / "mini.vcf.gz"

INCLUDED_RECORDS = [
    "chr1\t100\t.\tA\tT\t50\tPASS\t.",
    "chr1\t150\t.\tG\tC\t60\tPASS\t.",
]
EXCLUDED_RECORDS = [
    "chr1\t300\t.\tT\tA\t40\tPASS\t.",
    "chr2\t120\t.\tC\tG\t70\tPASS\t.",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _receipt(name: str) -> dict | None:
    path = RECEIPTS / name / "receipt.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_bytes(receipt: dict, receipt_name: str, relative: str) -> bytes:
    """Read one recorded artifact and cross-check it against its receipt hash."""
    recorded = next(a for a in receipt["artifacts"] if a["path"] == relative)
    path = RECEIPTS / receipt_name / relative
    assert path.is_file(), relative
    assert path.stat().st_size == recorded["bytes"]
    assert _sha256(path) == recorded["sha256"]
    return path.read_bytes()


def _all_receipts_present() -> bool:
    return all(
        (RECEIPTS / name / "receipt.json").is_file()
        for name in (
            "htslib-bgzip-compress",
            "htslib-bgzip-decompress",
            "htslib-tabix-index",
            "htslib-tabix-query",
        )
    )


# ── Contract tests (always run) ──────────────────────────────────────────


def test_node_contract_attributes_are_complete() -> None:
    from bionodulo.nodes.builtin.htslib_tabix_family import (
        BgzipCompressNode,
        BgzipDecompressNode,
        TabixIndexNode,
        TabixQueryNode,
    )

    expected = {
        BgzipCompressNode: ("bgzip_compress", ("bgzip", "-f")),
        BgzipDecompressNode: ("bgzip_decompress", ("bgzip", "-d", "-f")),
        TabixIndexNode: ("tabix_index", ("tabix", "-p")),
        TabixQueryNode: ("tabix_query", ("tabix",)),
    }
    for cls, (node_id, prefix) in expected.items():
        assert cls.NODE_ID == node_id
        assert cls.DISPLAY_NAME and cls.DESCRIPTION and cls.SEARCH_ALIASES
        assert cls.CATEGORY
        assert cls.RETURN_TYPES and cls.RETURN_NAMES
        assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES)
        assert cls.OUTPUT_FILENAMES and len(cls.OUTPUT_FILENAMES) == len(cls.RETURN_TYPES)
        assert cls.REQUIRED_EXECUTABLES == ["bgzip", "tabix"]
        assert cls.REQUIRED_CONDA_PACKAGES == ["tabix"]
        assert cls.VERSION == "0.2.5"
        assert cls.DOCUMENTATION_URL.startswith("https://www.htslib.org/")
        # render_command must lead with the tool and its operation flags
        inputs = {
            "output": "/out",
            "file": "/in/x.vcf",
            "compressed": "/in/x.vcf.gz",
            "bgzf": "/in/x.vcf.gz",
            "region": "chr1:100-200",
            "preset": "vcf",
        }
        argv = cls.render_command(inputs)
        assert tuple(argv[: len(prefix)]) == prefix, (node_id, argv)
        it = cls.INPUT_TYPES()
        assert set(it) >= {"required", "optional", "hidden"}
        assert "output" in it["hidden"]


def test_validate_inputs_is_fail_closed_on_missing_and_empty_paths() -> None:
    from bionodulo.nodes.builtin.htslib_tabix_family import (
        BgzipCompressNode,
        BgzipDecompressNode,
        TabixIndexNode,
        TabixQueryNode,
    )

    # Every node rejects an empty input set and an empty/blank primary path.
    for cls, key in (
        (BgzipCompressNode, "file"),
        (BgzipDecompressNode, "compressed"),
        (TabixIndexNode, "bgzf"),
        (TabixQueryNode, "bgzf"),
    ):
        assert cls.VALIDATE_INPUTS({}) is not True
        assert cls.VALIDATE_INPUTS({key: ""}) is not True
        assert cls.VALIDATE_INPUTS({key: "   "}) is not True
        assert cls.VALIDATE_INPUTS({key: None}) is not True

    # bgzip_compress refuses an already-compressed input (would double-suffix).
    assert BgzipCompressNode.VALIDATE_INPUTS({"file": "/in/x.vcf.gz"}) is not True
    assert BgzipCompressNode.VALIDATE_INPUTS({"file": "/in/x.vcf"}) is True
    # bgzip_decompress and tabix nodes require a compressed suffix.
    assert BgzipDecompressNode.VALIDATE_INPUTS({"compressed": "/in/x.vcf"}) is not True
    assert BgzipDecompressNode.VALIDATE_INPUTS({"compressed": "/in/x.vcf.gz"}) is True
    assert TabixIndexNode.VALIDATE_INPUTS({"bgzf": "/in/x.vcf"}) is not True
    assert TabixIndexNode.VALIDATE_INPUTS({"bgzf": "/in/x.vcf.gz"}) is True
    assert TabixIndexNode.VALIDATE_INPUTS({"bgzf": "/in/x.vcf.gz", "preset": "sam"}) is not True


def test_tabix_query_region_validation_rejects_nonsense() -> None:
    from bionodulo.nodes.builtin.htslib_tabix_family import TabixQueryNode

    ok = TabixQueryNode.VALIDATE_INPUTS
    base = {"bgzf": "/in/x.vcf.gz"}
    for region in ("chr1", "chr1:100", "chr1:100-200", "chr1:100-", "chr1:-200"):
        assert ok({**base, "region": region}) is True, region
    for region in ("", "   ", "chr1 100", "chr1; rm -rf /", "chr1:abc", "chr1:100-200-300"):
        assert ok({**base, "region": region}) is not True, region
    # print_header must be a boolean
    assert ok({**base, "region": "chr1:1-2", "print_header": "yes"}) is not True


def test_knowledge_uses_a_real_biotools_accession_and_validated_labels() -> None:
    from bionodulo.nodes.builtin.htslib_tabix_family import BgzipCompressNode
    from bionodulo.nodes.knowledge import validate_knowledge

    knowledge = validate_knowledge(BgzipCompressNode.KNOWLEDGE, node_id="bgzip_compress")
    assert knowledge["tool_id"] == "https://bio.tools/tabix"
    labels = {entry["label"] for entry in knowledge["topics"]}
    labels |= {entry["label"] for entry in knowledge["operations"]}
    assert labels == {"Genomics", "Data handling", "Data retrieval"}
    assert knowledge["citation_evidence"][0]["identifier"] == "10.1093/bioinformatics/btq671"


def test_plan_outputs_and_staging_produce_exactly_the_rendered_target(tmp_path: Path) -> None:
    """PLAN_OUTPUTS must name the file the command actually writes."""
    from bionodulo.nodes.builtin.htslib_tabix_family import (
        BgzipCompressNode,
        BgzipDecompressNode,
        TabixIndexNode,
        TabixQueryNode,
    )

    cases = [
        (BgzipCompressNode, "file", FIXTURE_VCF, lambda s: [Path(f"{s}.gz")]),
        (BgzipDecompressNode, "compressed", FIXTURE_GZ, lambda s: [Path(str(s)[:-3])]),
        (TabixIndexNode, "bgzf", FIXTURE_GZ, lambda s: [Path(s), Path(f"{s}.tbi")]),
    ]
    for cls, key, fixture, produced_from_staged in cases:
        inputs = {"output": str(tmp_path), key: str(fixture), "preset": "vcf"}
        outputs = cls.PLAN_OUTPUTS(inputs, tmp_path)
        assert [p.name for p in outputs] == list(cls.OUTPUT_FILENAMES)
        cls.PREPARE_EXECUTION(inputs, outputs)
        staged = inputs[key]
        assert Path(staged).is_file(), f"{cls.NODE_ID} did not stage its input"
        argv = cls.render_command(inputs)
        assert str(staged) in argv, (cls.NODE_ID, argv)
        produced = produced_from_staged(staged)
        assert produced == outputs, (cls.NODE_ID, produced, outputs)

    # tabix_query captures stdout, so its planned output is STDOUT_OUTPUT_INDEX.
    assert TabixQueryNode.STDOUT_OUTPUT_INDEX == 0
    query_inputs = {"output": str(tmp_path), "bgzf": str(FIXTURE_GZ), "region": "chr1:100-200"}
    query_outputs = TabixQueryNode.PLAN_OUTPUTS(query_inputs, tmp_path)
    assert [p.name for p in query_outputs] == list(TabixQueryNode.OUTPUT_FILENAMES)
    argv = TabixQueryNode.render_command(query_inputs)
    assert argv == ["tabix", str(FIXTURE_GZ), "chr1:100-200"]
    # -h is opt-in only
    assert TabixQueryNode.render_command({**query_inputs, "print_header": True})[1] == "-h"


def test_fixtures_are_self_consistent() -> None:
    """The committed .gz must decompress to the committed .vcf; the .tbi is BGZF."""
    assert gzip.decompress(FIXTURE_GZ.read_bytes()) == FIXTURE_VCF.read_bytes()
    tbi = gzip.decompress((FIXTURES / "mini.vcf.gz.tbi").read_bytes())
    assert tbi[:4] == b"TBI\x01"


# ── Receipt oracle (skipped without receipts) ────────────────────────────


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_receipts_record_successful_digest_pinned_runs() -> None:
    for name, node_id in (
        ("htslib-bgzip-compress", "bgzip_compress"),
        ("htslib-bgzip-decompress", "bgzip_decompress"),
        ("htslib-tabix-index", "tabix_index"),
        ("htslib-tabix-query", "tabix_query"),
    ):
        receipt = _receipt(name)
        assert receipt is not None
        assert receipt["node_id"] == node_id
        assert receipt["status"] == "completed", (node_id, receipt["stderr"][:300])
        assert receipt["exit_code"] == 0
        assert receipt["execution"]["kind"] == "digest_pinned_container"
        assert receipt["execution"]["image"] == EXPECTED_IMAGE
        assert receipt["execution"]["image_digest_expected"] == EXPECTED_DIGEST
        assert (
            receipt["execution"]["image_digest_observed_after_run"]
            == f"{EXPECTED_IMAGE.split(':')[0]}@{EXPECTED_DIGEST}"
        )
        assert receipt["execution"]["digest_stable"] is True
        assert receipt["execution"]["network"] == "none"


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_rendered_command_is_the_nodes_own_argv() -> None:
    from bionodulo.nodes.builtin.htslib_tabix_family import (
        BgzipCompressNode,
        BgzipDecompressNode,
        TabixIndexNode,
        TabixQueryNode,
    )

    cases = (
        ("htslib-bgzip-compress", BgzipCompressNode, ("bgzip", "-f")),
        ("htslib-bgzip-decompress", BgzipDecompressNode, ("bgzip", "-d", "-f")),
        ("htslib-tabix-index", TabixIndexNode, ("tabix", "-p", "vcf", "-f")),
        ("htslib-tabix-query", TabixQueryNode, ("tabix",)),
    )
    for name, cls, prefix in cases:
        receipt = _receipt(name)
        assert tuple(receipt["rendered_command"][: len(prefix)]) == prefix
        # The host renders Windows separators; that difference must be recorded.
        if any("\\" in argument for argument in receipt["rendered_command_as_rendered_on_this_host"]):
            assert receipt["platform_path_rewrites"]


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_bgzip_compress_output_round_trips_byte_identically() -> None:
    receipt = _receipt("htslib-bgzip-compress")
    raw = _artifact_bytes(receipt, "htslib-bgzip-compress", "work/mini.vcf.gz")
    # BGZF is a valid multi-member gzip stream; stdlib gzip decompresses it.
    assert gzip.decompress(raw) == FIXTURE_VCF.read_bytes()
    # And it is byte-identical to the committed, independently produced fixture.
    assert raw == FIXTURE_GZ.read_bytes()


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_bgzip_decompress_output_is_the_original_text() -> None:
    receipt = _receipt("htslib-bgzip-decompress")
    raw = _artifact_bytes(receipt, "htslib-bgzip-decompress", "work/mini.vcf")
    assert raw == FIXTURE_VCF.read_bytes()


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_tabix_index_artifact_starts_with_the_tbi_magic() -> None:
    receipt = _receipt("htslib-tabix-index")
    gz = _artifact_bytes(receipt, "htslib-tabix-index", "work/mini.vcf.gz")
    assert gz == FIXTURE_GZ.read_bytes()
    tbi = _artifact_bytes(receipt, "htslib-tabix-index", "work/mini.vcf.gz.tbi")
    # The .tbi is itself BGZF-compressed; its payload starts with the TBI magic.
    assert tbi[:2] == b"\x1f\x8b", "index is not a BGZF stream"
    payload = gzip.decompress(tbi)
    assert payload[:4] == b"TBI\x01"
    assert len(payload) > 4


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_tabix_query_returns_exactly_the_records_in_the_region() -> None:
    receipt = _receipt("htslib-tabix-query")
    lines = [line for line in receipt["stdout"].splitlines() if line]
    assert lines == INCLUDED_RECORDS, lines
    for excluded in EXCLUDED_RECORDS:
        assert excluded not in lines
    # The query ran against the bgzipped fixture with its colocated index.
    paths = {a["path"] for a in receipt["artifacts"]}
    assert {"work/mini.vcf.gz", "work/mini.vcf.gz.tbi"} <= paths


@pytest.mark.skipif(not _all_receipts_present(), reason="pinned-container receipts not present")
def test_every_recorded_artifact_hash_matches_disk() -> None:
    for name in (
        "htslib-bgzip-compress",
        "htslib-bgzip-decompress",
        "htslib-tabix-index",
        "htslib-tabix-query",
    ):
        receipt = _receipt(name)
        assert receipt["artifact_count"] >= 1, name
        for artifact in receipt["artifacts"]:
            path = RECEIPTS / name / artifact["path"]
            assert path.is_file(), artifact["path"]
            assert path.stat().st_size == artifact["bytes"], artifact["path"]
            assert _sha256(path) == artifact["sha256"], artifact["path"]
