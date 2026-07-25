from __future__ import annotations

import hashlib
import json

from scripts.compile_catalog import (
    BASELINE_LEDGER,
    BASELINE_NODE_COUNT,
    expected_documents,
    main,
)


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
        "baseline_nodes": BASELINE_NODE_COUNT,
        "evidence_pending_nodes": 936,
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
