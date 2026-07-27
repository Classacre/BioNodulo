from __future__ import annotations

import json
from pathlib import Path

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.catalog.registry import CatalogRegistry, QuarantinedNodeError
from scripts.compile_catalog import (
    EXPECTED_NODE_COUNT,
    POST_BASELINE_NODE_IDS,
    expected_documents,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _operational_document() -> dict[str, object]:
    documents = expected_documents()
    path = next(path for path in documents if path.name == "catalog.operational.json")
    return json.loads(documents[path])


def test_operational_catalog_matches_every_focused_legacy_owner() -> None:
    document = _operational_document()
    nodes = document["nodes"]
    legacy_index = json.loads((REPO_ROOT / "bionodulo/nodes/node_index.json").read_text())
    legacy_metadata = json.loads((REPO_ROOT / "bionodulo/nodes/node_metadata.json").read_text())
    baseline = json.loads((REPO_ROOT / "bionodulo/nodes/generated/baseline-ledger.json").read_text())
    baseline_ids = {entry["node_id"] for entry in baseline["entries"]}

    assert len(nodes) == EXPECTED_NODE_COUNT
    # The operational catalog is the sealed ledger PLUS declared post-baseline
    # nodes; the two legacy projections must match it exactly either way.
    assert set(nodes) == set(legacy_index) == set(legacy_metadata)
    assert set(nodes) - baseline_ids == set(POST_BASELINE_NODE_IDS)
    assert baseline_ids - set(nodes) == set()
    assert {entry["status"] for entry in nodes.values()} == {"legacy_compatible"}
    assert {entry["runtime_adapter"] for entry in nodes.values()} == {"base_node_v1"}
    assert {entry["availability"] for entry in nodes.values()} == {"active"}
    assert len({entry["execution_factory"] for entry in nodes.values()}) == EXPECTED_NODE_COUNT

    for node_id, entry in nodes.items():
        python_class = legacy_metadata[node_id]["python_class"]
        module_name, symbol = python_class.rsplit(".", 1)
        assert entry["module"] == legacy_index[node_id] == module_name
        assert entry["symbol"] == symbol
        assert entry["execution_factory"] == f"{module_name}:{symbol}"
        assert entry["legacy_execution_factory"] == entry["execution_factory"]


def test_operational_registry_resolves_all_943_base_node_classes() -> None:
    document = _operational_document()
    registry = CatalogRegistry.from_operational_document(document)

    assert len(registry.node_ids) == EXPECTED_NODE_COUNT
    for node_id in registry.node_ids:
        implementation = registry.resolve(node_id)
        assert isinstance(implementation, type)
        assert issubclass(implementation, BaseNode)
        assert implementation.NODE_ID == node_id


def test_availability_agrees_with_what_actually_resolves() -> None:
    """``availability`` must mean what it says.

    The palette and the preflight both trust this field. If a node marked
    active cannot be resolved, an invalid workflow reaches a provisioned cloud
    worker before anything notices; if a node marked blocked resolves fine, we
    are hiding working nodes. Pin both directions.
    """
    document = _operational_document()
    nodes = document["nodes"]
    registry = CatalogRegistry.from_operational_document(document)

    claimed_active = {node_id for node_id, entry in nodes.items() if entry["availability"] == "active"}
    claimed_blocked = {node_id for node_id, entry in nodes.items() if entry["availability"] == "blocked"}
    assert claimed_active | claimed_blocked == set(nodes), "unexpected availability value"

    unresolvable: list[str] = []
    for node_id in sorted(claimed_active):
        try:
            registry.resolve(node_id)
        except Exception as error:  # noqa: BLE001 - any failure disproves "active"
            unresolvable.append(f"{node_id}: {type(error).__name__}: {error}")

    assert not unresolvable, "nodes advertised as active that do not resolve:\n  " + "\n  ".join(unresolvable)

    for node_id in sorted(claimed_blocked):
        assert nodes[node_id]["blocked_reason"], f"{node_id} is blocked without a reason"

    summary = document["summary"]
    assert summary["availability_counts"]["active"] == len(claimed_active)
    assert summary["availability_counts"]["blocked"] == len(claimed_blocked)
    assert summary["importability_verified"] is (len(claimed_blocked) == 0)


def test_operational_samtools_entries_use_the_focused_one_file_classes() -> None:
    document = _operational_document()
    nodes = document["nodes"]
    expected = {
        "samtools_view": "bionodulo.nodes.builtin.samtools_family.view:SamtoolsViewNode",
        "samtools_collate": "bionodulo.nodes.builtin.samtools_family.collate:SamtoolsCollateNode",
        "samtools_fixmate": "bionodulo.nodes.builtin.samtools_family.fixmate:SamtoolsFixmateNode",
        "samtools_sort": "bionodulo.nodes.builtin.samtools_family.sort:SamtoolsSortNode",
        "samtools_markdup": "bionodulo.nodes.builtin.samtools_family.markdup:SamtoolsMarkdupNode",
        "samtools_index": "bionodulo.nodes.builtin.samtools_family.index:SamtoolsIndexNode",
        "samtools_flagstat": "bionodulo.nodes.builtin.samtools_family.flagstat:SamtoolsFlagstatNode",
    }

    for node_id, execution_factory in expected.items():
        entry = nodes[node_id]
        assert entry["execution_factory"] == execution_factory
        assert entry["verification_status"] == "promotion_candidate"
        assert entry["typed_contract_digest"].startswith("sha256:")
        assert entry["typed_execution_factory"].endswith(":build_plan")


def test_legacy_compatible_status_without_exact_adapter_remains_blocked() -> None:
    document = _operational_document()
    node_id = "samtools_view"
    broken = {
        **document,
        "nodes": {
            **document["nodes"],
            node_id: {**document["nodes"][node_id], "runtime_adapter": "future"},
        },
    }
    registry = CatalogRegistry.from_operational_document(broken)

    with pytest.raises(QuarantinedNodeError):
        registry.resolve(node_id)
