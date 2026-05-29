"""Runtime tool installer for BioNodulo.

Provides automatic installation of pixi and bioinformatics tools
to ensure nodes have their dependencies available.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Type alias for progress emit callback
EmitCallback = Callable[[str, dict[str, Any]], Any]

# Default paths for managed pixi installation
_DEFAULT_ROOT = Path.home() / ".pixi"
_PIXI_BIN = Path("bin") / "pixi" if platform.system() != "Windows" else Path("bin") / "pixi.exe"


def managed_pixi_root() -> Path:
    """Get the root prefix for the managed pixi installation.

    Returns:
        Path to the pixi root directory.
    """
    env_root = os.environ.get("BIONODULO_PIXI_ROOT", "")
    if env_root:
        return Path(env_root)
    return _DEFAULT_ROOT


def managed_pixi_path() -> Path:
    """Get the path to the managed pixi binary.

    Returns:
        Path to the pixi executable.
    """
    return managed_pixi_root() / _PIXI_BIN


def get_pixi_path() -> Path | None:
    """Get the path to the pixi executable to use.

    Prefers the system installation on PATH, then falls back to the
    managed installation in ~/.pixi.

    Returns:
        Path to the executable, or None if not found anywhere.
    """
    sys_path = shutil.which("pixi")
    if sys_path:
        return Path(sys_path)
    managed = managed_pixi_path()
    if managed.exists():
        return managed
    return None


def is_pixi_installed() -> bool:
    """Check if pixi is already installed (system or managed).

    Returns:
        True if pixi is available on PATH or in the managed location.
    """
    return get_pixi_path() is not None


def _emit_log(emit: EmitCallback | None, level: str, message: str) -> None:
    """Emit a log event if a callback is provided."""
    if emit is not None:
        try:
            emit(level, {"message": message, "source": "pixi-installer"})
        except Exception:
            pass


def install_managed_pixi(
    prefix: Path | None = None,
    force: bool = False,
    emit: EmitCallback | None = None,
) -> bool:
    """Automatically install pixi to a managed location.

    Downloads and installs pixi using the official installer script.

    Args:
        prefix: Override the installation prefix.
        force: Re-install even if already present.
        emit: Optional callback for progress events. Called with (level, data).

    Returns:
        True if installation succeeded or was already present.
    """
    root = prefix or managed_pixi_root()
    bin_path = root / _PIXI_BIN

    if bin_path.exists() and not force:
        logger.info("pixi already installed at %s", bin_path)
        _emit_log(emit, "info", f"pixi already installed at {bin_path}")
        return True

    logger.info("Installing pixi to %s", bin_path.parent)
    _emit_log(emit, "info", "Starting pixi installation...")
    bin_path.parent.mkdir(parents=True, exist_ok=True)

    # Use the official pixi install script
    install_script_url = "https://pixi.sh/install.sh"

    try:
        import urllib.request

        script_path = bin_path.parent / "install.sh"
        logger.info("Downloading pixi installer from %s", install_script_url)
        _emit_log(emit, "info", f"Downloading pixi installer from {install_script_url} ...")
        urllib.request.urlretrieve(install_script_url, script_path)

        _emit_log(emit, "info", "Running installer...")
        # Keep the official installer aligned with BioNodulo's managed path.
        env = os.environ.copy()
        env["PIXI_NO_PATH_UPDATE"] = "1"
        env["PIXI_HOME"] = str(root)
        env["PIXI_BIN_DIR"] = str(bin_path.parent)
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True,
            text=True,
            env=env,
        )

        script_path.unlink(missing_ok=True)

        if result.returncode != 0:
            output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
            logger.error("pixi install script failed: %s", output)
            _emit_log(emit, "error", f"pixi install failed: {output[:1200] or 'installer exited with no output'}")
            return False

        if bin_path.exists():
            bin_path.chmod(0o755)
            msg = f"pixi installed successfully at {bin_path}"
            logger.info(msg)
            _emit_log(emit, "success", msg)
            return True
        else:
            err = f"pixi binary not found after installation: {bin_path}"
            logger.error(err)
            _emit_log(emit, "error", err)
            return False

    except Exception as exc:
        err = f"Failed to install pixi: {exc}"
        logger.error(err)
        _emit_log(emit, "error", err)
        return False

