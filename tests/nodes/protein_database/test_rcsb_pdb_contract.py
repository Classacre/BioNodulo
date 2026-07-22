from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.builtin.protein_database_family import rcsb_pdb
from bionodulo.nodes.builtin.protein_database_family.rcsb_pdb import PDBDownloadNode


async def _recording_download(
    calls: list[tuple[str, Path]],
    url: str,
    path: Path,
) -> None:
    calls.append((url, path))
    path.write_bytes(f"downloaded from {url}\n".encode())


@pytest.mark.asyncio
async def test_multiple_ids_expose_download_directory_with_relative_manifest_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    downloads: list[tuple[str, Path]] = []

    async def fake_download(url: str, path: Path, **_kwargs: Any) -> None:
        await _recording_download(downloads, url, path)

    monkeypatch.setattr(rcsb_pdb, "_download_file", fake_download)

    result = await PDBDownloadNode().run(
        pdb_ids="4hhb,1cbs",
        format="cif",
        fetch_metadata=False,
        download_density=False,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    outputs = result["outputs"]
    download_directory = Path(outputs["download_directory"])
    assert PDBDownloadNode.RETURN_NAMES == (
        "structure_file",
        "pdb_metadata",
        "download_directory",
    )
    assert Path(outputs["structure_file"]) == download_directory / "4HHB.cif"
    assert Path(outputs["pdb_metadata"]) == download_directory / "pdb_metadata.json"
    assert sorted(path.name for path in download_directory.iterdir()) == [
        "1CBS.cif",
        "4HHB.cif",
        "pdb_metadata.json",
    ]
    assert downloads == [
        (
            "https://files.rcsb.org/download/4HHB.cif",
            download_directory / "4HHB.cif",
        ),
        (
            "https://files.rcsb.org/download/1CBS.cif",
            download_directory / "1CBS.cif",
        ),
    ]

    metadata = json.loads(Path(outputs["pdb_metadata"]).read_text(encoding="utf-8"))
    assert metadata["record_count"] == 2
    assert [item["structure_file"] for item in metadata["structures"]] == [
        "4HHB.cif",
        "1CBS.cif",
    ]
    assert all(not Path(item["structure_file"]).is_absolute() for item in metadata["structures"])
    assert all(item["density_files"] == [] for item in metadata["structures"])


@pytest.mark.asyncio
async def test_xray_density_uses_pdb_id_and_explicit_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    metadata_calls: list[str] = []
    downloads: list[tuple[str, Path]] = []

    async def fake_metadata(resource: str, **_kwargs: Any) -> dict[str, Any]:
        metadata_calls.append(resource)
        return {"exptl": [{"method": "X-RAY DIFFRACTION"}]}

    async def fake_download(url: str, path: Path, **_kwargs: Any) -> None:
        await _recording_download(downloads, url, path)

    monkeypatch.setattr(rcsb_pdb, "_request_json", fake_metadata)
    monkeypatch.setattr(rcsb_pdb, "_download_file", fake_download)

    result = await PDBDownloadNode().run(
        pdb_ids="1cbs",
        format="cif",
        fetch_metadata=False,
        download_density=True,
        density_detail=4,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    download_directory = Path(result["outputs"]["download_directory"])
    density_name = "1CBS_density_detail4.bcif"
    assert metadata_calls == ["entry/1CBS"]
    assert downloads == [
        (
            "https://files.rcsb.org/download/1CBS.cif",
            download_directory / "1CBS.cif",
        ),
        (
            "https://maps.rcsb.org/x-ray/1cbs/cell/?detail=4",
            download_directory / density_name,
        ),
    ]

    metadata = json.loads(Path(result["outputs"]["pdb_metadata"]).read_text(encoding="utf-8"))
    record = metadata["structures"][0]
    assert record["density_detail"] == 4
    assert record["density_file"] == density_name
    assert record["density_files"] == [density_name]
    assert record["metadata"] == {}


@pytest.mark.asyncio
async def test_electron_microscopy_density_uses_emdb_identifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    entry_metadata = {
        "exptl": [{"method": "ELECTRON MICROSCOPY"}],
        "rcsb_entry_container_identifiers": {"emdb_ids": ["EMD-21452"]},
    }
    downloads: list[tuple[str, Path]] = []

    async def fake_metadata(_resource: str, **_kwargs: Any) -> dict[str, Any]:
        return entry_metadata

    async def fake_download(url: str, path: Path, **_kwargs: Any) -> None:
        await _recording_download(downloads, url, path)

    monkeypatch.setattr(rcsb_pdb, "_request_json", fake_metadata)
    monkeypatch.setattr(rcsb_pdb, "_download_file", fake_download)

    result = await PDBDownloadNode().run(
        pdb_ids="6vxx",
        format="cif",
        fetch_metadata=True,
        download_density=True,
        density_detail=2,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    download_directory = Path(result["outputs"]["download_directory"])
    density_name = "6VXX_EMD-21452_density_detail2.bcif"
    assert downloads[-1] == (
        "https://maps.rcsb.org/em/emd-21452/cell/?detail=2",
        download_directory / density_name,
    )

    metadata = json.loads(Path(result["outputs"]["pdb_metadata"]).read_text(encoding="utf-8"))
    record = metadata["structures"][0]
    assert record["density_files"] == [density_name]
    assert record["metadata"] == entry_metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("density_outcome", "fatal_message"),
    [
        ("not_found", None),
        ("server_error", "HTTP 503"),
        ("transport_error", "transport unavailable"),
    ],
)
async def test_only_density_not_found_is_optional(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    density_outcome: str,
    fatal_message: str | None,
) -> None:
    class FakeClient:
        def __init__(
            self,
            *,
            cache: object | None = None,
            rate_limiter: object | None = None,
        ) -> None:
            del cache, rate_limiter

        async def request(self, method: str, url: str, **_kwargs: Any) -> httpx.Response:
            request = httpx.Request(method, url)
            if url.startswith(rcsb_pdb.RCSB_FILE_BASE_URL):
                return httpx.Response(200, content=b"data_1cbs\n", request=request)
            if density_outcome == "transport_error":
                raise httpx.ConnectError("transport unavailable", request=request)
            status = 404 if density_outcome == "not_found" else 503
            response = httpx.Response(status, request=request)
            raise httpx.HTTPStatusError(
                f"density response was HTTP {status}",
                request=request,
                response=response,
            )

    async def fake_metadata(_resource: str, **_kwargs: Any) -> dict[str, Any]:
        return {"exptl": [{"method": "X-RAY DIFFRACTION"}]}

    monkeypatch.setattr(rcsb_pdb, "APIHttpClient", FakeClient)
    monkeypatch.setattr(rcsb_pdb, "_request_json", fake_metadata)

    kwargs = {
        "pdb_ids": "1CBS",
        "format": "cif",
        "fetch_metadata": False,
        "download_density": True,
        "density_detail": 0,
        "context": SimpleNamespace(node_dir=tmp_path / density_outcome),
    }
    if fatal_message is not None:
        with pytest.raises(RuntimeError, match=fatal_message):
            await PDBDownloadNode().run(**kwargs)
        return

    result = await PDBDownloadNode().run(**kwargs)
    metadata = json.loads(Path(result["outputs"]["pdb_metadata"]).read_text(encoding="utf-8"))
    record = metadata["structures"][0]
    assert record["density_file"] == ""
    assert record["density_files"] == []
    assert not (Path(result["outputs"]["download_directory"]) / "1CBS_density_detail0.bcif").exists()
