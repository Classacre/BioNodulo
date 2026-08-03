"""Workflow environment manifest generator for BioNodulo.

Generates per-workflow Pixi manifests based on the tools actually used in a
workflow. Bundles are content-addressed by package constraints and, when a
documented incompatibility requires it, the deterministic default/named
environment partition.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from bionodulo.environments.platform_support import ENVIRONMENT_PLATFORMS
from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_BUILD_CONSTRAINTS,
    R_PACKAGE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
    normalize_conda_package,
)

logger = logging.getLogger(__name__)

_COMMITTED_LOCKS_ROOT = Path(__file__).with_name("locks")
_LOCK_DIGEST_MARKER = ".bionodulo-lock-sha256"
_PIXI_ENVIRONMENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Every rendered manifest pins this today; named explicitly so the lock cache is
# keyed by it instead of assuming it.
DEFAULT_LOCK_PLATFORM = "linux-64"

# Platforms a workflow environment may target. linux-64 is what the cloud
# workers run and is never dropped; the macOS entries let the desktop app
# install environments natively. Windows is absent on purpose -- bioconda
# publishes no win-64 packages at all (see explain_unsupported_platform).
SUPPORTED_LOCK_PLATFORMS = ("linux-64", "osx-64", "osx-arm64")

# macOS support is recorded, never predicted. A table of package names cannot
# express it: a pin whose exact version has no macOS build (blast 2.17.0), a
# linux-only build string (macs2 py311hdad781d_1), and a transitive dead end
# (bcftools 1.24 -> htslib >=1.24) all produce the same unsolvable result from
# package names that each look fine in isolation. scripts/solve_macos_locks.py
# asks the solver and writes the answer here.

# Optional second source of locks, consulted only when the repo has no committed
# bundle. Returns (manifest_text, lock_bytes), or None on a miss.
#
# One committed bundle per environment only covers the curated templates: a user
# who edits a workflow into a different package set produces an unknown
# environment ID, and the run dies *after* a VM is already provisioned. A cache
# populated by solving once at submit time closes that gap without relaxing the
# worker's rule — it still never solves, it only installs a lock it was handed.
LockCache = Callable[[str, str], "tuple[str, bytes] | None"]
_LOCK_CACHE: LockCache | None = None


def set_lock_cache(cache: LockCache | None) -> None:
    """Install (or clear) the fallback lock source.

    ``cache`` takes ``(environment_id, platform)``. Platform is passed
    explicitly because the environment ID deliberately does not hash it — an
    aarch64-solved lock must never be served to a linux-64 run.
    """
    global _LOCK_CACHE
    _LOCK_CACHE = cache


def _lock_from_cache(
    env_id: str,
    platform: str,
    expected_manifest: str,
) -> tuple[str, bytes] | None:
    """Fetch and validate a cached bundle, or return None on a miss."""
    if _LOCK_CACHE is None:
        return None
    bundle = _LOCK_CACHE(env_id, platform)
    if bundle is None:
        return None
    manifest_text, lock_bytes = bundle
    if manifest_text != expected_manifest:
        # The same guard the committed path applies: a lock must belong to the
        # exact environment we asked for, or it is not usable.
        raise RuntimeError(f"Cached environment manifest is stale for {env_id} ({platform})")
    if not lock_bytes:
        raise RuntimeError(f"Cached environment lock is empty for {env_id} ({platform})")
    return manifest_text, lock_bytes


def _write_lock_bundle(env_dir: str | Path, manifest_text: str, lock_bytes: bytes) -> str:
    """Write a validated bundle into ``env_dir``; return its lock digest."""
    env_path = Path(env_dir)
    env_path.mkdir(parents=True, exist_ok=True)
    (env_path / "pixi.toml").write_text(manifest_text, encoding="utf-8")
    (env_path / "pixi.lock").write_bytes(lock_bytes)
    return hashlib.sha256(lock_bytes).hexdigest()


@dataclass(frozen=True)
class WorkflowEnvironmentPlan:
    """Deterministic package partition for one committed Pixi bundle.

    Most workflows use only ``default_packages`` and retain the historical
    manifest bytes and environment ID.  A node may explicitly select a named
    Pixi environment when its documented runtime is incompatible with the
    workflow's default environment (Manta 1.6.0 is the first such case).
    Named environments live in the same manifest and lock, so one digest still
    attests the complete runtime closure.
    """

    default_packages: tuple[str, ...]
    named_environments: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def environment_names(self) -> tuple[str, ...]:
        default = ("default",) if self.default_packages else ()
        return (*default, *(name for name, _packages in self.named_environments))

    @property
    def all_packages(self) -> tuple[str, ...]:
        packages = set(self.default_packages)
        for _name, environment_packages in self.named_environments:
            packages.update(environment_packages)
        return tuple(sorted(packages))

    def packages_for(self, environment_name: str) -> tuple[str, ...]:
        if environment_name == "default":
            return self.default_packages
        for name, packages in self.named_environments:
            if name == environment_name:
                return packages
        raise KeyError(environment_name)


def _norm_pkg(name: str) -> str:
    """Normalise a package name for stable hashing."""
    return name.strip().lower()


def _version_spec(pkg: str) -> str:
    """Return the version constraint for a package."""
    return PACKAGE_MIN_VERSIONS.get(pkg, "*")


def _constraint_identity(pkg: str) -> str | dict[str, str]:
    """Return the complete package constraint used for environment identity."""
    version = _version_spec(pkg)
    build = PACKAGE_BUILD_CONSTRAINTS.get(pkg)
    if build is None:
        return version
    return {"version": version, "build": build}


def _dependency_line(pkg: str) -> str:
    """Render one canonical Pixi dependency, including an exact build if set."""
    version = _version_spec(pkg)
    build = PACKAGE_BUILD_CONSTRAINTS.get(pkg)
    if build is None:
        return f'{pkg} = "{version}"'
    return f'{pkg} = {{ version = "{version}", build = "{build}" }}'


def get_env_id(packages: list[str]) -> str:
    """Compute a content hash for a set of packages.

    Package names and their effective constraints identify the environment.
    Order and duplicate package names do not affect the ID.
    """
    normalized = sorted({_norm_pkg(package) for package in packages})
    canonical = json.dumps(
        {package: _constraint_identity(package) for package in normalized},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def get_environment_plan_id(plan: WorkflowEnvironmentPlan) -> str:
    """Return the content ID for a package partition.

    Default-only plans deliberately use the historical package-set identity so
    every existing committed lock remains valid.  Partitioned plans include
    environment names and their effective constraints to prevent two different
    runtime layouts from colliding merely because their flat package union is
    equal.
    """
    if not plan.named_environments:
        return get_env_id(list(plan.default_packages))
    canonical = json.dumps(
        {
            "default": {
                package: _constraint_identity(package)
                for package in plan.default_packages
            },
            "named": {
                name: {
                    package: _constraint_identity(package)
                    for package in packages
                }
                for name, packages in plan.named_environments
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def get_env_dir(env_id: str, workspace_dir: str | Path) -> Path:
    """Return the directory for a given environment ID."""
    return Path(workspace_dir) / "envs" / env_id


def _workflow_nodes(workflow: dict[str, Any]) -> list[Any]:
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        return list(nodes.values())
    return list(nodes) if isinstance(nodes, list) else []


def _node_packages(node: Any, registry: Any | None = None) -> tuple[set[str], Any | None]:
    if isinstance(node, dict):
        node_type = node.get("type", "")
    else:
        node_type = getattr(node, "type", "")
    if not node_type:
        return set(), None

    node_class = None
    if registry is not None and hasattr(registry, "get"):
        node_class = registry.get(node_type)

    packages: set[str] = set()
    if node_class is None:
        node_info = node.get("node_info", {}) if isinstance(node, dict) else {}
        executables = node_info.get("required_executables", [])
        r_packages = node_info.get("required_r_packages", [])
        conda_packages: list[str] = []
    else:
        executables = getattr(node_class, "REQUIRED_EXECUTABLES", [])
        r_packages = getattr(node_class, "REQUIRED_R_PACKAGES", [])
        conda_packages = getattr(node_class, "REQUIRED_CONDA_PACKAGES", [])

    for conda_package in conda_packages:
        if conda_package:
            packages.add(normalize_conda_package(conda_package))
    for executable in executables:
        package = EXECUTABLE_TO_CONDA_PACKAGE.get(executable, executable)
        if package:
            packages.add(package)
    for r_package in r_packages:
        package = R_PACKAGE_TO_CONDA_PACKAGE.get(r_package)
        if package:
            packages.add(package)
    if any(package.startswith("r-") or package.startswith("bioconductor-") for package in packages):
        packages.add("r-base")
    return packages, node_class


def _named_pixi_environment(node_class: Any | None) -> str | None:
    environment = getattr(node_class, "ENVIRONMENT", {}) if node_class is not None else {}
    if not isinstance(environment, dict) or environment.get("type") != "pixi":
        return None
    name = str(environment.get("name", "")).strip()
    if not name:
        return None
    if name == "default" or not _PIXI_ENVIRONMENT_NAME_RE.fullmatch(name):
        raise ValueError(f"invalid named Pixi environment: {name!r}")
    return name


def workflow_to_environment_plan(
    workflow: dict[str, Any],
    registry: Any | None = None,
) -> WorkflowEnvironmentPlan:
    """Partition workflow packages into one default and optional named envs."""
    default_packages: set[str] = set()
    named_packages: dict[str, set[str]] = {}
    for node in _workflow_nodes(workflow):
        packages, node_class = _node_packages(node, registry)
        environment_name = _named_pixi_environment(node_class)
        if environment_name is None:
            default_packages.update(packages)
        else:
            named_packages.setdefault(environment_name, set()).update(packages)

    return WorkflowEnvironmentPlan(
        default_packages=tuple(sorted(default_packages)),
        named_environments=tuple(
            (name, tuple(sorted(packages)))
            for name, packages in sorted(named_packages.items())
        ),
    )


def workflow_to_packages(
    workflow: dict[str, Any],
    registry: Any | None = None,
) -> list[str]:
    """Extract the flat list of conda packages required by a workflow.

    Scans all nodes for REQUIRED_EXECUTABLES and REQUIRED_R_PACKAGES,
    maps them to conda package names, and returns a deduplicated list.  This
    compatibility API intentionally returns the union across named environments;
    runtime callers that need the partition use ``workflow_to_environment_plan``.
    """
    return list(workflow_to_environment_plan(workflow, registry).all_packages)


def _platforms_for_env(env_id: str) -> list[str]:
    """Platforms recorded as solvable for an environment, linux-64 first.

    A pure function of the environment id, and therefore of the package set:
    committed manifests are compared to generated text byte-for-byte, so
    anything host-dependent here would mark every committed lock stale on the
    machines that did not generate it.

    An unrecorded environment falls back to linux-64 alone. That is the safe
    direction -- a new environment runs in the cloud immediately, and gains
    macOS once someone runs the solver script.
    """
    recorded = ENVIRONMENT_PLATFORMS.get(env_id)
    if not recorded:
        return [DEFAULT_LOCK_PLATFORM]
    return [p for p in SUPPORTED_LOCK_PLATFORMS if p in recorded]


def _render_platforms(env_id: str) -> str:
    """Render the platforms array as TOML, for embedding in manifest text."""
    inner = ", ".join(f'"{p}"' for p in _platforms_for_env(env_id))
    return f"[{inner}]"


def _manifest_text(packages: list[str]) -> str:
    toml_lines = [
        '[workspace]',
        'name = "bionodulo-workflow"',
        'version = "0.1.0"',
        'channels = ["conda-forge", "bioconda"]',
        f'platforms = {_render_platforms(get_env_id(packages))}',
        '',
        '[dependencies]',
    ]

    for pkg in sorted(packages):
        toml_lines.append(_dependency_line(pkg))

    toml_lines.append("")
    return "\n".join(toml_lines)


def _manifest_text_for_plan(plan: WorkflowEnvironmentPlan) -> str:
    """Render the canonical manifest for a workflow environment plan."""
    if not plan.named_environments:
        return _manifest_text(list(plan.default_packages))

    toml_lines = [
        "[workspace]",
        'name = "bionodulo-workflow"',
        'version = "0.1.0"',
        'channels = ["conda-forge", "bioconda"]',
        f"platforms = {_render_platforms(get_environment_plan_id(plan))}",
        "",
        "[dependencies]",
    ]
    for package in plan.default_packages:
        toml_lines.append(_dependency_line(package))
    for name, packages in plan.named_environments:
        toml_lines.extend(("", f"[feature.{name}.dependencies]"))
        for package in packages:
            toml_lines.append(_dependency_line(package))
    toml_lines.extend(("", "[environments]"))
    for name, _packages in plan.named_environments:
        toml_lines.append(
            f'{name} = {{ features = ["{name}"], no-default-feature = true }}'
        )
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


def generate_environment_manifest(
    env_dir: str | Path,
    plan: WorkflowEnvironmentPlan,
) -> Path:
    """Write a canonical manifest for a default/named environment plan."""
    env_dir = Path(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = env_dir / "pixi.toml"
    manifest_path.write_text(_manifest_text_for_plan(plan), encoding="utf-8")
    logger.info(
        "Generated environment plan %s with %d default and %d named environments",
        manifest_path,
        len(plan.default_packages),
        len(plan.named_environments),
    )
    return manifest_path


def materialize_committed_lock(
    env_dir: str | Path,
    packages: list[str],
    *,
    platform: str = DEFAULT_LOCK_PLATFORM,
) -> str | None:
    """Copy a manifest/lock pair into ``env_dir``.

    Prefers the repository-owned bundle — the repo is the source of truth for
    curated environments — and falls back to the lock cache. A partial or stale
    bundle is an error; ``None`` means this package set has no lock from any
    source.
    """
    env_id = get_env_id(packages)
    expected_manifest = _manifest_text(packages)
    source_dir = _COMMITTED_LOCKS_ROOT / env_id
    source_manifest = source_dir / "pixi.toml"
    source_lock = source_dir / "pixi.lock"
    if not source_manifest.exists() and not source_lock.exists():
        cached = _lock_from_cache(env_id, platform, expected_manifest)
        if cached is None:
            return None
        return _write_lock_bundle(env_dir, *cached)
    if not source_manifest.is_file() or not source_lock.is_file():
        raise RuntimeError(f"Committed environment bundle is incomplete: {source_dir}")
    if source_manifest.read_text(encoding="utf-8") != expected_manifest:
        raise RuntimeError(f"Committed environment manifest is stale: {source_manifest}")

    env_path = Path(env_dir)
    env_path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_manifest, env_path / "pixi.toml")
    shutil.copy2(source_lock, env_path / "pixi.lock")
    return hashlib.sha256(source_lock.read_bytes()).hexdigest()


def materialize_committed_environment(
    env_dir: str | Path,
    plan: WorkflowEnvironmentPlan,
    *,
    platform: str = DEFAULT_LOCK_PLATFORM,
) -> str | None:
    """Copy a manifest/lock pair for a possibly named plan.

    Committed bundle first, then the lock cache. See ``set_lock_cache``.
    """
    if not plan.named_environments:
        return materialize_committed_lock(
            env_dir, list(plan.default_packages), platform=platform
        )

    plan_id = get_environment_plan_id(plan)
    expected_manifest = _manifest_text_for_plan(plan)
    source_dir = _COMMITTED_LOCKS_ROOT / plan_id
    source_manifest = source_dir / "pixi.toml"
    source_lock = source_dir / "pixi.lock"
    if not source_manifest.exists() and not source_lock.exists():
        cached = _lock_from_cache(plan_id, platform, expected_manifest)
        if cached is None:
            return None
        return _write_lock_bundle(env_dir, *cached)
    if not source_manifest.is_file() or not source_lock.is_file():
        raise RuntimeError(f"Committed environment bundle is incomplete: {source_dir}")
    if source_manifest.read_text(encoding="utf-8") != expected_manifest:
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


def is_environment_ready_for_lock(
    env_dir: str | Path,
    lock_digest: str | None,
    plan: WorkflowEnvironmentPlan,
) -> bool:
    """Require every planned Pixi prefix plus the committed-lock marker."""
    if not is_env_ready(env_dir, plan.environment_names):
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


def is_environment_manifest_current(
    env_dir: str | Path,
    plan: WorkflowEnvironmentPlan,
) -> bool:
    """Check exact canonical bytes for a default/named environment plan."""
    manifest_path = Path(env_dir) / "pixi.toml"
    try:
        return manifest_path.read_text(encoding="utf-8") == _manifest_text_for_plan(plan)
    except (OSError, UnicodeError):
        return False


def is_env_ready(
    env_dir: str | Path,
    environment_names: Iterable[str] | None = None,
) -> bool:
    """Check that every requested Pixi environment prefix is installed."""
    env_dir = Path(env_dir)
    names = (
        tuple(environment_names)
        if environment_names is not None
        else _manifest_environment_names(env_dir / "pixi.toml")
    )
    if not names:
        return False
    return all(
        (env_dir / ".pixi" / "envs" / name).is_dir()
        and (env_dir / ".pixi" / "envs" / name / "bin").is_dir()
        for name in names
    )


def _manifest_environment_names(manifest: Path) -> tuple[str, ...]:
    """Return the Pixi prefixes declared by a workflow manifest."""
    try:
        import tomllib

        with manifest.open("rb") as handle:
            data = tomllib.load(handle)
        names: list[str] = []
        dependencies = data.get("dependencies")
        if isinstance(dependencies, dict) and dependencies:
            names.append("default")
        environments = data.get("environments")
        if isinstance(environments, dict):
            names.extend(
                str(name)
                for name in sorted(environments)
                if str(name) != "default"
            )
        return tuple(names) or ("default",)
    except (OSError, UnicodeError, ValueError):
        return ("default",)


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


def host_conda_subdir() -> str:
    """Return this machine's conda subdir, e.g. linux-64 / win-64 / osx-arm64."""
    import platform as _platform

    system = _platform.system()
    machine = _platform.machine().lower()
    is_arm = machine in ("arm64", "aarch64")
    if system == "Windows":
        return "win-64"
    if system == "Darwin":
        return "osx-arm64" if is_arm else "osx-64"
    return "linux-aarch64" if is_arm else "linux-64"


def manifest_platforms(manifest: Path) -> list[str]:
    """Platforms declared by a pixi manifest, in declaration order."""
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return []
    match = re.search(r"^platforms\s*=\s*\[([^\]]*)\]", text, re.M)
    if not match:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))


def explain_unsupported_platform(declared: list[str], host: str) -> str:
    """Human-readable reason a workflow environment cannot install here.

    pixi's own error ends with "Add it with 'pixi workspace platform add
    win-64'", which is actively misleading here: bioconda publishes NO Windows
    packages at all -- blast and samtools exist only for linux-64,
    linux-aarch64, osx-64 and osx-arm64 -- so following that advice trades a
    clear install failure for a confusing solve failure.
    """
    declared_text = ", ".join(declared) or "none"
    if host == "win-64":
        return (
            "This workflow's tools are not available for Windows. Its "
            f"environment targets {declared_text}, and the bioconda channel that "
            "provides most bioinformatics tools publishes no Windows builds at "
            "all. Running on the cloud is the quickest route and needs no setup. "
            "To run locally instead, enable local execution in Settings: it "
            "installs a private Linux environment via WSL2, which needs "
            "administrator rights once and a few GB of disk."
        )
    return (
        f"This workflow's environment targets {declared_text}, which does not "
        f"include this machine ({host}). Run it on the cloud, or use a machine "
        "matching one of those platforms."
    )


async def run_pixi_install(
    env_dir: str | Path,
    timeout: int = _PIXI_INSTALL_TIMEOUT,
    emit: Callable[[str, dict[str, Any]], Any] | None = None,
    job_id: str | None = None,
    locked: bool = False,
    all_environments: bool = False,
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

    # Fail before pixi does, with a reason the user can act on: pixi's own
    # message suggests adding the platform, which cannot work when the packages
    # do not exist for it.
    declared = manifest_platforms(manifest)
    host = host_conda_subdir()
    if declared and host not in declared:
        reason = explain_unsupported_platform(declared, host)
        if emit:
            emit("install.log", {"job_id": job_id, "stream": "stderr", "message": reason})
        return False, reason

    if emit:
        emit("install.log", {"job_id": job_id, "stream": "stdout", "message": f"[pixi] Starting pixi install in {env_dir}"})

    proc: asyncio.subprocess.Process | None = None
    try:
        command = [str(pixi), "install"]
        if locked:
            command.append("--locked")
        if all_environments:
            command.append("--all")
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
    """Parse package names across default and named Pixi environments."""
    if not manifest.exists():
        return []
    try:
        import tomllib

        with manifest.open("rb") as handle:
            data = tomllib.load(handle)
        packages = set(data.get("dependencies", {}))
        features = data.get("feature", {})
        if isinstance(features, dict):
            for feature in features.values():
                if not isinstance(feature, dict):
                    continue
                dependencies = feature.get("dependencies", {})
                if isinstance(dependencies, dict):
                    packages.update(dependencies)
        return sorted(str(package) for package in packages)
    except (OSError, UnicodeError, ValueError):
        packages: set[str] = set()
        in_deps = False
        try:
            lines = manifest.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return []
        for line in lines:
            stripped = line.strip()
            if stripped == "[dependencies]" or (
                stripped.startswith("[feature.")
                and stripped.endswith(".dependencies]")
            ):
                in_deps = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_deps = False
                continue
            if in_deps and "=" in stripped:
                packages.add(stripped.split("=", 1)[0].strip())
        return sorted(packages)


def get_env_packages(env_dir: str | Path) -> list[dict[str, str]]:
    """List packages in an environment by parsing pixi.toml."""
    env_dir = Path(env_dir)
    manifest = env_dir / "pixi.toml"
    return [{"name": name, "version": "*"} for name in _parse_manifest_packages(manifest)]
