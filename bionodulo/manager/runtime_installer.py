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

# GitHub rejects urllib's default User-Agent with 403.
_USER_AGENT = "BioNodulo-runtime-installer"

# (system, normalised machine) -> release asset. Windows ships a .zip, the rest
# a .tar.gz; both contain a single `pixi` executable at the archive root.
_PIXI_ASSETS = {
    ("Windows", "x86_64"): "pixi-x86_64-pc-windows-msvc.zip",
    ("Windows", "aarch64"): "pixi-aarch64-pc-windows-msvc.zip",
    ("Darwin", "x86_64"): "pixi-x86_64-apple-darwin.tar.gz",
    ("Darwin", "aarch64"): "pixi-aarch64-apple-darwin.tar.gz",
    ("Linux", "x86_64"): "pixi-x86_64-unknown-linux-musl.tar.gz",
    ("Linux", "aarch64"): "pixi-aarch64-unknown-linux-musl.tar.gz",
}


def _normalise_machine(machine: str) -> str:
    """Map platform.machine() spellings onto the release naming."""
    m = machine.lower()
    if m in ("amd64", "x86_64", "x64"):
        return "x86_64"
    if m in ("arm64", "aarch64"):
        return "aarch64"
    return m


def _pixi_asset_name() -> str | None:
    return _PIXI_ASSETS.get((platform.system(), _normalise_machine(platform.machine())))


def _extract_pixi(archive: Path, bin_path: Path) -> None:
    """Extract the single pixi executable from `archive` to `bin_path`."""
    import tarfile
    import zipfile

    wanted = bin_path.name  # pixi or pixi.exe
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            member = next(
                (n for n in zf.namelist() if Path(n).name.lower() == wanted.lower()),
                None,
            )
            if member is None:
                raise RuntimeError(f"{wanted} not found inside {archive.name}")
            with zf.open(member) as src:
                bin_path.write_bytes(src.read())
        return

    with tarfile.open(archive, "r:gz") as tf:
        member = next(
            (m for m in tf.getmembers() if Path(m.name).name == wanted), None
        )
        if member is None:
            raise RuntimeError(f"{wanted} not found inside {archive.name}")
        extracted = tf.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"could not read {wanted} from {archive.name}")
        bin_path.write_bytes(extracted.read())


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

    # Fetch the release BINARY, not the install script.
    #
    # The previous implementation downloaded https://pixi.sh/install.sh and ran
    # it with `bash`. That is broken on Windows three separate ways: install.sh
    # is a POSIX shell script, stock Windows has no `bash`, and
    # urllib.urlretrieve sends "Python-urllib/3.x" as its User-Agent, which the
    # CDN rejects -- the reported failure was exactly
    # "failed to install pixi ... HTTP Error 403: Forbidden".
    #
    # pixi publishes a plain binary per platform, so no shell is involved at
    # all and the same code path works everywhere.
    asset = _pixi_asset_name()
    if asset is None:
        err = (
            f"No pixi build for this platform ({platform.system()} "
            f"{platform.machine()})."
        )
        logger.error(err)
        _emit_log(emit, "error", err)
        return False

    url = f"https://github.com/prefix-dev/pixi/releases/latest/download/{asset}"

    try:
        import urllib.request

        logger.info("Downloading pixi from %s", url)
        _emit_log(emit, "info", f"Downloading pixi ({asset}) ...")
        # An explicit User-Agent is required: the default one is 403'd.
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        archive = bin_path.parent / asset
        with urllib.request.urlopen(request, timeout=300) as response:
            archive.write_bytes(response.read())

        _emit_log(emit, "info", "Extracting pixi ...")
        _extract_pixi(archive, bin_path)
        archive.unlink(missing_ok=True)

        if bin_path.exists():
            if platform.system() != "Windows":
                bin_path.chmod(0o755)
            msg = f"pixi installed successfully at {bin_path}"
            logger.info(msg)
            _emit_log(emit, "success", msg)
            return True

        err = f"pixi binary not found after installation: {bin_path}"
        logger.error(err)
        _emit_log(emit, "error", err)
        return False

    except Exception as exc:
        err = f"Failed to install pixi: {exc}"
        logger.error(err)
        _emit_log(emit, "error", err)
        return False

