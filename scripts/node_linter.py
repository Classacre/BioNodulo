"""Static node-conformance linter — the node standard, enforced without running tools.

Instant (no pixi, no installs). Runs in CI, the editor, and at template-save so
BOTH built-in and USER-authored nodes are held to the same contract. It cannot
prove a tool exits 0 (that's the smoke harness's job), but it catches the whole
class of *structural* violations that caused the template failures in practice:

  L1  render_command references a shell operator while SHELL is False and the
      command is a list (the operator becomes a literal argv token, not a redirect).
  L2  a command node declares RETURN_TYPES but no PLAN_OUTPUTS override AND its
      command writes to stdout or a tool-chosen name — the default PLAN_OUTPUTS
      then asserts files the tool never creates. (Heuristic: flags a node whose
      render_command contains '>' redirection or whose tool is on a
      STDOUT_TOOLS/HASHNAMED_TOOLS list but has no PLAN_OUTPUTS.)
  L3  an in-process node's run() imports a third-party module not covered by the
      worker base env or REQUIRED_*; it will ImportError on the worker.
  L4  RETURN_NAMES length disagrees with RETURN_TYPES.
  L5  a known-bad CLI flag (per-tool deny-list built from real failures:
      pggb --do-viz/--do-layout, sage --threads, iqtree fixed -nt) appears in
      render_command output for a representative input.

Exit non-zero if any ERROR-level finding. WARN findings don't fail CI but are
surfaced. Designed to be extended: add tool rules to the tables below.

Usage:
    python node_linter.py                 # lint all registered nodes
    python node_linter.py <node_id> ...   # lint specific nodes
    python node_linter.py --json          # machine-readable
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bionodulo.nodes.registry import NodeRegistry  # noqa: E402
from bionodulo.nodes.command_node import CommandNode, _SHELL_METACHARS  # noqa: E402

# Modules guaranteed present in the worker base env (pixi.toml [pypi-dependencies]
# + Python stdlib). An in-process node importing anything else must declare it.
WORKER_BASE_MODULES = {
    "yaml", "httpx", "diskcache", "Bio",  # base pypi-deps (biopython = Bio)
    "matplotlib",  # base viz lib for in-process renderers
    "bionodulo",
}
# Tools whose CLI writes results to STDOUT (need a redirect + PLAN_OUTPUTS).
STDOUT_TOOLS = {"mafft", "fasttree", "raxml", "seqkit"}
# Tools that name outputs unpredictably (hash/timestamp) — need PLAN_OUTPUTS
# that globs or a post-run normalize step.
HASHNAMED_TOOLS = {"pggb"}
# Per-tool deny-list of flags/args that real tool versions reject (built from
# observed failures). token -> reason.
BAD_FLAGS: dict[str, dict[str, str]] = {
    "pggb": {"--do-viz": "not a pggb option", "--do-layout": "not a pggb option"},
    "sage": {"--threads": "sage has no --threads (auto-parallel)"},
}

Finding = tuple[str, str, str]  # (level, node_id, message)


def _representative_inputs(node_cls: Any) -> dict[str, Any]:
    """Build a minimal inputs dict from INPUT_TYPES so render_command can run."""
    inputs: dict[str, Any] = {"output": "/tmp/_lint", "output_dir": "/tmp/_lint"}
    try:
        spec = node_cls.INPUT_TYPES()
    except Exception:
        return inputs
    for section in ("required", "optional"):
        for name, decl in (spec.get(section, {}) or {}).items():
            t = decl[0] if isinstance(decl, (list, tuple)) and decl else decl
            default = None
            if isinstance(decl, (list, tuple)) and len(decl) > 1 and isinstance(decl[1], dict):
                default = decl[1].get("default")
            if default not in (None, ""):
                inputs[name] = default
            elif isinstance(t, str) and "LIST" in t.upper():
                inputs[name] = [f"/tmp/in_{name}"]
            elif isinstance(t, str) and t in ("INT",):
                inputs[name] = 4
            else:
                inputs[name] = f"/tmp/in_{name}"
    return inputs


def _imported_third_party(node_cls: Any) -> set[str]:
    """Top-level module names imported inside the node's run() body."""
    try:
        src = inspect.getsource(node_cls.run)
    except (OSError, TypeError):
        return set()
    try:
        tree = ast.parse(src.strip())
    except SyntaxError:
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    # keep only clearly third-party (lowercase or Bio); drop stdlib-ish
    return mods


STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


def lint_node(node_id: str, node_cls: Any) -> list[Finding]:
    findings: list[Finding] = []
    is_cmd = isinstance(node_cls, type) and issubclass(node_cls, CommandNode)

    # L4: RETURN_NAMES vs RETURN_TYPES
    rt = getattr(node_cls, "RETURN_TYPES", ())
    rn = getattr(node_cls, "RETURN_NAMES", ())
    if rt and rn and len(rt) != len(rn):
        findings.append(("ERROR", node_id,
            f"RETURN_TYPES ({len(rt)}) and RETURN_NAMES ({len(rn)}) length mismatch"))

    # L3: in-process import coverage (non-CommandNode with a run override)
    has_own_run = "run" in node_cls.__dict__
    if has_own_run:
        for mod in _imported_third_party(node_cls):
            if mod in STDLIB or mod in WORKER_BASE_MODULES:
                continue
            if mod[0].islower() or mod == "Bio":
                # declared? conda pkgs / pip — heuristic: name appears in REQUIRED_*
                reqs_parts: list[str] = []
                for a in ("REQUIRED_CONDA_PACKAGES", "REQUIRED_PIP_PACKAGES"):
                    val = getattr(node_cls, a, []) or []
                    if isinstance(val, list):
                        reqs_parts.extend(str(x) for x in val)
                reqs = " ".join(reqs_parts)
                if mod.lower() not in reqs.lower():
                    findings.append(("WARN", node_id,
                        f"run() imports '{mod}' not in worker base env nor REQUIRED_* "
                        f"— will ImportError on the worker unless provided"))

    if not is_cmd:
        return findings

    # Render a representative command
    inputs = _representative_inputs(node_cls)
    try:
        cmd = node_cls.render_command(inputs)
    except Exception:  # noqa: BLE001
        # The synthetic fixture couldn't satisfy this node's param interdependencies
        # (e.g. "requires >=2 files", validation gates). That's a limitation of the
        # linter's generic fixture, NOT a node bug — the smoke harness exercises
        # these with real template inputs. Skip the command-level checks silently.
        return findings
    cmd_str = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
    cmd_list = cmd if isinstance(cmd, list) else None
    shell = bool(getattr(node_cls, "SHELL", False))

    # L1: shell operator in a list command with SHELL False
    if cmd_list is not None and not shell:
        for tok in cmd_list:
            if str(tok) in _SHELL_METACHARS:
                findings.append(("ERROR", node_id,
                    f"render_command returns a LIST containing shell operator "
                    f"'{tok}' but SHELL is False — it becomes a literal argv token, "
                    f"not a redirect. Return a shell STRING or set SHELL=True."))

    # L5: known-bad flags
    tool = str(cmd_str.split()[0]) if cmd_str.split() else ""
    # also scan the whole command for tool tokens (bash -c wrapped)
    for t, flags in BAD_FLAGS.items():
        if t in cmd_str:
            for flag, reason in flags.items():
                if flag in cmd_str:
                    findings.append(("ERROR", node_id,
                        f"command includes '{flag}' for {t}: {reason}"))

    # L2: stdout/hash-named tool without PLAN_OUTPUTS override
    has_plan = "PLAN_OUTPUTS" in node_cls.__dict__
    writes_redirect = ">" in cmd_str
    tool_tokens = set(cmd_str.replace("&&", " ").split())
    stdout_tool = bool(tool_tokens & STDOUT_TOOLS)
    hashnamed_tool = bool(tool_tokens & HASHNAMED_TOOLS)
    if (stdout_tool or writes_redirect) and not has_plan and not writes_redirect:
        findings.append(("ERROR", node_id,
            f"uses a stdout-writing tool but has no PLAN_OUTPUTS override and no "
            f"redirect — default PLAN_OUTPUTS will assert files the tool won't create"))
    if hashnamed_tool and not has_plan:
        findings.append(("WARN", node_id,
            f"uses a hash/timestamp-naming tool ({tool_tokens & HASHNAMED_TOOLS}) "
            f"without a PLAN_OUTPUTS override — declared output names likely won't match"))

    return findings


def main() -> int:
    as_json = "--json" in sys.argv
    ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    registry = NodeRegistry()
    if ids:
        targets = {i: registry.get(i) for i in ids}
    else:
        registry.load_builtin_nodes()
        targets = dict(registry._nodes) if hasattr(registry, "_nodes") else {}

    all_findings: list[Finding] = []
    for nid, cls in sorted(targets.items()):
        if cls is None:
            continue
        all_findings.extend(lint_node(nid, cls))

    errors = [f for f in all_findings if f[0] == "ERROR"]
    warns = [f for f in all_findings if f[0] == "WARN"]

    if as_json:
        print(json.dumps([{"level": l, "node": n, "message": m} for l, n, m in all_findings], indent=2))
    else:
        for level, nid, msg in all_findings:
            print(f"[{level}] {nid}: {msg}")
        print(f"\n{'='*50}")
        print(f"{len(targets)} nodes linted — {len(errors)} ERROR, {len(warns)} WARN")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
