"""Compatibility facade for focused HPC nodes."""

from .hpc_family import HPCCheckStatusNode as HPCCheckStatusNode
from .hpc_family import HPCSubmitJobNode as HPCSubmitJobNode

__all__ = ["HPCCheckStatusNode", "HPCSubmitJobNode"]
