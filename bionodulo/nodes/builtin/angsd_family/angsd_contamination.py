"""Focused registered node for ``angsd_contamination``."""

from .adapter import ANGSDContaminationNode as _NodeContract


class ANGSDContaminationNode(_NodeContract):
    NODE_ID = "angsd_contamination"
