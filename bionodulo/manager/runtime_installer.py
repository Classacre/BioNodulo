"""Runtime tool installer for BioNodulo.

Provides automatic installation of micromamba and bioinformatics tools
to ensure nodes have their dependencies available.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Type alias for progress emit callback
EmitCallback = Callable[[str, dict[str, Any]], Any]

# Default paths for managed micromamba installation
_DEFAULT_ROOT = Path.home() / ".local" / "share" / "bionodulo"
_MICROMAMBA_BIN = Path("bin") / "micromamba" if platform.system() != "Windows" else Path("Library") / "bin" / "micromamba.exe"


def managed_micromamba_root() -> Path:
    """Get the root prefix for the managed micromamba installation.

    Returns:
        Path to the micromamba root directory.
    """
    env_root = os.environ.get("BIONODULO_MICROMAMBA_ROOT", "")
    if env_root:
        return Path(env_root)
    return _DEFAULT_ROOT


def managed_micromamba_path() -> Path:
    """Get the path to the managed micromamba binary.

    Returns:
        Path to the micromamba executable.
    """
    return managed_micromamba_root() / _MICROMAMBA_BIN


def get_micromamba_path() -> Path | None:
    """Get the path to the micromamba executable to use.

    Prefers the system installation on PATH, then falls back to the
    managed installation in ~/.local/share/bionodulo.

    Returns:
        Path to the executable, or None if not found anywhere.
    """
    sys_path = shutil.which("micromamba") or shutil.which("mamba") or shutil.which("conda")
    if sys_path:
        return Path(sys_path)
    managed = managed_micromamba_path()
    if managed.exists():
        return managed
    return None


def is_micromamba_installed() -> bool:
    """Check if micromamba is already installed (system or managed).

    Returns:
        True if micromamba is available on PATH or in the managed location.
    """
    return get_micromamba_path() is not None


def _emit_log(emit: EmitCallback | None, level: str, message: str) -> None:
    """Emit a log event if a callback is provided."""
    if emit is not None:
        try:
            emit(level, {"message": message, "source": "micromamba-installer"})
        except Exception:
            pass


def install_managed_micromamba(
    prefix: Path | None = None,
    force: bool = False,
    emit: EmitCallback | None = None,
) -> bool:
    """Automatically install micromamba to a managed location.

    Downloads and installs micromamba using the official installer script.

    Args:
        prefix: Override the installation prefix.
        force: Re-install even if already present.
        emit: Optional callback for progress events. Called with (level, data).

    Returns:
        True if installation succeeded or was already present.
    """
    root = prefix or managed_micromamba_root()
    bin_path = root / _MICROMAMBA_BIN

    if bin_path.exists() and not force:
        logger.info("micromamba already installed at %s", bin_path)
        _emit_log(emit, "info", f"micromamba already installed at {bin_path}")
        return True

    logger.info("Installing micromamba to %s", root)
    _emit_log(emit, "info", f"Starting micromamba installation to {root}")
    root.mkdir(parents=True, exist_ok=True)

    # Determine platform for download URL
    system = platform.system()
    machine = platform.machine()
    if system == "Linux":
        plat = "linux-64"
    elif system == "Darwin":
        plat = "osx-64" if machine != "arm64" else "osx-arm64"
    else:
        err = f"Unsupported platform: {system} {machine}"
        logger.error(err)
        _emit_log(emit, "error", err)
        return False

    url = f"https://micro.mamba.pm/api/micromamba/{plat}/latest"

    try:
        import tarfile
        import urllib.request

        tar_path = root / "micromamba.tar.bz2"
        logger.info("Downloading micromamba from %s", url)
        _emit_log(emit, "info", f"Downloading micromamba from {url} ...")
        urllib.request.urlretrieve(url, tar_path)

        _emit_log(emit, "info", "Download complete. Extracting archive...")
        with tarfile.open(tar_path, "r:bz2") as tf:
            tf.extractall(root)

        tar_path.unlink(missing_ok=True)

        if bin_path.exists():
            bin_path.chmod(0o755)
            msg = f"micromamba installed successfully at {bin_path}"
            logger.info(msg)
            _emit_log(emit, "success", msg)

            _emit_log(emit, "info", "Initializing shell integration...")
            init_result = subprocess.run(
                [str(bin_path), "shell", "init", "-s", "bash", "-r", str(root)],
                capture_output=True,
                text=True,
            )
            if init_result.returncode != 0:
                logger.warning("Shell init output: %s", init_result.stderr)
                _emit_log(emit, "warn", f"Shell init warning: {init_result.stderr[:200]}")
            else:
                _emit_log(emit, "info", "Shell integration initialized.")

            return True
        else:
            err = f"micromamba binary not found after extraction: {bin_path}"
            logger.error(err)
            _emit_log(emit, "error", err)
            return False

    except Exception as exc:
        err = f"Failed to install micromamba: {exc}"
        logger.error(err)
        _emit_log(emit, "error", err)
        return False


def ensure_tool_available(
    executable: str,
    conda_package: str | None = None,
    env_name: str = "bionodulo-tools",
) -> bool:
    """Ensure a bioinformatics tool is available, installing if needed.

    Args:
        executable: Name of the executable to check.
        conda_package: Conda package name (defaults to executable name).
        env_name: Conda environment to install into.

    Returns:
        True if the tool is available.
    """
    import shutil

    if shutil.which(executable) is not None:
        return True

    pkg = conda_package or executable
    mamba = managed_micromamba_path()

    if not mamba.exists():
        if not install_managed_micromamba():
            return False

    logger.info("Installing %s via micromamba...", pkg)
    try:
        # Create env if it doesn't exist
        subprocess.run(
            [str(mamba), "create", "-n", env_name, "-y", "-c", "bioconda", "-c", "conda-forge", pkg],
            capture_output=True,
            timeout=600,
        )

        # Check again
        return shutil.which(executable) is not None
    except Exception as exc:
        logger.error("Failed to install %s: %s", pkg, exc)
        return False
