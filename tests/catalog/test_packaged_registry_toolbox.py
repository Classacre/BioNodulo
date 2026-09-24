"""The shipped all-record catalog must retain its exhaustive generation receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bionodulo.nodes.registry_catalog import DEFAULT_CATALOG, RegistryCatalog


def test_packaged_registry_catalog_matches_verified_generation_receipt():
    receipt_path = Path(__file__).resolve().parents[2] / "reports" / "registry-toolbox" / "coverage.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(DEFAULT_CATALOG.read_bytes()).hexdigest() == receipt["catalog_file_sha256"]
    actual = RegistryCatalog(DEFAULT_CATALOG).verify()
    assert actual["verified_definitions"] == receipt["source_records_verified"] == receipt["metadata_round_trips"]
    assert actual["definition_digest"] == receipt["definition_digest"]
    assert actual["sha256"] == receipt["sha256"]
    assert actual["executable_definitions"] == 0
    assert receipt["source_accessions_missing"] == receipt["source_accessions_duplicated"] == 0
