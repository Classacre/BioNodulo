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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Ensure the repo root is importable when run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bionodulo.nodes.base import BaseNode  # noqa: E402
from bionodulo.nodes.command_node import CommandNode  # noqa: E402

INDEX_PATH = _REPO_ROOT / "bionodulo" / "nodes" / "node_index.json"
METADATA_PATH = _REPO_ROOT / "bionodulo" / "nodes" / "node_metadata.json"


@dataclass(frozen=True)
class NodeOwner:
    """One concrete, own-module builtin node class."""

    node_id: str
    module: str
    class_name: str

    @property
    def qualified_class(self) -> str:
        return f"{self.module}.{self.class_name}"


def discover_node_owners() -> tuple[NodeOwner, ...]:
    """Return every unique own-module builtin ``BaseNode`` subclass.

    Owners are kept as individual records instead of being collapsed into an
    ID-keyed dictionary.  That distinction lets callers detect two classes
    claiming the same ``NODE_ID`` even when both classes live in one module.
    """
    import bionodulo.nodes.builtin as builtin_pkg

    pkg_path = Path(builtin_pkg.__file__).parent
    owners: list[NodeOwner] = []
    seen_classes: set[type[BaseNode]] = set()
    import_errors: list[str] = []

    for _, full_name, ispkg in pkgutil.walk_packages([str(pkg_path)], prefix="bionodulo.nodes.builtin."):
        modname = full_name.rsplit(".", 1)[-1]
        if ispkg or modname.startswith("_"):
            continue
        try:
            module = importlib.import_module(full_name)
        except Exception as exc:  # noqa: BLE001
            import_errors.append(f"{full_name}: {exc}")
            continue
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseNode)
                and obj is not BaseNode
                and obj is not CommandNode
                and getattr(obj, "NODE_ID", "")
                and obj.__module__ == module.__name__  # own-module only
            ):
                # A module may expose the same class under two names.  That is
                # one owner, unlike two distinct classes sharing a NODE_ID.
                if obj in seen_classes:
                    continue
                seen_classes.add(obj)
                owners.append(
                    NodeOwner(
                        node_id=obj.NODE_ID,
                        module=full_name,
                        class_name=obj.__qualname__,
                    )
                )

    if import_errors:
        raise SystemExit(
            "Failed to import builtin node modules (index not generated):\n  " + "\n  ".join(import_errors)
        )

    return tuple(
        sorted(
            owners,
            key=lambda owner: (owner.node_id, owner.module, owner.class_name),
        )
    )


def build_index(owners: Iterable[NodeOwner] | None = None) -> dict[str, str]:
    """Return ``{node_id: module_name}`` for every builtin node (sorted)."""
    discovered = tuple(owners) if owners is not None else discover_node_owners()
    owners_by_id: dict[str, list[NodeOwner]] = {}
    for owner in discovered:
        owners_by_id.setdefault(owner.node_id, []).append(owner)

    collisions = {node_id: node_owners for node_id, node_owners in owners_by_id.items() if len(node_owners) > 1}

    if collisions:
        details = []
        for node_id, node_owners in sorted(collisions.items()):
            qualified = " vs ".join(owner.qualified_class for owner in node_owners)
            details.append(f"{node_id}: {qualified}")
        raise SystemExit("Duplicate NODE_ID class owners (fix before indexing):\n  " + "\n  ".join(details))

    index = {owner.node_id: owner.module for owner in discovered}
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
    # strict: a module failing to import here would silently drop its nodes from
    # the generated manifest, and the palette would advertise a catalog nobody
    # proved. A partial catalog is a build failure, not a warning.
    reg.load_builtin_nodes(strict=True)
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
    print(f"Wrote {INDEX_PATH.name} ({len(index)} nodes) + {METADATA_PATH.name} ({len(metadata_payload) // 1024} KB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
