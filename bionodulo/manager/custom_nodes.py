"""Custom node package management for BioNodulo.

Provides install, remove, update, and registry listing for third-party
custom node packages.
"""
from __future__ import annotations

import dataclasses
import logging
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Known custom node registries (name -> git URL pattern or index URL)
DEFAULT_REGISTRIES: dict[str, str] = {
    "bionodulo-community": "https://github.com/bionodulo/community-nodes.git",
    "bioconda-nodes": "https://github.com/bioconda/bionodulo-nodes.git",
}


@dataclasses.dataclass(frozen=True)
class CustomNodePackage:
    """Manifest-backed metadata for a custom node package."""

    name: str
    version: str
    directory: str
    description: str = ""
    repository: str = ""
    entrypoints: list[str] = dataclasses.field(default_factory=list)
    requirements: list[str] = dataclasses.field(default_factory=list)
    manifest_path: str = ""
    manifest_present: bool = False
    valid: bool = True
    errors: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize package metadata for manager/UI consumers."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "repository": self.repository,
            "entrypoints": list(self.entrypoints),
            "requirements": list(self.requirements),
            "directory": self.directory,
            "manifest_path": self.manifest_path,
            "manifest_present": self.manifest_present,
            "valid": self.valid,
            "errors": list(self.errors),
        }


def load_package_manifest(package_dir: str | Path) -> CustomNodePackage:
    """Load and validate a custom node package manifest.

    The manifest lives at ``bionodulo.toml`` and uses a ``[package]`` table.
    Required fields are ``name`` and ``version``. Optional fields are
    ``description``, ``repository``, ``entrypoints``, and ``requirements``.
    """
    path = Path(package_dir)
    manifest_path = path / "bionodulo.toml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Custom node package manifest not found: {manifest_path}")

    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    package = data.get("package", {})
    if not isinstance(package, dict):
        raise ValueError("bionodulo.toml must contain a [package] table")

    errors: list[str] = []
    name = _string_field(package, "name")
    version = _string_field(package, "version")
    if not name:
        errors.append("package.name is required")
    if not version:
        errors.append("package.version is required")
    if errors:
        raise ValueError("; ".join(errors))

    entrypoints = _string_list_field(package, "entrypoints")
    requirements = _string_list_field(package, "requirements")

    return CustomNodePackage(
        name=name,
        version=version,
        description=_string_field(package, "description"),
        repository=_string_field(package, "repository"),
        entrypoints=entrypoints,
        requirements=requirements,
        directory=path.name,
        manifest_path=str(manifest_path),
        manifest_present=True,
        valid=True,
        errors=[],
    )


def list_installed_packages(custom_nodes_dir: str | Path) -> list[dict[str, Any]]:
    """List custom node packages installed in a custom_nodes directory."""
    root = Path(custom_nodes_dir)
    if not root.exists():
        return []

    packages: list[CustomNodePackage] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("_") or entry.name.endswith(".pyc"):
            continue
        if entry.is_dir():
            manifest = entry / "bionodulo.toml"
            if manifest.exists():
                try:
                    packages.append(load_package_manifest(entry))
                except Exception as exc:
                    packages.append(_invalid_manifest_package(entry, manifest, exc))
            elif (entry / "__init__.py").exists():
                packages.append(_legacy_package(entry))
        elif entry.is_file() and entry.suffix == ".py":
            packages.append(_legacy_package(entry))

    return [
        package.to_dict()
        for package in sorted(packages, key=lambda package: package.name.lower())
    ]


def install_git(
    url: str,
    install_dir: str | Path,
    branch: str = "main",
    overwrite: bool = False,
) -> bool:
    """Install a custom node package from a Git repository.

    Args:
        url: Git repository URL.
        install_dir: Directory to install into (typically custom_nodes/<name>).
        branch: Git branch to checkout.
        overwrite: Whether to overwrite if already exists.

    Returns:
        True if installation succeeded.
    """
    dest = Path(install_dir)
    if dest.exists():
        if overwrite:
            logger.info("Removing existing installation: %s", dest)
            shutil.rmtree(dest)
        else:
            logger.error("Installation already exists: %s", dest)
            return False

    logger.info("Cloning %s -> %s (branch: %s)", url, dest, branch)
    try:
        result = subprocess.run(
            ["git", "clone", "--branch", branch, "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Successfully installed %s", url)
            # Optionally install requirements
            req_file = dest / "requirements.txt"
            if req_file.exists():
                _install_requirements(req_file)
            return True
        else:
            logger.error("Git clone failed: %s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("Git clone timed out")
        return False
    except FileNotFoundError:
        logger.error("git command not found")
        return False


def remove_package(package_dir: str | Path) -> bool:
    """Remove an installed custom node package.

    Args:
        package_dir: Directory of the installed package.

    Returns:
        True if removal succeeded.
    """
    dest = Path(package_dir)
    if not dest.exists():
        logger.warning("Package not found: %s", dest)
        return False

    try:
        shutil.rmtree(dest)
        logger.info("Removed package: %s", dest)
        return True
    except Exception as exc:
        logger.error("Failed to remove %s: %s", dest, exc)
        return False


def update_package(package_dir: str | Path, branch: str = "main") -> bool:
    """Update an installed custom node package via git pull.

    Args:
        package_dir: Directory of the installed package.
        branch: Branch to pull from.

    Returns:
        True if update succeeded.
    """
    dest = Path(package_dir)
    if not dest.exists():
        logger.error("Package not found: %s", dest)
        return False

    git_dir = dest / ".git"
    if not git_dir.exists():
        logger.error("Not a git repository: %s", dest)
        return False

    try:
        result = subprocess.run(
            ["git", "-C", str(dest), "pull", "origin", branch],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Updated package: %s", dest)
            # Re-install requirements if updated
            req_file = dest / "requirements.txt"
            if req_file.exists():
                _install_requirements(req_file)
            return True
        else:
            logger.error("Git pull failed: %s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("Git pull timed out")
        return False


def registry_entries(custom_nodes_dir: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """List available custom node registries.

    Returns:
        Dictionary of registry name -> metadata.
    """
    installed_packages = list_installed_packages(custom_nodes_dir) if custom_nodes_dir is not None else []
    installed_by_repository = {
        str(package.get("repository", "")).rstrip("/").lower(): package
        for package in installed_packages
        if package.get("repository")
    }
    entries: dict[str, dict[str, Any]] = {}
    for name, url in DEFAULT_REGISTRIES.items():
        installed_package = installed_by_repository.get(url.rstrip("/").lower())
        entries[name] = {
            "name": name,
            "url": url,
            "description": f"BioNodulo custom node registry: {name}",
            "installed": installed_package is not None,
            "install_status": "installed" if installed_package is not None else "available",
            "installed_package": installed_package,
            "verified": True,
            "compatibility": {
                "manifest_required": True,
                "supported_manifest": "bionodulo.toml",
            },
        }
    return entries


def _install_requirements(req_file: Path) -> bool:
    """Install Python requirements from a requirements.txt file.

    Args:
        req_file: Path to requirements.txt.

    Returns:
        True if installation succeeded.
    """
    logger.info("Installing requirements from %s", req_file)
    try:
        result = subprocess.run(
            ["pip", "install", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.warning("Failed to install requirements: %s", exc)
        return False


def _string_field(data: dict[str, Any], key: str) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"package.{key} must be a string")
    return value.strip()


def _string_list_field(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"package.{key} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"package.{key} must be a list of strings")
        if item.strip():
            result.append(item.strip())
    return result


def _legacy_package(path: Path) -> CustomNodePackage:
    name = path.stem if path.is_file() else path.name
    return CustomNodePackage(
        name=name,
        version="",
        directory=path.name,
        manifest_present=False,
    )


def _invalid_manifest_package(path: Path, manifest_path: Path, exc: Exception) -> CustomNodePackage:
    return CustomNodePackage(
        name=path.name,
        version="",
        directory=path.name,
        manifest_path=str(manifest_path),
        manifest_present=True,
        valid=False,
        errors=[str(exc)],
    )
