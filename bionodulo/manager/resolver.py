"""Workflow dependency resolution for BioNodulo.

Scans workflows for node types, executables, and Python packages,
then returns what is required and how to obtain it.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
)
from bionodulo.environments.manifest import (
    get_env_dir,
    get_env_id,
    is_env_ready,
    workflow_to_packages,
)

logger = logging.getLogger(__name__)


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
                if hasattr(node_class, "lifecycle_metadata"):
                    entry["lifecycle"] = node_class.lifecycle_metadata()
                if hasattr(node_class, "versioning_metadata"):
                    entry["versioning"] = node_class.versioning_metadata()
                entry["git_url"] = getattr(node_class, "GIT_URL", "")
                entry["git_commit"] = getattr(node_class, "GIT_COMMIT", "")
                entry["required_executables"] = getattr(
                    node_class, "REQUIRED_EXECUTABLES", []
                )
                entry["required_r_packages"] = getattr(
                    node_class, "REQUIRED_R_PACKAGES", []
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
                    entry["lifecycle"] = node_info.get("lifecycle", {})
                    entry["versioning"] = node_info.get("versioning", {})
                    entry["git_url"] = node_info.get("git_url", "")
                    entry["git_commit"] = node_info.get("git_commit", "")
                    entry["required_executables"] = node_info.get(
                        "required_executables", []
                    )
                    entry["required_r_packages"] = node_info.get(
                        "required_r_packages", []
                    )
                    entry["builtin"] = node_info.get("builtin", False)

        manifest[node_type] = entry

    return manifest


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
    """An external tool executable that is not available."""

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
class MissingRPackage:
    """An R package that needs installation."""

    name: str
    source: str = "cran"  # cran or bioconductor
    node_types: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class ResolutionReport:
    """Complete resolution report for a workflow."""

    missing_nodes: list[MissingNode] = field(default_factory=list)
    missing_executables: list[MissingExecutable] = field(default_factory=list)
    missing_packages: list[MissingPackage] = field(default_factory=list)
    missing_r_packages: list[MissingRPackage] = field(default_factory=list)
    required_packages: list[str] = field(default_factory=list)
    env_id: str = ""
    env_ready: bool = False
    installable: bool = True
    errors: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.missing_nodes
            or self.missing_executables
            or self.missing_packages
            or self.missing_r_packages
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
            parts.append(f"{len(self.missing_packages)} Python package(s)")
        if self.missing_r_packages:
            parts.append(f"{len(self.missing_r_packages)} R package(s)")
        if not self.env_ready and self.required_packages:
            parts.append(f"env not ready ({len(self.required_packages)} packages)")
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
            "missing_r_packages": [
                {
                    "name": p.name,
                    "source": p.source,
                    "node_types": p.node_types,
                    "message": p.message,
                }
                for p in self.missing_r_packages
            ],
            "required_packages": self.required_packages,
            "env_id": self.env_id,
            "env_ready": self.env_ready,
            "installable": self.installable,
            "errors": self.errors,
            "has_issues": self.has_issues,
            "summary": self.summary,
        }


async def _resolve_node_type(
    node_type: str,
    node_ids: list[str],
    registry: Any,
    manifest: dict[str, Any],
) -> tuple[
    list[MissingNode],
    list[MissingExecutable],
    list[MissingPackage],
    dict[str, list[str]],
]:
    """Resolve dependencies for a single node type.

    Returns missing nodes, required executables (for later filtering),
    missing packages, and a map of R packages to the node types that require them.
    """
    missing_nodes: list[MissingNode] = []
    required_executables: list[MissingExecutable] = []
    missing_packages: list[MissingPackage] = []
    r_packages_to_check: dict[str, list[str]] = {}

    node_class = None
    if registry is not None and hasattr(registry, "get"):
        node_class = registry.get(node_type)

    if node_class is None:
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

        missing_nodes.append(
            MissingNode(
                node_type=node_type,
                git_url=git_url,
                git_commit=git_commit,
                message=msg,
            )
        )
        return missing_nodes, required_executables, missing_packages, r_packages_to_check

    # Collect required executables (availability checked later against env)
    executables = getattr(node_class, "REQUIRED_EXECUTABLES", [])
    conda_packages = getattr(node_class, "REQUIRED_CONDA_PACKAGES", [])

    for exe in executables:
        conda_pkg = ""
        if conda_packages:
            conda_pkg = conda_packages[0]
        else:
            conda_pkg = EXECUTABLE_TO_CONDA_PACKAGE.get(exe, exe)

        required_executables.append(
            MissingExecutable(
                name=exe,
                conda_package=conda_pkg,
                node_types=[node_type],
                message=f"Executable '{exe}' required by '{node_type}'",
            )
        )

    # Collect required R packages for later batch check
    r_packages = getattr(node_class, "REQUIRED_R_PACKAGES", [])
    for pkg in r_packages:
        r_packages_to_check.setdefault(pkg, []).append(node_type)

    # Check for requirements.txt in custom node package
    module_name = getattr(node_class, "__module__", "")
    if not module_name.startswith("bionodulo.nodes.builtin"):
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
                        pkg_name = req.split("==")[0].split(">=")[0].strip()
                        missing_packages.append(
                            MissingPackage(
                                name=pkg_name,
                                source="pip",
                                node_types=[node_type],
                                message=f"Python package '{pkg_name}' from {node_type} requirements",
                            )
                        )
        except Exception as exc:
            logger.debug("Could not check requirements for %s: %s", node_type, exc)

    return missing_nodes, required_executables, missing_packages, r_packages_to_check


async def _resolve_workflow_async(
    workflow: dict[str, Any],
    registry: Any,
    workspace_dir: str | Path = "./workspace",
) -> ResolutionReport:
    """Async implementation of dependency resolution."""
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

    manifest = workflow.get("node_manifest", {})

    # Run checks for each node type concurrently
    coros = [
        _resolve_node_type(node_type, node_ids, registry, manifest)
        for node_type, node_ids in node_type_usages.items()
    ]

    results = await asyncio.gather(*coros, return_exceptions=True)

    r_packages_to_check: dict[str, list[str]] = {}

    for result in results:
        if isinstance(result, BaseException):
            logger.warning("Node-type resolution failed: %s", result)
            report.errors.append(str(result))
            continue

        missing_nodes, missing_executables, missing_packages, node_r_pkgs = result
        report.missing_nodes.extend(missing_nodes)
        report.missing_executables.extend(missing_executables)
        report.missing_packages.extend(missing_packages)

        for pkg, node_types in node_r_pkgs.items():
            r_packages_to_check.setdefault(pkg, []).extend(node_types)

    # If any node was missing without a git URL, mark as not installable
    if any(not n.git_url for n in report.missing_nodes):
        report.installable = False

    # Build required packages list and env status
    report.required_packages = workflow_to_packages(workflow, registry)
    report.env_id = get_env_id(report.required_packages)
    env_dir = get_env_dir(report.env_id, workspace_dir)
    report.env_ready = is_env_ready(env_dir)

    # Filter executables: available if on PATH or in ready env
    deduped_exes: dict[str, MissingExecutable] = {}
    for exe in report.missing_executables:
        if exe.name in deduped_exes:
            deduped_exes[exe.name].node_types.extend(exe.node_types)
        else:
            deduped_exes[exe.name] = exe

    report.missing_executables = []
    for exe in deduped_exes.values():
        if shutil.which(exe.name):
            continue  # Available on system PATH
        if report.env_ready:
            # Env is installed — check if binary exists inside it
            env_bin = env_dir / ".pixi" / "envs" / "default" / "bin" / exe.name
            if env_bin.exists():
                continue
        report.missing_executables.append(exe)

    # Filter R packages: available if env is ready (they're in the manifest)
    if r_packages_to_check and not report.env_ready:
        for pkg_name, node_types in r_packages_to_check.items():
            source = (
                "bioconductor"
                if pkg_name.lower()
                in {
                    "deseq2",
                    "edger",
                    "limma",
                    "biostrings",
                    "genomicranges",
                    "rtracklayer",
                    "complexheatmap",
                    "summarizedexperiment",
                    "tximport",
                    "ape",
                    "phyloseq",
                    "variantannotation",
                }
                else "cran"
            )
            report.missing_r_packages.append(
                MissingRPackage(
                    name=pkg_name,
                    source=source,
                    node_types=node_types,
                    message=f"R package '{pkg_name}' required by {', '.join(node_types)}",
                )
            )

    # Deduplicate Python packages
    seen_pkgs: dict[str, MissingPackage] = {}
    for pkg in report.missing_packages:
        if pkg.name in seen_pkgs:
            seen_pkgs[pkg.name].node_types.extend(pkg.node_types)
        else:
            seen_pkgs[pkg.name] = pkg
    report.missing_packages = list(seen_pkgs.values())

    # Deduplicate R packages
    seen_r_pkgs: dict[str, MissingRPackage] = {}
    for pkg in report.missing_r_packages:
        if pkg.name in seen_r_pkgs:
            seen_r_pkgs[pkg.name].node_types.extend(pkg.node_types)
        else:
            seen_r_pkgs[pkg.name] = pkg
    report.missing_r_packages = list(seen_r_pkgs.values())

    return report


def resolve_workflow(
    workflow: dict[str, Any],
    registry: Any,
    workspace_dir: str | Path = "./workspace",
) -> ResolutionReport:
    """Resolve dependencies for a workflow.

    This is a synchronous wrapper around the async implementation.
    Callers inside an async context should await _resolve_workflow_async directly.
    """
    return asyncio.run(_resolve_workflow_async(workflow, registry, workspace_dir))
