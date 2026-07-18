"""Workflow environment manifest generator for BioNodulo.

Generates per-workflow pixi manifests based on the tools actually used
in a workflow. Environments are content-addressed by the sorted list of
required packages, so workflows with identical tool requirements share
the same isolated environment.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    R_PACKAGE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
    normalize_conda_package,
)

logger = logging.getLogger(__name__)

_COMMITTED_LOCKS_ROOT = Path(__file__).with_name("locks")
_LOCK_DIGEST_MARKER = ".bionodulo-lock-sha256"


def _norm_pkg(name: str) -> str:
    """Normalise a package name for stable hashing."""
    return name.strip().lower()


def _version_spec(pkg: str) -> str:
    """Return the version constraint for a package."""
    return PACKAGE_MIN_VERSIONS.get(pkg, "*")


def get_env_id(packages: list[str]) -> str:
    """Compute a content hash for a set of packages.

    Package names and their effective constraints identify the environment.
    Order and duplicate package names do not affect the ID.
    """
    normalized = sorted({_norm_pkg(package) for package in packages})
    canonical = json.dumps(
        {package: _version_spec(package) for package in normalized},
        sort_keys=True,
        separators=(",", ":"),
    )
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
                    packages.add(normalize_conda_package(cpkg))

        for exe in executables:
            pkg = EXECUTABLE_TO_CONDA_PACKAGE.get(exe, exe)
            if pkg:
                packages.add(pkg)

        for rpkg in r_packages:
            pkg = R_PACKAGE_TO_CONDA_PACKAGE.get(rpkg)
            if pkg:
                packages.add(pkg)

    sorted_packages: list[str] = sorted(packages)
    # Ensure r-base is present if any R packages are needed
    if any(p.startswith("r-") or p.startswith("bioconductor-") for p in sorted_packages):
        if "r-base" not in sorted_packages:
            sorted_packages.append("r-base")
            sorted_packages.sort()
    return sorted_packages


def _manifest_text(packages: list[str]) -> str:
    toml_lines = [
        '[workspace]',
        'name = "bionodulo-workflow"',
        'version = "0.1.0"',
        'channels = ["conda-forge", "bioconda"]',
        'platforms = ["linux-64"]',
        '',
        '[dependencies]',
    ]

    for pkg in sorted(packages):
        toml_lines.append(f'{pkg} = "{_version_spec(pkg)}"')

    toml_lines.append("")
    return "\n".join(toml_lines)


def generate_manifest(env_dir: str | Path, packages: list[str]) -> Path:
    """Write a pixi.toml manifest for the given packages.

    Returns the path to the written manifest.
    """
    env_dir = Path(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = env_dir / "pixi.toml"
    manifest_path.write_text(_manifest_text(packages), encoding="utf-8")
    logger.info("Generated manifest at %s with %d packages", manifest_path, len(packages))
    return manifest_path


def materialize_committed_lock(env_dir: str | Path, packages: list[str]) -> str | None:
    """Copy a repository-owned manifest/lock pair into ``env_dir``.

    Committed bundles are keyed by the same environment ID used at runtime. A
    partial or stale bundle is an error; returning ``None`` means this package
    set has no committed lock and may use the legacy solve path.
    """
    source_dir = _COMMITTED_LOCKS_ROOT / get_env_id(packages)
    source_manifest = source_dir / "pixi.toml"
    source_lock = source_dir / "pixi.lock"
    if not source_manifest.exists() and not source_lock.exists():
        return None
    if not source_manifest.is_file() or not source_lock.is_file():
        raise RuntimeError(f"Committed environment bundle is incomplete: {source_dir}")
    if source_manifest.read_text(encoding="utf-8") != _manifest_text(packages):
        raise RuntimeError(f"Committed environment manifest is stale: {source_manifest}")

    env_path = Path(env_dir)
    env_path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_manifest, env_path / "pixi.toml")
    shutil.copy2(source_lock, env_path / "pixi.lock")
    return hashlib.sha256(source_lock.read_bytes()).hexdigest()


def is_env_ready_for_lock(env_dir: str | Path, lock_digest: str | None) -> bool:
    """Return whether an installed environment attests to ``lock_digest``."""
    if not is_env_ready(env_dir):
        return False
    if lock_digest is None:
        return True
    marker = Path(env_dir) / _LOCK_DIGEST_MARKER
    return marker.is_file() and marker.read_text(encoding="ascii").strip() == lock_digest


def mark_env_lock_installed(env_dir: str | Path, lock_digest: str | None) -> None:
    """Record the committed lock digest after a successful locked install."""
    if lock_digest is None:
        return
    (Path(env_dir) / _LOCK_DIGEST_MARKER).write_text(
        f"{lock_digest}\n",
        encoding="ascii",
    )


def is_manifest_current(env_dir: str | Path, packages: list[str]) -> bool:
    """Check if the existing manifest matches the required packages."""
    env_dir = Path(env_dir)
    manifest_path = env_dir / "pixi.toml"
    if not manifest_path.exists():
        return False

    try:
        import tomllib  # Python 3.11+
        with open(manifest_path, "rb") as f:
            data = tomllib.load(f)
        current_pkgs = set(data.get("dependencies", {}).keys())
    except Exception:
        # Fallback: section-aware parsing
        content = manifest_path.read_text(encoding="utf-8")
        current_pkgs = set()
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "[dependencies]":
                in_deps = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_deps = False
                continue
            if in_deps and "=" in stripped:
                pkg_name = stripped.split("=", 1)[0].strip()
                if pkg_name:
                    current_pkgs.add(pkg_name)

    required_pkgs = {_norm_pkg(p) for p in packages}
    return current_pkgs == required_pkgs


def is_env_ready(env_dir: str | Path) -> bool:
    """Check if the pixi environment has been installed."""
    env_dir = Path(env_dir)
    prefix = env_dir / ".pixi" / "envs" / "default"
    return prefix.exists() and (prefix / "bin").exists()


# ANSI escape sequence pattern (colors, cursor movement, etc.)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_PIXI_LOCK_TIMEOUT = 1800
_PIXI_INSTALL_TIMEOUT = 3600


async def _read_stream(
    stream: asyncio.StreamReader,
    name: str,
    lines: list[str],
    emit: Callable[[str, dict[str, Any]], Any] | None,
    job_id: str | None,
) -> None:
    """Read lines from an asyncio stream and optionally emit them.

    Strips ANSI escape codes and carriage returns so that progress-bar
    spam from tools like pixi doesn't produce empty or garbled log lines.
    """
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        # Pixi and other Rust tools use \r to overwrite the current line.
        # Split on \r and keep only the last segment (the final visible text).
        if "\r" in decoded:
            decoded = decoded.split("\r")[-1]
        # Strip ANSI escape codes (colors, cursor movement, etc.)
        decoded = _ANSI_RE.sub("", decoded)
        # Strip whitespace
        decoded = decoded.strip()
        if decoded:
            lines.append(decoded)
            if emit:
                emit("install.log", {"job_id": job_id, "stream": name, "message": decoded})


async def _stop_process(proc: asyncio.subprocess.Process | None) -> None:
    """Stop a timed-out Pixi child so it does not keep solving in the background."""
    if proc is None or proc.returncode is not None:
        return
    proc.kill()
    await proc.wait()


def _pixi_failure_excerpt(stderr_lines: list[str], stdout_lines: list[str]) -> str:
    """Prefer Pixi errors, but keep stdout when Pixi reports there instead."""
    lines = stderr_lines or stdout_lines
    if not lines:
        return "pixi exited without output"
    return "\n".join(lines)[-500:]


async def run_pixi_lock(
    env_dir: str | Path,
    timeout: int = _PIXI_LOCK_TIMEOUT,
    emit: Callable[[str, dict[str, Any]], Any] | None = None,
    job_id: str | None = None,
) -> tuple[bool, str]:
    """Run `pixi lock` in the environment directory.

    When *emit* is provided, stdout/stderr are streamed in real time via
    ``emit("install.log", {"job_id": ..., "stream": "stdout|stderr", "message": ...})``.

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

    if emit:
        emit("install.log", {"job_id": job_id, "stream": "stdout", "message": f"[pixi] Starting pixi lock in {env_dir}"})

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            str(pixi), "lock",
            cwd=str(env_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        if proc.stdout is None or proc.stderr is None:
            return False, "Failed to capture subprocess output"

        await asyncio.wait_for(
            asyncio.gather(
                _read_stream(proc.stdout, "stdout", stdout_lines, emit, job_id),
                _read_stream(proc.stderr, "stderr", stderr_lines, emit, job_id),
            ),
            timeout=timeout,
        )

        returncode = proc.returncode
        if returncode == 0:
            return True, "Lockfile updated"
        return False, f"pixi lock failed: {_pixi_failure_excerpt(stderr_lines, stdout_lines)}"
    except asyncio.TimeoutError:
        await _stop_process(proc)
        return False, f"pixi lock timed out after {timeout}s"
    except FileNotFoundError:
        return False, "pixi executable not found"


async def run_pixi_install(
    env_dir: str | Path,
    timeout: int = _PIXI_INSTALL_TIMEOUT,
    emit: Callable[[str, dict[str, Any]], Any] | None = None,
    job_id: str | None = None,
    locked: bool = False,
) -> tuple[bool, str]:
    """Run `pixi install` in the environment directory.

    When *emit* is provided, stdout/stderr are streamed in real time via
    ``emit("install.log", {"job_id": ..., "stream": "stdout|stderr", "message": ...})``.

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

    if emit:
        emit("install.log", {"job_id": job_id, "stream": "stdout", "message": f"[pixi] Starting pixi install in {env_dir}"})

    proc: asyncio.subprocess.Process | None = None
    try:
        command = [str(pixi), "install"]
        if locked:
            command.append("--locked")
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(env_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        if proc.stdout is None or proc.stderr is None:
            return False, "Failed to capture subprocess output"

        await asyncio.wait_for(
            asyncio.gather(
                _read_stream(proc.stdout, "stdout", stdout_lines, emit, job_id),
                _read_stream(proc.stderr, "stderr", stderr_lines, emit, job_id),
            ),
            timeout=timeout,
        )

        returncode = proc.returncode
        if returncode == 0:
            return True, "Environment installed"
        return False, f"pixi install failed: {_pixi_failure_excerpt(stderr_lines, stdout_lines)}"
    except asyncio.TimeoutError:
        await _stop_process(proc)
        return False, f"pixi install timed out after {timeout}s"
    except FileNotFoundError:
        return False, "pixi executable not found"


async def ensure_workflow_env(
    env_dir: str | Path,
    packages: list[str],
    name: str = "",
    emit: Callable[[str, dict[str, Any]], Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Ensure a workflow environment exists and is installed.

    This is the high-level entry point. It:
    1. Generates/updates the manifest if needed
    2. Runs `pixi lock` if the lockfile is missing or stale
    3. Runs `pixi install` if the environment is not installed

    When *emit* is provided, subprocess output is streamed in real time.

    Returns a status dict with keys: ready, env_dir, packages, message.
    """
    env_dir = Path(env_dir)
    committed_lock_digest = materialize_committed_lock(env_dir, packages)

    # Write default display name if provided and not already set
    if name and not get_env_name(env_dir):
        set_env_meta(env_dir, name=name)

    # Step 1: manifest
    if committed_lock_digest is None and not is_manifest_current(env_dir, packages):
        generate_manifest(env_dir, packages)
        # Lockfile is now stale
        lockfile = env_dir / "pixi.lock"
        if lockfile.exists():
            lockfile.unlink()

    # Step 2: lockfile
    lockfile = env_dir / "pixi.lock"
    if committed_lock_digest is None and not lockfile.exists():
        ok, msg = await run_pixi_lock(env_dir, emit=emit, job_id=job_id)
        if not ok:
            return {"ready": False, "env_dir": str(env_dir), "packages": packages, "message": msg}

    # Step 3: install
    if not is_env_ready_for_lock(env_dir, committed_lock_digest):
        ok, msg = await run_pixi_install(
            env_dir,
            emit=emit,
            job_id=job_id,
            locked=committed_lock_digest is not None,
        )
        if not ok:
            return {"ready": False, "env_dir": str(env_dir), "packages": packages, "message": msg}
        mark_env_lock_installed(env_dir, committed_lock_digest)

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
            [str(pixi), "list", "--json", "--frozen", "--manifest-path", str(manifest)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return {
                entry["name"].lower(): entry["version"]
                for entry in data
                if "name" in entry and "version" in entry
            }
        if isinstance(data, dict):
            return {
                name.lower(): info["version"]
                for name, info in data.items()
                if isinstance(info, dict) and "version" in info
            }
        return {}
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
        import tomllib
        with open(manifest, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        return False, f"Failed to parse manifest: {exc}"

    deps = data.get("dependencies", {})
    if not isinstance(deps, dict):
        return False, "Invalid manifest: dependencies section is not a table"

    removed_key = None
    for key in list(deps.keys()):
        if key.lower() == pkg_norm:
            removed_key = key
            del deps[key]
            break

    if removed_key is None:
        return False, f"Package '{package_name}' not found in dependencies"

    # Regenerate manifest preserving workspace metadata
    ws = data.get("workspace", {})
    toml_lines = [
        "[workspace]",
        f'name = "{ws.get("name", "bionodulo-workflow")}"',
    ]
    if "version" in ws:
        toml_lines.append(f'version = "{ws["version"]}"')
    if "description" in ws:
        toml_lines.append(f'description = "{ws["description"]}"')
    toml_lines.extend([
        'channels = ["conda-forge", "bioconda"]',
        'platforms = ["linux-64"]',
        "",
        "[dependencies]",
    ])
    for key, val in sorted(deps.items()):
        if isinstance(val, str):
            toml_lines.append(f'{key} = "{val}"')
        else:
            toml_lines.append(f"{key} = {json.dumps(val)}")
    toml_lines.append("")

    manifest.write_text("\n".join(toml_lines) + "\n", encoding="utf-8")

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
