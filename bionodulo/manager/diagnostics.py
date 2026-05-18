"""Workflow diagnostics and environment status for BioNodulo.

Provides tools to check if required executables are available and
report on the overall tool installation status.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
from typing import Any

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE as KNOWN_EXECUTABLES
from bionodulo.nodes.base import BaseNode

logger = logging.getLogger(__name__)

# Module-level TTL cache for environment_status() to avoid 50+ shutil.which()
# calls on every status check.
_ENV_STATUS_CACHE: dict[str, Any] | None = None
_ENV_STATUS_TIMESTAMP = 0.0
_ENV_STATUS_TTL = 60.0  # seconds

# Module-level cache for R package checks.
# Key: (tuple(sorted(packages)), env_name)
# Value: dict[str, bool]  — {package_name: available}
_R_PACKAGE_CACHE: dict[tuple[tuple[str, ...], str], dict[str, bool]] = {}


def _check_r_packages_env_aware(
    packages: list[str],
    _cache: dict[tuple[tuple[str, ...], str], dict[str, bool]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Check R package availability across pixi envs and system PATH.

    Args:
        packages: List of R package names to check.
        _cache: Optional mutable cache dict.  If provided, results for the
            same set of packages in the same environment are reused.

    Returns:
        Dict mapping each package name to ``{"available": bool}`` (or
        ``{"available": False, "error": "..."}`` when missing).
    """
    if _cache is None:
        _cache = _R_PACKAGE_CACHE

    sorted_pkgs = tuple(sorted(packages))
    r_script = (
        "cat(paste(sapply(c("
        + ",".join(f"'{p}'" for p in packages)
        + "), function(p) paste(p, requireNamespace(p, quietly=TRUE), sep=':')), collapse='\\n'))"
    )
    available_anywhere: dict[str, bool] = {}

    def _check(cmd: list[str], env_name: str) -> None:
        cache_key = (sorted_pkgs, env_name)
        cached = _cache.get(cache_key)
        if cached is not None:
            available_anywhere.update(cached)
            return

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        env_results: dict[str, bool] = {}
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    pkg_name, available = line.strip().rsplit(":", 1)
                    is_avail = available.strip().lower() == "true"
                    env_results[pkg_name] = is_avail
                    if is_avail:
                        available_anywhere[pkg_name] = True
        _cache[cache_key] = env_results

    # Check via system PATH Rscript (per-workflow envs are checked separately)
    try:
        _check(["Rscript", "-e", r_script], "__system__")
    except Exception:
        pass

    results: dict[str, dict[str, Any]] = {}
    for pkg in packages:
        if available_anywhere.get(pkg):
            results[pkg] = {"available": True}
        else:
            results[pkg] = {"available": False, "error": "Not installed in any R environment"}
    return results


def diagnose_workflow(nodes: list[type[BaseNode]]) -> dict[str, Any]:
    """Check if all required executables and R packages for a workflow are available.

    Args:
        nodes: List of node classes to check.

    Returns:
        Dictionary with diagnostic results including missing tools and R packages.
    """
    required: set[str] = set()
    required_r: set[str] = set()
    for node_cls in nodes:
        if getattr(node_cls, "REQUIRES_EXTERNAL_TOOLS", False):
            required.update(getattr(node_cls, "REQUIRED_EXECUTABLES", []))
        required_r.update(getattr(node_cls, "REQUIRED_R_PACKAGES", []))

    results: dict[str, dict[str, Any]] = {}
    all_available = True
    for exe in sorted(required):
        available = shutil.which(exe) is not None
        results[exe] = {
            "available": available,
            "path": shutil.which(exe),
            "conda_package": KNOWN_EXECUTABLES.get(exe, "unknown"),
        }
        if not available:
            all_available = False

    # Check R packages across all R environments
    r_results: dict[str, dict[str, Any]] = {}
    r_available = True
    if required_r:
        r_results = _check_r_packages_env_aware(list(required_r))
        for info in r_results.values():
            if not info.get("available"):
                r_available = False
                break

    return {
        "all_available": all_available and r_available,
        "required": list(sorted(required)),
        "results": results,
        "missing": [exe for exe, info in results.items() if not info["available"]],
        "install_command": _generate_install_command(results),
        "required_r_packages": list(sorted(required_r)),
        "r_packages": r_results,
        "missing_r_packages": [pkg for pkg, info in r_results.items() if not info["available"]],
    }


def environment_status() -> dict[str, Any]:
    """Check which bioinformatics tools are installed on the system.

    Results are cached for 60 seconds to avoid repeated ``shutil.which()``
    and Rscript subprocess calls.

    Returns:
        Dictionary with overall status and per-tool availability.
    """
    global _ENV_STATUS_CACHE, _ENV_STATUS_TIMESTAMP

    if _ENV_STATUS_CACHE is not None and (time.time() - _ENV_STATUS_TIMESTAMP) < _ENV_STATUS_TTL:
        return _ENV_STATUS_CACHE

    results: dict[str, dict[str, Any]] = {}
    available_count = 0
    for exe, package in sorted(KNOWN_EXECUTABLES.items()):
        path = shutil.which(exe)
        available = path is not None
        if available:
            available_count += 1
        results[exe] = {
            "available": available,
            "path": path,
            "conda_package": package,
        }

    # Check common bioinformatics R packages across all environments
    r_packages_check = [
        "ggplot2", "dplyr", "tidyr", "readr", "pheatmap",
        "DESeq2", "edgeR", "limma", "Biostrings", "GenomicRanges",
        "ape", "vegan", "ComplexHeatmap",
    ]
    r_results = _check_r_packages_env_aware(r_packages_check)
    r_available_count = sum(1 for info in r_results.values() if info.get("available"))

    total_available = available_count + r_available_count
    total_known = len(KNOWN_EXECUTABLES) + len(r_packages_check)

    _ENV_STATUS_CACHE = {
        "total_known": total_known,
        "available": total_available,
        "missing": total_known - total_available,
        "tools": results,
        "r_packages": r_results,
        "summary": {
            "all_available": total_available == total_known,
            "percent_ready": round(total_available / total_known * 100, 1) if total_known else 100,
        },
    }
    _ENV_STATUS_TIMESTAMP = time.time()
    return _ENV_STATUS_CACHE


def _generate_install_command(results: dict[str, dict[str, Any]]) -> str:
    """Generate a pixi install command for missing packages.

    Args:
        results: Diagnostic results dictionary.

    Returns:
        Shell command string to install missing packages.
    """
    missing_packages: set[str] = set()
    for exe, info in results.items():
        if not info["available"] and info["conda_package"] != "unknown":
            missing_packages.add(info["conda_package"])

    if not missing_packages:
        return "# All required tools are already installed"

    return (
        f"pixi add "
        f"{' '.join(sorted(missing_packages))}"
    )


def host_diagnostics() -> dict[str, Any]:
    """Return host-level prerequisite diagnostics.

    Returns data shaped for the frontend HostStatus / HostPrerequisitesBanner.
    """
    import platform

    import psutil

    from bionodulo.manager.runtime_installer import get_pixi_path

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Build prerequisite checks
    checks: dict[str, dict[str, Any]] = {}
    missing_required: list[str] = []
    missing_optional: list[str] = []

    # Python
    py_path = shutil.which("python3") or shutil.which("python")
    checks["python3"] = {
        "available": py_path is not None,
        "path": py_path,
        "required": True,
        "auto_installable": False,
        "description": "Python interpreter (>=3.11)",
    }
    if not checks["python3"]["available"]:
        missing_required.append("python3")

    # Pixi
    pixi_path = get_pixi_path()
    checks["pixi"] = {
        "available": pixi_path is not None,
        "path": str(pixi_path) if pixi_path else None,
        "required": True,
        "auto_installable": True,
        "description": "Pixi package manager",
    }
    if not checks["pixi"]["available"]:
        missing_required.append("pixi")

    # Node / npm (optional, for frontend dev)
    node_path = shutil.which("node")
    checks["node"] = {
        "available": node_path is not None,
        "path": node_path,
        "required": False,
        "auto_installable": False,
        "description": "Node.js (optional, for frontend development)",
    }
    if not checks["node"]["available"]:
        missing_optional.append("node")

    # Rscript (optional, for R nodes)
    r_path = shutil.which("Rscript")
    checks["Rscript"] = {
        "available": r_path is not None,
        "path": r_path,
        "required": False,
        "auto_installable": False,
        "description": "R interpreter (optional, for R-based analysis nodes)",
    }
    if not checks["Rscript"]["available"]:
        missing_optional.append("Rscript")

    all_ready = len(missing_required) == 0

    return {
        "ready": all_ready,
        "checks": checks,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "message": (
            "All prerequisites satisfied"
            if all_ready
            else f"{len(missing_required)} required tool(s) missing"
        ),
        "_system": {
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "percent_used": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "free_gb": round(disk.free / (1024 ** 3), 2),
                "percent_used": round((disk.used / disk.total) * 100, 2),
            },
        },
    }
