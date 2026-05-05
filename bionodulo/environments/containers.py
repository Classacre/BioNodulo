from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from bionodulo.environments.model import EnvironmentSpec


def docker_available() -> bool:
    return shutil.which("docker") is not None


def apptainer_available() -> bool:
    return shutil.which("apptainer") is not None or shutil.which("singularity") is not None


def apptainer_executable() -> str | None:
    return shutil.which("apptainer") or shutil.which("singularity")


def docker_plan(spec: EnvironmentSpec) -> dict[str, Any]:
    return {
        "kind": "environment",
        "target": spec.image or "unset docker image",
        "action": "pull_docker_image",
        "command": ["docker", "pull", spec.image] if spec.image else [],
        "available": docker_available(),
        "requires_confirmation": True,
    }


def apptainer_plan(spec: EnvironmentSpec) -> dict[str, Any]:
    image = spec.image or spec.file or "workflow.sif"
    command = [apptainer_executable() or "apptainer", "pull", spec.file or f"{spec.name}.sif", image] if image.startswith("docker://") else []
    return {
        "kind": "environment",
        "target": image,
        "action": "pull_apptainer_image",
        "command": command,
        "available": apptainer_available(),
        "requires_confirmation": True,
    }


def docker_run_prefix(spec: EnvironmentSpec, run_dir: Path) -> list[str]:
    image = spec.image or "bionodulo/workflow:latest"
    mounts = ["-v", f"{run_dir.resolve()}:/work", "-w", "/work"]
    return ["docker", "run", "--rm", *mounts, image]


def apptainer_run_prefix(spec: EnvironmentSpec, run_dir: Path) -> list[str]:
    image = spec.file or spec.image or f"{spec.name}.sif"
    return [apptainer_executable() or "apptainer", "exec", "--bind", f"{run_dir.resolve()}:/work", image]
