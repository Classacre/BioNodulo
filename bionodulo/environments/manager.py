"""Environment manager for BioNodulo.

Provides CRUD operations for pixi environments,
plus utilities to check tool availability within specific environments.
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.environments.model import EnvironmentSpec
from bionodulo.environments.pixi import (
    _to_pixi_env_name,
    create_pixi_env,
    delete_pixi_env,
    env_exists,
    executable_in_env,
    get_env_packages,
    install_into_env,
    list_pixi_envs,
    pixi_run_prefix,
)

logger = logging.getLogger(__name__)


# Re-export for backwards compatibility until callers are updated
conda_run_prefix = pixi_run_prefix


def list_conda_envs() -> list[dict[str, Any]]:
    """List all environments (delegates to pixi)."""
    return list_pixi_envs()


def get_env_packages(env_name: str) -> list[dict[str, str]]:
    """List packages installed in an environment (delegates to pixi)."""
    return get_env_packages(env_name)


def create_conda_env(
    name: str,
    packages: list[str],
    channels: list[str] | None = None,
    pip_packages: list[str] | None = None,
) -> tuple[bool, str]:
    """Create a new environment with specified packages (delegates to pixi)."""
    return create_pixi_env(name, packages, channels, pip_packages)


def delete_conda_env(name: str) -> tuple[bool, str]:
    """Remove an environment (delegates to pixi)."""
    return delete_pixi_env(name)


def install_into_env(
    env_name: str,
    packages: list[str],
    channels: list[str] | None = None,
) -> tuple[bool, str]:
    """Install packages into an existing environment (delegates to pixi)."""
    return install_into_env(env_name, packages, channels)


def executable_in_env(executable: str, env_name: str) -> bool:
    """Check if an executable exists within a specific environment (delegates to pixi)."""
    return executable_in_env(executable, env_name)


def create_workflow_env(
    workflow_id: str,
    dependencies: list[str],
    channels: list[str] | None = None,
) -> tuple[bool, str, str]:
    """Create a dedicated environment for a specific workflow (delegates to pixi)."""
    return create_workflow_env(workflow_id, dependencies, channels)


def env_exists(name: str) -> bool:
    """Check if an environment exists by name (delegates to pixi)."""
    return env_exists(name)


@dataclass
class DependencyStatus:
    """Status of a single dependency for a workflow."""

    name: str
    type: str  # "node", "executable", "package"
    status: str  # "installed", "missing", "installing", "error"
    source: str = ""  # git_url, conda_package, pip_name
    message: str = ""
    envs: list[str] = field(default_factory=list)  # envs where this is available


async def workflow_dependency_tree(
    workflow: dict[str, Any],
    registry: Any,
) -> list[DependencyStatus]:
    """Build a dependency status tree for a workflow.

    Checks each node type and its required executables against:
    1. The node registry (is the node installed?)
    2. System PATH (is the executable available?)
    3. Pixi environments (is the executable available in any env?)
    """
    from bionodulo.manager.resolver import _resolve_workflow_async

    report = await _resolve_workflow_async(workflow, registry)
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

                # Check all pixi envs as fallback
                envs_with_tool: list[str] = []
                if not on_path and not in_isolated_env:
                    for env in list_pixi_envs():
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
                        message="Not on PATH and not found in any pixi environment",
                    ))

    # Add missing executables from report (deduplicate with above)
    seen_names = {s.name for s in statuses}
    for exe in report.missing_executables:
        if exe.name not in seen_names:
            envs_with_tool = []
            for env in list_pixi_envs():
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
