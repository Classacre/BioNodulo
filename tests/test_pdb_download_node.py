from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_pdb_download_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["pdb_download"]["display_name"] == "PDB Download"
    assert info["pdb_download"]["category"] == "api"
    assert info["pdb_download"]["output_name"] == ["structure_file", "pdb_metadata"]


@pytest.mark.asyncio
async def test_pdb_download_writes_structure_density_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("pdb_download")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[str] = []
    download_calls: list[tuple[str, Path]] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        json_calls.append(resource)
        pdb_id = resource.rsplit("/", 1)[-1]
        return {
            "rcsb_id": pdb_id,
            "struct": {"title": f"{pdb_id} test structure"},
            "rcsb_entry_info": {"experimental_method": ["X-ray"]},
        }

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_download_file", fake_download)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        pdb_ids="4hhb, 1mbn",
        format="cif",
        fetch_metadata=True,
        download_density=True,
        context=context,
    )

    structure_path = Path(result["outputs"]["structure_file"])
    metadata_path = Path(result["outputs"]["pdb_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert structure_path.name == "4HHB.cif"
    assert structure_path.read_text(encoding="utf-8") == (
        "downloaded from https://files.rcsb.org/download/4HHB.cif\n"
    )
    assert metadata_path.name == "pdb_metadata.json"
    assert metadata == {
        "record_count": 2,
        "structures": [
            {
                "pdb_id": "4HHB",
                "format": "cif",
                "structure_file": str(tmp_path / "pdb_download" / "4HHB.cif"),
                "density_file": str(tmp_path / "pdb_download" / "4HHB_density.bcif"),
                "metadata": {
                    "rcsb_id": "4HHB",
                    "struct": {"title": "4HHB test structure"},
                    "rcsb_entry_info": {"experimental_method": ["X-ray"]},
                },
            },
            {
                "pdb_id": "1MBN",
                "format": "cif",
                "structure_file": str(tmp_path / "pdb_download" / "1MBN.cif"),
                "density_file": str(tmp_path / "pdb_download" / "1MBN_density.bcif"),
                "metadata": {
                    "rcsb_id": "1MBN",
                    "struct": {"title": "1MBN test structure"},
                    "rcsb_entry_info": {"experimental_method": ["X-ray"]},
                },
            },
        ],
    }
    assert json_calls == ["entry/4HHB", "entry/1MBN"]
    assert download_calls == [
        ("https://files.rcsb.org/download/4HHB.cif", tmp_path / "pdb_download" / "4HHB.cif"),
        ("https://maps.rcsb.org/x-ray/4hhb/cell/", tmp_path / "pdb_download" / "4HHB_density.bcif"),
        ("https://files.rcsb.org/download/1MBN.cif", tmp_path / "pdb_download" / "1MBN.cif"),
        ("https://maps.rcsb.org/x-ray/1mbn/cell/", tmp_path / "pdb_download" / "1MBN_density.bcif"),
    ]


@pytest.mark.asyncio
async def test_pdb_download_rejects_invalid_format() -> None:
    node_class = _node_class("pdb_download")

    with pytest.raises(ValueError, match="Unsupported PDB format"):
        await node_class().run(pdb_ids="4HHB", format="mtz")
