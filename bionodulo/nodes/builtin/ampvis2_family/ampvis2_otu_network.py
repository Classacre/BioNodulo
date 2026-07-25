"""Focused registered node for ``ampvis2_otu_network``."""

from .abundance_adapter import Ampvis2OtuNetworkNode as _NodeContract


class Ampvis2OtuNetworkNode(_NodeContract):
    NODE_ID = "ampvis2_otu_network"
