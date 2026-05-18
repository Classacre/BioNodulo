"""Custom node package management for BioNodulo.

Provides install, remove, update, and registry listing for third-party
custom node packages.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Known custom node registries (name -> git URL pattern or index URL)
DEFAULT_REGISTRIES: dict[str, str] = {
    "bionodulo-community": "https://github.com/bionodulo/community-nodes.git",
    "bioconda-nodes": "https://github.com/bioconda/bionodulo-nodes.git",
}


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


def registry_entries() -> dict[str, dict[str, Any]]:
    """List available custom node registries.

    Returns:
        Dictionary of registry name -> metadata.
    """
    entries: dict[str, dict[str, Any]] = {}
    for name, url in DEFAULT_REGISTRIES.items():
        entries[name] = {
            "name": name,
            "url": url,
            "description": f"BioNodulo custom node registry: {name}",
            "installed": False,
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
