"""Directory inputs must be able to consume published archive bundles safely.

Reference data (kraken2 databases, Space Ranger references) is only published as
.tar.gz. Before this, a directory input pointed at an archive URL downloaded the
tarball as a *file* and then failed "Expected a directory input, got file", so
those templates could never run.

Extraction is attacker-adjacent: member names come from a remote archive, so the
traversal tests below matter as much as the happy path.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.input_family import adapter


def _tar_gz(path: Path, entries: dict[str, bytes], *, root: str | None = None) -> Path:
    with tarfile.open(path, "w:gz") as tf:
        for name, payload in entries.items():
            full = f"{root}/{name}" if root else name
            info = tarfile.TarInfo(full)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return path


def test_archive_suffixes_are_recognised() -> None:
    for name in ("db.tar.gz", "db.tgz", "db.tar", "db.zip", "db.tar.bz2", "db.tar.xz"):
        assert adapter._looks_like_archive(name), name
    for name in ("genome.fa", "reads.fastq.gz", "notes.txt"):
        assert not adapter._looks_like_archive(name), name


def test_tar_extraction_returns_the_inner_root(tmp_path: Path) -> None:
    """Archives wrap content in one top directory; hand back the real content."""
    archive = _tar_gz(tmp_path / "db.tar.gz", {"hash.k2d": b"x", "taxo.k2d": b"y"}, root="k2_viral")
    destination = tmp_path / "out"
    adapter._extract_archive(archive, destination)

    resolved = adapter._flatten_single_root(destination)
    assert resolved.name == "k2_viral"
    assert (resolved / "hash.k2d").is_file()
    assert (resolved / "taxo.k2d").is_file()


def test_multi_root_archive_is_not_flattened(tmp_path: Path) -> None:
    archive = _tar_gz(tmp_path / "multi.tar.gz", {"a.txt": b"a", "b.txt": b"b"})
    destination = tmp_path / "out"
    adapter._extract_archive(archive, destination)

    assert adapter._flatten_single_root(destination) == destination


def test_tar_traversal_member_is_refused(tmp_path: Path) -> None:
    """The classic tar-slip: a member escaping the extraction root."""
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("../escaped.txt")
        payload = b"pwned"
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))

    with pytest.raises(ValueError, match="outside the target"):
        adapter._extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_absolute_member_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "abs.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("/tmp/bionodulo-escape-probe")
        info.size = 0
        tf.addfile(info, io.BytesIO(b""))

    with pytest.raises(ValueError, match="outside the target"):
        adapter._extract_archive(archive, tmp_path / "out")


def test_symlink_escaping_the_root_is_refused(tmp_path: Path) -> None:
    """A benign-looking name whose LINK TARGET escapes is still an escape."""
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("inside/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../../etc/passwd"
        tf.addfile(info)

    with pytest.raises(ValueError, match="outside the target"):
        adapter._extract_archive(archive, tmp_path / "out")


def test_zip_traversal_member_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escaped.txt", "pwned")

    with pytest.raises(ValueError, match="outside the target"):
        adapter._extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_zip_round_trip(tmp_path: Path) -> None:
    archive = tmp_path / "ok.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("refdata/genome.fa", ">chr1\nACGT\n")

    destination = tmp_path / "out"
    adapter._extract_archive(archive, destination)
    assert (destination / "refdata" / "genome.fa").is_file()


def test_partial_extraction_is_never_promoted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted unpack must not look like a complete reference database."""

    class _Ctx:
        workspace_dir = tmp_path

    def _boom(archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "half-written.k2d").write_bytes(b"partial")
        raise OSError("connection reset mid-extract")

    monkeypatch.setattr(adapter, "_extract_archive", _boom)
    monkeypatch.setattr(
        adapter.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(b"payload"),
    )

    url = "https://example.invalid/db.tar.gz"
    with pytest.raises(OSError):
        adapter._download_archive_to_cache(url, _Ctx())

    cache_dir = adapter._cache_root(_Ctx()) / adapter._url_cache_key(url)
    assert not (cache_dir / "extracted").exists()
