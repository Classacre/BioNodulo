#!/usr/bin/env python3
"""Generate the builtin-node index (§44).

Walks ``bionodulo.nodes.builtin`` once and writes ``node_index.json`` mapping
every builtin node_id → the module that defines it. The registry uses this to
LAZILY import only the module holding a requested node (worker path), instead of
eagerly importing all ~1k (soon 10k+) modules on every run.

This is a BUILD-TIME step: run it whenever builtin nodes change. A test
(``tests/test_node_index.py``) asserts the committed index matches a live walk,
so it cannot silently drift.

Usage:  python scripts/gen_node_index.py         # writes bionodulo/nodes/node_index.json
        python scripts/gen_node_index.py --check  # exit 1 if stale (CI)
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
from pathlib import Path

# Ensure the repo root is importable when run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bionodulo.nodes.base import BaseNode  # noqa: E402
from bionodulo.nodes.command_node import CommandNode  # noqa: E402

INDEX_PATH = _REPO_ROOT / "bionodulo" / "nodes" / "node_index.json"
METADATA_PATH = _REPO_ROOT / "bionodulo" / "nodes" / "node_metadata.json"


def build_index() -> dict[str, str]:
    """Return {node_id: module_name} for every builtin node (sorted)."""
    import bionodulo.nodes.builtin as builtin_pkg

    pkg_path = Path(builtin_pkg.__file__).parent
    index: dict[str, str] = {}
    collisions: list[str] = []

    for _, full_name, ispkg in pkgutil.walk_packages(
        [str(pkg_path)], prefix="bionodulo.nodes.builtin."
    ):
        modname = full_name.rsplit(".", 1)[-1]
        if ispkg or modname.startswith("_"):
            continue
        try:
            module = importlib.import_module(full_name)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: skipping {full_name}: {exc}", file=sys.stderr)
            continue
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseNode)
                and obj is not BaseNode
                and obj is not CommandNode
                and getattr(obj, "NODE_ID", "")
                and obj.__module__ == module.__name__  # own-module only
            ):
                nid = obj.NODE_ID
                if nid in index and index[nid] != full_name:
                    collisions.append(f"{nid}: {index[nid]} vs {full_name}")
                index[nid] = full_name

    if collisions:
        raise SystemExit(
            "Duplicate NODE_IDs across modules (fix before indexing):\n  "
            + "\n  ".join(collisions)
        )
    return dict(sorted(index.items()))


def build_metadata() -> dict[str, object]:
    """Return the full {node_id: object_info} metadata for all builtin nodes.

    This is the editor palette payload — metadata only, no executable classes.
    The app serves it statically so the editor doesn't import every node class
    just to render the node list (§44).
    """
    # Fresh isolated registry, eagerly loaded ONCE at build time.
    from bionodulo.nodes.registry import NodeRegistry

    reg = NodeRegistry.create_isolated()
    reg.load_builtin_nodes()
    return reg.object_info()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if outputs are stale")
    args = ap.parse_args()

    index = build_index()
    index_payload = json.dumps(index, indent=2, sort_keys=True) + "\n"
    metadata = build_metadata()
    # Compact (no indent) — this file gets large (2MB@1k, 20MB@10k); it's machine-read.
    metadata_payload = json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n"

    if args.check:
        stale = []
        if (INDEX_PATH.read_text() if INDEX_PATH.exists() else "") != index_payload:
            stale.append("node_index.json")
        if (METADATA_PATH.read_text() if METADATA_PATH.exists() else "") != metadata_payload:
            stale.append("node_metadata.json")
        if stale:
            print(
                f"STALE: {', '.join(stale)}. Run: python scripts/gen_node_index.py",
                file=sys.stderr,
            )
            return 1
        print(f"node index + metadata are up to date ({len(index)} nodes).")
        return 0

    INDEX_PATH.write_text(index_payload)
    METADATA_PATH.write_text(metadata_payload)
    print(
        f"Wrote {INDEX_PATH.name} ({len(index)} nodes) + "
        f"{METADATA_PATH.name} ({len(metadata_payload)//1024} KB)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
