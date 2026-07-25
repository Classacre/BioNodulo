"""Stable owner for ``strelka2``."""

from .legacy import _Strelka2Contract


class Strelka2Node(_Strelka2Contract):
    NODE_ID = "strelka2"
