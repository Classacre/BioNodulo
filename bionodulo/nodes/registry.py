from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.comfy_v3_adapter import adapt_comfy_v3_node


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, type[BaseNode]] = {}
        self.import_warnings: list[str] = []

    def register(self, node_cls: type[BaseNode]) -> None:
        node_id = getattr(node_cls, "NODE_ID", "")
        if not node_id:
            raise ValueError(f"Node class {node_cls.__name__} is missing NODE_ID")
        self._nodes[node_id] = node_cls

    def get(self, node_id: str) -> type[BaseNode]:
        return self._nodes[node_id]

    def has(self, node_id: str) -> bool:
        return node_id in self._nodes

    def all(self) -> dict[str, type[BaseNode]]:
        return dict(self._nodes)

    def object_info(self) -> dict[str, dict]:
        return {node_id: node_cls.metadata() for node_id, node_cls in sorted(self._nodes.items())}

    def load_builtin_nodes(self) -> None:
        modules = [
            "bionodulo.nodes.builtin.inputs",
            "bionodulo.nodes.builtin.qc",
            "bionodulo.nodes.builtin.trimming",
            "bionodulo.nodes.builtin.alignment",
            "bionodulo.nodes.builtin.generic",
            "bionodulo.api_nodes.base",
        ]
        for module_name in modules:
            module = importlib.import_module(module_name)
            self.register_from_module(module)

    def load_custom_nodes(self, custom_nodes_dir: Path) -> None:
        if not custom_nodes_dir.exists():
            return
        sys.path.insert(0, str(custom_nodes_dir.resolve()))
        for path in custom_nodes_dir.rglob("*.py"):
            if path.name.startswith("_") or path.name.endswith(".example"):
                continue
            try:
                module = _load_module_from_path(path)
                self.register_from_module(module)
            except Exception as exc:  # pragma: no cover - warning path depends on user plugins
                self.import_warnings.append(f"{path}: {exc}")

    def register_from_module(self, module: ModuleType) -> None:
        for node_cls in iter_node_classes(module):
            self.register(node_cls)


def iter_node_classes(module: ModuleType) -> Iterable[type[BaseNode]]:
    for _, value in inspect.getmembers(module, inspect.isclass):
        if value is BaseNode:
            continue
        if issubclass(value, BaseNode) and getattr(value, "NODE_ID", ""):
            yield value
            continue
        adapted = adapt_comfy_v3_node(value)
        if adapted is not None:
            yield adapted


def _load_module_from_path(path: Path) -> ModuleType:
    module_name = f"bionodulo_custom_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
