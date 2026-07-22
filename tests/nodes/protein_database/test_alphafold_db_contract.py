from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.protein_database_family import alphafold_db
from bionodulo.nodes.builtin.protein_database_family.alphafold_db import AlphaFoldDBNode


CURRENT_OPENAPI_SHA256 = "714607265fd8edc581baf28df038ea804d96d871baa6034ff60d22d0cf893163"


def _entry(
    accession: str,
    *,
    with_pae: bool = True,
    sequence_checksum: str = "0123456789abcdef0123456789abcdef",
    model_id: str | None = None,
    is_complex: bool = False,
    uniprot_accession: Any = None,
) -> dict[str, Any]:
    model_id = model_id or f"AF-{accession}-F1"
    return {
        "modelEntityId": model_id,
        "entryId": model_id,
        "uniprotAccession": accession if uniprot_accession is None else uniprot_accession,
        "uniprotId": "P53_HUMAN",
        "latestVersion": 6,
        "allVersions": [1, 2, 3, 4, 5, 6],
        "sequenceChecksum": sequence_checksum,
        "isComplex": is_complex,
        "cifUrl": f"https://alphafold.example/{model_id}-model_v6.cif",
        "pdbUrl": f"https://alphafold.example/{model_id}-model_v6.pdb",
        "paeDocUrl": (f"https://alphafold.example/{model_id}-predicted_aligned_error_v6.json" if with_pae else None),
    }


def test_current_openapi_inputs_replace_ignored_model_version() -> None:
    optional = AlphaFoldDBNode.INPUT_TYPES()["optional"]

    assert AlphaFoldDBNode.SOURCE_SHA256 == CURRENT_OPENAPI_SHA256
    assert "sequence_checksum" in optional
    assert "include_complexes" in optional
    assert "model_version" not in optional
    assert "unsupported" in str(AlphaFoldDBNode.VALIDATE_INPUTS({"uniprot_ids": "P04637", "model_version": "1"}))
    assert "32-character MD5" in str(
        AlphaFoldDBNode.VALIDATE_INPUTS({"uniprot_ids": "P04637", "sequence_checksum": "not-an-md5"})
    )
    assert "only be used with one" in str(
        AlphaFoldDBNode.VALIDATE_INPUTS(
            {
                "uniprot_ids": "P04637,Q5VSL9",
                "sequence_checksum": "0123456789abcdef0123456789abcdef",
            }
        )
    )
    assert "only be used with one" in str(
        AlphaFoldDBNode.VALIDATE_INPUTS(
            {
                "uniprot_ids": "P04637,Q5VSL9",
                "include_complexes": True,
            }
        )
    )


@pytest.mark.asyncio
async def test_live_shaped_response_selects_exact_accession_and_exposes_all_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    requests: list[tuple[str, dict[str, Any] | None]] = []
    downloads: list[str] = []

    async def fake_request(resource: str, *, params: dict[str, Any] | None = None, **_kwargs: Any) -> Any:
        requests.append((resource, params))
        accession = resource.rsplit("/", 1)[-1]
        return [_entry(f"{accession}-2"), _entry(accession)]

    async def fake_download(url: str, path: Path, **_kwargs: Any) -> None:
        downloads.append(url)
        path.write_text("synthetic", encoding="utf-8")

    monkeypatch.setattr(alphafold_db, "_request_json", fake_request)
    monkeypatch.setattr(alphafold_db, "_download_file", fake_download)

    result = await AlphaFoldDBNode().run(
        uniprot_ids="P04637,Q5VSL9",
        structure_format="mmcif",
        include_complexes=False,
        download_pae=True,
        context=type("Context", (), {"node_dir": tmp_path})(),
    )

    outputs = result["outputs"]
    assert requests == [
        (
            "prediction/P04637",
            {
                "include_complexes": False,
            },
        ),
        (
            "prediction/Q5VSL9",
            {
                "include_complexes": False,
            },
        ),
    ]
    assert len(downloads) == 4
    assert outputs["structure_mmcif"].endswith("P04637.cif")
    assert outputs["pae_json"].endswith("P04637_pae.json")
    assert Path(outputs["artifacts_directory"]).is_dir()
    assert (Path(outputs["artifacts_directory"]) / "Q5VSL9.cif").is_file()
    metadata = json.loads(Path(outputs["structure_metadata"]).read_text(encoding="utf-8"))
    assert [item["uniprot_accession"] for item in metadata["structures"]] == [
        "P04637",
        "Q5VSL9",
    ]
    assert all(item["response_record_count"] == 2 for item in metadata["structures"])
    assert [item["structure_file"] for item in metadata["structures"]] == [
        "P04637.cif",
        "Q5VSL9.cif",
    ]


@pytest.mark.asyncio
async def test_include_complexes_materializes_every_returned_complex_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    primary = _entry("P04637")
    complex_entry = _entry(
        "P04637",
        model_id="AF-COMPLEX-1001",
        is_complex=True,
        uniprot_accession=["P04637", "Q9Y6K9"],
    )
    downloads: list[tuple[str, Path]] = []

    async def fake_request(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return [_entry("P04637-2"), primary, complex_entry]

    async def fake_download(url: str, path: Path, **_kwargs: Any) -> None:
        downloads.append((url, path))
        path.write_text("synthetic", encoding="utf-8")

    monkeypatch.setattr(alphafold_db, "_request_json", fake_request)
    monkeypatch.setattr(alphafold_db, "_download_file", fake_download)

    result = await AlphaFoldDBNode().run(
        uniprot_ids="P04637",
        include_complexes=True,
        download_pae=True,
        context=type("Context", (), {"node_dir": tmp_path})(),
    )

    output_dir = Path(result["outputs"]["artifacts_directory"])
    assert len(downloads) == 4
    assert (output_dir / "P04637.cif").is_file()
    assert (output_dir / "P04637_pae.json").is_file()
    assert (output_dir / "AF-COMPLEX-1001.cif").is_file()
    assert (output_dir / "AF-COMPLEX-1001_pae.json").is_file()
    metadata = json.loads(Path(result["outputs"]["structure_metadata"]).read_text(encoding="utf-8"))
    assert metadata["record_count"] == 2
    assert [item["entry_id"] for item in metadata["structures"]] == [
        "AF-P04637-F1",
        "AF-COMPLEX-1001",
    ]
    assert metadata["structures"][1]["uniprot_accession"] == ["P04637", "Q9Y6K9"]


@pytest.mark.asyncio
async def test_sequence_checksum_is_forwarded_and_verified_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any] | None] = []

    async def fake_request(
        _resource: str,
        *,
        params: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        requests.append(params)
        return [_entry("P04637", sequence_checksum="f" * 32)]

    monkeypatch.setattr(alphafold_db, "_request_json", fake_request)

    with pytest.raises(RuntimeError, match="checksum did not match"):
        await AlphaFoldDBNode().run(
            uniprot_ids="P04637",
            sequence_checksum="0" * 32,
        )

    assert requests == [{"include_complexes": False, "sequence_checksum": "0" * 32}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response_kind", "message"),
    [
        ("empty", "returned no prediction records"),
        ("no_exact_match", "did not contain an exact accession/model match"),
    ],
)
async def test_missing_exact_prediction_response_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    response_kind: str,
    message: str,
) -> None:
    async def fake_request(*_args: Any, **_kwargs: Any) -> list[Any]:
        return [] if response_kind == "empty" else [_entry("Q5VSL9")]

    monkeypatch.setattr(alphafold_db, "_request_json", fake_request)

    with pytest.raises(RuntimeError, match=message):
        await AlphaFoldDBNode().run(uniprot_ids="P04637")


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["cifUrl", "paeDocUrl"])
async def test_requested_missing_artifact_url_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    entry = _entry("P04637")
    entry[missing] = None
    downloads: list[str] = []

    async def fake_request(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return [entry]

    async def fake_download(url: str, *_args: Any, **_kwargs: Any) -> None:
        downloads.append(url)

    monkeypatch.setattr(alphafold_db, "_request_json", fake_request)
    monkeypatch.setattr(alphafold_db, "_download_file", fake_download)

    with pytest.raises(RuntimeError, match="did not provide"):
        await AlphaFoldDBNode().run(
            uniprot_ids="P04637",
            download_pae=missing == "paeDocUrl",
        )
    assert downloads == []
