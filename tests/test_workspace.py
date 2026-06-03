from __future__ import annotations

from pathlib import Path

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
