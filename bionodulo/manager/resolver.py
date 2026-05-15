"""Workflow dependency resolution for BioNodulo.

Scans workflows for node types, executables, and Python packages,
then resolves what's missing and how to install it.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Module-level TTL caches for expensive subprocess operations that rarely
# change during normal operation.
_ENV_LIST_CACHE: list[dict[str, Any]] | None = None
_ENV_LIST_TIMESTAMP = 0.0
_ENV_LIST_TTL = 30.0  # seconds

_IN_ENV_CACHE: dict[tuple[str, str], bool] = {}
_IN_ENV_TIMESTAMP = 0.0
_IN_ENV_TTL = 60.0  # seconds


def _get_cached_env_list() -> list[dict[str, Any]] | None:
    """Return the cached conda env list if still within TTL."""
    global _ENV_LIST_CACHE, _ENV_LIST_TIMESTAMP
    if _ENV_LIST_CACHE is not None and (time.time() - _ENV_LIST_TIMESTAMP) < _ENV_LIST_TTL:
        return _ENV_LIST_CACHE
    return None


def _set_cached_env_list(envs: list[dict[str, Any]]) -> None:
    """Store the conda env list and reset the TTL timestamp."""
    global _ENV_LIST_CACHE, _ENV_LIST_TIMESTAMP
    _ENV_LIST_CACHE = envs
    _ENV_LIST_TIMESTAMP = time.time()


def _get_cached_in_env(exe: str, env_name: str) -> bool | None:
    """Return cached executable-in-env result if still within TTL."""
    global _IN_ENV_CACHE, _IN_ENV_TIMESTAMP
    if _IN_ENV_TIMESTAMP and (time.time() - _IN_ENV_TIMESTAMP) < _IN_ENV_TTL:
        return _IN_ENV_CACHE.get((exe, env_name))
    return None


def _set_cached_in_env(exe: str, env_name: str, result: bool) -> None:
    """Store an executable-in-env result and update the TTL timestamp."""
    global _IN_ENV_CACHE, _IN_ENV_TIMESTAMP
    _IN_ENV_CACHE[(exe, env_name)] = result
    _IN_ENV_TIMESTAMP = time.time()


class _ResolverCache:
    """Fast in-memory cache for executable checks during a single resolve call.

    The resolver's main performance bottleneck is spawning subprocesses
    (``shutil.which`` is fast, but ``executable_in_env`` shells out to
    conda).  Many nodes share the same executables, and many envs do not
    exist at all, so caching per-resolve eliminates redundant work.
    """

    def __init__(self) -> None:
        self._which: dict[str, str | None] = {}
        self._env_check: dict[tuple[str, str], bool] = {}
        self._env_list: list[dict[str, Any]] | None = None

    def which(self, exe: str) -> str | None:
        if exe not in self._which:
            self._which[exe] = shutil.which(exe)
        return self._which[exe]

    def _list_envs(self) -> list[dict[str, Any]]:
        if self._env_list is None:
            cached = _get_cached_env_list()
            if cached is not None:
                self._env_list = cached
            else:
                try:
                    from bionodulo.environments.manager import list_conda_envs

                    self._env_list = list_conda_envs()
                    _set_cached_env_list(self._env_list)
                except Exception:
                    self._env_list = []
        return self._env_list

    def env_exists(self, env_name: str) -> bool:
        return any(e.get("name") == env_name for e in self._list_envs())

    def in_env(self, exe: str, env_name: str) -> bool:
        key = (exe, env_name)
        if key not in self._env_check:
            # Check module-level TTL cache first
            cached = _get_cached_in_env(exe, env_name)
            if cached is not None:
                self._env_check[key] = cached
            else:
                # Fast-path: if env does not exist, skip the subprocess call
                if not self.env_exists(env_name):
                    self._env_check[key] = False
                else:
                    try:
                        from bionodulo.environments.manager import executable_in_env

                        result = executable_in_env(exe, env_name)
                        self._env_check[key] = result
                        _set_cached_in_env(exe, env_name, result)
                    except Exception:
                        self._env_check[key] = False
        return self._env_check[key]


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
    """An external tool executable that is not on PATH or incompatible."""

    name: str
    conda_package: str = ""
    node_types: list[str] = field(default_factory=list)
    message: str = ""
    compatibility_error: str = ""
    recommended_env: str = "bionodulo-tools"
    category: str = "general"

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
    recommended_env: str = "bionodulo-tools"


@dataclass
class CompatibilityIssue:
    """An executable that exists but cannot run on the host."""

    name: str
    path: str = ""
    error: str = ""
    node_types: list[str] = field(default_factory=list)
    conda_package: str = ""
    message: str = ""


@dataclass
class ResolutionReport:
    """Complete resolution report for a workflow."""

    missing_nodes: list[MissingNode] = field(default_factory=list)
    missing_executables: list[MissingExecutable] = field(default_factory=list)
    missing_packages: list[MissingPackage] = field(default_factory=list)
    missing_r_packages: list[MissingRPackage] = field(default_factory=list)
    compatibility_issues: list[CompatibilityIssue] = field(default_factory=list)
    installable: bool = True
    errors: list[str] = field(default_factory=list)
    env_strategy: str = "shared"  # "shared" | "isolated"

    @property
    def has_issues(self) -> bool:
        return bool(
            self.missing_nodes
            or self.missing_executables
            or self.missing_packages
            or self.missing_r_packages
            or self.compatibility_issues
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
                    "compatibility_error": e.compatibility_error,
                    "recommended_env": e.recommended_env,
                    "category": e.category,
                }
                for e in self.missing_executables
            ],
            "compatibility_issues": [
                {
                    "name": c.name,
                    "path": c.path,
                    "error": c.error,
                    "node_types": c.node_types,
                    "conda_package": c.conda_package,
                    "message": c.message,
                }
                for c in self.compatibility_issues
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
                    "recommended_env": p.recommended_env,
                }
                for p in self.missing_r_packages
            ],
            "installable": self.installable,
            "errors": self.errors,
            "has_issues": self.has_issues,
            "summary": self.summary,
            "env_strategy": self.env_strategy,
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


async def _resolve_node_type(
    node_type: str,
    node_ids: list[str],
    registry: Any,
    manifest: dict[str, Any],
    cache: _ResolverCache,
) -> tuple[
    list[MissingNode],
    list[MissingExecutable],
    list[MissingPackage],
    dict[str, list[str]],
]:
    """Resolve dependencies for a single node type.

    Returns any missing nodes, executables, packages, and a map of
    R packages to the node types that require them.
    """
    missing_nodes: list[MissingNode] = []
    missing_executables: list[MissingExecutable] = []
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
        return missing_nodes, missing_executables, missing_packages, r_packages_to_check

    # Check required executables (fast-path first)
    executables = getattr(node_class, "REQUIRED_EXECUTABLES", [])
    conda_packages = getattr(node_class, "REQUIRED_CONDA_PACKAGES", [])
    category = getattr(node_class, "CATEGORY", "general")
    isolated_env_name = f"bionodulo-{category.lower().replace(' ', '_').replace('/', '_')}"

    for exe in executables:
        exe_path = cache.which(exe)
        if exe_path is not None:
            continue
        if cache.in_env(exe, isolated_env_name):
            continue
        if cache.in_env(exe, "bionodulo-tools"):
            continue

        conda_pkg = ""
        if conda_packages:
            conda_pkg = conda_packages[0]
        else:
            from bionodulo.manager.diagnostics import KNOWN_EXECUTABLES

            conda_pkg = KNOWN_EXECUTABLES.get(exe, exe)

        missing_executables.append(
            MissingExecutable(
                name=exe,
                conda_package=conda_pkg,
                node_types=[node_type],
                message=f"Executable '{exe}' required by '{node_type}' is not on PATH or in its isolated environment",
                recommended_env=isolated_env_name,
                category=category,
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

    return missing_nodes, missing_executables, missing_packages, r_packages_to_check


async def _resolve_workflow_async(
    workflow: dict[str, Any],
    registry: Any,
) -> ResolutionReport:
    """Async implementation of dependency resolution.

    Node-type checks run concurrently via ``asyncio.gather``.
    """
    report = ResolutionReport()
    cache = _ResolverCache()
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
        _resolve_node_type(node_type, node_ids, registry, manifest, cache)
        for node_type, node_ids in node_type_usages.items()
    ]

    results = await asyncio.gather(*coros, return_exceptions=True)

    r_packages_to_check: dict[str, list[str]] = {}

    for result in results:
        if isinstance(result, Exception):
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

    # Check R packages via Rscript — check ALL candidate envs and consider
    # a package available if it is found in ANY environment.
    if r_packages_to_check:
        try:
            import subprocess

            from bionodulo.manager.runtime_installer import get_pixi_path
            from bionodulo.environments.pixi import _to_pixi_env_name

            pixi = get_pixi_path()
            r_script = (
                "cat(paste(sapply(c("
                + ",".join(f"'{p}'" for p in r_packages_to_check)
                + "), function(p) paste(p, requireNamespace(p, quietly=TRUE), sep=':')), collapse='\\n'))"
            )

            available_anywhere: dict[str, bool] = {}

            def _check_r_in_env(cmd: list[str]) -> None:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if ":" in line:
                            pkg_name, available = line.strip().rsplit(":", 1)
                            if available.strip().lower() == "true":
                                available_anywhere[pkg_name] = True

            # Check pixi envs
            if pixi:
                for env_name in ["r", "tools"]:
                    try:
                        check = subprocess.run(
                            [str(pixi), "run", "-e", env_name, "Rscript", "--version"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if check.returncode == 0:
                            _check_r_in_env(
                                [str(pixi), "run", "-e", env_name, "Rscript", "-e", r_script]
                            )
                    except Exception:
                        pass

            # Check system PATH as fallback
            try:
                _check_r_in_env(["Rscript", "-e", r_script])
            except Exception:
                pass

            for pkg, node_types in r_packages_to_check.items():
                if available_anywhere.get(pkg):
                    continue
                source = (
                    "bioconductor"
                    if pkg.lower()
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
                        name=pkg,
                        source=source,
                        node_types=node_types,
                        message=f"R package '{pkg}' required by {', '.join(node_types)} is not installed",
                        recommended_env="bionodulo-r",
                    )
                )
        except Exception as exc:
            logger.debug("Could not check R packages: %s", exc)
            for pkg, node_types in r_packages_to_check.items():
                source = (
                    "bioconductor"
                    if pkg.lower()
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
                        name=pkg,
                        source=source,
                        node_types=node_types,
                        message=f"R package '{pkg}' required by {', '.join(node_types)} — could not verify: {exc}",
                        recommended_env="bionodulo-r",
                    )
                )

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
) -> ResolutionReport:
    """Resolve dependencies for a workflow.

    Checks:
    1. All node types are registered (missing custom nodes).
    2. Required executables are on PATH.
    3. Python requirements from custom node packages.

    This is a synchronous wrapper around the async implementation.
    Callers inside an async context (e.g. FastAPI handlers) should
    ``await _resolve_workflow_async(...)`` directly.
    """
    return asyncio.run(_resolve_workflow_async(workflow, registry))
