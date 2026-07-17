from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.build_node_migration_queue import (
    MigrationQueueError,
    build_queue,
    canonical_json_bytes,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "bionodulo/nodes/generated/baseline-ledger.json"
RULES_PATH = REPO_ROOT / "bionodulo/nodes/catalog/family-assignment-rules.json"


def samtools_rules() -> dict[str, object]:
    return {
        "schema_version": 1,
        "confirmed_families": [
            {
                "family_id": "samtools",
                "ownership": "external_tool",
                "node_id_prefix": "samtools_",
                "expected_count": 27,
                "exclusive_path": "bionodulo/nodes/catalog/tools/samtools",
                "fixture_prefix": "samtools",
                "cloud_job_label": "catalog-samtools",
                "r2_test_prefix": "catalog-tests/samtools",
                "upstream": {
                    "repository_url": "https://github.com/samtools/samtools",
                    "release_tag": "1.23.1",
                    "tag_object": "4ac78a7e9938dbef3c6f97d549758feceb0252db",
                    "commit": "6efb9b6da35224cf804921dedecf9fb8f411365d",
                    "documentation_url": "https://www.htslib.org/doc/samtools.html",
                },
            }
        ],
    }


def load_baseline() -> dict[str, object]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def load_rules() -> dict[str, object]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def test_queue_accounts_for_every_stable_id_once() -> None:
    queue = build_queue(load_baseline(), samtools_rules())
    assignments = queue["assignments"]

    assert isinstance(assignments, list)
    assert len(assignments) == 943
    assert len({item["node_id"] for item in assignments}) == 943
    assert queue["summary"]["stable_node_ids"] == 943
    assert queue["summary"]["quarantined"] == 943


def test_confirmed_samtools_lane_is_exclusive_but_still_quarantined() -> None:
    queue = build_queue(load_baseline(), samtools_rules())
    samtools = [item for item in queue["assignments"] if item["family_id"] == "samtools"]

    assert len(samtools) == 27
    assert {item["node_id"] for item in samtools} >= {
        "samtools_sort",
        "samtools_index",
        "samtools_flagstat",
        "samtools_view",
    }
    assert {item["assignment_status"] for item in samtools} == {"upstream_owner_confirmed"}
    assert {item["contract_status"] for item in samtools} == {"evidence_pending"}
    assert {item["disposition"] for item in samtools} == {"quarantined"}
    assert {item["exclusive_path"] for item in samtools} == {"bionodulo/nodes/catalog/tools/samtools"}
    assert {item["upstream"]["commit"] for item in samtools} == {"6efb9b6da35224cf804921dedecf9fb8f411365d"}


def test_unreviewed_nodes_remain_explicitly_provisional() -> None:
    queue = build_queue(load_baseline(), samtools_rules())
    unresolved = next(item for item in queue["assignments"] if item["node_id"] == "abricate")

    assert unresolved["family_id"] is None
    assert unresolved["ownership"] == "unresolved"
    assert unresolved["assignment_status"] == "family_review_pending"
    assert unresolved["assignment_basis"] == "legacy_source_module"
    assert unresolved["exclusive_path"].startswith("bionodulo/nodes/catalog/migration_lanes/")
    assert unresolved["upstream"] is None


def test_template_references_drive_priority_without_releasing_nodes() -> None:
    queue = build_queue(load_baseline(), samtools_rules())
    by_id = {item["node_id"]: item for item in queue["assignments"]}

    assert by_id["samtools_sort"]["priority"] == "template"
    assert by_id["samtools_sort"]["template_paths"]
    assert by_id["samtools_ampliconclip"]["priority"] == "catalog"
    assert by_id["samtools_ampliconclip"]["template_paths"] == []
    assert by_id["samtools_sort"]["disposition"] == "quarantined"


def test_rule_count_mismatch_is_fatal() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["expected_count"] = 28

    with pytest.raises(MigrationQueueError, match="samtools.*expected 28.*found 27"):
        build_queue(load_baseline(), rules)


def test_overlapping_confirmed_rules_are_fatal() -> None:
    rules = samtools_rules()
    duplicate = copy.deepcopy(rules["confirmed_families"][0])
    duplicate["family_id"] = "samtools_duplicate"
    duplicate["exclusive_path"] = "bionodulo/nodes/catalog/tools/samtools_duplicate"
    rules["confirmed_families"].append(duplicate)

    with pytest.raises(MigrationQueueError, match="assigned by multiple confirmed"):
        build_queue(load_baseline(), rules)


def test_queue_bytes_are_deterministic_and_digest_bound() -> None:
    baseline = load_baseline()
    first = build_queue(baseline, samtools_rules())
    second = build_queue(copy.deepcopy(baseline), copy.deepcopy(samtools_rules()))

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["queue_sha256"].startswith("sha256:")
    assert first["baseline_aggregate_sha256"] == baseline["aggregate_sha256"]


def test_repository_rules_build_the_reviewed_samtools_lane() -> None:
    queue = build_queue(load_baseline(), load_rules())

    assert queue["summary"]["confirmed_family_nodes"] == 27
    assert next(lane for lane in queue["lanes"] if lane["lane_id"] == "samtools")["node_ids"] == sorted(
        item["node_id"] for item in queue["assignments"] if item["family_id"] == "samtools"
    )


def test_confirmed_upstream_identity_is_closed_and_immutable() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["upstream"]["branch"] = "develop"

    with pytest.raises(MigrationQueueError, match="upstream.*unknown or missing"):
        build_queue(load_baseline(), rules)

    rules = samtools_rules()
    rules["confirmed_families"][0]["upstream"]["commit"] = "develop"
    with pytest.raises(MigrationQueueError, match="upstream commit.*40 lowercase"):
        build_queue(load_baseline(), rules)

    rules = samtools_rules()
    rules["confirmed_families"][0]["upstream"]["documentation_url"] = "http://www.htslib.org/doc/samtools.html"
    with pytest.raises(MigrationQueueError, match="documentation_url.*HTTPS"):
        build_queue(load_baseline(), rules)


def test_cli_writes_and_checks_exact_canonical_bytes(tmp_path: Path) -> None:
    output = tmp_path / "migration-queue.json"
    command = [
        sys.executable,
        "scripts/build_node_migration_queue.py",
        "--baseline",
        str(BASELINE_PATH),
        "--rules",
        str(RULES_PATH),
        "--output",
        str(output),
    ]

    written = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    checked = subprocess.run(
        [*command, "--check"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    expected = canonical_json_bytes(build_queue(load_baseline(), load_rules()))
    assert output.read_bytes() == expected
    assert "943 nodes queued" in written.stdout
    assert "916 pending family review" in checked.stdout
