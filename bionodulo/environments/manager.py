"""Environment manager for BioNodulo.

Provides CRUD operations for Conda/Mamba/Micromamba environments,
plus utilities to check tool availability within specific environments.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.environments.model import EnvironmentSpec

logger = logging.getLogger(__name__)


def _find_conda_executable() -> str | None:
    """Find micromamba, mamba, or conda executable.

    Prefers the system PATH, then falls back to the managed micromamba
    installation that BioNodulo can bootstrap automatically.
    """
    for exe in ("micromamba", "mamba", "conda"):
        path = shutil.which(exe)
        if path:
            return path
    # Fallback to managed installation
    from bionodulo.manager.runtime_installer import get_micromamba_path
    managed = get_micromamba_path()
    if managed is not None:
        return str(managed)
    return None


def list_conda_envs() -> list[dict[str, Any]]:
    """List all conda environments.

    Returns a list of dicts with name, path, and active status.
    """
    exe = _find_conda_executable()
    if not exe:
        return []

    try:
        result = subprocess.run(
            [exe, "env", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("conda env list failed: %s", result.stderr)
            return []
        data = json.loads(result.stdout)
        envs = []
        for item in data.get("envs", []):
            path = Path(item)
            name = path.name if path.name != "conda" else "base"
            # Try to detect if it's the base env
            if "envs" not in str(path):
                name = "base"
            envs.append({
                "name": name,
                "path": str(path),
                "active": False,  # We don't track active shell env
            })
        return envs
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning("Failed to list conda environments: %s", exc)
        return []


def get_env_packages(env_name: str) -> list[dict[str, str]]:
    """List packages installed in a conda environment.

    Returns list of dicts with name and version.
    """
    exe = _find_conda_executable()
    if not exe:
        return []

    try:
        result = subprocess.run(
            [exe, "list", "-n", env_name, "--json"],
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
                    "build": pkg.get("build_string", ""),
                })
        return packages
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def create_conda_env(
    name: str,
    packages: list[str],
    channels: list[str] | None = None,
    pip_packages: list[str] | None = None,
) -> tuple[bool, str]:
    """Create a new conda environment with specified packages.

    Returns (success, message).
    """
    exe = _find_conda_executable()
    if not exe:
        return False, "No conda executable found (micromamba, mamba, or conda)"

    channels = channels or ["bioconda", "conda-forge", "defaults"]

    cmd = [exe, "create", "-y", "-n", name]
    for ch in channels:
        cmd.extend(["-c", ch])
    cmd.extend(packages)

    logger.info("Creating conda env '%s': %s", name, " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            logger.error("Failed to create env '%s': %s", name, result.stderr)
            return False, f"Environment creation failed: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "Environment creation timed out after 10 minutes"
    except FileNotFoundError:
        return False, f"Conda executable not found: {exe}"

    # Install pip packages if specified
    if pip_packages:
        pip_cmd = [exe, "run", "-n", name, "python", "-m", "pip", "install"] + pip_packages
        try:
            result = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error("Failed to install pip packages in '%s': %s", name, result.stderr)
                return False, f"Pip install failed: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return False, "Pip install timed out"

    return True, f"Environment '{name}' created successfully"


def delete_conda_env(name: str) -> tuple[bool, str]:
    """Remove a conda environment.

    Returns (success, message).
    """
    exe = _find_conda_executable()
    if not exe:
        return False, "No conda executable found"

    # Use 'env remove' for micromamba/mamba, fallback to 'remove --all' for conda
    if "micromamba" in exe or "mamba" in exe:
        cmd = [exe, "env", "remove", "-y", "-n", name]
    else:
        cmd = [exe, "remove", "-y", "-n", name, "--all"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, f"Failed to remove environment: {result.stderr[:500]}"
        return True, f"Environment '{name}' removed"
    except subprocess.TimeoutExpired:
        return False, "Remove operation timed out"
    except FileNotFoundError:
        return False, f"Conda executable not found: {exe}"


def install_into_env(
    env_name: str,
    packages: list[str],
    channels: list[str] | None = None,
) -> tuple[bool, str]:
    """Install conda packages into an existing environment.

    Returns (success, message).
    """
    exe = _find_conda_executable()
    if not exe:
        return False, "No conda executable found"

    channels = channels or ["bioconda", "conda-forge", "defaults"]
    cmd = [exe, "install", "-y", "-n", env_name]
    for ch in channels:
        cmd.extend(["-c", ch])
    cmd.extend(packages)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return False, f"Install failed: {result.stderr[:500]}"
        return True, f"Installed {len(packages)} package(s) into '{env_name}'"
    except subprocess.TimeoutExpired:
        return False, "Install timed out"
    except FileNotFoundError:
        return False, f"Conda executable not found: {exe}"


def executable_in_env(executable: str, env_name: str) -> bool:
    """Check if an executable exists within a specific conda environment."""
    exe = _find_conda_executable()
    if not exe:
        return False

    try:
        result = subprocess.run(
            [exe, "run", "-n", env_name, "which", executable],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def create_workflow_env(
    workflow_id: str,
    dependencies: list[str],
    channels: list[str] | None = None,
) -> tuple[bool, str, str]:
    """Create a dedicated environment for a specific workflow.

    Args:
        workflow_id: Unique workflow identifier (used to name the env).
        dependencies: List of conda package specs to install.
        channels: Optional channel list.

    Returns:
        (success, message, env_name)
    """
    env_name = f"bionodulo-wf-{workflow_id[:16]}"
    success, msg = create_conda_env(env_name, dependencies, channels)
    return success, msg, env_name


def env_exists(name: str) -> bool:
    """Check if a conda environment exists by name."""
    envs = list_conda_envs()
    return any(e["name"] == name for e in envs)


@dataclass
class DependencyStatus:
    """Status of a single dependency for a workflow."""

    name: str
    type: str  # "node", "executable", "package"
    status: str  # "installed", "missing", "installing", "error"
    source: str = ""  # git_url, conda_package, pip_name
    message: str = ""
    envs: list[str] = field(default_factory=list)  # envs where this is available


def workflow_dependency_tree(
    workflow: dict[str, Any],
    registry: Any,
) -> list[DependencyStatus]:
    """Build a dependency status tree for a workflow.

    Checks each node type and its required executables against:
    1. The node registry (is the node installed?)
    2. System PATH (is the executable available?)
    3. Conda environments (is the executable available in any env?)
    """
    from bionodulo.manager.resolver import resolve_workflow

    report = resolve_workflow(workflow, registry)
    statuses: list[DependencyStatus] = []

    # Add missing nodes
    for node in report.missing_nodes:
        statuses.append(DependencyStatus(
            name=node.node_type,
            type="node",
            status="missing",
            source=node.git_url,
            message=node.message or "Not installed",
        ))

    # Check installed nodes' executables
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    node_types_seen: set[str] = set()
    for n in nodes:
        node_type = n.get("type", "") if isinstance(n, dict) else getattr(n, "type", "")
        if not node_type or node_type in node_types_seen:
            continue
        node_types_seen.add(node_type)

        if registry.has(node_type):
            meta = registry.object_info(node_type) or {}
            execs = meta.get("requires_external_tools", [])
            for exe in execs:
                on_path = shutil.which(exe) is not None
                # Check node's default isolated environment
                in_isolated_env = False
                isolated_env_name = ""
                try:
                    node_cls = registry.get(node_type)
                    if node_cls is not None:
                        category = getattr(node_cls, "CATEGORY", "general")
                        isolated_env_name = f"bionodulo-{category.lower().replace(' ', '_').replace('/', '_')}"
                        if executable_in_env(exe, isolated_env_name):
                            in_isolated_env = True
                except Exception:
                    pass

                # Check all conda envs as fallback
                envs_with_tool: list[str] = []
                if not on_path and not in_isolated_env:
                    for env in list_conda_envs():
                        if executable_in_env(exe, env["name"]):
                            envs_with_tool.append(env["name"])

                if on_path:
                    statuses.append(DependencyStatus(
                        name=exe,
                        type="executable",
                        status="installed",
                        message="Available on PATH",
                    ))
                elif in_isolated_env:
                    statuses.append(DependencyStatus(
                        name=exe,
                        type="executable",
                        status="installed",
                        message=f"Available in isolated env: {isolated_env_name}",
                        envs=[isolated_env_name],
                    ))
                elif envs_with_tool:
                    statuses.append(DependencyStatus(
                        name=exe,
                        type="executable",
                        status="installed",
                        message=f"Available in: {', '.join(envs_with_tool)}",
                        envs=envs_with_tool,
                    ))
                else:
                    statuses.append(DependencyStatus(
                        name=exe,
                        type="executable",
                        status="missing",
                        message="Not on PATH and not found in any conda environment",
                    ))

    # Add missing executables from report (deduplicate with above)
    seen_names = {s.name for s in statuses}
    for exe in report.missing_executables:
        if exe.name not in seen_names:
            envs_with_tool = []
            for env in list_conda_envs():
                if executable_in_env(exe.name, env["name"]):
                    envs_with_tool.append(env["name"])
            if envs_with_tool:
                statuses.append(DependencyStatus(
                    name=exe.name,
                    type="executable",
                    status="installed",
                    message=f"Available in: {', '.join(envs_with_tool)}",
                    envs=envs_with_tool,
                ))
            else:
                statuses.append(DependencyStatus(
                    name=exe.name,
                    type="executable",
                    status="missing",
                    source=exe.conda_package,
                    message=exe.message or "Not installed",
                ))

    return statuses
