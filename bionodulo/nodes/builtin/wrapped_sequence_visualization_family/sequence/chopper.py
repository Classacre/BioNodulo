"""Stable owner for ``chopper``."""

from ..adapter import _ChopperContract


class ChopperNode(_ChopperContract):
    NODE_ID = "chopper"
