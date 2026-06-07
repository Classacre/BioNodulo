from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.manager.custom_nodes import list_installed_packages, load_package_manifest, registry_entries
from bionodulo.nodes.registry import NodeRegistry


def test_load_package_manifest_parses_bionodulo_toml(tmp_path: Path) -> None:
    manifest = tmp_path / "bionodulo.toml"
    manifest.write_text(
        """
[package]
name = "bionodulo-qc"
version = "0.3.0"
description = "QC helper nodes"
repository = "https://github.com/example/bionodulo-qc"
entrypoints = ["qc_nodes"]
requirements = ["pandas>=2", "numpy"]
""".strip(),
        encoding="utf-8",
    )

    package = load_package_manifest(tmp_path)

    assert package.to_dict() == {
        "name": "bionodulo-qc",
        "version": "0.3.0",
        "description": "QC helper nodes",
        "repository": "https://github.com/example/bionodulo-qc",
        "entrypoints": ["qc_nodes"],
        "requirements": ["pandas>=2", "numpy"],
        "directory": tmp_path.name,
        "manifest_path": str(manifest),
        "manifest_present": True,
        "valid": True,
        "errors": [],
    }


def test_load_package_manifest_rejects_missing_required_fields(tmp_path: Path) -> None:
    (tmp_path / "bionodulo.toml").write_text(
        """
[package]
name = "missing-version"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="version"):
        load_package_manifest(tmp_path)


def test_list_installed_packages_includes_manifest_and_legacy_entries(tmp_path: Path) -> None:
    manifest_pkg = tmp_path / "manifest_pkg"
    manifest_pkg.mkdir()
    (manifest_pkg / "bionodulo.toml").write_text(
        """
[package]
name = "manifest-pkg"
version = "1.2.0"
entrypoints = ["nodes"]
""".strip(),
        encoding="utf-8",
    )
    legacy_pkg = tmp_path / "legacy_pkg"
    legacy_pkg.mkdir()
    (legacy_pkg / "__init__.py").write_text("", encoding="utf-8")
    single_file = tmp_path / "single_file.py"
    single_file.write_text("NODE_CLASS_MAPPINGS = {}\n", encoding="utf-8")

    packages = list_installed_packages(tmp_path)

    assert [pkg["name"] for pkg in packages] == ["legacy_pkg", "manifest-pkg", "single_file"]
    assert packages[0] | {"manifest_path": ""} == {
        "name": "legacy_pkg",
        "version": "",
        "description": "",
        "repository": "",
        "entrypoints": [],
        "requirements": [],
        "directory": "legacy_pkg",
        "manifest_path": "",
        "manifest_present": False,
        "valid": True,
        "errors": [],
    }
    assert packages[1]["version"] == "1.2.0"
    assert packages[1]["entrypoints"] == ["nodes"]
    assert packages[1]["manifest_present"] is True
    assert packages[2]["directory"] == "single_file.py"


def test_registry_entries_marks_installed_packages_by_repository(tmp_path: Path) -> None:
    installed_dir = tmp_path / "community_nodes"
    installed_dir.mkdir()
    (installed_dir / "bionodulo.toml").write_text(
        """
[package]
name = "community-nodes"
version = "0.1.0"
repository = "https://github.com/bionodulo/community-nodes.git"
""".strip(),
        encoding="utf-8",
    )

    entries = registry_entries(tmp_path)

    community = entries["bionodulo-community"]
    assert community["installed"] is True
    assert community["installed_package"]["name"] == "community-nodes"
    assert community["install_status"] == "installed"
    assert community["verified"] is True
    assert community["compatibility"]["manifest_required"] is True
    assert entries["bioconda-nodes"]["installed"] is False


def test_node_registry_loads_manifest_declared_entrypoint_modules(tmp_path: Path) -> None:
    package_dir = tmp_path / "custom_nodes" / "manifest_pkg"
    package_dir.mkdir(parents=True)
    (package_dir / "bionodulo.toml").write_text(
        """
[package]
name = "manifest-pkg"
version = "0.1.0"
entrypoints = ["nodes"]
""".strip(),
        encoding="utf-8",
    )
    (package_dir / "nodes.py").write_text(
        """
from bionodulo.nodes.base import BaseNode

class ManifestEntrypointNode(BaseNode):
    NODE_ID = "manifest_entrypoint"
    DISPLAY_NAME = "Manifest Entrypoint"
    CATEGORY = "custom"
    GIT_URL = "https://example.test/manifest-pkg.git"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)

    async def run(self, **kwargs):
        return {"outputs": {"value": "ok"}}
""".strip(),
        encoding="utf-8",
    )

    registry = NodeRegistry.create_isolated()

    loaded_count = registry.load_custom_nodes(tmp_path / "custom_nodes")

    assert loaded_count == 1
    assert registry.get("manifest_entrypoint") is not None


def test_node_registry_falls_back_to_package_init_when_manifest_has_no_entrypoints(tmp_path: Path) -> None:
    package_dir = tmp_path / "custom_nodes" / "manifest_init_pkg"
    package_dir.mkdir(parents=True)
    (package_dir / "bionodulo.toml").write_text(
        """
[package]
name = "manifest-init-pkg"
version = "0.1.0"
""".strip(),
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text(
        """
from bionodulo.nodes.base import BaseNode

class ManifestInitNode(BaseNode):
    NODE_ID = "manifest_init"
    DISPLAY_NAME = "Manifest Init"
    CATEGORY = "custom"
    GIT_URL = "https://example.test/manifest-init-pkg.git"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)

    async def run(self, **kwargs):
        return {"outputs": {"value": "ok"}}
""".strip(),
        encoding="utf-8",
    )

    registry = NodeRegistry.create_isolated()

    loaded_count = registry.load_custom_nodes(tmp_path / "custom_nodes")

    assert loaded_count == 1
    assert registry.get("manifest_init") is not None
