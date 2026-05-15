"""Pixi environment management for BioNodulo.

Replaces the legacy Conda/Mamba/Micromamba backend with prefix.dev pixi.
All environments are defined in the root ``pixi.toml`` manifest.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from bionodulo.environments.model import EnvironmentSpec

logger = logging.getLogger(__name__)

# Default channels (kept for reference, but pixi reads these from pixi.toml)
DEFAULT_CHANNELS = ["conda-forge", "bioconda"]


def _find_pixi_executable() -> str | None:
    """Find pixi executable on PATH or in the managed installation."""
    path = shutil.which("pixi")
    if path:
        return path
    # Fallback to the default pixi install location
    fallback = Path.home() / ".pixi" / "bin" / "pixi"
    if fallback.exists():
        return str(fallback)
    return None


def _pixi_root() -> Path:
    """Return the directory containing ``pixi.toml``."""
    # Project root is two levels above this file: bionodulo/environments/ -> root
    return Path(__file__).resolve().parent.parent.parent


def _to_pixi_env_name(env_name: str) -> str:
    """Map BioNodulo env names to pixi environment names.

    Examples:
        bionodulo-tools     -> tools
        bionodulo-r         -> r
        bionodulo-rna_seq   -> rna-seq
        bionodulo-chip_seq  -> chip-seq
    """
    if env_name.startswith("bionodulo-"):
        return env_name[len("bionodulo-"):].replace("_", "-")
    return env_name.replace("_", "-")


def pixi_run_prefix(env_name: str | None = None) -> list[str]:
    """Generate a pixi run prefix command.

    Args:
        env_name: Pixi environment name. If None, uses the default env.

    Returns:
        List of command prefix tokens.
    """
    pixi = _find_pixi_executable()
    if pixi is None:
        raise RuntimeError("pixi executable not found")
    cmd: list[str] = [pixi, "run"]
    if env_name:
        cmd.extend(["-e", env_name])
    cmd.extend(["--cwd", str(_pixi_root())])
    return cmd


def list_pixi_envs() -> list[dict[str, Any]]:
    """List all pixi environments defined in the manifest.

    Returns a list of dicts with name and path.
    """
    pixi = _find_pixi_executable()
    if pixi is None:
        return []
    root = _pixi_root()
    envs_dir = root / ".pixi" / "envs"
    try:
        result = subprocess.run(
            [pixi, "info", "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("pixi info failed: %s", result.stderr)
            return []
        data = json.loads(result.stdout)
        environments = data.get("environments", {})
        env_list = []
        for name, info in environments.items():
            env_path = envs_dir / name
            env_list.append({
                "name": name,
                "path": str(env_path),
                "active": False,
            })
        return env_list
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning("Failed to list pixi environments: %s", exc)
        return []


def get_env_packages(env_name: str) -> list[dict[str, str]]:
    """List packages installed in a pixi environment.

    Returns list of dicts with name and version.
    """
    pixi = _find_pixi_executable()
    if pixi is None:
        return []
    root = _pixi_root()
    try:
        result = subprocess.run(
            [pixi, "list", "-e", env_name, "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        packages = []
        for pkg in data:
            if isinstance(pkg, dict):
                packages.append({
                    "name": pkg.get("name", ""),
                    "version": pkg.get("version", ""),
                    "channel": pkg.get("channel", ""),
                    "build": pkg.get("build", ""),
                })
        return packages
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def create_pixi_env(
    name: str,
    packages: list[str],
    channels: list[str] | None = None,
    pip_packages: list[str] | None = None,
) -> tuple[bool, str]:
    """Ensure a pixi environment exists with the specified packages.

    With pixi, environments are defined in ``pixi.toml`` features.  This
    function adds the requested packages to the manifest and installs them.

    Returns:
        (success, message)
    """
    pixi = _find_pixi_executable()
    if pixi is None:
        return False, "pixi executable not found"

    root = _pixi_root()
    pixi_name = _to_pixi_env_name(name)

    # Add conda packages via pixi add
    if packages:
        cmd = [pixi, "add", "-e", pixi_name] + packages
        logger.info("Adding packages to pixi env '%s': %s", pixi_name, " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                logger.error("pixi add failed: %s", result.stderr)
                return False, f"pixi add failed: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return False, "pixi add timed out after 10 minutes"
        except FileNotFoundError:
            return False, f"pixi executable not found: {pixi}"

    # Add PyPI packages if specified
    if pip_packages:
        cmd = [pixi, "add", "-e", pixi_name, "--pypi"] + pip_packages
        try:
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error("pixi add (pypi) failed: %s", result.stderr)
                return False, f"pip install via pixi failed: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return False, "PyPI install timed out"

    return True, f"Environment '{pixi_name}' updated successfully"


def delete_pixi_env(name: str) -> tuple[bool, str]:
    """Remove a pixi environment.

    With pixi, environments live in ``.pixi/envs/<name>/``.  Deleting the
    directory is sufficient; the manifest entry can remain.

    Returns:
        (success, message)
    """
    pixi_name = _to_pixi_env_name(name)
    root = _pixi_root()
    env_dir = root / ".pixi" / "envs" / pixi_name
    if not env_dir.exists():
        return True, f"Environment '{pixi_name}' does not exist"
    try:
        import shutil as _shutil
        _shutil.rmtree(env_dir)
        return True, f"Environment '{pixi_name}' removed"
    except Exception as exc:
        return False, f"Failed to remove environment: {exc}"


def install_into_env(
    env_name: str,
    packages: list[str],
    channels: list[str] | None = None,
) -> tuple[bool, str]:
    """Install conda packages into an existing pixi environment.

    Returns:
        (success, message)
    """
    return create_pixi_env(env_name, packages, channels)


def executable_in_env(executable: str, env_name: str) -> bool:
    """Check if an executable exists within a specific pixi environment."""
    pixi_name = _to_pixi_env_name(env_name)
    root = _pixi_root()
    env_bin = root / ".pixi" / "envs" / pixi_name / "bin" / executable
    if env_bin.exists():
        return True
    # Also check the default env as fallback
    default_bin = root / ".pixi" / "envs" / "default" / "bin" / executable
    if default_bin.exists():
        return True
    return False


def create_workflow_env(
    workflow_id: str,
    dependencies: list[str],
    channels: list[str] | None = None,
) -> tuple[bool, str, str]:
    """Create a dedicated environment for a specific workflow.

    Returns:
        (success, message, env_name)
    """
    env_name = f"bionodulo-wf-{workflow_id[:16]}"
    success, msg = create_pixi_env(env_name, dependencies, channels)
    return success, msg, env_name


def env_exists(name: str) -> bool:
    """Check if a pixi environment is defined in the manifest or installed."""
    pixi_name = _to_pixi_env_name(name)
    root = _pixi_root()
    env_dir = root / ".pixi" / "envs" / pixi_name
    if env_dir.exists():
        return True
    # Also check if the environment is defined in the manifest
    pixi = _find_pixi_executable()
    if pixi is None:
        return False
    try:
        result = subprocess.run(
            [pixi, "info", "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            environments = data.get("environments", {})
            return pixi_name in environments
    except Exception:
        pass
    return False


def ensure_channels_configured() -> bool:
    """Channels are defined in ``pixi.toml``; no runtime configuration needed."""
    return True


def create_env_from_yaml(
    yaml_path: str,
    env_name: str | None = None,
    timeout: int = 600,
) -> bool:
    """Pixi does not use Conda YAML specs natively.

    This function logs a warning and returns False.  Users should migrate
    to ``pixi.toml`` features instead.
    """
    logger.warning(
        "create_env_from_yaml is not supported with pixi. "
        "Add dependencies to pixi.toml instead."
    )
    return False
