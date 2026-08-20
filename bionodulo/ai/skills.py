"""Skill packs for the BioNodulo AI assistant (Claude/ZCode SKILL.md format).

A *skill* is a directory containing a ``SKILL.md`` file: a small YAML
frontmatter block (flat ``key: value`` pairs, at minimum ``name`` and
``description``) followed by a markdown body describing a workflow the
assistant can adopt on demand (literature review, deep research, structure
prediction, replication, ...).

Discovery scans three roots, in precedence order — later roots override
earlier ones *by skill name*:

1. bundled:  ``bionodulo/ai/bundled_skills/`` (ships with the package; the
   Feynman research-agent library lives under the ``feynman/`` prefix, so
   discovery recurses into subdirectories)
2. user:     ``~/.bionodulo/skills/``
3. workspace: ``<workspace_dir>/skills/``

The frontmatter parser is hand-rolled on purpose: skill frontmatter is flat
``key: value`` (optionally quoted), so no PyYAML dependency is taken on for
it, and bodies are never parsed.

SECURITY: skill bodies are PROMPT CONTENT for the LLM only. They are returned
to the model as instructions to read and follow. This module never executes,
imports, compiles, or evaluates anything read from a skill file, and callers
must not either. The optional ``run_feynman`` tool bridges to an external
CLI the *user* installed; it never derives commands from a skill body by
itself.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.ai.tools import ToolContext, ToolDefinition, ToolParameter, _workspace_root

logger = logging.getLogger(__name__)

BUNDLED_SKILLS_DIR = Path(__file__).resolve().parent / "bundled_skills"
USER_SKILLS_DIR = Path.home() / ".bionodulo" / "skills"

MAX_FEYNMAN_OUTPUT_BYTES = 50 * 1024


# ---------------------------------------------------------------------------
# Frontmatter parsing (hand-rolled; flat key: value only)
# ---------------------------------------------------------------------------


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_skill_md(text: str) -> tuple[dict[str, str], str] | None:
    """Split a SKILL.md into (frontmatter, body). Returns None when malformed."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    frontmatter: dict[str, str] = {}
    closing = None
    for idx in range(1, len(lines)):
        line = lines[idx]
        if line.strip() in ("---", "..."):
            closing = idx
            break
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, raw_value = line.partition(":")
        if not sep or not key.strip():
            return None
        frontmatter[key.strip()] = _unquote(raw_value)
    if closing is None:
        return None
    body = "\n".join(lines[closing + 1 :]).strip()
    return frontmatter, body


# ---------------------------------------------------------------------------
# Skill model + discovery
# ---------------------------------------------------------------------------


@dataclass
class Skill:
    """A discovered skill pack. The body is read lazily on first access."""

    name: str
    description: str
    path: Path
    source: str  # "bundled" | "user" | "workspace"
    _body: str | None = field(default=None, repr=False)

    @property
    def body(self) -> str:
        if self._body is None:
            try:
                text = self.path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self._body = ""
                logger.warning("Could not read skill %s: %s", self.path, exc)
                return self._body
            parsed = parse_skill_md(text)
            self._body = parsed[1] if parsed else text
        return self._body

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "source": self.source}


#: Discovery cache, keyed by the workspace dir ("" means "no workspace").
SKILL_CACHE: dict[str, dict[str, Skill]] = {}
SKILL_ERRORS: dict[str, list[dict[str, str]]] = {}


def _cache_key(workspace_dir: Path | None) -> str:
    return str(workspace_dir.resolve()) if workspace_dir is not None else ""


def _scan_root(root: Path, source: str, skills: dict[str, Skill], errors: list[dict[str, str]]) -> None:
    """Register every ``SKILL.md`` under ``root``; later roots override by name."""
    if not root.is_dir():
        return
    for skill_file in sorted(root.rglob("SKILL.md")):
        if not skill_file.is_file():
            continue
        try:
            text = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append({"path": str(skill_file), "error": str(exc)})
            continue
        parsed = parse_skill_md(text)
        if parsed is None:
            errors.append({"path": str(skill_file), "error": "Missing or malformed frontmatter"})
            continue
        frontmatter, _body = parsed
        name = frontmatter.get("name", "").strip()
        description = frontmatter.get("description", "").strip()
        if not name or not description:
            errors.append(
                {"path": str(skill_file), "error": "Frontmatter must define 'name' and 'description'"}
            )
            continue
        skills[name] = Skill(name=name, description=description, path=skill_file, source=source)


def discover_skills(workspace_dir: Path | None = None) -> dict[str, Skill]:
    """Discover skills across bundled, user, and workspace roots (cached)."""
    key = _cache_key(workspace_dir)
    if key in SKILL_CACHE:
        return SKILL_CACHE[key]
    skills: dict[str, Skill] = {}
    errors: list[dict[str, str]] = []
    _scan_root(BUNDLED_SKILLS_DIR, "bundled", skills, errors)
    _scan_root(USER_SKILLS_DIR, "user", skills, errors)
    if workspace_dir is not None:
        _scan_root(Path(workspace_dir) / "skills", "workspace", skills, errors)
    SKILL_CACHE[key] = skills
    SKILL_ERRORS[key] = errors
    return skills


def invalidate_cache(workspace_dir: Path | None = None) -> None:
    """Drop cached discovery (e.g. after import_skills writes new packs)."""
    if workspace_dir is None:
        SKILL_CACHE.clear()
        SKILL_ERRORS.clear()
        return
    SKILL_CACHE.pop(_cache_key(workspace_dir), None)
    SKILL_ERRORS.pop(_cache_key(workspace_dir), None)


def list_skills(workspace_dir: Path | None = None) -> dict[str, Any]:
    """Cheap listing: name/description/source only, no bodies read."""
    workspace = Path(workspace_dir) if workspace_dir is not None else None
    skills = discover_skills(workspace)
    errors = SKILL_ERRORS.get(_cache_key(workspace), [])
    summaries = [skill.summary() for skill in sorted(skills.values(), key=lambda s: s.name)]
    return {"skills": summaries, "count": len(summaries), "errors": errors}


def get_skill(name: str, workspace_dir: Path | None = None) -> Skill | None:
    workspace = Path(workspace_dir) if workspace_dir is not None else None
    return discover_skills(workspace).get(name)


def get_skill_body(name: str, workspace_dir: Path | None = None) -> str | None:
    skill = get_skill(name, workspace_dir)
    return skill.body if skill else None


# ---------------------------------------------------------------------------
# Assistant tools
# ---------------------------------------------------------------------------


def _list_skills_tool(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    return list_skills(_workspace_root(ctx))


def _load_skill_tool(ctx: ToolContext, name: str, **kwargs: Any) -> dict[str, Any]:
    skill = get_skill(name, _workspace_root(ctx))
    if skill is None:
        available = sorted(discover_skills(_workspace_root(ctx)))
        return {"error": f"Skill '{name}' not found.", "available": available}
    return {**skill.summary(), "body": skill.body, "path": str(skill.path)}


def _import_skills(ctx: ToolContext, path: str, **kwargs: Any) -> dict[str, Any]:
    """Copy skill pack(s) from ``path`` into the workspace skills directory."""
    source = Path(path).expanduser()
    if not source.exists():
        return {"error": f"Source path does not exist: {path}"}
    if source.is_file():
        if source.name != "SKILL.md":
            return {"error": "Source file must be a SKILL.md (or pass its parent directory)."}
        source = source.parent

    # A directory that is itself a skill, or a tree containing skill dirs.
    candidates = [source] if (source / "SKILL.md").is_file() else sorted(
        {p.parent for p in source.rglob("SKILL.md") if p.is_file()}
    )
    if not candidates:
        return {"error": f"No SKILL.md found under: {path}"}

    skills_root = (_workspace_root(ctx) / "skills").resolve()
    imported: list[str] = []
    errors: list[dict[str, str]] = []
    for candidate in candidates:
        parsed = None
        try:
            parsed = parse_skill_md((candidate / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            errors.append({"path": str(candidate), "error": str(exc)})
            continue
        if parsed is None:
            errors.append({"path": str(candidate), "error": "Missing or malformed frontmatter"})
            continue
        frontmatter, _body = parsed
        name = frontmatter.get("name", "").strip()
        if not name or not frontmatter.get("description", "").strip():
            errors.append({"path": str(candidate), "error": "Frontmatter must define 'name' and 'description'"})
            continue
        dest = (skills_root / name).resolve()
        try:
            dest.relative_to(skills_root)
        except ValueError:
            errors.append({"path": str(candidate), "error": f"Skill name '{name}' escapes the workspace"})
            continue
        try:
            skills_root.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(candidate, dest)
        except OSError as exc:
            errors.append({"path": str(candidate), "error": str(exc)})
            continue
        imported.append(name)

    if imported:
        invalidate_cache(_workspace_root(ctx))
    result: dict[str, Any] = {"imported": imported, "count": len(imported), "skills_dir": str(skills_root)}
    if errors:
        result["errors"] = errors
    if not imported and errors:
        result["error"] = "No skills could be imported."
    return result


def _run_feynman(ctx: ToolContext, args: list[str] | None = None, timeout_s: int = 120, **kwargs: Any) -> dict[str, Any]:
    """Run the external ``feynman`` CLI when the user has it installed.

    Some bundled Feynman skills reference ``feynman`` CLI commands. The CLI is
    optional: when it is not on PATH this returns a structured error so the
    assistant can fall back to doing the work itself. Never invoked with
    ``shell=True``; output is capped at 50 KB per stream.
    """
    executable = shutil.which("feynman") or shutil.which("feynman.cmd")
    if executable is None:
        return {
            "error": "feynman CLI not installed",
            "install": "https://feynman.is",
            "available": False,
        }
    argv = [executable, *[str(a) for a in (args or [])]]
    try:
        timeout = max(1, min(int(timeout_s), 3600))
    except (TypeError, ValueError):
        timeout = 120
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"feynman timed out after {timeout}s", "available": True, "args": args or []}
    except OSError as exc:
        return {"error": f"Could not run feynman: {exc}", "available": True}
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[:MAX_FEYNMAN_OUTPUT_BYTES],
        "stderr": (completed.stderr or "")[:MAX_FEYNMAN_OUTPUT_BYTES],
    }


SKILL_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        "list_skills",
        "List available skill packs (SKILL.md format): name, description, and source (bundled/user/workspace). Bodies are not read. Use this when a task looks like literature review, deep research, structure prediction, replication, or another packaged workflow.",
        [],
        _list_skills_tool,
    ),
    ToolDefinition(
        "load_skill",
        "Load a skill pack's full markdown body so you can follow its workflow. Skill bodies are instructions to read, never code to execute. Call list_skills first if unsure which skills exist.",
        [ToolParameter("name", "string", "Skill name as reported by list_skills")],
        _load_skill_tool,
    ),
    ToolDefinition(
        "import_skills",
        "Import skill pack(s) into the workspace skills directory. Accepts a directory containing SKILL.md, a tree of skill directories, or a path to a single SKILL.md. Every skill must define name+description; imported names are returned and discovery is refreshed.",
        [ToolParameter("path", "string", "Source directory or SKILL.md path to import from")],
        _import_skills,
        action=True,
    ),
    ToolDefinition(
        "run_feynman",
        "Run the external feynman CLI with the given arguments, only when a loaded skill body explicitly calls for feynman CLI commands and the user has it installed. Returns a structured error with an install link when the CLI is absent.",
        [
            ToolParameter("args", "array", "CLI arguments, e.g. [\"research\", \"--topic\", \"...\"]", required=False, default=None),
            ToolParameter("timeout_s", "integer", "Hard timeout in seconds (<=3600)", required=False, default=120),
        ],
        _run_feynman,
        action=True,
    ),
]


__all__ = [
    "BUNDLED_SKILLS_DIR",
    "SKILL_CACHE",
    "SKILL_TOOLS",
    "USER_SKILLS_DIR",
    "Skill",
    "discover_skills",
    "get_skill",
    "get_skill_body",
    "invalidate_cache",
    "list_skills",
    "parse_skill_md",
]
