"""Focused registered node for ``ampvis2_frequency``."""

from .abundance_adapter import Ampvis2FrequencyNode as _NodeContract


class Ampvis2FrequencyNode(_NodeContract):
    NODE_ID = "ampvis2_frequency"
