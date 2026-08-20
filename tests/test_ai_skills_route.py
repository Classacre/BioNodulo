"""GET /ai/skills: the payload behind the chat input's slash-command autocomplete.

The route is a thin wrapper over ``bionodulo.ai.skills.list_skills`` — these
tests point the bundled/user discovery roots at tmp dirs (same trick as
``tests/ai/test_skills.py``) so the suite stays hermetic, and mount the router
on a bare FastAPI app since the endpoint needs no registry or run queue.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bionodulo.ai import skills
from bionodulo.api.ai_routes import ai_router


@pytest.fixture(autouse=True)
def _clean_skill_cache():
    skills.invalidate_cache()
    yield
    skills.invalidate_cache()


def _write_skill(root: Path, name: str, description: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nDo the thing.\n",
        encoding="utf-8",
        newline="\n",
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(ai_router)
    return TestClient(app)


@pytest.fixture()
def _isolated_skill_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", tmp_path / "bundled")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "user")
    return tmp_path


@pytest.mark.usefixtures("_isolated_skill_roots")
def test_skills_route_lists_name_description_and_source(tmp_path: Path) -> None:
    _write_skill(tmp_path / "bundled", "rnaseq", "RNA-seq pipeline helper")
    _write_skill(tmp_path / "user", "qc", "QC helper")

    response = _client().get("/ai/skills")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["errors"] == []
    # Sorted by name; bodies are never read for the listing.
    assert payload["skills"] == [
        {"name": "qc", "description": "QC helper", "source": "user"},
        {"name": "rnaseq", "description": "RNA-seq pipeline helper", "source": "bundled"},
    ]


@pytest.mark.usefixtures("_isolated_skill_roots")
def test_skills_route_returns_an_empty_list_when_no_packs_exist() -> None:
    response = _client().get("/ai/skills")

    assert response.status_code == 200
    payload = response.json()
    assert payload["skills"] == []
    assert payload["count"] == 0
