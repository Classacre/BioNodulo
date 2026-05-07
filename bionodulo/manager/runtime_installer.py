from __future__ import annotations

import platform
import shutil
import tarfile
import urllib.request
from pathlib import Path
from typing import Any


def bionodulo_home() -> Path:
    return Path.home() / ".bionodulo"


def managed_micromamba_path() -> Path:
    executable = "micromamba.exe" if platform.system() == "Windows" else "micromamba"
    return bionodulo_home() / "runtimes" / "micromamba" / executable


def managed_micromamba_root() -> Path:
    return bionodulo_home() / "runtimes" / "micromamba-root"


def managed_micromamba_available() -> bool:
    return managed_micromamba_path().exists()


def micromamba_download_url() -> str | None:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "https://micro.mamba.pm/api/micromamba/win-64/latest"
    if system == "Darwin":
        return "https://micro.mamba.pm/api/micromamba/osx-arm64/latest" if machine in {"arm64", "aarch64"} else "https://micro.mamba.pm/api/micromamba/osx-64/latest"
    if system == "Linux":
        return "https://micro.mamba.pm/api/micromamba/linux-aarch64/latest" if machine in {"arm64", "aarch64"} else "https://micro.mamba.pm/api/micromamba/linux-64/latest"
    return None


def managed_micromamba_plan() -> dict[str, Any] | None:
    url = micromamba_download_url()
    if not url:
        return None
    return {
        "kind": "runtime",
        "target": "BioNodulo managed micromamba",
        "status": "available" if managed_micromamba_available() else "missing",
        "action": "install_managed_micromamba",
        "command": [],
        "command_hint": f"Download micromamba into {managed_micromamba_path()} without changing system PATH.",
        "requires_confirmation": True,
        "recommended": True,
    }


def docker_runtime_plan() -> dict[str, Any] | None:
    system = platform.system()
    if system == "Windows" and shutil.which("winget"):
        command = ["winget", "install", "-e", "--id", "Docker.DockerDesktop"]
    elif system == "Darwin" and shutil.which("brew"):
        command = ["brew", "install", "--cask", "docker"]
    elif system == "Linux" and shutil.which("apt-get"):
        command = ["sudo", "apt-get", "install", "-y", "docker.io"]
    else:
        command = []
    return {
        "kind": "runtime",
        "target": "Docker",
        "status": "missing",
        "action": "install_docker_runtime",
        "command": command,
        "command_hint": "Install Docker Desktop or Docker Engine, then restart BioNodulo if needed.",
        "requires_confirmation": True,
        "recommended": False,
    }


def apptainer_runtime_plan() -> dict[str, Any] | None:
    system = platform.system()
    if system == "Linux" and shutil.which("apt-get"):
        command = ["sudo", "apt-get", "install", "-y", "apptainer"]
    elif system == "Darwin" and shutil.which("brew"):
        command = ["brew", "install", "apptainer"]
    else:
        command = []
    return {
        "kind": "runtime",
        "target": "Apptainer",
        "status": "missing",
        "action": "install_apptainer_runtime",
        "command": command,
        "command_hint": "Install Apptainer where supported. On Windows, use WSL or Docker for now.",
        "requires_confirmation": True,
        "recommended": False,
    }


def install_managed_micromamba() -> dict[str, Any]:
    url = micromamba_download_url()
    if not url:
        return {"target": "BioNodulo managed micromamba", "status": "blocked", "message": f"Unsupported platform: {platform.system()}"}
    destination = managed_micromamba_path()
    if destination.exists():
        return {"target": "BioNodulo managed micromamba", "status": "completed", "message": f"Already installed at {destination}"}
    runtime_dir = destination.parent
    runtime_dir.mkdir(parents=True, exist_ok=True)
    archive_path = runtime_dir / "micromamba.tar.bz2"
    urllib.request.urlretrieve(url, archive_path)
    extract_dir = runtime_dir / "extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with tarfile.open(archive_path, "r:bz2") as archive:
        _safe_extract(archive, extract_dir)
    candidates = list(extract_dir.rglob("micromamba.exe" if platform.system() == "Windows" else "micromamba"))
    if not candidates:
        return {"target": "BioNodulo managed micromamba", "status": "failed", "message": "Downloaded archive did not contain micromamba."}
    shutil.copy2(candidates[0], destination)
    destination.chmod(0o755)
    shutil.rmtree(extract_dir, ignore_errors=True)
    archive_path.unlink(missing_ok=True)
    return {"target": "BioNodulo managed micromamba", "status": "completed", "message": f"Installed at {destination}"}


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if not target.is_relative_to(root):
            raise RuntimeError(f"Blocked unsafe archive member: {member.name}")
    archive.extractall(destination)
