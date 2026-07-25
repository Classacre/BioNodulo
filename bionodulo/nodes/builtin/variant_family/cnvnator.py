"""Stable owner for ``cnvnator``."""

from .legacy import _CNVnatorContract


class CNVnatorNode(_CNVnatorContract):
    NODE_ID = "cnvnator"
