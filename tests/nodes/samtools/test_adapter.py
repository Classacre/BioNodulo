from __future__ import annotations

import importlib
import inspect

import pytest

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import generate_manifest
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


OPERATIONS = (
    ("view", "SamtoolsViewNode", "samtools_view", "doc/samtools-view.1", "sam_view.c"),
    ("collate", "SamtoolsCollateNode", "samtools_collate", "doc/samtools-collate.1", "bamshuf.c"),
    ("fixmate", "SamtoolsFixmateNode", "samtools_fixmate", "doc/samtools-fixmate.1", "bam_mate.c"),
    ("sort", "SamtoolsSortNode", "samtools_sort", "doc/samtools-sort.1", "bam_sort.c"),
    ("markdup", "SamtoolsMarkdupNode", "samtools_markdup", "doc/samtools-markdup.1", "bam_markdup.c"),
    ("index", "SamtoolsIndexNode", "samtools_index", "doc/samtools-index.1", "bam_index.c"),
    ("flagstat", "SamtoolsFlagstatNode", "samtools_flagstat", "doc/samtools-flagstat.1", "bam_stat.c"),
)


def _module_name(operation: str) -> str:
    return f"bionodulo.nodes.builtin.samtools_family.{operation}"


def _node(operation: str, class_name: str) -> type[BaseNode]:
    return getattr(importlib.import_module(_module_name(operation)), class_name)


def test_live_builtin_index_assigns_each_stable_id_to_its_operation_module() -> None:
    live_index = build_index()

    for operation, _class_name, node_id, _manpage, _source in OPERATIONS:
        assert live_index[node_id] == _module_name(operation)


def test_fresh_lazy_registry_resolves_each_stable_id_to_its_operation_module() -> None:
    registry = NodeRegistry.create_isolated()

    for operation, _class_name, node_id, _manpage, _source in OPERATIONS:
        node = registry.get(node_id)
        assert node is not None
        assert node.__module__ == _module_name(operation)


def test_legacy_samtools_module_no_longer_owns_the_migrated_ids() -> None:
    legacy = importlib.import_module("bionodulo.nodes.builtin.samtools")
    migrated_ids = {node_id for _operation, _class_name, node_id, _manpage, _source in OPERATIONS}
    legacy_owned_ids = {
        obj.NODE_ID
        for _name, obj in inspect.getmembers(legacy, inspect.isclass)
        if issubclass(obj, BaseNode)
        and obj not in {BaseNode, CommandNode}
        and obj.__module__ == legacy.__name__
    }

    assert migrated_ids.isdisjoint(legacy_owned_ids)


@pytest.mark.parametrize(
    ("operation", "class_name", "_node_id", "_manpage", "_source"),
    OPERATIONS,
)
def test_operation_module_defines_one_direct_adapter_subclass(
    operation: str,
    class_name: str,
    _node_id: str,
    _manpage: str,
    _source: str,
) -> None:
    adapter_module = importlib.import_module("bionodulo.nodes.builtin.samtools_family.adapter")
    adapter = adapter_module.SamtoolsCommandNode
    module = importlib.import_module(_module_name(operation))
    node = getattr(module, class_name)
    owned = [
        obj
        for _name, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__module__ == module.__name__ and issubclass(obj, adapter)
    ]

    assert owned == [node]
    assert node.__bases__ == (adapter,)


@pytest.mark.parametrize(
    ("operation", "class_name", "node_id", "manpage", "source"),
    OPERATIONS,
)
def test_first_wave_nodes_declare_exact_shared_and_source_metadata(
    operation: str,
    class_name: str,
    node_id: str,
    manpage: str,
    source: str,
) -> None:
    node = _node(operation, class_name)

    assert node.NODE_ID == node_id
    assert node.CATEGORY == "samtools"
    assert node.REQUIRED_EXECUTABLES == ["samtools"]
    assert node.REQUIRED_CONDA_PACKAGES == ["samtools"]
    assert node.CONDA_PACKAGE_CONSTRAINTS == {"samtools": "==1.23.1"}
    assert node.PACKAGE_CONSTRAINTS == ("samtools==1.23.1",)
    assert node.PACKAGE_CONSTRAINT == "samtools==1.23.1"
    assert node.VERSION == "1.23.1"
    assert node.GIT_URL == "https://github.com/samtools/samtools.git"
    assert node.GIT_COMMIT == "6efb9b6da35224cf804921dedecf9fb8f411365d"
    assert node.CITATION_DOIS == [
        "10.1093/gigascience/giab008",
        "10.1093/bioinformatics/btp352",
    ]
    assert node.CITATION_URLS == [
        "https://doi.org/10.1093/gigascience/giab008",
        "https://doi.org/10.1093/bioinformatics/btp352",
    ]
    assert node.CITATION_TEXT == (
        "Twelve years of SAMtools and BCFtools; "
        "The Sequence Alignment/Map format and SAMtools."
    )
    assert node.SHELL is False
    assert node.__dict__["UPSTREAM_MANPAGE"] == manpage
    assert node.__dict__["UPSTREAM_SOURCE"] == source


def test_adapter_declares_narrow_source_metadata_slots() -> None:
    adapter_module = importlib.import_module("bionodulo.nodes.builtin.samtools_family.adapter")
    adapter = adapter_module.SamtoolsCommandNode

    assert adapter.UPSTREAM_MANPAGE == ""
    assert adapter.UPSTREAM_SOURCE == ""


def test_samtools_pixi_constraint_is_exact() -> None:
    assert PACKAGE_MIN_VERSIONS["samtools"] == "==1.23.1"


def test_generated_manifest_uses_exact_samtools_constraint(tmp_path) -> None:
    manifest = generate_manifest(tmp_path, ["samtools"])

    assert 'samtools = "==1.23.1"' in manifest.read_text(encoding="utf-8").splitlines()
