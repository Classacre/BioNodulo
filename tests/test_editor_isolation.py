"""Shared editor processes must never expose per-user filesystem/runtime state."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def editor_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.setenv("BIONODULO_PROXY_SECRET", "editor-test-secret")
    monkeypatch.setenv("BIONODULO_HOSTED_AI", "1")
    from server import create_app

    with TestClient(create_app(), headers={"X-Bionodulo-Session": "editor-test-secret"}) as client:
        yield client


def test_shared_editor_blocks_stateful_routes_and_proxy_prefixes(editor_client: TestClient, tmp_path: Path) -> None:
    for method, path in [
        ("GET", "/settings"),
        ("POST", "/settings"),
        ("POST", "/settings/bionodulo.llm.baseUrl"),
        ("GET", "/workspace/file?path=bionodulo.settings.json"),
        ("GET", "/workspace/download?path=bionodulo.settings.json"),
        ("GET", "/workspace/files"),
        ("POST", "/workspace/cloud-directory-archive"),
        ("POST", "/workspace/cloud-upload-directory"),
        ("POST", "/getting-started/download"),
        ("POST", "/collab/tunnel"),
        ("POST", "/collab/rooms"),
        ("POST", "/workflow_triggers/evaluate"),
        ("POST", "/ai/reproduce-paper"),
        ("GET", "/desktop/session"),
        ("POST", "/runs"),
        ("POST", "/object_info"),
    ]:
        for prefix in ("/api", "/proxy/8000/api"):
            response = editor_client.request(method, prefix + path, json={})
            assert response.status_code == 403, (method, prefix + path, response.status_code)
    assert not (tmp_path / "bionodulo.settings.json").exists()


def test_shared_editor_keeps_stateless_editing_available(editor_client: TestClient) -> None:
    assert editor_client.get("/api/config").json()["editorMode"] is True
    assert editor_client.get("/api/object_info").status_code == 200
    assert editor_client.get("/api/workflow_templates").status_code == 200
    assert editor_client.post("/api/workflow/validate", json={"workflow": {"nodes": [], "edges": []}}).status_code == 200


def test_shared_editor_does_not_load_old_shared_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    monkeypatch.setenv("BIONODULO_PROXY_SECRET", "editor-test-secret")
    path = tmp_path / "bionodulo.settings.json"
    previous = json.dumps({"bionodulo.llm.apiKey": "old-tenant-test-key", "bionodulo.llm.baseUrl": "https://other.example"})
    path.write_text(previous, encoding="utf-8")
    app = create_app()
    assert app.state.settings_manager.get("bionodulo.llm.apiKey") == ""
    assert app.state.settings_manager.get("bionodulo.llm.baseUrl") == ""
    assert path.read_text(encoding="utf-8") == previous


@pytest.mark.parametrize("endpoint", ["/api/ai/chat", "/api/ai/chat/stream"])
def test_shared_chat_uses_only_the_proxy_verified_identity(
    editor_client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str,
) -> None:
    from bionodulo.api import ai_routes
    from bionodulo.ai.hosted import HOSTED_MODEL, HOSTED_PROVIDER, hosted_api_base

    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(steps=[], reply="ok", proposed_workflow=None, proposed_description=None)

    monkeypatch.setattr(ai_routes, "chat_with_tools", fake_chat)
    body = {"message": "hello", "provider": "custom", "model": "untrusted-model"}
    assert editor_client.post(endpoint, json=body).status_code == 401
    assert editor_client.post(endpoint, json=body, headers={"Authorization": "Bearer direct-token"}).status_code == 401
    response = editor_client.post(endpoint, json=body, headers={"X-Bionodulo-Authorization": "Bearer verified-test-token"})
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["api_key"] == "verified-test-token"
    assert calls[0]["provider"] == HOSTED_PROVIDER
    assert calls[0]["model"] == HOSTED_MODEL
    assert calls[0]["api_base"] == hosted_api_base()


@pytest.mark.asyncio
async def test_shared_editor_blocks_assistant_file_execution_and_settings_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bionodulo.ai.tools import ToolContext, aexecute_tool, execute_tool, get_tool

    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")

    def forbidden(*args, **kwargs):
        raise AssertionError("Stateful tool implementation must not be reached")

    for name in (
        "write_custom_node", "download_dataset", "read_workspace_file", "import_skills", "run_feynman",
        "save_as_template", "get_settings", "read_run_logs", "run_workflow", "update_setting", "get_run_events",
    ):
        tool = get_tool(name)
        assert tool is not None
        monkeypatch.setattr(tool, "execute", forbidden)
        for result in (execute_tool(name, {}, ToolContext()), await aexecute_tool(name, {}, ToolContext())):
            assert result["status"] == "error"
            assert "disabled in shared editor mode" in result["error"]


def test_shared_editor_keeps_request_scoped_graph_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from bionodulo.ai.tools import ToolContext, execute_tool

    monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
    first = ToolContext(workflow={"name": "First", "nodes": [], "edges": []})
    second = ToolContext(workflow={"name": "Second", "nodes": [], "edges": []})
    result = execute_tool("set_workflow_name", {"name": "Edited"}, first)
    assert result["status"] == "ok"
    assert second.workflow["name"] == "Second"


def test_shared_editor_skills_cannot_read_other_tenants_packs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from bionodulo.ai import skills

    skills.invalidate_cache()
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", tmp_path / "bundled")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "user")
    for folder in (tmp_path / "bundled", tmp_path / "user", tmp_path / "workspace" / "skills"):
        folder.mkdir(parents=True)
        name = "private" if folder.name == "skills" else folder.name
        (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test\n---\nTest body.", encoding="utf-8")
    try:
        monkeypatch.delenv("BIONODULO_EDITOR_MODE", raising=False)
        assert skills.list_skills(tmp_path / "workspace")["count"] == 3
        monkeypatch.setenv("BIONODULO_EDITOR_MODE", "1")
        result = skills.list_skills(tmp_path / "workspace")
        assert [skill["name"] for skill in result["skills"]] == ["bundled"]
        assert skills.get_skill_body("private", tmp_path / "workspace") is None
    finally:
        skills.invalidate_cache()
