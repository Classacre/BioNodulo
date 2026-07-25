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
from collections import defaultdict
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bionodulo.nodes.registry import NodeRegistry, _to_frontend_input_spec  # noqa: E402

sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import gen_node_index  # noqa: E402


EXPECTED_NODE_COUNT = 943
EXPECTED_HISTORICAL_ALIAS_COUNT = 22
BUILTIN_MODULE_PREFIX = "bionodulo.nodes.builtin."


@pytest.fixture(scope="module")
def live_owners() -> tuple[gen_node_index.NodeOwner, ...]:
    return gen_node_index.discover_node_owners()


def test_catalog_identity_and_generated_manifests_are_consistent(live_owners):
    """Pin node ownership, historical IDs, and both generated manifests."""
    owners_by_id: dict[str, list[gen_node_index.NodeOwner]] = defaultdict(list)
    for owner in live_owners:
        owners_by_id[owner.node_id].append(owner)

    duplicate_owners = {
        node_id: [owner.qualified_class for owner in owners]
        for node_id, owners in owners_by_id.items()
        if len(owners) != 1
    }
    assert len(live_owners) == EXPECTED_NODE_COUNT
    assert len(owners_by_id) == EXPECTED_NODE_COUNT
    assert duplicate_owners == {}

    live_index = gen_node_index.build_index(live_owners)
    committed_index = json.loads((_REPO_ROOT / "bionodulo/nodes/node_index.json").read_text())
    assert committed_index == live_index, "node_index.json is stale — run `python scripts/gen_node_index.py`"

    baseline = json.loads((_REPO_ROOT / "bionodulo/nodes/generated/baseline-ledger.json").read_text())
    baseline_ids = {entry["node_id"] for entry in baseline["entries"]}
    live_ids = set(owners_by_id)
    assert len(baseline["entries"]) == EXPECTED_NODE_COUNT
    assert baseline_ids == live_ids

    committed_metadata = json.loads((_REPO_ROOT / "bionodulo/nodes/node_metadata.json").read_text())
    assert set(committed_metadata) == live_ids

    historical_aliases = {
        entry["node_id"]: entry["alias_of"] for entry in baseline["entries"] if entry.get("alias_of") is not None
    }
    assert len(historical_aliases) == EXPECTED_HISTORICAL_ALIAS_COUNT
    assert set(historical_aliases) <= live_ids
    assert set(historical_aliases.values()) <= live_ids


def test_build_index_rejects_duplicate_ids_within_one_module():
    owners = (
        gen_node_index.NodeOwner("duplicate", "example.nodes", "FirstNode"),
        gen_node_index.NodeOwner("duplicate", "example.nodes", "SecondNode"),
    )
    with pytest.raises(SystemExit, match="example.nodes.FirstNode.*SecondNode"):
        gen_node_index.build_index(owners)


def owner_module_root(module: str) -> str:
    """Return the first package component below ``builtin``."""
    return module.removeprefix(BUILTIN_MODULE_PREFIX).split(".", 1)[0]


def test_final_one_node_per_file_family_layout(live_owners):
    """Enforce the final one-owner-per-file semantic family layout."""
    owners_by_module: dict[str, list[str]] = defaultdict(list)
    for owner in live_owners:
        owners_by_module[owner.module].append(owner.node_id)

    multi_owner_modules = {
        module: sorted(node_ids) for module, node_ids in owners_by_module.items() if len(node_ids) != 1
    }
    direct_builtin = {
        owner.node_id: owner.module
        for owner in live_owners
        if "." not in owner.module.removeprefix(BUILTIN_MODULE_PREFIX)
    }
    wrapped_modules = {
        module: len(node_ids)
        for module, node_ids in owners_by_module.items()
        if owner_module_root(module).startswith("wrapped_")
    }

    assert multi_owner_modules == {}, json.dumps(multi_owner_modules, sort_keys=True)
    assert direct_builtin == {}, json.dumps(direct_builtin, sort_keys=True)
    assert wrapped_modules == {}, json.dumps(wrapped_modules, sort_keys=True)
    assert len(owners_by_module) == EXPECTED_NODE_COUNT


def test_no_node_bakes_a_build_host_path_into_its_metadata():
    """Generated metadata must be machine-independent.

    A widget default computed from ``__file__`` is correct in-process but is
    frozen into node_metadata.json at generation time, shipping the build
    host's directory layout to every client and cloud worker — where the path
    does not exist. Defaults must be blank and resolved at runtime instead.
    """
    metadata = json.loads((_REPO_ROOT / "bionodulo/nodes/node_metadata.json").read_text())
    offenders: dict[str, str] = {}

    def scan(value: object, trail: str, node_id: str) -> None:
        if isinstance(value, str):
            if value.startswith("/") and ("/home/" in value or "/Users/" in value):
                offenders[f"{node_id}{trail}"] = value
        elif isinstance(value, dict):
            for key, child in value.items():
                scan(child, f"{trail}.{key}", node_id)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, f"{trail}[{index}]", node_id)

    for node_id, node_meta in metadata.items():
        scan(node_meta, "", node_id)

    assert not offenders, (
        "Absolute build-host paths baked into node metadata — resolve these at "
        "runtime and leave the widget default blank:\n  "
        + "\n  ".join(f"{where} = {what}" for where, what in sorted(offenders.items()))
    )


def test_node_metadata_is_fresh():
    """The committed node_metadata.json matches a live object_info() build.

    Compare JSON-normalized forms — object_info() returns tuples (input specs)
    that JSON serializes to lists, so a direct Python-object compare would
    spuriously differ. What matters is the SERVED file matches a fresh build.
    """
    live = json.loads(json.dumps(gen_node_index.build_metadata(), sort_keys=True))
    committed = json.loads((_REPO_ROOT / "bionodulo/nodes/node_metadata.json").read_text())
    assert committed == live, "node_metadata.json is stale — run `python scripts/gen_node_index.py`"


def test_frontend_metadata_distinguishes_socket_unions_from_enum_options():
    socket_type, socket_config = _to_frontend_input_spec(
        (("SAM", "BAM"), {"description": "Alignment input"})
    )
    enum_type, enum_config = _to_frontend_input_spec(
        (["fastq", "fasta"], {"default": "fastq"})
    )

    assert socket_type == "SAM|BAM"
    assert socket_config == {"description": "Alignment input"}
    assert enum_type == "STRING"
    assert enum_config == {"default": "fastq", "options": ["fastq", "fasta"]}
    assert _to_frontend_input_spec(("QC_REPORT_DIR", {}))[0] == "QC_REPORT_DIR"


def test_official_template_edges_have_renderable_editor_handles():
    """Every bundled edge must attach to a port the editor actually renders."""
    metadata = json.loads((_REPO_ROOT / "bionodulo/nodes/node_metadata.json").read_text())
    widget_types = {"STRING", "INT", "FLOAT", "BOOLEAN", "COMBO"}
    failures: list[str] = []

    for template_path in sorted((_REPO_ROOT / "templates").glob("*.json")):
        workflow = json.loads(template_path.read_text(encoding="utf-8"))
        nodes = {str(node["id"]): node for node in workflow.get("nodes", [])}
        for edge in workflow.get("edges", []):
            edge_id = str(edge.get("id", "<unnamed>"))
            source = edge.get("from", {})
            target = edge.get("to", {})
            source_node = nodes.get(str(source.get("node")))
            target_node = nodes.get(str(target.get("node")))
            if source_node is None or target_node is None:
                failures.append(f"{template_path.name}:{edge_id}: missing endpoint node")
                continue

            source_meta = metadata.get(str(source_node.get("type")))
            target_meta = metadata.get(str(target_node.get("type")))
            if source_meta is None or target_meta is None:
                failures.append(f"{template_path.name}:{edge_id}: missing node metadata")
                continue

            source_handle = str(source.get("output"))
            if source_handle not in source_meta.get("output_name", []):
                failures.append(
                    f"{template_path.name}:{edge_id}: missing source handle {source_handle!r}"
                )

            visible_inputs = {
                **target_meta.get("input", {}).get("required", {}),
                **target_meta.get("input", {}).get("optional", {}),
            }
            target_handle = str(target.get("input"))
            spec = visible_inputs.get(target_handle)
            if not isinstance(spec, list) or len(spec) < 2:
                failures.append(
                    f"{template_path.name}:{edge_id}: missing target handle {target_handle!r}"
                )
                continue

            input_type, config = str(spec[0]), spec[1]
            config = config if isinstance(config, dict) else {}
            is_widget = (
                input_type in widget_types or bool(config.get("options"))
            ) and not config.get("forceInput") and not config.get("link")
            promoted = target_handle in target_node.get("ui", {}).get("promotedInputs", [])
            if is_widget and not promoted:
                failures.append(
                    f"{template_path.name}:{edge_id}: target {target_handle!r} renders as a widget"
                )

    assert failures == [], "\n".join(failures)


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
