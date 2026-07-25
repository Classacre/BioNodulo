"""Focused owner for ``phyml``."""

from .classic_adapter import PhyMLNode as _NodeContract


class PhyMLNode(_NodeContract):
    NODE_ID = "phyml"
