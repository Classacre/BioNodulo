"""Focused registered owner for ``brew3r_r``."""

from .brew3r_adapter import Brew3rRNode as _NodeContract


class Brew3rRNode(_NodeContract):
    NODE_ID = "brew3r_r"
