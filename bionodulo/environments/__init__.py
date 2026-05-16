"""BioNodulo environment management package.

Provides manifest-based per-workflow environment generation
using pixi for reproducible, isolated bioinformatics tool environments.
"""
from bionodulo.environments.manifest import (
    ensure_workflow_env,
    get_env_dir,
    get_env_id,
    is_env_ready,
    workflow_to_packages,
)
from bionodulo.environments.model import EnvironmentSpec

__all__ = [
    "EnvironmentSpec",
    "ensure_workflow_env",
    "get_env_dir",
    "get_env_id",
    "is_env_ready",
    "workflow_to_packages",
]
