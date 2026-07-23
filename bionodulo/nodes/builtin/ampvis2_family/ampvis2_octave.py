"""Focused registered node for ``ampvis2_octave``."""

from .diversity_adapter import Ampvis2OctaveNode as _NodeContract


class Ampvis2OctaveNode(_NodeContract):
    NODE_ID = "ampvis2_octave"
