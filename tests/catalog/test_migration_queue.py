from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.contract.environments import (
    _HOST_RE as CONTRACT_HOST_RE,
    _validate_https_url as validate_contract_https_url,
)
from bionodulo.nodes.contract.model import MACHINE_ID_PATTERN, NodeOwnership
import scripts.build_node_migration_queue as migration_queue_builder
import scripts.node_migration_ledger_validation as migration_ledger_validation
from scripts.build_node_migration_queue import (
    MigrationQueueError,
    build_queue,
    canonical_json_bytes,
    write_or_check,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "bionodulo/nodes/generated/baseline-ledger.json"
RULES_PATH = REPO_ROOT / "bionodulo/nodes/catalog/family-assignment-rules.json"
AVAILABLE_PYTHONS = tuple(
    dict.fromkeys(
        executable
        for executable in (
            sys.executable,
            shutil.which("python3.11"),
            shutil.which("python3.12"),
            shutil.which("python3.13"),
        )
        if executable is not None
    )
)
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
                "source_module": "bionodulo.nodes.builtin.samtools.samtools",
                "source_path": "bionodulo/nodes/builtin/samtools/samtools.py",
                "exclusive_path": "bionodulo/nodes/catalog/tools/samtools",
                "fixture_prefix": "samtools/",
                "cloud_job_label": "catalog-samtools",
                "r2_test_prefix": "catalog-tests/samtools/",
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


def refresh_current_source_digests(baseline: dict[str, Any]) -> None:
    entries = baseline["entries"]
    baseline["digests"]["entries_sha256"] = hashlib.sha256(canonical_json_bytes(entries)).hexdigest()
    current_inventory = [
        {
            "ast_sha256": entry["current_source"]["ast_sha256"],
            "module": entry["current_source"]["module"],
            "node_id": entry["node_id"],
            "path": entry["current_source"]["path"],
            "qualified_class": entry["current_source"]["qualified_class"],
            "raw_class_sha256": entry["current_source"]["raw_class_sha256"],
        }
        for entry in entries
    ]
    snapshot = baseline["current_snapshot"]
    snapshot["projected_inventory_sha256"] = hashlib.sha256(canonical_json_bytes(current_inventory)).hexdigest()
    snapshot["repair_map"] = [
        {
            "comparison_path": entry["current_source"]["comparison_path"],
            "current_path": entry["current_source"]["path"],
            "node_id": entry["node_id"],
        }
        for entry in entries
        if entry["current_source"]["path"] != entry["current_source"]["comparison_path"]
    ]
    snapshot["repair_map_sha256"] = hashlib.sha256(canonical_json_bytes(snapshot["repair_map"])).hexdigest()
    snapshot_identity = dict(snapshot)
    snapshot_identity.pop("snapshot_sha256", None)
    snapshot["snapshot_sha256"] = hashlib.sha256(canonical_json_bytes(snapshot_identity)).hexdigest()
    refresh_baseline_aggregate(baseline)


def replace_current_source_identity(baseline: dict[str, Any], node_id: str, donor_node_id: str) -> None:
    entries = {entry["node_id"]: entry for entry in baseline["entries"]}
    current = entries[node_id]["current_source"]
    donor = entries[donor_node_id]["current_source"]
    old_module = current["module"]
    qualified_name = current["qualified_class"][len(old_module) + 1 :]
    current["module"] = donor["module"]
    current["path"] = donor["path"]
    current["qualified_class"] = f"{donor['module']}.{qualified_name}"
    refresh_current_source_digests(baseline)


def rules_with_second_family() -> tuple[dict[str, Any], dict[str, Any]]:
    rules = samtools_rules()
    family = copy.deepcopy(rules["confirmed_families"][0])
    family.update(
        {
            "family_id": "samtools_secondary",
            "exclusive_path": "bionodulo/nodes/catalog/tools/samtools_secondary",
            "fixture_prefix": "bcftools/",
            "cloud_job_label": "catalog-samtools-secondary",
            "r2_test_prefix": "catalog-tests/bcftools/",
        }
    )
    rules["confirmed_families"].append(family)
    return rules, family


def rules_with_family_count(count: int) -> dict[str, Any]:
    family_template = samtools_rules()["confirmed_families"][0]
    families: list[dict[str, Any]] = []
    for index in range(count):
        family = copy.deepcopy(family_template)
        family.update(
            {
                "cloud_job_label": f"family-{index}",
                "exclusive_path": f"bionodulo/nodes/catalog/tools/family_{index}",
                "expected_count": 1,
                "family_id": f"family_{index}",
                "fixture_prefix": f"family_{index}/",
                "node_id_prefix": f"family{index}_",
                "r2_test_prefix": f"catalog-tests/family_{index}/",
            }
        )
        families.append(family)
    return {"schema_version": 1, "confirmed_families": families}


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


def test_assignment_rules_accept_at_most_one_family_per_stable_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(migration_queue_builder, "_validate_scope_collisions", lambda _scopes: None)

    families = migration_queue_builder._validated_rules(rules_with_family_count(943))

    assert len(families) == 943


def test_assignment_rules_reject_oversized_family_array_before_collision_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_collision_validation(_scopes: object) -> None:
        raise AssertionError("oversized rules reached pairwise collision validation")

    monkeypatch.setattr(migration_queue_builder, "_validate_scope_collisions", unexpected_collision_validation)

    with pytest.raises(MigrationQueueError, match="confirmed_families.*at most 943"):
        migration_queue_builder._validated_rules(rules_with_family_count(944))


@pytest.mark.parametrize("expected_count", [True, False, 1.0, 0, -1, 944])
def test_expected_count_requires_a_bounded_exact_integer(expected_count: object) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["expected_count"] = expected_count

    with pytest.raises(MigrationQueueError, match="expected_count.*exact integer between 1 and 943"):
        build_queue(load_baseline(), rules)


def test_confirmed_family_rejects_matching_node_from_another_current_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = load_baseline()
    replace_current_source_identity(baseline, "samtools_sort", "abricate")
    monkeypatch.setattr(
        migration_ledger_validation,
        "EXPECTED_BASELINE_AGGREGATE_SHA256",
        baseline["aggregate_sha256"],
    )
    rules = samtools_rules()
    families = tuple(rules["confirmed_families"])
    monkeypatch.setattr(migration_queue_builder, "_validated_rules", lambda _rules: families)

    with pytest.raises(
        MigrationQueueError,
        match=r"confirmed family samtools source mismatch for node samtools_sort",
    ):
        build_queue(baseline, rules)


@pytest.mark.parametrize("field", ["source_module", "source_path"])
def test_confirmed_family_rule_requires_exact_source_identity_fields(field: str) -> None:
    rules = samtools_rules()
    del rules["confirmed_families"][0][field]

    with pytest.raises(MigrationQueueError, match=r"confirmed_families\[0\].*unknown or missing fields"):
        build_queue(load_baseline(), rules)


def test_confirmed_family_source_identity_schema_is_closed() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["source_qualified_classes"] = ["SamtoolsSortNode"]

    with pytest.raises(MigrationQueueError, match=r"confirmed_families\[0\].*unknown or missing fields"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    "source_module",
    [
        "bionodulo/nodes/builtin/samtools/samtools",
        ".bionodulo.nodes.builtin.samtools.samtools",
        "bionodulo.nodes..builtin.samtools.samtools",
        "bionodulo.nodes.builtin.sam-tools.samtools",
        "bionodulo.nodes.builtin.samtools.samtoolsé",
    ],
)
def test_confirmed_family_source_module_requires_canonical_ascii_python_identity(source_module: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["source_module"] = source_module

    with pytest.raises(MigrationQueueError, match="source_module.*canonical ASCII Python module"):
        build_queue(load_baseline(), rules)


def test_confirmed_family_source_module_is_length_bounded() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["source_module"] = "a" * 1025

    with pytest.raises(MigrationQueueError, match="source_module.*1024 ASCII characters"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    "source_path",
    [
        "/bionodulo/nodes/builtin/samtools/samtools.py",
        "bionodulo/nodes/builtin/../samtools/samtools.py",
        "bionodulo/nodes/builtin/samtools\\samtools.py",
        "bionodulo/nodes/builtin/samtools/samtoolsé.py",
        "bionodulo/nodes/catalog/samtools/samtools.py",
        "bionodulo/nodes/builtin/samtools/samtools.pyi",
    ],
)
def test_confirmed_family_source_path_requires_canonical_builtin_python_identity(source_path: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["source_path"] = source_path

    with pytest.raises(
        MigrationQueueError,
        match="source_path.*canonical repository-relative builtin Python path",
    ):
        build_queue(load_baseline(), rules)


def test_confirmed_family_source_path_is_length_bounded() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["source_path"] = "bionodulo/nodes/builtin/" + "a" * 1024 + ".py"

    with pytest.raises(MigrationQueueError, match="source_path.*1024 ASCII characters"):
        build_queue(load_baseline(), rules)


def test_confirmed_family_source_module_must_be_derived_from_source_path() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["source_module"] = "bionodulo.nodes.builtin.annotation.abricate"

    with pytest.raises(MigrationQueueError, match="source_module.*derived from source_path"):
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
    ("field", "value"),
    [
        ("exclusive_path", "bionodulo/nodes/catalog/tools/" + "a" * 1024),
        ("fixture_prefix", "a" * 1024 + "/"),
        ("r2_test_prefix", "catalog-tests/" + "a" * 1024 + "/"),
    ],
)
def test_confirmed_scope_paths_and_namespaces_are_length_bounded(field: str, value: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0][field] = value

    with pytest.raises(MigrationQueueError, match=rf"{field}.*1024"):
        build_queue(load_baseline(), rules)


def test_fixture_and_r2_namespaces_require_explicit_trailing_delimiters() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["fixture_prefix"] = "samtools"
    rules["confirmed_families"][0]["r2_test_prefix"] = "catalog-tests/samtools"

    with pytest.raises(MigrationQueueError, match="fixture_prefix.*ending in /"):
        build_queue(load_baseline(), rules)

    rules["confirmed_families"][0]["fixture_prefix"] = "samtools/"
    with pytest.raises(MigrationQueueError, match="r2_test_prefix.*ending in /"):
        build_queue(load_baseline(), rules)


def test_slash_delimited_sibling_namespaces_are_disjoint() -> None:
    rules, family = rules_with_second_family()
    rules["confirmed_families"][0]["fixture_prefix"] = "samtools/"
    family["fixture_prefix"] = "samtools_extra/"
    rules["confirmed_families"][0]["r2_test_prefix"] = "catalog-tests/samtools/"
    family["r2_test_prefix"] = "catalog-tests/samtools_extra/"

    with pytest.raises(MigrationQueueError, match="assigned by multiple confirmed"):
        build_queue(load_baseline(), rules)


def test_slash_delimited_nested_namespaces_overlap() -> None:
    rules, family = rules_with_second_family()
    rules["confirmed_families"][0]["fixture_prefix"] = "samtools/"
    family["fixture_prefix"] = "samtools/subfamily/"
    rules["confirmed_families"][0]["r2_test_prefix"] = "catalog-tests/samtools/"
    family["r2_test_prefix"] = "catalog-tests/bcftools/"

    with pytest.raises(MigrationQueueError, match="fixture_prefix"):
        build_queue(load_baseline(), rules)


def test_every_lane_namespace_is_self_delimiting_and_literal_prefix_safe() -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["fixture_prefix"] = "samtools/"
    rules["confirmed_families"][0]["r2_test_prefix"] = "catalog-tests/samtools/"
    queue = build_queue(load_baseline(), rules)

    for field in ("fixture_prefix", "r2_test_prefix"):
        values = [lane["agent_scope"][field] for lane in queue["lanes"]]
        assert all(value.endswith("/") for value in values)
        assert not any(
            left.startswith(right) or right.startswith(left)
            for index, left in enumerate(values)
            for right in values[index + 1 :]
        )


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


@pytest.mark.parametrize("fixture_prefix", ["samtools/", "samtools/subfamily/"])
def test_duplicate_or_nested_confirmed_fixture_prefixes_are_fatal(fixture_prefix: str) -> None:
    rules, family = rules_with_second_family()
    family["fixture_prefix"] = fixture_prefix

    with pytest.raises(MigrationQueueError, match="fixture_prefix"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    ("first_prefix", "second_prefix"),
    [("samtools/", "samtools/subfamily/"), ("samtools/subfamily/", "samtools/")],
)
def test_confirmed_fixture_namespaces_reject_literal_prefixes_in_either_direction(
    first_prefix: str,
    second_prefix: str,
) -> None:
    rules, family = rules_with_second_family()
    rules["confirmed_families"][0]["fixture_prefix"] = first_prefix
    family["fixture_prefix"] = second_prefix

    with pytest.raises(MigrationQueueError, match="fixture_prefix"):
        build_queue(load_baseline(), rules)


def test_duplicate_confirmed_cloud_job_labels_are_fatal() -> None:
    rules, family = rules_with_second_family()
    family["cloud_job_label"] = "catalog-samtools"

    with pytest.raises(MigrationQueueError, match="cloud_job_label"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize("r2_test_prefix", ["catalog-tests/samtools/", "catalog-tests/samtools/subfamily/"])
def test_duplicate_or_nested_confirmed_r2_prefixes_are_fatal(r2_test_prefix: str) -> None:
    rules, family = rules_with_second_family()
    family["r2_test_prefix"] = r2_test_prefix

    with pytest.raises(MigrationQueueError, match="r2_test_prefix"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    ("first_prefix", "second_prefix"),
    [
        ("catalog-tests/samtools/", "catalog-tests/samtools/subfamily/"),
        ("catalog-tests/samtools/subfamily/", "catalog-tests/samtools/"),
    ],
)
def test_confirmed_r2_namespaces_reject_literal_prefixes_in_either_direction(
    first_prefix: str,
    second_prefix: str,
) -> None:
    rules, family = rules_with_second_family()
    rules["confirmed_families"][0]["r2_test_prefix"] = first_prefix
    family["r2_test_prefix"] = second_prefix
    family["fixture_prefix"] = "bcftools/"

    with pytest.raises(MigrationQueueError, match="r2_test_prefix"):
        build_queue(load_baseline(), rules)


@pytest.mark.parametrize(
    ("field", "provisional_value"),
    [
        ("exclusive_path", "bionodulo/nodes/catalog/migration_lanes/legacy_annotation_abricate"),
        ("fixture_prefix", "legacy_annotation_abricate/"),
        ("cloud_job_label", "catalog-legacy_annotation_abricate"),
        ("r2_test_prefix", "catalog-tests/legacy_annotation_abricate/"),
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
        "fixture_prefix": "samtools/",
        "r2_test_prefix": "catalog-tests/samtools/",
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
    values = [scope["exclusive_path"] for scope in complete_scopes]
    assert not any(
        scope_values_overlap(left, right) for index, left in enumerate(values) for right in values[index + 1 :]
    )
    for field in ("fixture_prefix", "r2_test_prefix"):
        values = [scope[field] for scope in complete_scopes]
        assert not any(
            left.startswith(right) or right.startswith(left)
            for index, left in enumerate(values)
            for right in values[index + 1 :]
        )


def test_colliding_legacy_module_slugs_get_distinct_deterministic_scopes() -> None:
    modules = {
        "bionodulo.nodes.builtin.collision.foo.bar",
        "bionodulo.nodes.builtin.collision.foo_bar",
    }
    first = migration_queue_builder._legacy_lanes(modules)
    second = migration_queue_builder._legacy_lanes(modules)
    lane_ids = list(first.values())

    assert first == second
    assert len(set(lane_ids)) == 2
    assert len({f"bionodulo/nodes/catalog/migration_lanes/{lane_id}" for lane_id in lane_ids}) == 2
    for prefixes in (
        [f"{lane_id}/" for lane_id in lane_ids],
        [f"catalog-tests/{lane_id}/" for lane_id in lane_ids],
    ):
        assert not (prefixes[0].startswith(prefixes[1]) or prefixes[1].startswith(prefixes[0]))


def test_queue_bytes_are_deterministic_and_digest_bound() -> None:
    baseline = load_baseline()
    rules = samtools_rules()
    first = build_queue(baseline, rules)
    second = build_queue(copy.deepcopy(baseline), copy.deepcopy(rules))
    queue_preimage = dict(first)
    queue_sha256 = queue_preimage.pop("queue_sha256")
    baseline_preimage = dict(baseline)
    baseline_sha256 = baseline_preimage.pop("aggregate_sha256")

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert queue_sha256 == "sha256:" + hashlib.sha256(canonical_json_bytes(queue_preimage)).hexdigest()
    assert first["rules_sha256"] == "sha256:" + hashlib.sha256(canonical_json_bytes(rules)).hexdigest()
    assert baseline_sha256 == hashlib.sha256(canonical_json_bytes(baseline_preimage)).hexdigest()
    assert first["baseline_aggregate_sha256"] == baseline_sha256


def test_canonical_queue_serialization_is_bounded_to_eight_mib() -> None:
    with pytest.raises(MigrationQueueError, match="canonical JSON exceeds 8388608 bytes"):
        canonical_json_bytes({"payload": "x" * (8 * 1024 * 1024)})


def test_queue_digest_streams_without_materializing_canonical_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_materialization(_value: object) -> bytes:
        raise AssertionError("queue digest materialized canonical JSON")

    monkeypatch.setattr(migration_queue_builder, "canonical_json_bytes", unexpected_materialization)

    assert migration_queue_builder._sha256({"value": 1}) == ("sha256:" + hashlib.sha256(b'{"value":1}\n').hexdigest())


def test_standalone_ownership_values_match_node_contract() -> None:
    assert migration_queue_builder._NODE_OWNERSHIP_VALUES == frozenset(owner.value for owner in NodeOwnership)


def test_standalone_machine_prefix_grammar_matches_node_contract() -> None:
    expected_pattern = MACHINE_ID_PATTERN.removesuffix("$") + r"_$"

    assert migration_queue_builder._NODE_ID_PREFIX_RE.pattern == expected_pattern


def test_standalone_hostname_and_url_policies_match_environment_contract() -> None:
    assert migration_queue_builder._HOST_RE.pattern == CONTRACT_HOST_RE.pattern
    canonical_urls = (
        "https://repo.example.org/owner/project",
        "https://repo.example.org:8443/owner/project",
        "https://repo.example.org/owner/project/",
    )
    for url in (*INVALID_UPSTREAM_URLS, *canonical_urls):
        try:
            expected = validate_contract_https_url(url, require_path=True)
        except ValueError:
            with pytest.raises(MigrationQueueError):
                migration_queue_builder._https_url(url, "upstream repository_url")
        else:
            assert migration_queue_builder._https_url(url, "upstream repository_url") == expected


def test_atomic_replace_failure_preserves_existing_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "migration-queue.json"
    output.write_bytes(b"existing artifact\n")

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(MigrationQueueError, match="cannot atomically write migration queue"):
        write_or_check(output, b"replacement artifact\n", check=False)

    assert output.read_bytes() == b"existing artifact\n"
    assert sorted(tmp_path.iterdir()) == [output]


def test_atomic_write_failure_preserves_existing_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "migration-queue.json"
    output.write_bytes(b"existing artifact\n")

    def fail_fsync(_descriptor: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(MigrationQueueError, match="cannot atomically write migration queue"):
        write_or_check(output, b"replacement artifact\n", check=False)

    assert output.read_bytes() == b"existing artifact\n"
    assert sorted(tmp_path.iterdir()) == [output]


def test_atomic_write_fsyncs_file_then_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synced_modes: list[int] = []

    def record_fsync(file_descriptor: int) -> None:
        synced_modes.append(os.fstat(file_descriptor).st_mode)

    monkeypatch.setattr(os, "fsync", record_fsync)

    write_or_check(tmp_path / "migration-queue.json", b"new\n", check=False)

    assert len(synced_modes) == 2
    assert stat.S_ISREG(synced_modes[0])
    assert stat.S_ISDIR(synced_modes[1])


def test_directory_fsync_failure_is_normalized_after_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "migration-queue.json"
    output.write_bytes(b"existing artifact\n")

    def fail_directory_fsync(file_descriptor: int) -> None:
        if stat.S_ISDIR(os.fstat(file_descriptor).st_mode):
            raise OSError("directory fsync failed")

    monkeypatch.setattr(os, "fsync", fail_directory_fsync)

    with pytest.raises(MigrationQueueError, match="cannot atomically write migration queue"):
        write_or_check(output, b"replacement artifact\n", check=False)

    assert output.read_bytes() == b"replacement artifact\n"
    assert sorted(tmp_path.iterdir()) == [output]


def test_write_rejects_unbounded_queue_payload(tmp_path: Path) -> None:
    output = tmp_path / "migration-queue.json"

    with pytest.raises(MigrationQueueError, match="migration queue payload exceeds"):
        write_or_check(output, b"x" * (8 * 1024 * 1024 + 1), check=False)

    assert not output.exists()


def test_check_mode_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "migration-queue.json"
    payload = b"canonical queue\n"
    output.write_bytes(payload)

    def unexpected_mutation(*_arguments: object) -> None:
        raise AssertionError("check mode attempted to mutate output")

    monkeypatch.setattr(os, "replace", unexpected_mutation)
    monkeypatch.setattr(os, "fsync", unexpected_mutation)

    write_or_check(output, payload, check=True)

    assert output.read_bytes() == payload


def test_check_mode_rejects_existing_artifact_larger_than_eight_mib(tmp_path: Path) -> None:
    output = tmp_path / "migration-queue.json"
    output.write_bytes(b"x" * (8 * 1024 * 1024 + 1))

    with pytest.raises(MigrationQueueError, match="existing migration queue exceeds 8388608 bytes"):
        write_or_check(output, b"canonical queue\n", check=True)


def test_read_json_rejects_input_larger_than_eight_mib(tmp_path: Path) -> None:
    source = tmp_path / "oversized.json"
    source.write_bytes(b" " * (8 * 1024 * 1024 + 1))

    with pytest.raises(MigrationQueueError, match=r"exceeds 8388608 bytes"):
        migration_queue_builder._read_json(source)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b'\xef\xbb\xbf{"schema_version":1}\n', "UTF-8 BOM"),
        (b'{"schema_version":"\xff"}\n', "valid UTF-8"),
    ],
)
def test_read_json_rejects_noncanonical_utf8(payload: bytes, message: str, tmp_path: Path) -> None:
    source = tmp_path / "invalid-utf8.json"
    source.write_bytes(payload)

    with pytest.raises(MigrationQueueError, match=message):
        migration_queue_builder._read_json(source)


@pytest.mark.parametrize("unsafe_key", ["__proto__", "prototype", "constructor"])
def test_read_json_rejects_recursive_unsafe_object_members(unsafe_key: str, tmp_path: Path) -> None:
    source = tmp_path / "unsafe-key.json"
    source.write_bytes(canonical_json_bytes({"outer": [{unsafe_key: {"value": 1}}]}))

    with pytest.raises(MigrationQueueError, match=rf"unsafe JSON object member {unsafe_key!r}"):
        migration_queue_builder._read_json(source)


def nested_array_json(depth: int) -> bytes:
    return b"[" * depth + b"0" + b"]" * depth


def test_read_json_accepts_json_at_depth_limit(tmp_path: Path) -> None:
    source = tmp_path / "depth-64.json"
    source.write_bytes(nested_array_json(64))

    assert migration_queue_builder._read_json(source) is not None


def test_read_json_rejects_json_beyond_depth_limit(tmp_path: Path) -> None:
    source = tmp_path / "depth-65.json"
    source.write_bytes(nested_array_json(65))

    with pytest.raises(MigrationQueueError, match=r"nesting depth exceeds 64"):
        migration_queue_builder._read_json(source)


@pytest.mark.parametrize(
    ("decoder_error", "message"),
    [
        (RecursionError("decoder recursion"), "JSON decoder recursion limit"),
        (ValueError("decoder value limit"), "cannot read canonical JSON"),
    ],
)
def test_read_json_normalizes_decoder_errors(
    decoder_error: Exception,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "decoder-recursion.json"
    source.write_bytes(b"{}\n")

    def fail_decode(*_arguments: object, **_keywords: object) -> object:
        raise decoder_error

    monkeypatch.setattr(json, "loads", fail_decode)

    with pytest.raises(MigrationQueueError, match=message):
        migration_queue_builder._read_json(source)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("oversized", "exceeds 8388608 bytes"),
        ("bom", "UTF-8 BOM"),
        ("malformed_utf8", "valid UTF-8"),
        ("duplicate", "duplicate JSON object member"),
        ("unsafe_key", "unsafe JSON object member"),
        ("depth", "nesting depth exceeds 64"),
    ],
)
def test_cli_rejects_hostile_json_without_traceback_or_output_mutation(
    case: str,
    message: str,
    tmp_path: Path,
) -> None:
    rules = tmp_path / "hostile-rules.json"
    output = tmp_path / "migration-queue.json"
    output.write_bytes(b"existing artifact\n")
    payloads = {
        "oversized": b" " * (8 * 1024 * 1024 + 1),
        "bom": b'\xef\xbb\xbf{"schema_version":1,"confirmed_families":[]}\n',
        "malformed_utf8": b'{"schema_version":"\xff","confirmed_families":[]}\n',
        "duplicate": b'{"schema_version":1,"schema_version":1,"confirmed_families":[]}\n',
        "unsafe_key": b'{"schema_version":1,"confirmed_families":[],"nested":{"constructor":{}}}\n',
        "depth": nested_array_json(65),
    }
    rules.write_bytes(payloads[case])

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

    assert result.returncode != 0
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert output.read_bytes() == b"existing artifact\n"


def test_cli_rejects_internally_inconsistent_baseline_without_output_mutation(tmp_path: Path) -> None:
    baseline = load_baseline()
    baseline["digests"]["entries_sha256"] = "0" * 64
    refresh_baseline_aggregate(baseline)
    baseline_path = tmp_path / "invalid-baseline.json"
    baseline_path.write_bytes(canonical_json_bytes(baseline))
    output = tmp_path / "migration-queue.json"
    output.write_bytes(b"existing artifact\n")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_node_migration_queue.py",
            "--baseline",
            str(baseline_path),
            "--rules",
            str(RULES_PATH),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "entries_sha256 mismatch" in result.stderr
    assert "Traceback" not in result.stderr
    assert output.read_bytes() == b"existing artifact\n"


def test_repository_rules_build_the_reviewed_external_tool_lanes() -> None:
    queue = build_queue(load_baseline(), load_rules())

    assert queue["summary"]["confirmed_family_nodes"] == 47
    by_family = {
        family_id: sorted(item["node_id"] for item in queue["assignments"] if item["family_id"] == family_id)
        for family_id in ("bismark", "bowtie2", "hisat2", "kallisto", "macs2", "odgi", "salmon", "samtools")
    }
    assert by_family["bismark"] == [
        "bismark_align",
        "bismark_genome_preparation",
        "bismark_methylation",
        "bismark_methylation_extractor",
    ]
    assert by_family["bowtie2"] == ["bowtie2_align", "bowtie2_build", "bowtie2_inspect"]
    assert by_family["hisat2"] == ["hisat2_align", "hisat2_build"]
    assert by_family["kallisto"] == ["kallisto_index", "kallisto_quant"]
    assert by_family["macs2"] == ["macs2_bdgpeak", "macs2_callpeak"]
    assert by_family["odgi"] == ["odgi_build", "odgi_stats", "odgi_view", "odgi_visualize", "odgi_viz"]
    assert by_family["salmon"] == ["salmon_index", "salmon_quant"]
    assert next(lane for lane in queue["lanes"] if lane["lane_id"] == "samtools")["node_ids"] == sorted(
        by_family["samtools"]
    )
    assert {
        family_id: {item["upstream"]["commit"] for item in queue["assignments"] if item["family_id"] == family_id}
        for family_id in ("bismark", "bowtie2", "hisat2", "kallisto", "macs2", "odgi", "salmon")
    } == {
        "bismark": {"e552b8f307a7041bcebed8f8e5a764ebcf7b046c"},
        "bowtie2": {"0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2"},
        "hisat2": {"99583d7536b9ee017ac07de8834017a3bf99a2fe"},
        "kallisto": {"4e9f29cf3b021260415430c057a22469ca081391"},
        "macs2": {"1afcae6a09ced8cf9bb1e87c44dd58f7d7e4891c"},
        "odgi": {"be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6"},
        "salmon": {"d53fed6f0af6966a40825558f0edf71b6df7cf52"},
    }


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


@pytest.mark.parametrize("field", ["repository_url", "documentation_url"])
def test_confirmed_upstream_urls_are_length_bounded(field: str) -> None:
    rules = samtools_rules()
    rules["confirmed_families"][0]["upstream"][field] = "https://repo.example.org/" + "a" * 2048

    with pytest.raises(MigrationQueueError, match=rf"{field}.*2048"):
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
    assert "896 pending family review" in checked.stdout


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


@pytest.mark.parametrize("python_executable", AVAILABLE_PYTHONS)
def test_standalone_cli_checks_with_available_supported_python(python_executable: str) -> None:
    result = subprocess.run(
        [python_executable, "scripts/build_node_migration_queue.py", "--check"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert "943 nodes queued" in result.stdout


@pytest.mark.parametrize(
    "invocation",
    [
        ["scripts/build_node_migration_queue.py"],
        ["-m", "scripts.build_node_migration_queue"],
    ],
)
def test_cli_supports_direct_script_and_package_invocation(invocation: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, *invocation, "--check"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert "943 nodes queued" in result.stdout
