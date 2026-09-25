from fnmatch import fnmatch
from pathlib import Path


def test_worker_build_context_excludes_local_pixi_cache() -> None:
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert {".pixi/", "**/.pixi/"}.intersection(ignored)
    assert {".venv/", "**/.venv/"}.intersection(ignored)
    assert "**/__pycache__/" in ignored
    assert any(fnmatch("package/module.pyc", rule) for rule in ignored if not rule.startswith("!"))
