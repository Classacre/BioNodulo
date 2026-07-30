"""Provision tool binaries that no conda channel publishes.

Some tools are only distributed as vendor tarballs. Dorado is the case that
forced this module: Oxford Nanopore ships it exclusively as a ~4 GB
linux-x64 tarball from their CDN, and it exists in neither bioconda nor
conda-forge, so `pixi run dorado` can only ever be exit 127.

A node opts in by declaring::

    ENVIRONMENT = {
        "provisioning": "external_worker_binary",
        "source": "https://.../tool-1.2.3-linux-x64.tar.gz",
        "version": "1.2.3",
        "platform": "linux-64",
    }

`provision()` returns the directory holding the executable, which the caller
prepends to PATH for that node's command. Placement is content-addressed by
(url, version), so the download happens once per worker and is reused by every
later node and run on the same VM. When the shared reference cache is
configured the unpacked tree is published there too, so a *later VM* stages it
from object storage in-region instead of re-pulling from the vendor.

Failure is explicit: a node whose binary cannot be provisioned must not fall
through to a confusing exit 127 from the tool itself.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

PROVISIONING_KEY = "external_worker_binary"

#: Only extract members whose type we understand. A vendor tarball is not
#: hostile input, but `filter="data"` is still the correct default and this
#: keeps the behaviour identical on Python versions where it is not.
_TAR_FILTER = "data"


def spec_for(node_class: Any) -> dict[str, str] | None:
    """Return the external-binary spec for a node class, or None."""
    environment = getattr(node_class, "ENVIRONMENT", None)
    if not isinstance(environment, dict):
        return None
    if environment.get("provisioning") != PROVISIONING_KEY:
        return None
    source = str(environment.get("source", "")).strip()
    if not source:
        return None
    return {
        "source": source,
        "version": str(environment.get("version", "")).strip(),
        "platform": str(environment.get("platform", "")).strip(),
    }


def cache_id(spec: dict[str, str]) -> str:
    """Stable id for a provisioned binary tree."""
    digest = hashlib.sha256(spec["source"].encode()).hexdigest()[:16]
    version = spec.get("version") or "unversioned"
    return f"extbin-{version}-{digest}"


def _root_dir() -> Path:
    """Where provisioned trees live on this worker."""
    configured = os.environ.get("EXTERNAL_BINARY_DIR", "").strip()
    if configured:
        return Path(configured)
    local = os.environ.get("REFERENCE_LOCAL_DIR", "").strip()
    if local:
        return Path(local).parent / "extbin"
    temp = os.environ.get("TEMP_DIR", "").strip()
    return (Path(temp) if temp else Path(tempfile.gettempdir())) / "bionodulo-extbin"


def _find_executable(tree: Path, name: str) -> Path | None:
    """Locate `name` inside an unpacked vendor tree.

    Vendor tarballs unpack to a versioned root (dorado-0.9.6-linux-x64/bin/dorado),
    so the executable is not at a fixed depth.
    """
    direct = tree / "bin" / name
    if direct.is_file() and os.access(direct, os.X_OK):
        return direct
    for candidate in sorted(tree.rglob(name)):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _download(url: str, destination: Path) -> None:
    """Fetch `url` to `destination`, preferring curl for multi-GB transfers."""
    curl = shutil.which("curl")
    if curl:
        result = subprocess.run(  # noqa: S603 — fixed argv, url from node metadata
            [curl, "-sSL", "--retry", "3", "--retry-delay", "5", "-o", str(destination), url],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and destination.is_file() and destination.stat().st_size > 0:
            return
        raise RuntimeError(
            f"download failed for {url} (curl exit {result.returncode}): {result.stderr[:300]}"
        )
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:  # noqa: S310
        shutil.copyfileobj(response, handle)


def provision(node_class: Any, executable: str) -> Path | None:
    """Ensure `executable` exists on this worker; return its directory.

    Returns None when the node declares no external binary. Raises when the
    node DOES declare one and it cannot be provisioned -- silently continuing
    would surface as the tool's own exit 127, which names nothing useful.
    """
    spec = spec_for(node_class)
    if spec is None:
        return None

    # Already on PATH -- baked into the worker image, or a dev box that installed
    # it by hand. Nothing to fetch and PATH needs no change.
    on_path = shutil.which(executable)
    if on_path:
        return Path(on_path).parent

    # Tests and offline environments must never trigger a multi-GB vendor
    # download. Returning None leaves PATH untouched, which is exactly the
    # behaviour that existed before provisioning.
    if os.environ.get("BIONODULO_EXTERNAL_BINARY_OFFLINE", "").strip():
        return None

    identity = cache_id(spec)
    tree = _root_dir() / identity

    existing = _find_executable(tree, executable) if tree.is_dir() else None
    if existing is not None:
        return existing.parent

    tree.parent.mkdir(parents=True, exist_ok=True)

    # A later VM can stage the unpacked tree from the shared cache instead of
    # re-pulling gigabytes from the vendor CDN. Best-effort: a miss just means
    # we download.
    try:
        from bionodulo.execution import reference_cache as _refcache

        if _refcache.cache_enabled():
            staged = _refcache.stage(identity)
            if staged is not None:
                if tree.exists():
                    shutil.rmtree(tree, ignore_errors=True)
                shutil.copytree(staged, tree)
                found = _find_executable(tree, executable)
                if found is not None:
                    return found.parent
    except Exception:  # noqa: BLE001 — cache is an accelerator, never a gate
        pass

    staging = Path(f"{tree}.partial")
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    archive = staging / "download.tar.gz"
    _download(spec["source"], archive)
    with tarfile.open(archive) as handle:
        handle.extractall(staging, filter=_TAR_FILTER)  # noqa: S202 — vendor tarball, data filter
    archive.unlink(missing_ok=True)

    found = _find_executable(staging, executable)
    if found is None:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError(
            f"{executable} was not found in {spec['source']} after extraction"
        )

    # Publish before the rename so a crash mid-move cannot leave a half tree
    # advertised in the shared cache.
    try:
        from bionodulo.execution import reference_cache as _refcache

        if _refcache.cache_enabled():
            _refcache.publish(identity, staging)
    except Exception:  # noqa: BLE001 — publish is best-effort
        pass

    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    staging.rename(tree)

    resolved = _find_executable(tree, executable)
    if resolved is None:  # pragma: no cover — rename preserves layout
        raise RuntimeError(f"{executable} disappeared while installing {identity}")
    return resolved.parent
