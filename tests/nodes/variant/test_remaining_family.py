"""Compact ownership and release-evidence checks for the remaining variant nodes."""

from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import variant_family as facade
from bionodulo.nodes.builtin.variant_family import evidence, legacy


EXPECTED_REMAINING_IDS = frozenset(evidence.NODE_EVIDENCE)


def _facade_nodes() -> dict[str, type[BaseNode]]:
    return {
        candidate.NODE_ID: candidate
        for candidate in vars(facade).values()
        if inspect.isclass(candidate)
        and issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and bool(getattr(candidate, "NODE_ID", ""))
    }


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        candidate
        for candidate in vars(module).values()
        if inspect.isclass(candidate)
        and issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and candidate.__module__ == module.__name__
        and bool(candidate.__dict__.get("NODE_ID"))
    ]


def test_variant_family_has_32_focused_owners_and_no_live_legacy_owner() -> None:
    nodes = _facade_nodes()
    assert len(nodes) == 32
    assert EXPECTED_REMAINING_IDS <= set(nodes)
    assert _owned_node_classes(legacy) == []

    for node_class in nodes.values():
        assert node_class.__module__.startswith("bionodulo.nodes.builtin.variant_family.")
        assert getattr(facade, node_class.__name__) is node_class


@pytest.mark.parametrize("node_id", sorted(EXPECTED_REMAINING_IDS))
def test_each_remaining_node_has_one_owner_and_exact_release_evidence(node_id: str) -> None:
    node_class = _facade_nodes()[node_id]
    authority = evidence.NODE_EVIDENCE[node_id]
    owner = importlib.import_module(node_class.__module__)

    assert _owned_node_classes(owner) == [node_class]
    assert node_class.VERSION == authority.version
    assert node_class.SOURCE_URL == authority.source_url
    assert node_class.SOURCE_REF == authority.source_ref
    assert node_class.PACKAGE_CONSTRAINTS == authority.package_constraints
    assert node_class.EXIT_SEMANTICS
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    if authority.git_commit:
        assert node_class.GIT_COMMIT == authority.git_commit


def test_bcftools_index_uses_the_pinned_1_24_source_and_package() -> None:
    node_class = _facade_nodes()["bcftools_index"]
    command = node_class.render_command({"vcf": "calls.vcf.gz", "output": "/work/index"})

    assert node_class.VERSION == "1.24"
    assert node_class.PACKAGE_CONSTRAINTS == ("bcftools==1.24",)
    assert command[:2] == ["bcftools", "index"]
