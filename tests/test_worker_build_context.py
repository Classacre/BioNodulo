from pathlib import Path


def test_worker_build_context_excludes_local_pixi_cache() -> None:
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".pixi/" in ignored
    assert ".venv/" in ignored
    assert "**/__pycache__/" in ignored
    assert "**/*.pyc" in ignored
