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
    assert len(promotion["nodes"]) == 7
    assert {node["status"] for node in promotion["nodes"]} == {"promotion_candidate"}
    assert all(node["contract_digest"].startswith("sha256:") for node in promotion["nodes"])


def test_cli_check_does_not_change_forensic_baseline() -> None:
    before = BASELINE_LEDGER.read_bytes()
    before_digest = hashlib.sha256(before).hexdigest()
    assert main(["--check"]) == 0
    after = BASELINE_LEDGER.read_bytes()
    assert hashlib.sha256(after).hexdigest() == before_digest
    assert after == before
