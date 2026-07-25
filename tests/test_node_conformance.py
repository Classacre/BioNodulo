"""Node-conformance gate: the static node standard must hold for every node.

This runs the node linter (scripts/node_linter.py) in-process and FAILS the
suite on any ERROR-level finding. It's the cheap, always-on half of the node
standard — it can't prove a tool exits 0 (that's the smoke harness's job, run on
a tool-provisioned box), but it catches the structural contract violations that
caused real template failures: list-command shell operators without SHELL,
known-bad CLI flags, stdout/hash-named tools without PLAN_OUTPUTS, RETURN_TYPES/
RETURN_NAMES mismatch, and in-process imports missing from the worker env.

Because it also runs at template-save time, USER-authored nodes are held to the
same contract — the whole point of the standard.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE_METADATA = ROOT / "bionodulo" / "nodes" / "node_metadata.json"


def unswept_node_ids(advertised: Iterable[str], loaded: Iterable[str]) -> tuple[str, ...]:
    """Node IDs the palette advertises that the conformance sweep never sees.

    The sweep below iterates the nodes that successfully *loaded*, so a module
    that fails to import silently drops out of it — the gate passes while the
    node is unusable. Comparing against the advertised manifest is what makes
    that failure visible.
    """
    return tuple(sorted(set(advertised) - set(loaded)))


def _load_linter():
    spec = importlib.util.spec_from_file_location(
        "node_linter", ROOT / "scripts" / "node_linter.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["node_linter"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_all_builtin_nodes_pass_static_conformance() -> None:
    linter = _load_linter()
    from bionodulo.nodes.registry import NodeRegistry

    registry = NodeRegistry()
    registry.load_builtin_nodes()
    nodes = dict(registry._nodes)

    errors = []
    for nid, cls in sorted(nodes.items()):
        if cls is None:
            continue
        for level, node_id, msg in linter.lint_node(nid, cls):
            if level == "ERROR":
                errors.append(f"{node_id}: {msg}")

    assert not errors, (
        "Node standard violations (ERROR level) — fix the node or update the "
        "standard in scripts/node_linter.py:\n  " + "\n  ".join(errors)
    )


def test_conformance_sweep_covers_every_advertised_node() -> None:
    """Every node the palette offers must actually reach the linter.

    Without this, a module that fails to import vanishes from the sweep and the
    gate reports success on a catalog it never inspected.
    """
    from bionodulo.nodes.registry import NodeRegistry

    registry = NodeRegistry()
    registry.load_builtin_nodes()

    advertised = json.loads(NODE_METADATA.read_text(encoding="utf-8"))
    # Non-vacuity: an empty manifest would make this assertion meaningless.
    assert len(advertised) > 900, "node metadata manifest looks truncated"
    missing = unswept_node_ids(advertised, registry._nodes)

    assert not missing, (
        f"{len(missing)} advertised node(s) never reached the conformance sweep — "
        "they are offered in the palette but cannot be imported:\n  "
        + "\n  ".join(missing)
    )


def test_coverage_check_detects_an_unloadable_node() -> None:
    """Guard the guard: the coverage check must notice a node that never loads."""
    assert unswept_node_ids(["a", "b"], ["a", "b"]) == ()
    assert unswept_node_ids(["a", "b"], ["a"]) == ("b",)


def test_linter_detects_known_bad_patterns() -> None:
    """Guard the guard: the linter must still catch the historical bug classes."""
    linter = _load_linter()
    from bionodulo.nodes.command_node import CommandNode

    class ListRedirect(CommandNode):  # mafft-class bug
        NODE_ID = "t_listredirect"
        SHELL = False
        RETURN_TYPES = ("ALIGNMENT",)
        RETURN_NAMES = ("a",)

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"input": ("FASTA", {})}, "optional": {}}

        @classmethod
        def render_command(cls, inputs):
            return ["mafft", "x", ">", "out.fa"]

    class BadFlag(CommandNode):  # sage/pggb-class bug
        NODE_ID = "t_badflag"
        SHELL = False
        RETURN_TYPES = ("TSV",)
        RETURN_NAMES = ("r",)

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"spectra_files": ("FILE", {})}, "optional": {}}

        @classmethod
        def render_command(cls, inputs):
            return ["sage", "cfg", "--threads", "8"]

    levels_lr = {lvl for lvl, _, _ in linter.lint_node("t_listredirect", ListRedirect)}
    levels_bf = {lvl for lvl, _, _ in linter.lint_node("t_badflag", BadFlag)}
    assert "ERROR" in levels_lr, "linter must flag a list command with a shell operator"
    assert "ERROR" in levels_bf, "linter must flag a known-bad tool flag"
