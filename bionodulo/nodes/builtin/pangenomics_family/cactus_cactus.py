"""Stable owner for the Tools-IUC ``cactus_cactus`` contract."""

from .legacy import _CactusGalaxyContract


class CactusGalaxyNode(_CactusGalaxyContract):
    NODE_ID = "cactus_cactus"
