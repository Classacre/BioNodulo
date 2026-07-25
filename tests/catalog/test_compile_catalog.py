from __future__ import annotations

import hashlib
import importlib
import json
from typing import Any

import pytest

from scripts.compile_catalog import (
    BASELINE_LEDGER,
    BASELINE_NODE_COUNT,
    CatalogBuildError,
    expected_documents,
    main,
)

# A node whose legacy execution factory is a stable, low-churn builtin module.
SAMPLE_NODE_ID = "Add_a_column1"
SAMPLE_MODULE = "bionodulo.nodes.builtin.data_transform_family.column_maker"


def _operational(documents: dict[Any, bytes]) -> dict[str, Any]:
    path = next(path for path in documents if path.name == "catalog.operational.json")
    return json.loads(documents[path])


def _lock(documents: dict[Any, bytes]) -> dict[str, Any]:
    path = next(path for path in documents if path.name == "catalog.lock.json")
    return json.loads(documents[path])


def test_first_wave_projections_are_deterministic_and_cover_seven_nodes() -> None:
    first = expected_documents()
    second = expected_documents()
    assert first == second

    promotion_path = next(path for path in first if path.name == "catalog.promotion.json")
    promotion = json.loads(first[promotion_path])
    assert promotion["summary"] == {
        "all_nodes_released": False,
        "baseline_nodes": BASELINE_NODE_COUNT,
        "implemented_nodes": 7,
        "promotion_status": "promotion_candidate",
        "remaining_nodes": 936,
        "status_counts": {"promotion_candidate": 7},
    }
    assert promotion["status"] == "promotion_candidate"
    assert promotion["availability_status"] == "active"
    assert promotion["operational_summary"]["operational_nodes"] == BASELINE_NODE_COUNT
    assert promotion["operational_summary"]["remaining_operational_nodes"] == 0
    assert len(promotion["nodes"]) == 7
    assert {node["status"] for node in promotion["nodes"]} == {"promotion_candidate"}
    assert all(node["contract_digest"].startswith("sha256:") for node in promotion["nodes"])

    operational_path = next(path for path in first if path.name == "catalog.operational.json")
    operational = json.loads(first[operational_path])
    assert operational["summary"] == {
        "active_nodes": BASELINE_NODE_COUNT,
        "all_nodes_active": True,
        "all_nodes_released": False,
        "availability_counts": {"active": BASELINE_NODE_COUNT, "blocked": 0},
        "baseline_nodes": BASELINE_NODE_COUNT,
        "blocked_nodes": 0,
        "evidence_pending_nodes": 936,
        "importability_verified": True,
        "legacy_compatible_nodes": BASELINE_NODE_COUNT,
        "operational_nodes": BASELINE_NODE_COUNT,
        "released_typed_nodes": 0,
        "remaining_operational_nodes": 0,
        "remaining_typed_contract_nodes": 936,
        "typed_contract_nodes": 7,
        "typed_status_counts": {"promotion_candidate": 7},
        "verification_status_counts": {
            "evidence_pending": 936,
            "promotion_candidate": 7,
        },
    }
    assert len(operational["nodes"]) == BASELINE_NODE_COUNT


def test_cli_check_does_not_change_forensic_baseline() -> None:
    before = BASELINE_LEDGER.read_bytes()
    before_digest = hashlib.sha256(before).hexdigest()
    assert main(["--check"]) == 0
    after = BASELINE_LEDGER.read_bytes()
    assert hashlib.sha256(after).hexdigest() == before_digest
    assert after == before


def test_every_operational_node_is_proven_importable() -> None:
    """``availability`` is a proof, not an assertion.

    The legacy lane is projected from the AST-derived baseline ledger, which
    knows nothing about whether a module actually imports.  Compiling must
    resolve every ``execution_factory`` so a node that cannot be instantiated
    is never advertised as active.
    """
    operational = _operational(expected_documents())
    summary = operational["summary"]

    assert summary["availability_counts"] == {"active": BASELINE_NODE_COUNT, "blocked": 0}
    assert summary["blocked_nodes"] == 0
    assert summary["all_nodes_active"] is True
    assert {entry["availability"] for entry in operational["nodes"].values()} == {"active"}
    assert not any("blocked_reason" in entry for entry in operational["nodes"].values())


def test_lock_records_the_importability_proof() -> None:
    lock = _lock(expected_documents())
    assert lock["operational"]["importability_verified"] is True
    assert lock["operational"]["availability_counts"] == {"active": BASELINE_NODE_COUNT, "blocked": 0}


def test_unimportable_module_is_blocked_not_active() -> None:
    """The historical ghost-node failure: the module itself raises on import."""

    def importer(module_name: str) -> Any:
        if module_name == SAMPLE_MODULE:
            raise ImportError("synthetic module failure")
        return importlib.import_module(module_name)

    operational = _operational(expected_documents(legacy_importer=importer))
    entry = operational["nodes"][SAMPLE_NODE_ID]

    assert entry["availability"] == "blocked"
    assert "synthetic module failure" in entry["blocked_reason"]

    summary = operational["summary"]
    assert summary["availability_counts"] == {"active": BASELINE_NODE_COUNT - 1, "blocked": 1}
    assert summary["blocked_nodes"] == 1
    assert summary["legacy_compatible_nodes"] == BASELINE_NODE_COUNT - 1
    assert summary["all_nodes_active"] is False
    # Total membership is unchanged — a blocked node is still catalogued.
    assert summary["operational_nodes"] == BASELINE_NODE_COUNT
    assert len(operational["nodes"]) == BASELINE_NODE_COUNT


def test_missing_class_symbol_is_blocked_not_active() -> None:
    """The sibling-reference failure: module imports but the class is absent."""

    class _EmptyModule:
        pass

    def importer(module_name: str) -> Any:
        if module_name == SAMPLE_MODULE:
            return _EmptyModule()
        return importlib.import_module(module_name)

    operational = _operational(expected_documents(legacy_importer=importer))
    entry = operational["nodes"][SAMPLE_NODE_ID]

    assert entry["availability"] == "blocked"
    assert "ColumnMakerNode" in entry["blocked_reason"]
    assert operational["summary"]["blocked_nodes"] == 1


def test_blocked_nodes_change_the_operational_digest() -> None:
    """A blocked node must not hash identically to an active one."""

    def importer(module_name: str) -> Any:
        if module_name == SAMPLE_MODULE:
            raise ImportError("synthetic module failure")
        return importlib.import_module(module_name)

    healthy = _operational(expected_documents())
    degraded = _operational(expected_documents(legacy_importer=importer))
    assert healthy["catalog_digest"] != degraded["catalog_digest"]


def test_lock_marks_importability_unverified_when_a_node_is_blocked() -> None:
    def importer(module_name: str) -> Any:
        if module_name == SAMPLE_MODULE:
            raise ImportError("synthetic module failure")
        return importlib.import_module(module_name)

    lock = _lock(expected_documents(legacy_importer=importer))
    assert lock["operational"]["importability_verified"] is False


def test_blocked_reason_does_not_leak_build_host_paths() -> None:
    """catalog.operational.json ships to clients; a traceback must not carry
    the build machine's directory layout into it."""

    def importer(module_name: str) -> Any:
        if module_name == SAMPLE_MODULE:
            raise ImportError(
                "cannot open /home/buildbot/secrets/creds.pem while loading "
                "/opt/hostedtoolcache/python/site-packages/thing.py"
            )
        return importlib.import_module(module_name)

    operational = _operational(expected_documents(legacy_importer=importer))
    reason = operational["nodes"][SAMPLE_NODE_ID]["blocked_reason"]

    assert "/home/buildbot" not in reason
    assert "/opt/hostedtoolcache" not in reason
    assert "ImportError" in reason
    assert len(reason) <= 300


def test_importer_returning_a_non_module_is_a_build_error() -> None:
    """Guard the guard: a silently wrong importer must not pass as healthy."""

    def importer(module_name: str) -> Any:
        return None

    with pytest.raises(CatalogBuildError):
        expected_documents(legacy_importer=importer)
