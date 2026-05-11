"""BioNodulo environment management package.

Provides tools for managing Conda, Docker, Apptainer/Singularity,
and bare-metal execution environments for bioinformatics tools.
"""
from bionodulo.environments.model import EnvironmentSpec

__all__ = ["EnvironmentSpec"]
