"""Conda/Mamba/Micromamba environment management for BioNodulo.

Provides utilities for generating conda run prefixes and creating
environments from YAML specifications.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from bionodulo.environments.model import EnvironmentSpec

logger = logging.getLogger(__name__)

# Default channels for bioinformatics packages
DEFAULT_CHANNELS = ["bioconda", "conda-forge", "defaults"]


def conda_run_prefix(
    env_name: str | None = None,
    env_file: str | None = None,
    executable: str = "micromamba",
    env_root: str | None = None,
) -> list[str]:
    """Generate a conda/mamba/micromamba run prefix command.

    Args:
        env_name: Named environment to activate.
        env_file: environment.yml file path.
        executable: Which executable to use (micromamba, mamba, conda).
        env_root: Root prefix for environment storage.

    Returns:
        List of command prefix tokens to prepend before the actual command.

    Example:
        >>> conda_run_prefix(env_name="bioenv", executable="micromamba")
        ["micromamba", "run", "-n", "bioenv"]
    """
    cmd: list[str] = [executable, "run"]

    if env_name:
        cmd.extend(["-n", env_name])
    elif env_file:
        cmd.extend(["-f", env_file])
    else:
        # Run in base environment
        pass

    if env_root and executable == "micromamba":
        cmd.extend(["-r", env_root])

    return cmd


def create_env_from_yaml(
    yaml_path: str,
    env_name: str | None = None,
    executable: str = "micromamba",
    env_root: str | None = None,
    timeout: int = 600,
) -> bool:
    """Create a Conda environment from a YAML specification.

    Args:
        yaml_path: Path to environment YAML file.
        env_name: Optional name override for the environment.
        executable: Which conda executable to use.
        env_root: Root prefix for environment storage.
        timeout: Maximum seconds to wait for environment creation.

    Returns:
        True if environment was created successfully.
    """
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        logger.error("Environment YAML not found: %s", yaml_path)
        return False

    cmd: list[str] = [executable]

    if executable == "micromamba":
        cmd.extend(["create", "-y", "-f", str(yaml_file)])
        if env_name:
            cmd.extend(["-n", env_name])
        if env_root:
            cmd.extend(["-r", env_root])
    else:
        cmd.extend(["env", "create", "-f", str(yaml_file)])
        if env_name:
            cmd.extend(["-n", env_name])

    logger.info("Creating conda env: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            logger.info("Environment created successfully")
            return True
        else:
            logger.error("Environment creation failed: %s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("Environment creation timed out after %ds", timeout)
        return False
    except FileNotFoundError:
        logger.error("Conda executable not found: %s", executable)
        return False


def ensure_channels_configured(executable: str = "micromamba") -> bool:
    """Ensure default bioconda channels are configured.

    Args:
        executable: Which conda executable to use.

    Returns:
        True if channels are configured.
    """
    for channel in DEFAULT_CHANNELS:
        try:
            subprocess.run(
                [executable, "config", "append", "channels", channel],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return True
