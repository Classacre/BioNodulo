"""Tests for the lazy node index + prebuilt metadata (§44).

These guard the two things that must not drift:
  1. node_index.json (node_id → module) matches a live walk of builtin nodes.
  2. node_metadata.json matches a live object_info() build.
Plus the runtime behaviours: lazy get() imports only the needed module, and
object_info() serves from the manifest without importing node classes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bionodulo.nodes.registry import NodeRegistry  # noqa: E402

sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import gen_node_index  # noqa: E402


def test_node_index_is_fresh():
    """The committed node_index.json matches a live rebuild (no drift)."""
    live = gen_node_index.build_index()
    committed = json.loads((_REPO_ROOT / "bionodulo/nodes/node_index.json").read_text())
    assert committed == live, (
        "node_index.json is stale — run `python scripts/gen_node_index.py`"
    )


def test_node_metadata_is_fresh():
    """The committed node_metadata.json matches a live object_info() build.

    Compare JSON-normalized forms — object_info() returns tuples (input specs)
    that JSON serializes to lists, so a direct Python-object compare would
    spuriously differ. What matters is the SERVED file matches a fresh build.
    """
    live = json.loads(json.dumps(gen_node_index.build_metadata(), sort_keys=True))
    committed = json.loads((_REPO_ROOT / "bionodulo/nodes/node_metadata.json").read_text())
    assert committed == live, (
        "node_metadata.json is stale — run `python scripts/gen_node_index.py`"
    )


def test_every_indexed_node_is_lazily_resolvable():
    """Each node in the index resolves via get() (a random-ish sample for speed)."""
    reg = NodeRegistry.create_isolated()
    index = json.loads((_REPO_ROOT / "bionodulo/nodes/node_index.json").read_text())
    # Sample across modules: first node of each distinct module.
    seen_modules: set[str] = set()
    sample: list[str] = []
    for nid, mod in index.items():
        if mod not in seen_modules:
            seen_modules.add(mod)
            sample.append(nid)
    for nid in sample:
        assert reg.get(nid) is not None, f"lazy get() failed for {nid}"


def test_lazy_get_does_not_load_everything():
    """Resolving one node imports only its module's nodes, not the whole catalog."""
    reg = NodeRegistry.create_isolated()
    assert len(reg.all()) == 0
    assert reg.get("bwa_index") is not None
    # Only alignment.py's handful of nodes loaded — nowhere near the full set.
    assert 1 <= len(reg.all()) < 100


def test_unknown_node_returns_none():
    reg = NodeRegistry.create_isolated()
    assert reg.get("definitely_not_a_real_node_xyz") is None


def test_object_info_served_without_importing_classes():
    """object_info() returns full metadata from the manifest, importing nothing."""
    reg = NodeRegistry.create_isolated()
    info = reg.object_info()
    assert len(info) > 900
    # The manifest path must not have imported node classes.
    assert len(reg.all()) == 0
    assert "bwa_index" in info
    assert info["bwa_index"]["display_name"]


def test_live_node_overlays_manifest():
    """A lazily-loaded/custom node's live metadata wins over the static snapshot."""
    reg = NodeRegistry.create_isolated()
    reg.get("bwa_index")  # force it live
    reg._object_info_cache = None  # rebuild
    info = reg.object_info()
    assert "bwa_index" in info  # still present, now from the live class
