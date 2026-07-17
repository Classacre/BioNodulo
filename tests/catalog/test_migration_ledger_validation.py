from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import scripts.build_catalog_ledger as catalog_ledger_builder
import scripts.node_migration_ledger_validation as migration_ledger_validation
from scripts.node_migration_ledger_validation import (
    MigrationQueueError,
    canonical_json_bytes,
    validate_baseline,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "bionodulo/nodes/generated/baseline-ledger.json"


def load_baseline() -> dict[str, Any]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def refresh_baseline_aggregate(baseline: dict[str, Any]) -> None:
    baseline.pop("aggregate_sha256", None)
    baseline["aggregate_sha256"] = hashlib.sha256(canonical_json_bytes(baseline)).hexdigest()


def refresh_current_snapshot_digests(baseline: dict[str, Any]) -> None:
    snapshot = baseline["current_snapshot"]
    snapshot["repair_map_sha256"] = hashlib.sha256(canonical_json_bytes(snapshot["repair_map"])).hexdigest()
    identity = dict(snapshot)
    identity.pop("snapshot_sha256", None)
    snapshot["snapshot_sha256"] = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()


def refresh_baseline_canonical_digests(baseline: dict[str, Any]) -> None:
    entries = baseline["entries"]
    baseline["digests"]["entries_sha256"] = hashlib.sha256(canonical_json_bytes(entries)).hexdigest()
    behavior_inventory = [
        {
            "ast_sha256": entry["behavior_source"]["ast_sha256"],
            "git_blob": entry["behavior_source"]["git_blob"],
            "line": entry["behavior_source"]["line"],
            "node_id": entry["node_id"],
            "path": entry["behavior_source"]["path"],
            "qualified_class": entry["behavior_source"]["qualified_class"],
            "raw_class_sha256": entry["behavior_source"]["raw_class_sha256"],
        }
        for entry in entries
    ]
    baseline["digests"]["behavior_inventory_sha256"] = hashlib.sha256(
        canonical_json_bytes(behavior_inventory)
    ).hexdigest()
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
    refresh_current_snapshot_digests(baseline)
    refresh_baseline_aggregate(baseline)


def nested_mapping(root: dict[str, Any], path: tuple[str | int, ...]) -> dict[str, Any]:
    current: object = root
    for segment in path:
        if isinstance(segment, int):
            assert isinstance(current, list)
            current = current[segment]
        else:
            assert isinstance(current, dict)
            current = current[segment]
    assert isinstance(current, dict)
    return current


def baseline_entry(baseline: dict[str, Any], node_id: str = "abricate") -> dict[str, Any]:
    return next(entry for entry in baseline["entries"] if entry["node_id"] == node_id)


def baseline_entry_with_references(baseline: dict[str, Any]) -> dict[str, Any]:
    return next(entry for entry in baseline["entries"] if len(entry["template_references"]) >= 2)


def test_modified_baseline_entry_with_stale_aggregate_is_fatal() -> None:
    baseline = load_baseline()
    samtools_sort = next(entry for entry in baseline["entries"] if entry["node_id"] == "samtools_sort")
    samtools_sort["node_id"] = "tampered_stable_id"

    with pytest.raises(MigrationQueueError, match="baseline aggregate_sha256 mismatch"):
        validate_baseline(baseline)


def test_fully_redigested_node_id_swap_is_rejected_by_authority_anchor() -> None:
    baseline = load_baseline()
    abricate = baseline_entry(baseline, "abricate")
    samtools_sort = baseline_entry(baseline, "samtools_sort")
    abricate["node_id"], samtools_sort["node_id"] = samtools_sort["node_id"], abricate["node_id"]
    baseline["entries"].sort(key=lambda entry: entry["node_id"])
    refresh_baseline_canonical_digests(baseline)

    with pytest.raises(MigrationQueueError, match="immutable baseline authority"):
        validate_baseline(baseline)


def test_missing_baseline_aggregate_is_rejected_before_rule_assignment() -> None:
    baseline = load_baseline()
    del baseline["aggregate_sha256"]
    with pytest.raises(MigrationQueueError, match="baseline aggregate_sha256 is missing"):
        validate_baseline(baseline)


@pytest.mark.parametrize(
    "aggregate_sha256",
    ["sha256:" + "a" * 64, "A" * 64, "not-a-digest"],
)
def test_malformed_baseline_aggregate_is_fatal(aggregate_sha256: str) -> None:
    baseline = load_baseline()
    baseline["aggregate_sha256"] = aggregate_sha256

    with pytest.raises(MigrationQueueError, match="baseline aggregate_sha256.*64 lowercase hexadecimal"):
        validate_baseline(baseline)


def test_baseline_ledger_top_level_shape_is_closed() -> None:
    baseline = load_baseline()
    baseline["unexpected"] = "ignored"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="baseline ledger.*unknown or missing fields"):
        validate_baseline(baseline)


@pytest.mark.parametrize("schema_version", [True, False, 1.0, "1", 2])
def test_baseline_schema_version_requires_exact_integer_one(schema_version: object) -> None:
    baseline = load_baseline()
    baseline["schema_version"] = schema_version
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="baseline schema_version.*exact integer 1"):
        validate_baseline(baseline)


def test_baseline_entries_require_canonical_node_id_order() -> None:
    baseline = load_baseline()
    baseline["entries"].reverse()
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="baseline entries.*canonical node_id order"):
        validate_baseline(baseline)


def test_baseline_entry_shape_is_closed() -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["unexpected"] = "ignored"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="baseline entry.*unknown or missing fields"):
        validate_baseline(baseline)


def test_baseline_entry_requires_current_source_without_legacy_fallback() -> None:
    baseline = load_baseline()
    del baseline_entry(baseline)["current_source"]
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="current_source.*object"):
        validate_baseline(baseline)


@pytest.mark.parametrize("current_source", [None, [], "legacy fallback"])
def test_baseline_entry_rejects_non_object_current_source(current_source: object) -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["current_source"] = current_source
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="current_source.*object"):
        validate_baseline(baseline)


def test_current_source_shape_is_closed() -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["current_source"]["unexpected"] = "ignored"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="current_source.*unknown or missing fields"):
        validate_baseline(baseline)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ast_sha256", "not-a-digest", "current_source ast_sha256"),
        ("raw_class_sha256", "not-a-digest", "current_source raw_class_sha256"),
        ("comparison_git_blob", "not-a-blob", "current_source comparison_git_blob"),
        ("path", "../source.py", "current_source path"),
        ("comparison_path", "../comparison.py", "current_source comparison_path"),
        ("module", "not a module", "current_source module"),
        ("module", "external.module", "current_source module"),
        ("qualified_class", "not a class", "current_source qualified_class"),
    ],
)
def test_current_source_fields_require_canonical_values(field: str, value: str, message: str) -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["current_source"][field] = value
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match=message):
        validate_baseline(baseline)


def test_current_source_qualified_class_must_belong_to_its_module() -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["current_source"]["qualified_class"] = "external.module.Node"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="current_source qualified_class.*module"):
        validate_baseline(baseline)


def test_baseline_node_id_requires_a_safe_stable_identifier() -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["node_id"] = "../unsafe"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="node_id.*safe stable identifier"):
        validate_baseline(baseline)


@pytest.mark.parametrize("reference", [None, "reference", []])
def test_template_references_reject_non_object_members(reference: object) -> None:
    baseline = load_baseline()
    baseline_entry_with_references(baseline)["template_references"].append(reference)
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="template reference.*object"):
        validate_baseline(baseline)


def test_template_reference_shape_is_closed() -> None:
    baseline = load_baseline()
    reference = baseline_entry_with_references(baseline)["template_references"][0]
    reference["unexpected"] = "ignored"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="template reference.*unknown or missing fields"):
        validate_baseline(baseline)


def test_template_reference_kind_must_match_its_source_namespace() -> None:
    baseline = load_baseline()
    reference = baseline_entry_with_references(baseline)["template_references"][0]
    assert reference["source_path"].startswith("templates/")
    reference["kind"] = "example"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="template reference.*kind.*source_path"):
        validate_baseline(baseline)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_path", "../template.json", "template reference.*source_path"),
        ("source_blob", "not-a-blob", "template reference.*source_blob"),
        ("kind", "unknown", "template reference.*kind"),
        ("instance_id", "bad instance", "template reference.*instance_id"),
        ("input_ports", "not-an-array", "template reference.*input_ports"),
        ("output_ports", ["../port"], "template reference.*output_ports"),
    ],
)
def test_template_reference_fields_require_canonical_values(field: str, value: object, message: str) -> None:
    baseline = load_baseline()
    reference = baseline_entry_with_references(baseline)["template_references"][0]
    reference[field] = value
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match=message):
        validate_baseline(baseline)


def test_template_references_require_canonical_order() -> None:
    baseline = load_baseline()
    baseline_entry_with_references(baseline)["template_references"].reverse()
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="template_references.*canonical order"):
        validate_baseline(baseline)


def test_template_references_must_be_unique() -> None:
    baseline = load_baseline()
    references = baseline_entry_with_references(baseline)["template_references"]
    references.append(copy.deepcopy(references[0]))
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="template_references.*unique"):
        validate_baseline(baseline)


def test_template_reference_ports_require_canonical_order() -> None:
    baseline = load_baseline()
    reference = next(
        reference
        for entry in baseline["entries"]
        for reference in entry["template_references"]
        if len(reference["input_ports"]) >= 2
    )
    reference["input_ports"].reverse()
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="template reference.*input_ports.*canonical"):
        validate_baseline(baseline)


@pytest.mark.parametrize("current_snapshot", [None, {}])
def test_baseline_requires_a_complete_current_snapshot(current_snapshot: object) -> None:
    baseline = load_baseline()
    baseline["current_snapshot"] = current_snapshot
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="current_snapshot.*object|current_snapshot.*unknown or missing"):
        validate_baseline(baseline)


@pytest.mark.parametrize("behavior_source", [None, {}])
def test_baseline_entries_require_complete_behavior_source(behavior_source: object) -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["behavior_source"] = behavior_source
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="behavior_source.*object|behavior_source.*unknown or missing"):
        validate_baseline(baseline)


def test_baseline_aliases_cannot_reference_themselves() -> None:
    baseline = load_baseline()
    entry = baseline_entry(baseline)
    entry["alias_of"] = entry["node_id"]
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="alias_of must not reference itself"):
        validate_baseline(baseline)


def test_semantic_candidates_must_reference_another_stable_id() -> None:
    baseline = load_baseline()
    entry = baseline_entry(baseline, "feature_counts")
    entry["semantic_candidates"] = ["unknown_candidate"]
    refresh_baseline_canonical_digests(baseline)

    with pytest.raises(MigrationQueueError, match="semantic_candidates references unknown node"):
        validate_baseline(baseline)


@pytest.mark.parametrize("source", ["entry", "current"])
def test_entry_and_current_qualified_classes_remain_coherent(source: str) -> None:
    baseline = load_baseline()
    entry = baseline_entry(baseline)
    if source == "entry":
        module = entry["behavior_source"]["module"]
        entry["qualified_class"] = f"{module}.WrongNode"
    else:
        module = entry["current_source"]["module"]
        entry["current_source"]["qualified_class"] = f"{module}.WrongNode"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="qualified_class.*must match"):
        validate_baseline(baseline)


def test_current_source_qualified_class_rejects_injected_namespace() -> None:
    baseline = load_baseline()
    entry = baseline_entry(baseline)
    current = entry["current_source"]
    comparison = entry["comparison_locations"][0]
    current["qualified_class"] = f"{current['module']}.Injected.{comparison['class_name']}"
    refresh_baseline_canonical_digests(baseline)

    with pytest.raises(
        MigrationQueueError,
        match="current_source qualified_class must match module and comparison class_name",
    ):
        validate_baseline(baseline)


@pytest.mark.parametrize(
    ("source_path", "source", "expected_qualified_class"),
    [
        (
            "bionodulo/nodes/builtin/nested.py",
            'class Outer:\n    class Inner:\n        NODE_ID = "nested"\n',
            "bionodulo.nodes.builtin.nested.Outer.Inner",
        ),
        (
            "bionodulo/nodes/builtin/package/__init__.py",
            'class PackageNode:\n    NODE_ID = "package_node"\n',
            "bionodulo.nodes.builtin.package.PackageNode",
        ),
    ],
)
def test_standalone_validator_accepts_emitter_source_identities(
    source_path: str,
    source: str,
    expected_qualified_class: str,
) -> None:
    module = catalog_ledger_builder._module_name(source_path)
    nodes, anomalies = catalog_ledger_builder.extract_nodes(
        source,
        module,
        source_path=source_path,
        git_blob="a" * 40,
    )
    record = nodes[0].as_dict()

    assert anomalies == ()
    assert record["qualified_class"] == expected_qualified_class
    assert migration_ledger_validation._validated_source_node(record, "emitter source") == record


def test_current_source_preserves_comparison_nested_qualified_name_suffix() -> None:
    entry = copy.deepcopy(baseline_entry(load_baseline()))
    comparison = entry["comparison_locations"][0]
    current = entry["current_source"]
    nested_suffix = f"Outer.{comparison['class_name']}"
    comparison["qualified_class"] = f"{comparison['module']}.{nested_suffix}"
    current["qualified_class"] = f"{current['module']}.{nested_suffix}"

    validated = migration_ledger_validation._validated_baseline_entry(entry, 0)

    assert validated["current_source"]["qualified_class"] == current["qualified_class"]


@pytest.mark.parametrize(
    ("module", "path"),
    [
        ("bionodulo.nodes.builtin.annotation", "bionodulo/nodes/builtin/annotation/__init__.py"),
        ("bionodulo.nodes.builtin", "bionodulo/nodes/builtin/__init__.py"),
    ],
)
def test_current_source_accepts_emitter_package_init_module_identity(module: str, path: str) -> None:
    entry = copy.deepcopy(baseline_entry(load_baseline()))
    comparison = entry["comparison_locations"][0]
    current = entry["current_source"]
    current["module"] = module
    current["path"] = path
    current["qualified_class"] = f"{current['module']}.{comparison['class_name']}"

    validated = migration_ledger_validation._validated_baseline_entry(entry, 0)

    assert validated["current_source"]["path"] == current["path"]


def test_current_source_path_must_match_its_module() -> None:
    baseline = load_baseline()
    baseline_entry(baseline)["current_source"]["path"] = "bionodulo/nodes/builtin/mismatched.py"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="current_source path must match module"):
        validate_baseline(baseline)


def test_baseline_anomaly_must_identify_a_builtin_python_source() -> None:
    baseline = load_baseline()
    baseline["anomalies"][0]["path"] = "external/feature_counts.py"
    baseline["anomalies"][0]["module"] = "external.feature_counts"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="anomaly.*builtin Python source"):
        validate_baseline(baseline)


@pytest.mark.parametrize(
    "path",
    [
        ("canonicalizer",),
        ("digests",),
        ("current_snapshot",),
        ("current_snapshot", "repair_map", 0),
        ("entries", 0, "behavior_source"),
        ("entries", 0, "origin"),
        ("entries", 0, "origin", "selected"),
        ("entries", 0, "rebuild"),
        ("anomalies", 0),
        ("origin_collisions", 0),
        ("refs",),
        ("summary",),
    ],
)
def test_baseline_nested_record_shapes_are_closed(path: tuple[str | int, ...]) -> None:
    baseline = load_baseline()
    nested_mapping(baseline, path)["unexpected"] = "ignored"
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="unknown or missing fields"):
        validate_baseline(baseline)


@pytest.mark.parametrize(
    ("path", "message"),
    [
        (("digests", "entries_sha256"), "entries_sha256 mismatch"),
        (("digests", "behavior_inventory_sha256"), "behavior_inventory_sha256 mismatch"),
        (("current_snapshot", "repair_map_sha256"), "repair_map_sha256 mismatch"),
        (("current_snapshot", "projected_inventory_sha256"), "projected_inventory_sha256 mismatch"),
        (("current_snapshot", "snapshot_sha256"), "snapshot_sha256 mismatch"),
    ],
)
def test_baseline_recomputes_authored_canonical_digests(
    path: tuple[str, str],
    message: str,
) -> None:
    baseline = load_baseline()
    parent = baseline[path[0]]
    assert isinstance(parent, dict)
    parent[path[1]] = "0" * 64
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match=message):
        validate_baseline(baseline)


def test_current_snapshot_repair_map_is_derived_from_current_sources() -> None:
    baseline = load_baseline()
    baseline["current_snapshot"]["repair_map"][0]["current_path"] = "bionodulo/nodes/builtin/flow_control/not_break.py"
    refresh_current_snapshot_digests(baseline)
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match="repair_map must match current source repairs"):
        validate_baseline(baseline)


def test_origin_selection_is_recomputed_from_canonical_priority() -> None:
    baseline = load_baseline()
    entry = next(item for item in baseline["entries"] if len(item["origin"]["declarations"]) > 1)
    replacement = next(
        declaration for declaration in entry["origin"]["declarations"] if declaration != entry["origin"]["selected"]
    )
    entry["origin"]["selected"] = copy.deepcopy(replacement)
    refresh_baseline_canonical_digests(baseline)

    with pytest.raises(MigrationQueueError, match="selected source must match canonical origin priority"):
        validate_baseline(baseline)


@pytest.mark.parametrize("field", sorted(load_baseline()["summary"]))
def test_baseline_summary_is_recomputed_from_canonical_evidence(field: str) -> None:
    baseline = load_baseline()
    baseline["summary"][field] += 1
    refresh_baseline_aggregate(baseline)

    with pytest.raises(MigrationQueueError, match=rf"summary {field} mismatch"):
        validate_baseline(baseline)


def test_standalone_ledger_policy_matches_dependency_free_emitter() -> None:
    assert canonical_json_bytes({"policy": ["ascii", 1]}) == catalog_ledger_builder.canonical_json_bytes(
        {"policy": ["ascii", 1]}
    )
    assert migration_ledger_validation.EXPECTED_ALIAS_COUNT == catalog_ledger_builder.EXPECTED_ALIAS_COUNT
    assert migration_ledger_validation.EXPECTED_TEMPLATE_COUNT == catalog_ledger_builder.EXPECTED_TEMPLATE_COUNT
    assert migration_ledger_validation.EXPECTED_EXAMPLE_COUNT == catalog_ledger_builder.EXPECTED_EXAMPLE_COUNT
    assert migration_ledger_validation.EXPECTED_TEMPLATE_INSTANCES == catalog_ledger_builder.EXPECTED_TEMPLATE_INSTANCES
    assert migration_ledger_validation.EXPECTED_TEMPLATE_EDGES == catalog_ledger_builder.EXPECTED_TEMPLATE_EDGES
    assert migration_ledger_validation.FORENSIC_RAW_AST_DIGEST == catalog_ledger_builder.FORENSIC_RAW_AST_DIGEST
    behavior = catalog_ledger_builder.SourceNode(
        node_id="alpha",
        module="bionodulo.nodes.builtin.alpha",
        class_name="AlphaNode",
        qualified_name="AlphaNode",
        qualified_class="bionodulo.nodes.builtin.alpha.AlphaNode",
        line=1,
        node_id_line=2,
        raw_class_sha256="a" * 64,
        ast_sha256="b" * 64,
        base_symbols=(),
        metadata_only=False,
        source_path="bionodulo/nodes/builtin/alpha.py",
        git_blob="c" * 40,
    )
    origin = catalog_ledger_builder.SourceNode(
        **{
            **behavior.__dict__,
            "provenance": "native",
            "blame_commit": "d" * 40,
        }
    )
    current = catalog_ledger_builder.CurrentSourceEvidence(
        node_id="alpha",
        module="bionodulo.nodes.builtin.alpha",
        qualified_class="bionodulo.nodes.builtin.alpha.AlphaNode",
        source_path="bionodulo/nodes/builtin/alpha.py",
        raw_class_sha256="a" * 64,
        ast_sha256="b" * 64,
        comparison_path="bionodulo/nodes/builtin/alpha.py",
        comparison_git_blob="c" * 40,
    )
    repair = catalog_ledger_builder.CurrentRepair(
        node_id="alpha",
        comparison_path="bionodulo/nodes/builtin/alpha.py",
        current_path="bionodulo/nodes/builtin/alpha_.py",
    )
    snapshot = catalog_ledger_builder.CurrentSnapshot(
        kind="forensic_path_import_repair_projection",
        base_ref="e" * 40,
        base_builtin_tree="f" * 40,
        repairs=(repair,),
        repair_map_sha256="1" * 64,
        projected_inventory_sha256="2" * 64,
        limitations=migration_ledger_validation.CURRENT_SNAPSHOT_LIMITATIONS,
        snapshot_sha256="3" * 64,
    )
    reference = catalog_ledger_builder.TemplateReference(
        source_path="templates/alpha.json",
        source_blob="4" * 40,
        kind="template",
        instance_id="alpha_1",
        input_ports=("input",),
        output_ports=("output",),
    )
    entry = catalog_ledger_builder.LedgerEntry(
        node_id="alpha",
        behavior=behavior,
        origin=origin,
        origin_declarations=(origin,),
        split_locations=(behavior,),
        comparison_locations=(behavior,),
        current=current,
        template_references=(reference,),
    )
    collision = catalog_ledger_builder.OriginCollision(node_id="alpha", declarations=(origin,))

    assert frozenset(behavior.as_dict()) == migration_ledger_validation.SOURCE_NODE_FIELDS
    assert frozenset(origin.as_dict()) == migration_ledger_validation.ORIGIN_SOURCE_NODE_FIELDS
    assert frozenset(current.as_dict()) == migration_ledger_validation.CURRENT_SOURCE_FIELDS
    assert frozenset(repair.as_dict()) == migration_ledger_validation.CURRENT_REPAIR_FIELDS
    assert frozenset(snapshot.as_dict()) == migration_ledger_validation.CURRENT_SNAPSHOT_FIELDS
    assert frozenset(reference.as_dict()) == migration_ledger_validation.TEMPLATE_REFERENCE_FIELDS
    assert frozenset(entry.as_dict()) == migration_ledger_validation.BASELINE_ENTRY_FIELDS
    assert frozenset(entry.as_dict()["origin"]) == migration_ledger_validation.ORIGIN_FIELDS
    assert frozenset(entry.as_dict()["rebuild"]) == migration_ledger_validation.REBUILD_FIELDS
    assert frozenset(collision.as_dict()) == migration_ledger_validation.ORIGIN_COLLISION_FIELDS
