"""Import failures during builtin loading must be observable, never silent.

`load_builtin_nodes()` deliberately tolerates a broken module at runtime: one
node with a missing optional dependency should not take down a worker running
an unrelated workflow. But tolerance became silence — the failure went to a log
line and nothing downstream could tell that the catalog was incomplete.

These tests pin both halves: build-time callers get a hard failure, and the
tolerant runtime path still records what it dropped.
"""
from __future__ import annotations

import importlib

import pytest

from bionodulo.nodes.registry import NodeRegistry

BROKEN_MODULE = "bionodulo.nodes.builtin.data_transform_family.column_maker"


def _registry_with_one_broken_module(monkeypatch: pytest.MonkeyPatch) -> NodeRegistry:
    real_import = importlib.import_module

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == BROKEN_MODULE:
            raise ImportError("synthetic module failure")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("bionodulo.nodes.registry.importlib.import_module", fake_import)
    return NodeRegistry.create_isolated()


def test_strict_loading_raises_on_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry_with_one_broken_module(monkeypatch)

    with pytest.raises(RuntimeError) as excinfo:
        registry.load_builtin_nodes(strict=True)

    message = str(excinfo.value)
    assert BROKEN_MODULE in message
    assert "synthetic module failure" in message


def test_tolerant_loading_records_import_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry_with_one_broken_module(monkeypatch)

    registry.load_builtin_nodes()

    assert BROKEN_MODULE in registry.import_errors
    assert "synthetic module failure" in registry.import_errors[BROKEN_MODULE]


def test_healthy_load_reports_no_import_errors() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes(strict=True)
    assert registry.import_errors == {}
