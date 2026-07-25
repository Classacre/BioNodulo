"""Workflow provenance node."""

from .adapter import ProvenanceNode as _ProvenanceContract


class ProvenanceNode(_ProvenanceContract):
    """Capture configurable workflow provenance and pass data through."""

    NODE_ID = "provenance"
