"""Focused registered node for ``ampvis2_subset_samples``."""

from .filtering_adapter import Ampvis2SubsetSamplesNode as _NodeContract


class Ampvis2SubsetSamplesNode(_NodeContract):
    NODE_ID = "ampvis2_subset_samples"
