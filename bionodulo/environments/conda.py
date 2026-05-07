from __future__ import annotations

import shutil
from typing import Any

from bionodulo.environments.model import EnvironmentSpec
from bionodulo.manager.runtime_installer import managed_micromamba_path


def conda_available() -> bool:
    return conda_executable() is not None


def conda_executable() -> str | None:
    managed = managed_micromamba_path()
    if managed.exists():
        return str(managed)
    return shutil.which("mamba") or shutil.which("micromamba") or shutil.which("conda")


def conda_create_plan(spec: EnvironmentSpec) -> dict[str, Any]:
    executable = conda_executable() or "mamba"
    channels = [part for channel in spec.channels for part in ("-c", channel)]
    packages = spec.packages or []
    if spec.file:
        command = [executable, "env", "create", "-y", "-n", spec.name, "-f", spec.file]
    else:
        command = [executable, "create", "-y", "-n", spec.name, *channels, *packages]
    return {
        "kind": "environment",
        "target": spec.name,
        "action": "create_conda_environment",
        "command": command,
        "available": conda_available(),
        "requires_confirmation": True,
    }


def conda_run_prefix(spec: EnvironmentSpec) -> list[str]:
    return [conda_executable() or "conda", "run", "-n", spec.name]
