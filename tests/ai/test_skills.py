"""Skill packs: discovery precedence, lazy loading, tools, and the feynman bridge.

Skill discovery merges three roots (bundled < user < workspace, overriding by
name) and caches per workspace; these tests point the bundled/user roots at
tmp dirs so the suite stays hermetic. ``run_feynman`` is exercised with
``shutil.which`` monkeypatched: once to a missing CLI (structured error) and
once to ``sys.executable`` so a ``-c`` shim stands in for the real binary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.ai import skills
from bionodulo.ai.skills import Skill
from bionodulo.ai.tools import ToolContext, aexecute_tool, execute_tool, get_tool


@pytest.fixture(autouse=True)
def _clean_skill_cache():
    skills.invalidate_cache()
    yield
    skills.invalidate_cache()


def _write_skill(root: Path, name: str, description: str, body: str = "Do the thing.") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
        newline="\n",
    )
    return skill_dir


def _ctx(workspace: Path) -> ToolContext:
    return ToolContext(settings=SimpleNamespace(project_root=str(workspace)))


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def test_parse_skill_md_quoted_values() -> None:
    parsed = skills.parse_skill_md('---\nname: "my-skill"\ndescription: \'A: quoted thing\'\n---\n\nBody\n')
    assert parsed is not None
    frontmatter, body = parsed
    assert frontmatter == {"name": "my-skill", "description": "A: quoted thing"}
    assert body == "Body"


def test_parse_skill_md_rejects_missing_frontmatter() -> None:
    assert skills.parse_skill_md("# No frontmatter here\n") is None
    assert skills.parse_skill_md("---\nname: unterminated\n") is None


# ---------------------------------------------------------------------------
# Discovery + precedence
# ---------------------------------------------------------------------------


def test_discovery_precedence_and_lazy_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    workspace = tmp_path / "ws"
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", bundled)
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", user)

    # Bundled root recurses into prefix dirs (e.g. bundled_skills/feynman/<name>).
    _write_skill(bundled / "feynman", "alpha", "bundled alpha", body="bundled body")
    _write_skill(bundled / "feynman", "bundled-only", "only in bundled")
    _write_skill(user, "alpha", "user alpha")
    _write_skill(user, "beta", "user beta")
    _write_skill(workspace / "skills", "beta", "workspace beta", body="workspace body")

    # No workspace: user overrides bundled, bundled-only still visible.
    result = skills.list_skills(None)
    by_name = {s["name"]: s for s in result["skills"]}
    assert by_name["alpha"]["source"] == "user"
    assert by_name["bundled-only"]["source"] == "bundled"
    assert "beta" in by_name

    # Workspace overrides user.
    result = skills.list_skills(workspace)
    by_name = {s["name"]: s for s in result["skills"]}
    assert by_name["beta"]["source"] == "workspace"
    assert by_name["beta"]["description"] == "workspace beta"
    assert by_name["alpha"]["source"] == "user"  # untouched by the workspace layer

    # Bodies are not read during discovery; loading is lazy.
    skill = skills.get_skill("beta", workspace)
    assert isinstance(skill, Skill)
    assert skill._body is None
    assert "workspace body" in skill.body


def test_malformed_skill_skipped_with_error_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundled = tmp_path / "bundled"
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", bundled)
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "no-user")

    bad_dir = bundled / "feynman" / "broken"
    bad_dir.mkdir(parents=True)
    (bad_dir / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8", newline="\n")
    _write_skill(bundled / "feynman", "good", "a good skill")

    result = skills.list_skills(None)
    assert [s["name"] for s in result["skills"]] == ["good"]
    assert len(result["errors"]) == 1
    assert "broken" in result["errors"][0]["path"]


def test_bundled_feynman_skills_discovered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The shipped feynman library is discoverable with no workspace at all."""
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "no-user-skills")
    result = skills.list_skills(None)
    by_name = {s["name"]: s for s in result["skills"]}
    assert by_name["deep-research"]["source"] == "bundled"
    assert by_name["literature-review"]["source"] == "bundled"
    assert "boltz" in by_name
    # The description is real frontmatter, not the directory name.
    assert by_name["deep-research"]["description"]


# ---------------------------------------------------------------------------
# list/load/import tools
# ---------------------------------------------------------------------------


def test_list_and_load_skill_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", tmp_path / "no-bundled")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "no-user")
    _write_skill(tmp_path / "ws" / "skills", "review", "review things", body="Step 1. Step 2.")
    ctx = _ctx(tmp_path / "ws")

    listed = execute_tool("list_skills", {}, ctx)
    assert listed["status"] == "ok"
    assert listed["result"]["skills"] == [{"name": "review", "description": "review things", "source": "workspace"}]

    loaded = execute_tool("load_skill", {"name": "review"}, ctx)
    assert loaded["status"] == "ok"
    assert "Step 1. Step 2." in loaded["result"]["body"]
    assert loaded["result"]["source"] == "workspace"

    missing = execute_tool("load_skill", {"name": "nope"}, ctx)
    assert missing["status"] == "error"
    assert "available" in missing["result"]


def test_import_skills_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", tmp_path / "no-bundled")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "no-user")
    workspace = tmp_path / "ws"
    source = tmp_path / "external"
    _write_skill(source, "one", "first skill")
    _write_skill(source, "two", "second skill")
    ctx = _ctx(workspace)

    result = execute_tool("import_skills", {"path": str(source)}, ctx)
    assert result["status"] == "ok"
    assert result["result"]["imported"] == ["one", "two"]
    assert (workspace / "skills" / "one" / "SKILL.md").is_file()

    # Discovery was refreshed: the imported skills now list as workspace skills.
    listed = skills.list_skills(workspace)
    by_name = {s["name"]: s for s in listed["skills"]}
    assert by_name["one"]["source"] == "workspace"
    assert by_name["two"]["source"] == "workspace"

    # A single SKILL.md's parent dir also imports.
    single = _write_skill(tmp_path / "solo-skill", "solo", "lonely skill")
    result = execute_tool("import_skills", {"path": str(single / "SKILL.md")}, ctx)
    assert result["result"]["imported"] == ["solo"]


def test_import_skills_missing_source(tmp_path: Path) -> None:
    result = execute_tool("import_skills", {"path": str(tmp_path / "does-not-exist")}, _ctx(tmp_path / "ws"))
    assert result["status"] == "error"
    assert "does not exist" in result["error"]


def test_import_skills_rejects_workspace_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", tmp_path / "no-bundled")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "no-user")
    workspace = tmp_path / "ws"
    source = tmp_path / "evil"
    source.mkdir()
    # The directory itself is well-formed; the SKILL.md frontmatter carries a
    # traversal name, which must be rejected before anything is copied.
    (source / "SKILL.md").write_text(
        "---\nname: ../../escape-hatch\ndescription: malicious name\n---\n\nBody\n",
        encoding="utf-8",
        newline="\n",
    )
    ctx = _ctx(workspace)

    result = execute_tool("import_skills", {"path": str(source)}, ctx)
    assert result["status"] == "error"
    assert result["result"]["imported"] == []
    assert "escapes the workspace" in result["result"]["errors"][0]["error"]
    assert not (tmp_path / "escape-hatch").exists()


# ---------------------------------------------------------------------------
# run_feynman bridge
# ---------------------------------------------------------------------------


def test_run_feynman_not_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(skills.shutil, "which", lambda name: None)
    result = execute_tool("run_feynman", {"args": ["research"]}, _ctx(tmp_path))
    assert result["status"] == "error"
    inner = result["result"]
    assert inner["error"] == "feynman CLI not installed"
    assert inner["install"] == "https://feynman.is"
    assert inner["available"] is False


def test_run_feynman_installed_captures_stdout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(skills.shutil, "which", lambda name: sys.executable)
    result = execute_tool("run_feynman", {"args": ["-c", "print('hello feynman')"]}, _ctx(tmp_path))
    assert result["status"] == "ok"
    inner = result["result"]
    assert inner["available"] is True
    assert inner["returncode"] == 0
    assert "hello feynman" in inner["stdout"]


def test_run_feynman_timeout_enforced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(skills.shutil, "which", lambda name: sys.executable)
    result = execute_tool(
        "run_feynman",
        {"args": ["-c", "import time; time.sleep(30)"], "timeout_s": 1},
        _ctx(tmp_path),
    )
    assert result["status"] == "error"
    assert "timed out" in result["result"]["error"]


def test_skill_tools_registered() -> None:
    for name in ("list_skills", "load_skill", "import_skills", "run_feynman"):
        assert get_tool(name) is not None, name


@pytest.mark.asyncio
async def test_load_skill_via_aexecute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skills, "BUNDLED_SKILLS_DIR", tmp_path / "no-bundled")
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "no-user")
    _write_skill(tmp_path / "ws" / "skills", "async-skill", "async body check", body="async body")
    result = await aexecute_tool("load_skill", {"name": "async-skill"}, _ctx(tmp_path / "ws"))
    assert result["status"] == "ok"
    assert "async body" in result["result"]["body"]
