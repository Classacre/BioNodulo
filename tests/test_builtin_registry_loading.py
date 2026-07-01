from __future__ import annotations

import textwrap
from pathlib import Path


def test_builtin_loader_recurses_into_builtin_subpackages(monkeypatch, tmp_path: Path) -> None:
    from bionodulo.nodes.registry import NodeRegistry
    import bionodulo.nodes.builtin as builtin_pkg

    package_root = tmp_path / "builtin"
    subpackage = package_root / "split_nodes"
    subpackage.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (subpackage / "__init__.py").write_text("", encoding="utf-8")
    (subpackage / "example.py").write_text(
        textwrap.dedent(
            """
            from bionodulo.nodes.base import BaseNode

            class SplitBuiltinNode(BaseNode):
                NODE_ID = "split_builtin_node"
                DISPLAY_NAME = "Split Builtin Node"
                CATEGORY = "utility"
                RETURN_TYPES = ("STRING",)
                RETURN_NAMES = ("value",)

                async def run(self, **kwargs):
                    return {"outputs": {"value": "ok"}}
            """
        ).strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(builtin_pkg, "__file__", str(package_root / "__init__.py"))
    monkeypatch.setattr(builtin_pkg, "__path__", [str(package_root)], raising=False)

    registry = NodeRegistry.create_isolated()
    count = registry.load_builtin_nodes()

    assert count == 1
    assert registry.has("split_builtin_node") is True


def test_builtin_loader_skips_modules_already_loaded(monkeypatch, tmp_path: Path) -> None:
    from bionodulo.nodes.registry import NodeRegistry
    import bionodulo.nodes.builtin as builtin_pkg

    package_root = tmp_path / "builtin"
    package_root.mkdir(parents=True)
    module_path = package_root / "example.py"
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    module_path.write_text(
        textwrap.dedent(
            """
            from bionodulo.nodes.base import BaseNode

            class FastStartupNode(BaseNode):
                NODE_ID = "fast_startup_node"
                DISPLAY_NAME = "Fast Startup Node"
                CATEGORY = "utility"
                RETURN_TYPES = ("STRING",)
                RETURN_NAMES = ("value",)

                async def run(self, **kwargs):
                    return {"outputs": {"value": "ok"}}
            """
        ).strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(builtin_pkg, "__file__", str(package_root / "__init__.py"))
    monkeypatch.setattr(builtin_pkg, "__path__", [str(package_root)], raising=False)

    registry = NodeRegistry.create_isolated()

    assert registry.load_builtin_nodes() == 1
    assert registry.load_builtin_nodes() == 0
    assert registry.has("fast_startup_node") is True
