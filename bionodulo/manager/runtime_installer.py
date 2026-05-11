"""Runtime tool installer for BioNodulo.

Provides automatic installation of micromamba and bioinformatics tools
to ensure nodes have their dependencies available.
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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


def is_micromamba_installed() -> bool:
    """Check if micromamba is already installed (system or managed).

    Returns:
        True if micromamba is available on PATH or in the managed location.
    """
    if shutil.which("micromamba") is not None:
        return True
    return managed_micromamba_path().exists()


def install_managed_micromamba(
    prefix: Path | None = None,
    force: bool = False,
) -> bool:
    """Automatically install micromamba to a managed location.

    Downloads and installs micromamba using the official installer script.

    Args:
        prefix: Override the installation prefix.
        force: Re-install even if already present.

    Returns:
        True if installation succeeded or was already present.
    """
    import shutil

    root = prefix or managed_micromamba_root()
    bin_path = root / _MICROMAMBA_BIN

    if bin_path.exists() and not force:
        logger.info("micromamba already installed at %s", bin_path)
        return True

    logger.info("Installing micromamba to %s", root)
    root.mkdir(parents=True, exist_ok=True)

    # Determine platform for download URL
    system = platform.system()
    machine = platform.machine()
    if system == "Linux":
        plat = "linux-64"
    elif system == "Darwin":
        plat = "osx-64" if machine != "arm64" else "osx-arm64"
    else:
        logger.error("Unsupported platform: %s %s", system, machine)
        return False

    url = f"https://micro.mamba.pm/api/micromamba/{plat}/latest"

    try:
        # Download and extract micromamba
        import tarfile
        import urllib.request

        tar_path = root / "micromamba.tar.bz2"
        logger.info("Downloading micromamba from %s", url)
        urllib.request.urlretrieve(url, tar_path)

        with tarfile.open(tar_path, "r:bz2") as tf:
            tf.extractall(root)

        tar_path.unlink(missing_ok=True)

        if bin_path.exists():
            # Make executable
            bin_path.chmod(0o755)
            logger.info("micromamba installed successfully at %s", bin_path)

            # Initialize shell
            init_result = subprocess.run(
                [str(bin_path), "shell", "init", "-s", "bash", "-r", str(root)],
                capture_output=True,
                text=True,
            )
            if init_result.returncode != 0:
                logger.warning("Shell init output: %s", init_result.stderr)

            return True
        else:
            logger.error("micromamba binary not found after extraction: %s", bin_path)
            return False

    except Exception as exc:
        logger.error("Failed to install micromamba: %s", exc)
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
