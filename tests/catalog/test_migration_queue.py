from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.contract.model import NodeOwnership
from scripts.build_node_migration_queue import (
    MigrationQueueError,
    build_queue,
    canonical_json_bytes,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "bionodulo/nodes/generated/baseline-ledger.json"
RULES_PATH = REPO_ROOT / "bionodulo/nodes/catalog/family-assignment-rules.json"
INVALID_UPSTREAM_URLS = (
    "http://repo.example.org/owner/project",
    "HTTPS://repo.example.org/owner/project",
    "https://repo.example.org:notaport/owner/project",
    "https://repo.example.org:0/owner/project",
    "https://repo.example.org:65536/owner/project",
    "https://repo.example.org:443/owner/project",
    "https://repo.example.org:08443/owner/project",
    "https://REPO.example.org/owner/project",
    "https://repo.example.org./owner/project",
    "https://user@repo.example.org/owner/project",
    "https://user:secret@repo.example.org/owner/project",
    "https://repo.example.org/%6fwner/project",
    "https://repo.example.org/owner/project?version=1",
    "https://repo.example.org/owner/project?",
    "https://repo.example.org/owner/project#section",
    "https://repo.example.org/owner/project#",
    "https://repo.example.org/owner//project",
    "https://repo.example.org/owner/./project",
    "https://repo.example.org/owner/../project",
    "https://repo.example.org",
    "https://repo.example.org/",
    "https://repo.example.org/owner\\project",
    "https://repo.example.org/owner project",
    "https://repo.example.org/owner/project\n",
    "https://repo.example.org:/owner/project",
)


def samtools_rules() -> dict[str, Any]:
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


def load_baseline() -> dict[str, Any]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def load_rules() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def refresh_baseline_aggregate(baseline: dict[str, Any]) -> None:
    baseline.pop("aggregate_sha256", None)
    baseline["aggregate_sha256"] = hashlib.sha256(canonical_json_bytes(baseline)).hexdigest()


def rules_with_second_family() -> tuple[dict[str, Any], dict[str, Any]]:
    rules = samtools_rules()
    family = copy.deepcopy(rules["confirmed_families"][0])
    family.update(
        {
            "family_id": "samtools_secondary",
            "exclusive_path": "bionodulo/nodes/catalog/tools/samtools_secondary",
            "fixture_prefix": "samtools_secondary",
            "cloud_job_label": "catalog-samtools-secondary",
            "r2_test_prefix": "catalog-tests/samtools_secondary",
        }
    )
    rules["confirmed_families"].append(family)
    return rules, family


def scope_from_lane(lane: dict[str, object]) -> dict[str, str] | None:
    agent_scope = lane.get("agent_scope")
    exclusive_path = lane.get("exclusive_path")
    if not isinstance(agent_scope, dict) or not isinstance(exclusive_path, str):
        return None
    return {"exclusive_path": exclusive_path, **agent_scope}


def scope_values_overlap(left: str, right: str) -> bool:
    left_parts = left.split("/")
    right_parts = right.split("/")
    shared = min(len(left_parts), len(right_parts))
    return left_parts[:shared] == right_parts[:shared]


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


@pytest.mark.parametrize("schema_version", [True, False, 1.0, "1", "schema-v1"])
def test_assignment_rules_schema_version_requires_exact_integer_one(schema_version: object) -> None:
    rules = samtools_rules()
    rules["schema_version"] = schema_version

    with pytest.raises(MigrationQueueError, match="schema_version.*exact integer 1"):
        build_queue(load_baseline(), rules)


def test_assignment_rules_schema_version_accepts_exact_integer_one() -> None:
    rules = samtools_rules()
    rules["schema_version"] = 1

    assert build_queue(load_baseline(), rules)["summary"]["stable_node_ids"] == 943


@pytest.mark.parametrize("expected_count", [True, False, 1.0, 0, -1, 944])
def test_expected_count_requires_a_bounded_exact_integer(expected_count: object) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["expected_count"] = expected_count

    with pytest.raises(MigrationQueueError, match="expected_count.*exact integer between 1 and 943"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize("ownership", [owner.value for owner in NodeOwnership])
def test_confirmed_family_accepts_every_node_ownership_wire_value(ownership: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["ownership"] = ownership

    queue = build_queue(load_baseline(), rules)
    confirmed = [item for item in queue["assignments"] if item["family_id"] == "samtools"]

    assert {item["ownership"] for item in confirmed} == {ownership}


@pytest.mark.parametrize(
    "ownership",
    [
        None,
        True,
        1,
        1.0,
        {},
        [],
        "unresolved",
        "arbitrary_owner",
    ],
)
def test_confirmed_family_rejects_values_outside_node_ownership(ownership: object) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["ownership"] = ownership

    with pytest.raises(MigrationQueueError, match="ownership.*NodeOwnership"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    "node_id_prefix",
    [
        "",
        "../samtools_",
        "sam tools_",
        "samtools*_",
        "Samtools_",
        "_samtools_",
        "samtools__",
        "samtools__tools_",
        "samtools",
        "samtools-_",
        "samtools/",
        "samtools_é_",
        "a" * 128 + "_",
    ],
)
def test_node_id_prefix_requires_a_canonical_bounded_machine_prefix(node_id_prefix: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["node_id_prefix"] = node_id_prefix

    with pytest.raises(MigrationQueueError, match="node_id_prefix.*canonical lowercase machine-ID prefix"):
        build_queue(load_baseline(), rules)


def test_node_id_prefix_accepts_a_canonical_family_prefix() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["node_id_prefix"] = "samtools_"

    assert build_queue(load_baseline(), rules)["summary"]["confirmed_family_nodes"] == 27


def test_overlapping_confirmed_rules_are_fatal() -> None:
    rules, _family = rules_with_second_family()

    with pytest.raises(MigrationQueueError, match="assigned by multiple confirmed"):
        build_queue(load_baseline(), rules)


def test_modified_baseline_entry_with_stale_aggregate_is_fatal() -> None:
    baseline = load_baseline()
    samtools_sort = next(entry for entry in baseline["entries"] if entry["node_id"] == "samtools_sort")
    samtools_sort["node_id"] = "tampered_stable_id"

    with pytest.raises(MigrationQueueError, match="baseline aggregate_sha256 mismatch"):
        build_queue(baseline, samtools_rules())


def test_missing_baseline_aggregate_is_rejected_before_rule_assignment() -> None:
    baseline = load_baseline()
    del baseline["aggregate_sha256"]
    rules = samtools_rules()
    rules["confirmed_families"][0]["expected_count"] = 28

    with pytest.raises(MigrationQueueError, match="baseline aggregate_sha256 is missing"):
        build_queue(baseline, rules)


@pytest.mark.parametrize(
    "aggregate_sha256",
    ["sha256:" + "a" * 64, "A" * 64, "not-a-digest"],
)
def test_malformed_baseline_aggregate_is_fatal(aggregate_sha256: str) -> None:
    baseline = load_baseline()
    baseline["aggregate_sha256"] = aggregate_sha256

    with pytest.raises(MigrationQueueError, match="baseline aggregate_sha256.*64 lowercase hexadecimal"):
        build_queue(baseline, samtools_rules())


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("exclusive_path", "elsewhere/samtools"),
        ("fixture_prefix", "../samtools"),
        ("cloud_job_label", "Catalog Samtools"),
        ("r2_test_prefix", "/catalog-tests/samtools"),
    ],
)
def test_confirmed_scope_values_require_canonical_syntax(field: str, invalid_value: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0][field] = invalid_value

    with pytest.raises(MigrationQueueError, match=field):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    "exclusive_path",
    [
        "bionodulo/nodes/catalog/tools/samtools",
        "bionodulo/nodes/catalog/tools/samtools/subfamily",
    ],
)
def test_duplicate_or_nested_confirmed_exclusive_paths_are_fatal(exclusive_path: str) -> None:
    rules, family = rules_with_second_family()
    family["exclusive_path"] = exclusive_path

    with pytest.raises(MigrationQueueError, match=r"exclusive[ _]path"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize("fixture_prefix", ["samtools", "samtools/subfamily"])
def test_duplicate_or_nested_confirmed_fixture_prefixes_are_fatal(fixture_prefix: str) -> None:
    rules, family = rules_with_second_family()
    family["fixture_prefix"] = fixture_prefix

    with pytest.raises(MigrationQueueError, match="fixture_prefix"):
        build_queue(load_baseline(), rules)


def test_duplicate_confirmed_cloud_job_labels_are_fatal() -> None:
    rules, family = rules_with_second_family()
    family["cloud_job_label"] = "catalog-samtools"

    with pytest.raises(MigrationQueueError, match="cloud_job_label"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize("r2_test_prefix", ["catalog-tests/samtools", "catalog-tests/samtools/subfamily"])
def test_duplicate_or_nested_confirmed_r2_prefixes_are_fatal(r2_test_prefix: str) -> None:
    rules, family = rules_with_second_family()
    family["r2_test_prefix"] = r2_test_prefix

    with pytest.raises(MigrationQueueError, match="r2_test_prefix"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    ("field", "provisional_value"),
    [
        ("exclusive_path", "bionodulo/nodes/catalog/migration_lanes/legacy_annotation_abricate"),
        ("fixture_prefix", "legacy_annotation_abricate"),
        ("cloud_job_label", "catalog-legacy_annotation_abricate"),
        ("r2_test_prefix", "catalog-tests/legacy_annotation_abricate"),
    ],
)
def test_confirmed_scopes_cannot_collide_with_provisional_lanes(field: str, provisional_value: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0][field] = provisional_value

    with pytest.raises(MigrationQueueError, match=field):
        build_queue(load_baseline(), rules)


def test_lane_records_emit_the_exact_four_dimensional_assignment_scope() -> None:
    queue = build_queue(load_baseline(), samtools_rules())
    assignment = next(item for item in queue["assignments"] if item["node_id"] == "samtools_sort")
    lane = next(item for item in queue["lanes"] if item["lane_id"] == "samtools")

    expected_scope = {
        "exclusive_path": "bionodulo/nodes/catalog/tools/samtools",
        "cloud_job_label": "catalog-samtools",
        "fixture_prefix": "samtools",
        "r2_test_prefix": "catalog-tests/samtools",
    }
    assert scope_from_lane(lane) == expected_scope
    assert {"exclusive_path": assignment["exclusive_path"], **assignment["agent_scope"]} == expected_scope


def test_provisional_lane_scopes_are_deterministic_unique_and_nonoverlapping() -> None:
    first = build_queue(load_baseline(), samtools_rules())
    second = build_queue(load_baseline(), samtools_rules())
    first_lanes = [lane for lane in first["lanes"] if lane["assignment_status"] == "family_review_pending"]
    second_by_id = {lane["lane_id"]: lane for lane in second["lanes"]}
    scopes = [scope_from_lane(lane) for lane in first_lanes]

    assert all(scope is not None for scope in scopes)
    assert scopes == [scope_from_lane(second_by_id[lane["lane_id"]]) for lane in first_lanes]
    complete_scopes = [scope for scope in scopes if scope is not None]
    for field in ("exclusive_path", "fixture_prefix", "cloud_job_label", "r2_test_prefix"):
        values = [scope[field] for scope in complete_scopes]
        assert len(values) == len(set(values))
    for field in ("exclusive_path", "fixture_prefix", "r2_test_prefix"):
        values = [scope[field] for scope in complete_scopes]
        assert not any(
            scope_values_overlap(left, right) for index, left in enumerate(values) for right in values[index + 1 :]
        )


def test_colliding_legacy_module_slugs_get_distinct_deterministic_scopes() -> None:
    baseline = load_baseline()
    entries = {entry["node_id"]: entry for entry in baseline["entries"]}
    entries["abricate"]["current_source"]["module"] = "bionodulo.nodes.builtin.collision.foo-bar"
    entries["abritamr"]["current_source"]["module"] = "bionodulo.nodes.builtin.collision.foo_bar"
    refresh_baseline_aggregate(baseline)

    queue = build_queue(baseline, samtools_rules())
    assignments = {item["node_id"]: item for item in queue["assignments"]}
    abricate = assignments["abricate"]
    abritamr = assignments["abritamr"]

    assert abricate["lane_id"] != abritamr["lane_id"]
    assert abricate["exclusive_path"] != abritamr["exclusive_path"]
    assert abricate["agent_scope"] != abritamr["agent_scope"]


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


@pytest.mark.parametrize("field", ["repository_url", "documentation_url"])
@pytest.mark.parametrize("url", INVALID_UPSTREAM_URLS)
def test_confirmed_upstream_urls_reject_noncanonical_https_spellings(field: str, url: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["upstream"][field] = url

    with pytest.raises(MigrationQueueError, match=rf"{field}.*canonical HTTPS"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize("field", ["repository_url", "documentation_url"])
def test_confirmed_upstream_urls_preserve_one_canonical_https_spelling(field: str) -> None:
    canonical = "https://repo.example.org:8443/owner/project"
    rules = samtools_rules()
    rules["confirmed_families"][0]["upstream"][field] = canonical

    queue = build_queue(load_baseline(), rules)
    assignment = next(item for item in queue["assignments"] if item["node_id"] == "samtools_sort")

    assert assignment["upstream"][field] == canonical


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


def test_cli_rejects_duplicate_json_object_members(tmp_path: Path) -> None:
    rules = tmp_path / "duplicate-rules.json"
    output = tmp_path / "migration-queue.json"
    rules.write_text(
        '{"schema_version":999,"schema_version":1,"confirmed_families":[]}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_node_migration_queue.py",
            "--baseline",
            str(BASELINE_PATH),
            "--rules",
            str(rules),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "duplicate JSON object member 'schema_version'" in result.stderr
    assert not output.exists()
