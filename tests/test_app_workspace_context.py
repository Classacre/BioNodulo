from pathlib import Path
from types import SimpleNamespace

from bionodulo.api.app_state import AppState


def test_lazy_collaboration_stores_use_the_apps_configured_workspace(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path / "process-default"))
    one = AppState(SimpleNamespace(settings=SimpleNamespace(project_root=first)))
    two = AppState(SimpleNamespace(settings=SimpleNamespace(project_root=second)))

    assert one.workspace_root == first
    assert two.workspace_root == second
    assert Path(one.collab_store.db_path) == first / "collab.db"
    assert Path(two.collab_store.db_path) == second / "collab.db"
    assert Path(one.template_manager.db_path) == first / "collab.db"
    assert Path(two.template_manager.db_path) == second / "collab.db"
    assert not (tmp_path / "process-default").exists()


def test_environment_change_does_not_rebind_an_existing_app(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "original"
    state = AppState(SimpleNamespace(settings=SimpleNamespace(project_root=root)))
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path / "changed"))
    assert state.workspace_root == root
    assert Path(state.collab_store.db_path) == root / "collab.db"


def test_legacy_state_without_settings_keeps_environment_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    assert AppState(SimpleNamespace()).workspace_root == tmp_path
