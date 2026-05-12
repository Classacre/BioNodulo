"""Workflow dependency resolution for BioNodulo.

Scans workflows for node types, executables, and Python packages,
then resolves what's missing and how to install it.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MissingNode:
    """A custom node type that is not currently registered."""

    node_type: str
    git_url: str = ""
    git_commit: str = ""
    requirements: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class MissingExecutable:
    """An external tool executable that is not on PATH."""

    name: str
    conda_package: str = ""
    node_types: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class MissingPackage:
    """A Python package that needs installation."""

    name: str
    source: str = "pip"  # pip or conda
    node_types: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class ResolutionReport:
    """Complete resolution report for a workflow."""

    missing_nodes: list[MissingNode] = field(default_factory=list)
    missing_executables: list[MissingExecutable] = field(default_factory=list)
    missing_packages: list[MissingPackage] = field(default_factory=list)
    installable: bool = True
    errors: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.missing_nodes
            or self.missing_executables
            or self.missing_packages
            or self.errors
        )

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.missing_nodes:
            parts.append(f"{len(self.missing_nodes)} node(s)")
        if self.missing_executables:
            parts.append(f"{len(self.missing_executables)} tool(s)")
        if self.missing_packages:
            parts.append(f"{len(self.missing_packages)} package(s)")
        return ", ".join(parts) if parts else "All dependencies satisfied"

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_nodes": [
                {
                    "node_type": n.node_type,
                    "git_url": n.git_url,
                    "git_commit": n.git_commit,
                    "requirements": n.requirements,
                    "message": n.message,
                }
                for n in self.missing_nodes
            ],
            "missing_executables": [
                {
                    "name": e.name,
                    "conda_package": e.conda_package,
                    "node_types": e.node_types,
                    "message": e.message,
                }
                for e in self.missing_executables
            ],
            "missing_packages": [
                {
                    "name": p.name,
                    "source": p.source,
                    "node_types": p.node_types,
                    "message": p.message,
                }
                for p in self.missing_packages
            ],
            "installable": self.installable,
            "errors": self.errors,
            "has_issues": self.has_issues,
            "summary": self.summary,
        }


def build_node_manifest(
    workflow: dict[str, Any],
    registry: Any,
) -> dict[str, dict[str, Any]]:
    """Build a manifest of all node types used in a workflow.

    Captures metadata at save time so missing nodes can be resolved
    even if they are later uninstalled.
    """
    manifest: dict[str, dict[str, Any]] = {}
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = nodes.values()

    seen: set[str] = set()
    for node in nodes:
        if isinstance(node, dict):
            node_type = node.get("type", "")
        else:
            node_type = getattr(node, "type", "")
        if not node_type or node_type in seen:
            continue
        seen.add(node_type)

        entry: dict[str, Any] = {"type": node_type}

        if registry is not None and hasattr(registry, "get"):
            node_class = registry.get(node_type)
            if node_class is not None:
                entry["display_name"] = getattr(node_class, "DISPLAY_NAME", node_type)
                entry["category"] = getattr(node_class, "CATEGORY", "")
                entry["version"] = getattr(node_class, "VERSION", "")
                entry["git_url"] = getattr(node_class, "GIT_URL", "")
                entry["git_commit"] = getattr(node_class, "GIT_COMMIT", "")
                entry["required_executables"] = getattr(
                    node_class, "REQUIRED_EXECUTABLES", []
                )
                entry["builtin"] = getattr(node_class, "__module__", "").startswith(
                    "bionodulo.nodes.builtin"
                )
                entry["python_class"] = (
                    f"{node_class.__module__}.{node_class.__name__}"
                )
            else:
                # Node not registered — try to get info from the node's stored node_info
                node_info = node.get("node_info", {}) if isinstance(node, dict) else {}
                if node_info:
                    entry["display_name"] = node_info.get("display_name", node_type)
                    entry["category"] = node_info.get("category", "")
                    entry["version"] = node_info.get("version", "")
                    entry["git_url"] = node_info.get("git_url", "")
                    entry["git_commit"] = node_info.get("git_commit", "")
                    entry["required_executables"] = node_info.get(
                        "required_executables", []
                    )
                    entry["builtin"] = node_info.get("builtin", False)

        manifest[node_type] = entry

    return manifest


def resolve_workflow(
    workflow: dict[str, Any],
    registry: Any,
) -> ResolutionReport:
    """Resolve dependencies for a workflow.

    Checks:
    1. All node types are registered (missing custom nodes).
    2. Required executables are on PATH.
    3. Python requirements from custom node packages.
    """
    report = ResolutionReport()
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    # Collect node types and their usages
    node_type_usages: dict[str, list[str]] = {}
    for node in nodes:
        if isinstance(node, dict):
            node_type = node.get("type", "")
            node_id = node.get("id", "")
        else:
            node_type = getattr(node, "type", "")
            node_id = getattr(node, "id", "")
        if node_type:
            node_type_usages.setdefault(node_type, []).append(node_id)

    # Use manifest if available, otherwise build from registry
    manifest = workflow.get("node_manifest", {})

    for node_type, node_ids in node_type_usages.items():
        # 1. Check if node is registered
        node_class = None
        if registry is not None and hasattr(registry, "get"):
            node_class = registry.get(node_type)

        if node_class is None:
            # Missing node — try to resolve from manifest
            manifest_entry = manifest.get(node_type, {})
            git_url = manifest_entry.get("git_url", "")
            git_commit = manifest_entry.get("git_commit", "")

            if git_url:
                msg = f"Custom node '{node_type}' is not installed. Source: {git_url}"
            else:
                msg = (
                    f"Custom node '{node_type}' is not installed and no git URL "
                    f"was recorded in the workflow manifest."
                )
                report.installable = False

            report.missing_nodes.append(
                MissingNode(
                    node_type=node_type,
                    git_url=git_url,
                    git_commit=git_commit,
                    message=msg,
                )
            )
            continue

        # 2. Check required executables
        executables = getattr(node_class, "REQUIRED_EXECUTABLES", [])
        for exe in executables:
            if shutil.which(exe) is None:
                # Guess conda package name (usually same as executable)
                conda_pkg = exe
                report.missing_executables.append(
                    MissingExecutable(
                        name=exe,
                        conda_package=conda_pkg,
                        node_types=[node_type],
                        message=f"Executable '{exe}' required by '{node_type}' is not on PATH",
                    )
                )

        # 3. Check for requirements.txt in custom node package
        module_name = getattr(node_class, "__module__", "")
        if not module_name.startswith("bionodulo.nodes.builtin"):
            # Try to find requirements.txt in the custom node directory
            try:
                module = __import__(module_name, fromlist=[""])
                module_file = getattr(module, "__file__", None)
                if module_file:
                    module_dir = Path(module_file).parent
                    req_file = module_dir / "requirements.txt"
                    if req_file.exists():
                        reqs = [
                            line.strip()
                            for line in req_file.read_text().splitlines()
                            if line.strip() and not line.startswith("#")
                        ]
                        for req in reqs:
                            # Simple check: just report them as potentially missing
                            # A more robust check would try import, but that's fragile
                            pkg_name = req.split("==")[0].split(">=")[0].strip()
                            report.missing_packages.append(
                                MissingPackage(
                                    name=pkg_name,
                                    source="pip",
                                    node_types=[node_type],
                                    message=f"Python package '{pkg_name}' from {node_type} requirements",
                                )
                            )
            except Exception as exc:
                logger.debug("Could not check requirements for %s: %s", node_type, exc)

    # Deduplicate missing executables and packages
    seen_exes: dict[str, MissingExecutable] = {}
    for exe in report.missing_executables:
        if exe.name in seen_exes:
            seen_exes[exe.name].node_types.extend(exe.node_types)
        else:
            seen_exes[exe.name] = exe
    report.missing_executables = list(seen_exes.values())

    seen_pkgs: dict[str, MissingPackage] = {}
    for pkg in report.missing_packages:
        if pkg.name in seen_pkgs:
            seen_pkgs[pkg.name].node_types.extend(pkg.node_types)
        else:
            seen_pkgs[pkg.name] = pkg
    report.missing_packages = list(seen_pkgs.values())

    return report
