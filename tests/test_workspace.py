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


def test_examples_link_survives_losing_a_race(tmp_path, monkeypatch):
    """Two processes seeding the same workspace must both succeed.

    CI runs pytest with `-n auto`. Two workers both saw no `examples` link,
    both called `os.symlink`, and the loser got FileExistsError -- which is an
    OSError, so it fell through to the copytree fallback. By then the target
    WAS a symlink to the source, so copying the source into it copied a tree
    onto itself:

        shutil.Error: [... 'examples/workflows/fastq_qc_pipeline.bionodulo.json'
                       and '.../workspace/examples/workflows/...' are the same file]

    Losing the race is success: the link the caller wanted now exists.
    """
    import os

    from bionodulo.core.workspace import ensure_examples_link

    project = tmp_path / "project"
    (project / "examples").mkdir(parents=True)
    (project / "examples" / "w.json").write_text("{}")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    real_symlink = os.symlink

    def symlink_loses_the_race(src, dst, **kwargs):
        # Someone else created it between the existence check and here.
        real_symlink(src, dst, **kwargs)
        raise FileExistsError(17, "File exists", str(dst))

    monkeypatch.setattr(os, "symlink", symlink_loses_the_race)

    ensure_examples_link(workspace, project)

    assert (workspace / "examples" / "w.json").exists()


def test_examples_link_falls_back_to_copying(tmp_path, monkeypatch):
    """Windows without the symlink privilege has no link to fall back from."""
    import os

    from bionodulo.core.workspace import ensure_examples_link

    project = tmp_path / "project"
    (project / "examples").mkdir(parents=True)
    (project / "examples" / "w.json").write_text("{}")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def no_symlink_privilege(src, dst, **kwargs):
        raise OSError(1, "A required privilege is not held by the client")

    monkeypatch.setattr(os, "symlink", no_symlink_privilege)

    ensure_examples_link(workspace, project)

    target = workspace / "examples"
    assert not target.is_symlink()
    assert (target / "w.json").read_text() == "{}"
