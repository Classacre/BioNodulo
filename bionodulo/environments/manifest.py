"""Workflow environment manifest generator for BioNodulo.

Generates per-workflow pixi manifests based on the tools actually used
in a workflow. Environments are content-addressed by the sorted list of
required packages, so workflows with identical tool requirements share
the same isolated environment.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Mapping of executable names to conda package names.
# This is the single source of truth for tool → package resolution.
EXECUTABLE_PACKAGES: dict[str, str] = {
    "bwa": "bwa",
    "blastn": "blast",
    "bowtie2": "bowtie2",
    "bowtie2-build": "bowtie2",
    "bowtie2-inspect": "bowtie2",
    "hisat2": "hisat2",
    "hisat2-build": "hisat2",
    "STAR": "star",
    "minimap2": "minimap2",
    "salmon": "salmon",
    "kallisto": "kallisto",
    "samtools": "samtools",
    "bcftools": "bcftools",
    "gatk": "gatk4",
    "freebayes": "freebayes",
    "vcftools": "vcftools",
    "fastqc": "fastqc",
    "multiqc": "multiqc",
    "qualimap": "qualimap",
    "fastp": "fastp",
    "trimmomatic": "trimmomatic",
    "cutadapt": "cutadapt",
    "spades.py": "spades",
    "megahit": "megahit",
    "canu": "canu",
    "flye": "flye",
    "unicycler": "unicycler",
    "quast": "quast",
    "prokka": "prokka",
    "bakta": "bakta",
    "emapper.py": "eggnog-mapper",
    "mafft": "mafft",
    "clustalo": "clustal-omega",
    "iqtree": "iqtree",
    "iqtree2": "iqtree",
    "FastTree": "fasttree",
    "raxmlHPC": "raxml",
    "featureCounts": "subread",
    "stringtie": "stringtie",
    "kraken2": "kraken2",
    "kraken2-build": "kraken2",
    "bracken": "bracken",
    "metaphlan": "metaphlan",
    "humann": "humann",
    "run_MaxBin.pl": "maxbin2",
    "checkm": "checkm-genome",
    "macs2": "macs2",
    "bedtools": "bedtools",
    "bamCoverage": "deeptools",
    "cellranger": "cellranger",
    "Rscript": "r-base",
}

# Mapping of R packages to conda package names.
R_PACKAGE_MAP: dict[str, str] = {
    "ggplot2": "r-ggplot2",
    "readr": "r-readr",
    "dplyr": "r-dplyr",
    "tidyr": "r-tidyr",
    "pheatmap": "r-pheatmap",
    "DESeq2": "bioconductor-deseq2",
    "edgeR": "bioconductor-edger",
    "limma": "bioconductor-limma",
    "Biostrings": "bioconductor-biostrings",
    "GenomicRanges": "bioconductor-genomicranges",
    "ape": "r-ape",
    "vegan": "r-vegan",
    "ComplexHeatmap": "bioconductor-complexheatmap",
    "RColorBrewer": "r-rcolorbrewer",
    "rtracklayer": "bioconductor-rtracklayer",
    "summarizedexperiment": "bioconductor-summarizedexperiment",
    "tximport": "bioconductor-tximport",
}


def _norm_pkg(name: str) -> str:
    """Normalise a package name for stable hashing."""
    return name.strip().lower()


def get_env_id(packages: list[str]) -> str:
    """Compute a content hash for a set of packages.

    Two identical package lists (ignoring order and duplicates)
    will always produce the same env_id, allowing automatic
    deduplication of workflow environments.
    """
    canonical = json.dumps(sorted({_norm_pkg(p) for p in packages}), separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def get_env_dir(env_id: str, workspace_dir: str | Path) -> Path:
    """Return the directory for a given environment ID."""
    return Path(workspace_dir) / "envs" / env_id


def workflow_to_packages(
    workflow: dict[str, Any],
    registry: Any | None = None,
) -> list[str]:
    """Extract the list of conda packages required by a workflow.

    Scans all nodes for REQUIRED_EXECUTABLES and REQUIRED_R_PACKAGES,
    maps them to conda package names, and returns a deduplicated list.
    """
    packages: set[str] = set()
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    for node in nodes:
        if isinstance(node, dict):
            node_type = node.get("type", "")
        else:
            node_type = getattr(node, "type", "")
        if not node_type:
            continue

        node_class = None
        if registry is not None and hasattr(registry, "get"):
            node_class = registry.get(node_type)

        if node_class is None:
            # Try to get info from the node's stored node_info
            node_info = node.get("node_info", {}) if isinstance(node, dict) else {}
            executables = node_info.get("required_executables", [])
            r_packages = node_info.get("required_r_packages", [])
        else:
            executables = getattr(node_class, "REQUIRED_EXECUTABLES", [])
            r_packages = getattr(node_class, "REQUIRED_R_PACKAGES", [])
            # Also check REQUIRED_CONDA_PACKAGES
            conda_pkgs = getattr(node_class, "REQUIRED_CONDA_PACKAGES", [])
            for cpkg in conda_pkgs:
                if cpkg:
                    packages.add(cpkg)

        for exe in executables:
            pkg = EXECUTABLE_PACKAGES.get(exe, exe)
            if pkg:
                packages.add(pkg)

        for rpkg in r_packages:
            pkg = R_PACKAGE_MAP.get(rpkg, rpkg)
            if pkg:
                packages.add(pkg)

    return sorted(packages)


def generate_manifest(env_dir: str | Path, packages: list[str]) -> Path:
    """Write a pixi.toml manifest for the given packages.

    Returns the path to the written manifest.
    """
    env_dir = Path(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)

    toml_lines = [
        '[workspace]',
        'name = "bionodulo-workflow"',
        'channels = ["conda-forge", "bioconda"]',
        'platforms = ["linux-64"]',
        '',
        '[dependencies]',
    ]

    for pkg in sorted(packages):
        toml_lines.append(f'{pkg} = "*"')

    toml_lines.append("")

    manifest_path = env_dir / "pixi.toml"
    manifest_path.write_text("\n".join(toml_lines), encoding="utf-8")
    logger.info("Generated manifest at %s with %d packages", manifest_path, len(packages))
    return manifest_path


def is_manifest_current(env_dir: str | Path, packages: list[str]) -> bool:
    """Check if the existing manifest matches the required packages."""
    env_dir = Path(env_dir)
    manifest_path = env_dir / "pixi.toml"
    if not manifest_path.exists():
        return False

    # Quick check: count lines in [dependencies] section
    content = manifest_path.read_text(encoding="utf-8")
    current_pkgs = {line.split("=")[0].strip() for line in content.splitlines() if "=" in line and not line.startswith("[")}
    required_pkgs = {_norm_pkg(p) for p in packages}
    return current_pkgs == required_pkgs


def is_env_ready(env_dir: str | Path) -> bool:
    """Check if the pixi environment has been installed."""
    env_dir = Path(env_dir)
    prefix = env_dir / ".pixi" / "envs" / "default"
    return prefix.exists() and (prefix / "bin").exists()


def run_pixi_lock(env_dir: str | Path, timeout: int = 300) -> tuple[bool, str]:
    """Run `pixi lock` in the environment directory.

    Returns (success, message).
    """
    from bionodulo.manager.runtime_installer import get_pixi_path

    env_dir = Path(env_dir)
    manifest = env_dir / "pixi.toml"
    if not manifest.exists():
        return False, "Manifest not found"

    pixi = get_pixi_path()
    if pixi is None:
        return False, "pixi executable not found"

    try:
        result = subprocess.run(
            [str(pixi), "lock"],
            cwd=str(env_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, "Lockfile updated"
        return False, f"pixi lock failed: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, f"pixi lock timed out after {timeout}s"
    except FileNotFoundError:
        return False, "pixi executable not found"


def run_pixi_install(env_dir: str | Path, timeout: int = 300) -> tuple[bool, str]:
    """Run `pixi install` in the environment directory.

    Returns (success, message).
    """
    from bionodulo.manager.runtime_installer import get_pixi_path

    env_dir = Path(env_dir)
    manifest = env_dir / "pixi.toml"
    if not manifest.exists():
        return False, "Manifest not found"

    pixi = get_pixi_path()
    if pixi is None:
        return False, "pixi executable not found"

    try:
        result = subprocess.run(
            [str(pixi), "install"],
            cwd=str(env_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, "Environment installed"
        return False, f"pixi install failed: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, f"pixi install timed out after {timeout}s"
    except FileNotFoundError:
        return False, "pixi executable not found"


async def ensure_workflow_env(
    env_dir: str | Path,
    packages: list[str],
    name: str = "",
) -> dict[str, Any]:
    """Ensure a workflow environment exists and is installed.

    This is the high-level entry point. It:
    1. Generates/updates the manifest if needed
    2. Runs `pixi lock` if the lockfile is missing or stale
    3. Runs `pixi install` if the environment is not installed

    Returns a status dict with keys: ready, env_dir, packages, message.
    """
    env_dir = Path(env_dir)

    # Write default display name if provided and not already set
    if name and not get_env_name(env_dir):
        set_env_meta(env_dir, name=name)

    # Step 1: manifest
    if not is_manifest_current(env_dir, packages):
        generate_manifest(env_dir, packages)
        # Lockfile is now stale
        lockfile = env_dir / "pixi.lock"
        if lockfile.exists():
            lockfile.unlink()

    # Step 2: lockfile
    lockfile = env_dir / "pixi.lock"
    if not lockfile.exists():
        ok, msg = run_pixi_lock(env_dir)
        if not ok:
            return {"ready": False, "env_dir": str(env_dir), "packages": packages, "message": msg}

    # Step 3: install
    if not is_env_ready(env_dir):
        ok, msg = run_pixi_install(env_dir)
        if not ok:
            return {"ready": False, "env_dir": str(env_dir), "packages": packages, "message": msg}

    return {
        "ready": True,
        "env_dir": str(env_dir),
        "packages": packages,
        "message": "Environment ready",
    }


# ---------------------------------------------------------------------------
# Environment metadata (display names, listing, deletion)
# ---------------------------------------------------------------------------


def _meta_path(env_dir: str | Path) -> Path:
    return Path(env_dir) / "meta.json"


def get_env_meta(env_dir: str | Path) -> dict[str, Any]:
    """Read metadata for an environment."""
    path = _meta_path(env_dir)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def set_env_meta(env_dir: str | Path, **kwargs: Any) -> None:
    """Write metadata for an environment."""
    env_dir = Path(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)
    path = _meta_path(env_dir)
    meta = get_env_meta(env_dir)
    meta.update(kwargs)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def get_env_name(env_dir: str | Path, fallback: str = "") -> str:
    """Get the display name for an environment."""
    return get_env_meta(env_dir).get("name") or fallback


def get_installed_versions(env_dir: str | Path) -> dict[str, str]:
    """Query pixi for installed package versions in an environment.

    Returns a dict mapping lowercase package name to version string.
    """
    from bionodulo.manager.runtime_installer import get_pixi_path

    pixi = get_pixi_path()
    if pixi is None:
        return {}

    env_dir = Path(env_dir)
    manifest = env_dir / "pixi.toml"
    if not manifest.exists():
        return {}

    try:
        result = subprocess.run(
            [str(pixi), "list", "--json", "--manifest-path", str(manifest)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        versions: dict[str, str] = {}
        for pkg in data:
            name = pkg.get("name", "").strip().lower()
            version = pkg.get("version", "*")
            if name:
                versions[name] = version
        return versions
    except Exception:
        return {}


def remove_package_from_env(env_dir: str | Path, package_name: str) -> tuple[bool, str]:
    """Remove a package from an environment's pixi.toml.

    Deletes the lockfile and marks the env as not-ready in meta.
    Returns (success, message).
    """
    env_dir = Path(env_dir)
    manifest = env_dir / "pixi.toml"
    if not manifest.exists():
        return False, "Manifest not found"

    pkg_norm = package_name.strip().lower()
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        removed = False
        in_deps = False
        for line in lines:
            stripped = line.strip()
            if stripped == "[dependencies]":
                in_deps = True
                new_lines.append(line)
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_deps = False
                new_lines.append(line)
                continue
            if in_deps and "=" in stripped:
                dep_name = stripped.split("=")[0].strip().lower()
                if dep_name == pkg_norm:
                    removed = True
                    continue
            new_lines.append(line)

        if not removed:
            return False, f"Package '{package_name}' not found in dependencies"

        manifest.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        # Delete lockfile so env must be re-resolved
        lockfile = env_dir / "pixi.lock"
        if lockfile.exists():
            lockfile.unlink()

        # Mark env as not ready
        set_env_meta(
            env_dir,
            ready=False,
            broken_reason=f"Package '{package_name}' was manually removed",
        )

        return True, f"Removed '{package_name}'"
    except Exception as exc:
        return False, str(exc)


def list_all_envs(workspace_dir: str | Path) -> list[dict[str, Any]]:
    """List all environments in the workspace.

    Returns a list of dicts with keys: id, name, path, packages, ready.
    """
    envs_root = Path(workspace_dir) / "envs"
    if not envs_root.exists():
        return []

    results: list[dict[str, Any]] = []
    for entry in sorted(envs_root.iterdir(), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        manifest = entry / "pixi.toml"
        if not manifest.exists():
            continue

        meta = get_env_meta(entry)
        pkg_names = _parse_manifest_packages(manifest)
        versions = get_installed_versions(entry)

        packages = [
            {"name": name, "version": versions.get(name.lower(), "*")}
            for name in pkg_names
        ]

        ready = is_env_ready(entry)
        if meta.get("ready") is False:
            ready = False

        results.append({
            "id": entry.name,
            "name": meta.get("name") or f"Env {entry.name[:8]}",
            "path": str(entry),
            "packages": packages,
            "package_count": len(packages),
            "ready": ready,
            "status": "ready" if ready else "not_ready",
        })

    return results


def delete_env_dir(env_dir: str | Path) -> tuple[bool, str]:
    """Delete an environment directory.

    Returns (success, message).
    """
    env_dir = Path(env_dir)
    if not env_dir.exists():
        return False, "Environment not found"
    try:
        shutil.rmtree(env_dir)
        return True, f"Deleted environment {env_dir.name}"
    except Exception as exc:
        return False, str(exc)


def duplicate_env_dir(
    env_dir: str | Path, workspace_dir: str | Path
) -> tuple[bool, str, str | None]:
    """Duplicate an environment directory.

    Creates a copy with a new random ID and updates the display name.
    Returns (success, message, new_env_id).
    """
    env_dir = Path(env_dir)
    if not env_dir.exists():
        return False, "Environment not found", None

    new_id = uuid.uuid4().hex[:16]
    new_dir = Path(workspace_dir) / "envs" / new_id
    if new_dir.exists():
        return False, "Destination already exists", None

    try:
        shutil.copytree(env_dir, new_dir)
        meta = get_env_meta(new_dir)
        old_name = meta.get("name") or f"Env {env_dir.name[:8]}"
        set_env_meta(new_dir, name=f"{old_name} (copy)")
        return True, f"Duplicated to {new_id}", new_id
    except Exception as exc:
        return False, str(exc), None


def _parse_manifest_packages(manifest: Path) -> list[str]:
    """Parse package names from the [dependencies] section of a pixi.toml."""
    if not manifest.exists():
        return []
    pkgs: list[str] = []
    in_deps = False
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "[dependencies]":
                in_deps = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_deps = False
                continue
            if in_deps and "=" in stripped:
                pkgs.append(stripped.split("=")[0].strip())
    except Exception:
        pass
    return pkgs


def get_env_packages(env_dir: str | Path) -> list[dict[str, str]]:
    """List packages in an environment by parsing pixi.toml."""
    env_dir = Path(env_dir)
    manifest = env_dir / "pixi.toml"
    return [{"name": name, "version": "*"} for name in _parse_manifest_packages(manifest)]
