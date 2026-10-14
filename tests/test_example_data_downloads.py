from __future__ import annotations

import gzip
import io
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest

from bionodulo.manager import example_data
from bionodulo.nodes.builtin.input_family import adapter


@pytest.mark.parametrize("mode", ["plain", "gzip", "archive"])
def test_downloaded_examples_publish_converted_content(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b"gene,sample\na,1\n"
    payload = body
    options: dict[str, object] = {"rename_columns": {"sample": "condition"}}
    if mode == "gzip":
        payload = gzip.compress(body)
        options["gunzip"] = True
    elif mode == "archive":
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as handle:
            member = tarfile.TarInfo("data/counts.csv")
            member.size = len(body)
            handle.addfile(member, io.BytesIO(body))
        payload = archive.getvalue()
        options["archive_member"] = "data/counts.csv"
    monkeypatch.setattr(example_data.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(payload))
    destination = tmp_path / "counts.csv"

    example_data._download_url("https://example.invalid/data", destination, **options)

    assert destination.read_bytes() == b"gene,condition\na,1\n"
    assert list(tmp_path.iterdir()) == [destination]


def test_concurrent_example_downloads_do_not_share_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready = Barrier(2)

    def open_response(*_args: object, **_kwargs: object) -> io.BytesIO:
        ready.wait(timeout=5)
        return io.BytesIO(gzip.compress(b"@r\nACGT\n+\n!!!!\n"))

    monkeypatch.setattr(example_data.urllib.request, "urlopen", open_response)
    destination = tmp_path / "reads.fastq"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(example_data._download_url, "https://example.invalid/reads.gz", destination, gunzip=True)
            for _ in range(2)
        ]
        for future in futures:
            future.result(timeout=10)

    assert destination.read_bytes() == b"@r\nACGT\n+\n!!!!\n"
    assert list(tmp_path.iterdir()) == [destination]


def test_invalid_compressed_example_never_leaves_a_cache_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(example_data.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"not gzip"))
    destination = tmp_path / "reads.fastq"

    with pytest.raises(gzip.BadGzipFile):
        example_data._download_url("https://example.invalid/reads.fastq.gz", destination, gunzip=True)

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_example_header_conversion_failure_preserves_existing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "counts.csv"
    destination.write_bytes(b"previous complete data\n")
    monkeypatch.setattr(example_data.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"gene,sample\na,1\n"))

    def fail_rename(*_args: object) -> None:
        raise ValueError("cannot convert downloaded header")

    monkeypatch.setattr(example_data, "_apply_header_renames", fail_rename)
    with pytest.raises(ValueError, match="cannot convert"):
        example_data._download_url(
            "https://example.invalid/counts.csv", destination, rename_columns={"sample": "condition"},
        )

    assert destination.read_bytes() == b"previous complete data\n"
    assert list(tmp_path.iterdir()) == [destination]


def test_nested_example_file_resolves_the_full_manifest_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = example_data.DataFile("spatial", "outs/spatial/positions.csv", "https://example.invalid/positions.csv")
    monkeypatch.setattr(example_data, "EXAMPLE_DATA_MANIFEST", [entry])
    monkeypatch.setattr(example_data.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"spot,x,y\na,1,2\n"))

    resolved = adapter._resolve_example_data_fallback(
        "examples/data/spatial/outs/spatial/positions.csv", SimpleNamespace(workspace_dir=tmp_path),
    )

    assert resolved is not None
    assert resolved.read_bytes() == b"spot,x,y\na,1,2\n"
    assert resolved.relative_to(tmp_path).as_posix().endswith("examples_data/spatial/outs/spatial/positions.csv")


def test_example_directory_is_rejected_until_all_members_are_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = [
        example_data.DataFile("spatial", "outs/matrix.h5", "https://example.invalid/matrix.h5"),
        example_data.DataFile("spatial", "outs/spatial/positions.csv", "https://example.invalid/positions.csv"),
    ]
    monkeypatch.setattr(example_data, "EXAMPLE_DATA_MANIFEST", entries)

    def download(url: str, destination: Path, **_kwargs: object) -> None:
        if url.endswith("positions.csv"):
            raise OSError("download interrupted")
        destination.write_bytes(b"complete matrix")

    monkeypatch.setattr(example_data, "_download_url", download)
    resolved = adapter._resolve_example_data_fallback(
        "examples/data/spatial/outs", SimpleNamespace(workspace_dir=tmp_path),
    )

    assert resolved is None
