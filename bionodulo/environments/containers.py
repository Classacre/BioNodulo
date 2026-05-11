"""Docker/Apptainer/Singularity container management for BioNodulo.

Provides utilities for generating container run command prefixes.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from bionodulo.environments.model import EnvironmentSpec

logger = logging.getLogger(__name__)


def docker_run_prefix(
    image: str,
    mounts: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    workdir: str | None = None,
    gpus: bool = False,
    user: str | None = None,
    rm: bool = True,
) -> list[str]:
    """Generate a Docker run command prefix.

    Args:
        image: Docker image name (e.g., "biocontainers/bwa:v0.7.17").
        mounts: List of volume mounts in format "host:container[:ro]".
        env_vars: Environment variables to set inside the container.
        workdir: Working directory inside the container.
        gpus: Whether to pass --gpus all flag.
        user: User ID to run as (e.g., "$(id -u)").
        rm: Whether to auto-remove container after execution.

    Returns:
        List of Docker run command tokens.

    Example:
        >>> docker_run_prefix("biocontainers/bwa", mounts=["/data:/data:ro"])
        ["docker", "run", "--rm", "-v", "/data:/data:ro", "biocontainers/bwa"]
    """
    cmd: list[str] = ["docker", "run"]

    if rm:
        cmd.append("--rm")

    if user:
        cmd.extend(["--user", user])

    if gpus:
        cmd.append("--gpus=all")

    if workdir:
        cmd.extend(["-w", workdir])

    # Mounts
    for mount in (mounts or []):
        cmd.extend(["-v", mount])

    # Environment variables
    for key, value in (env_vars or {}).items():
        cmd.extend(["-e", f"{key}={value}"])

    # Interactive/TTY - keep false for batch execution
    # Network
    cmd.append("--network=host")

    cmd.append(image)
    return cmd


def apptainer_run_prefix(
    image: str,
    mounts: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    bind_host_paths: bool = True,
    writable: bool = False,
) -> list[str]:
    """Generate an Apptainer/Singularity exec command prefix.

    Args:
        image: Container image path or URI (e.g., "docker://biocontainers/bwa").
        mounts: List of bind mounts in format "host:container".
        env_vars: Environment variables to set.
        bind_host_paths: Auto-bind common host paths.
        writable: Use writable filesystem overlay.

    Returns:
        List of Apptainer exec command tokens.

    Example:
        >>> apptainer_run_prefix("bwa.sif", mounts=["/data:/data"])
        ["apptainer", "exec", "--bind", "/data:/data", "bwa.sif"]
    """
    cmd: list[str] = ["apptainer", "exec"]

    if writable:
        cmd.append("--writable")

    # Auto-bind home and current directory
    if bind_host_paths:
        cmd.append("--bind")
        bind_paths = []
        for mount in (mounts or []):
            bind_paths.append(mount)
        if bind_paths:
            cmd.append(",".join(bind_paths))
        else:
            # Default: bind current directory and home
            cwd = os.getcwd()
            home = os.path.expanduser("~")
            cmd.append(f"{cwd},{home}")

    # Environment variables via --env
    for key, value in (env_vars or {}).items():
        cmd.extend(["--env", f"{key}={value}"])

    # Clean environment by default for reproducibility
    cmd.append("--cleanenv")

    cmd.append(image)
    return cmd


def singularity_run_prefix(
    image: str,
    mounts: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    bind_host_paths: bool = True,
    writable: bool = False,
) -> list[str]:
    """Generate a Singularity exec command prefix.

    This is an alias for apptainer_run_prefix since Singularity
    was renamed to Apptainer.
    """
    # Singularity uses the same CLI as Apptainer
    return apptainer_run_prefix(
        image=image,
        mounts=mounts,
        env_vars=env_vars,
        bind_host_paths=bind_host_paths,
        writable=writable,
    )
