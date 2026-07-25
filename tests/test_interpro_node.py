"""Compact InterProScan REST contract tests."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get(node_id)
    assert node is not None
    return node


def test_interpro_ids_are_focused_and_preserve_ports() -> None:
    scan = _node("interpro_scan")
    interpro = _node("interpro")
    assert scan.__module__ == "bionodulo.nodes.builtin.interpro_family.scan"
    assert interpro.__module__ == "bionodulo.nodes.builtin.interpro_family.interpro"
    assert issubclass(interpro, scan)
    assert scan.RETURN_NAMES == ("domain_annotations", "domains_tsv")
    assert scan.INPUT_TYPES()["required"]["email"][0] == "STRING"
    assert "30 concurrent jobs" in scan.NETWORK_SEMANTICS


@pytest.mark.asyncio
async def test_interpro_submit_poll_and_native_json_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = _node("interpro_scan")
    module = importlib.import_module(node.__module__)
    submitted: list[dict[str, Any]] = []
    statuses = ["RUNNING", "FINISHED"]

    async def fake_post(endpoint: str, data: dict[str, Any]) -> str:
        submitted.append({"endpoint": endpoint, "data": dict(data)})
        return "JOB-1\n"

    async def fake_status(endpoint: str) -> str:
        assert endpoint == "status/JOB-1"
        return statuses.pop(0)

    async def fake_result(endpoint: str) -> dict[str, Any]:
        assert endpoint == "result/JOB-1/json"
        return {
            "results": [
                {
                    "xref": [{"id": "protein-1"}],
                    "matches": [
                        {
                            "signature": {
                                "accession": "PF00069",
                                "name": "Protein kinase domain",
                                "entry": {"accession": "IPR000719", "type": "DOMAIN"},
                            },
                            "locations": [{"start": 12, "end": 274, "evalue": 1.2e-45}],
                        }
                    ],
                }
            ]
        }

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(module, "_post_text", fake_post)
    monkeypatch.setattr(module, "_get_text", fake_status)
    monkeypatch.setattr(module, "_get_json", fake_result)
    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)

    result = await node().run(
        sequence=">protein-1\nMEEPQSDPSV",
        email="analyst@example.org",
        applications="PfamA,SMART",
        poll_interval_seconds=1.0,
        context=SimpleNamespace(node_dir=tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["domain_annotations"]).read_text(encoding="utf-8"))
    table = Path(result["outputs"]["domains_tsv"]).read_text(encoding="utf-8")
    assert payload["job_id"] == "JOB-1"
    assert "protein-1\tPF00069\tProtein kinase domain\tIPR000719\tDOMAIN\t12\t274\t1.2e-45" in table
    assert submitted[0]["data"] == {
        "email": "analyst@example.org",
        "title": "bionodulo_interpro",
        "stype": "p",
        "sequence": "MEEPQSDPSV",
        "goterms": "true",
        "pathways": "false",
        "appl": "PfamA,SMART",
    }


@pytest.mark.asyncio
async def test_interpro_fails_closed_without_contact_or_on_failed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node("interpro_scan")
    with pytest.raises(ValueError, match="valid contact email"):
        await node().run(sequence="MEEPQSDPSV", email="")

    module = importlib.import_module(node.__module__)

    async def fake_post(endpoint: str, data: dict[str, Any]) -> str:
        return "FAILED-JOB"

    async def fake_status(endpoint: str) -> str:
        return "FAILURE"

    monkeypatch.setattr(module, "_post_text", fake_post)
    monkeypatch.setattr(module, "_get_text", fake_status)
    with pytest.raises(RuntimeError, match="failed with status FAILURE"):
        await node().run(sequence="MEEPQSDPSV", email="analyst@example.org")


@pytest.mark.asyncio
async def test_interpro_preserves_zero_for_runtime_bound_validation() -> None:
    node = _node("interpro_scan")
    with pytest.raises(ValueError, match="timeout_minutes"):
        await node().run(sequence="MEEPQSDPSV", email="analyst@example.org", timeout_minutes=0)
    with pytest.raises(ValueError, match="poll_interval_seconds"):
        await node().run(sequence="MEEPQSDPSV", email="analyst@example.org", poll_interval_seconds=0)
