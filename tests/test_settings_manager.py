from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bionodulo.api.settings_routes import settings_router
from bionodulo.core.config import SettingsManager


def test_single_setting_is_visible_to_bulk_reads_and_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    manager = SettingsManager(path)
    app = FastAPI()
    app.state.settings_manager = manager
    app.include_router(settings_router, prefix="/api")

    with TestClient(app) as client:
        assert client.post("/api/settings/bionodulo.llm.provider", json={"value": "custom"}).status_code == 200
        assert client.get("/api/settings").json()["bionodulo.llm.provider"] == "custom"
        assert client.get("/api/settings/bionodulo.llm.provider").json() == {"bionodulo.llm.provider": "custom"}
        assert client.post("/api/settings", json={"settings": {"bionodulo.llm.provider": "litellm"}}).status_code == 200
        assert client.get("/api/settings/bionodulo.llm.provider").json() == {"bionodulo.llm.provider": "litellm"}

    reloaded = SettingsManager(path)
    assert reloaded.get("bionodulo.llm.provider") == "litellm"
    assert reloaded.get_all()["bionodulo.llm.provider"] == "litellm"


def test_legacy_nested_application_settings_are_migrated(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "bionodulo.llm.provider": "openai",
        "bionodulo": {"llm": {"provider": "custom", "baseUrl": "http://localhost:4000/v1"}},
        "editor_settings": {"font_size": 18},
    }), encoding="utf-8")

    manager = SettingsManager(path)
    assert manager.get("bionodulo.llm.provider") == "custom"
    assert manager.get_all()["bionodulo.llm.provider"] == "custom"
    assert "bionodulo" not in manager.get_all()
    assert manager.get("editor_settings.font_size") == 18
    manager.set_many({"bionodulo.llm.provider": "litellm"})
    assert SettingsManager(path).get("bionodulo.llm.provider") == "litellm"


def test_nested_bulk_application_settings_are_normalized(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.json")
    manager.set_many({"bionodulo": {"llm": {"provider": "custom"}}})
    assert manager.get_all()["bionodulo.llm.provider"] == "custom"
    manager.set("bionodulo.llm.provider", "litellm")
    assert manager.get("bionodulo.llm.provider") == "litellm"


def test_reset_and_partial_files_use_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"locale": "fr"}', encoding="utf-8")
    manager = SettingsManager(path)
    assert manager.get("bionodulo.llm.provider") == "openai"
    manager.set("bionodulo.llm.provider", "custom")
    manager.reset("bionodulo.llm.provider")
    assert manager.get("bionodulo.llm.provider") == "openai"
    assert manager.get_all()["bionodulo.llm.provider"] == "openai"
    assert manager.get("locale") == "fr"


def test_nested_editor_settings_remain_supported(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.json")
    manager.set("editor_settings.font_size", 18)
    assert manager.get("editor_settings.font_size") == 18
    assert manager.get_all()["editor_settings"]["font_size"] == 18


def test_assistant_settings_inspection_never_sends_provider_keys_to_the_model(tmp_path: Path) -> None:
    from bionodulo.ai.tools import ToolContext, execute_tool

    manager = SettingsManager(tmp_path / "settings.json")
    manager.set_many({"bionodulo.llm.apiKey": "private-test-key", "bionodulo.llm.provider": "custom"})
    result = execute_tool("get_settings", {}, ToolContext(settings_manager=manager))

    assert result["status"] == "ok"
    assert result["result"]["settings"]["bionodulo.llm.apiKey"] == "***"
    assert result["result"]["settings"]["bionodulo.llm.provider"] == "custom"
    assert "private-test-key" not in json.dumps(result)
    assert manager.get("bionodulo.llm.apiKey") == "private-test-key"
