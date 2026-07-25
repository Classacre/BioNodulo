from __future__ import annotations

import tarfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from bionodulo.api.routes import _scan_cloud_directory, _write_cloud_directory_archive
from bionodulo.core.workspace import ensure_examples_link


def test_ensure_examples_link_replaces_stale_examples_symlink(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    examples_dir = project_dir / "examples"
    examples_dir.mkdir(parents=True)
    (examples_dir / "example.txt").write_text("current examples\n", encoding="utf-8")

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    stale_target = tmp_path / "removed-checkout" / "examples"
    stale_link = workspace_root / "examples"
    stale_link.symlink_to(stale_target)

    ensure_examples_link(workspace_root, project_dir)

    assert stale_link.exists()
    assert stale_link.resolve() == examples_dir.resolve()


def test_cloud_directory_snapshot_and_archive_are_bounded_and_deterministic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inputs"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "reference.fa").write_text(">r\nACGT\n", encoding="utf-8")
    (source / "reads.fastq").write_text("@r\nACGT\n+\n!!!!\n", encoding="utf-8")

    snapshot = _scan_cloud_directory(source)
    assert snapshot["entries"] == 3
    first = tmp_path / "one.tar"
    second = tmp_path / "two.tar"
    assert _write_cloud_directory_archive(snapshot, first) == first.stat().st_size
    assert _write_cloud_directory_archive(snapshot, second) == second.stat().st_size
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:") as archive:
        assert [member.name for member in archive] == [
            "nested",
            "nested/reference.fa",
            "reads.fastq",
        ]


def test_cloud_directory_snapshot_rejects_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "inputs"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    (source / "link").symlink_to(outside)

    with pytest.raises(HTTPException, match="symbolic links"):
        _scan_cloud_directory(source)
