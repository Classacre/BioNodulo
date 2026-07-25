from __future__ import annotations

import json
from pathlib import Path

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.catalog.registry import CatalogRegistry, QuarantinedNodeError
from scripts.compile_catalog import BASELINE_NODE_COUNT, expected_documents


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

    assert len(nodes) == BASELINE_NODE_COUNT
    assert set(nodes) == set(legacy_index) == set(legacy_metadata) == baseline_ids
    assert {entry["status"] for entry in nodes.values()} == {"legacy_compatible"}
    assert {entry["runtime_adapter"] for entry in nodes.values()} == {"base_node_v1"}
    assert {entry["availability"] for entry in nodes.values()} == {"active"}
    assert len({entry["execution_factory"] for entry in nodes.values()}) == BASELINE_NODE_COUNT

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

    assert len(registry.node_ids) == BASELINE_NODE_COUNT
    for node_id in registry.node_ids:
        implementation = registry.resolve(node_id)
        assert isinstance(implementation, type)
        assert issubclass(implementation, BaseNode)
        assert implementation.NODE_ID == node_id


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
