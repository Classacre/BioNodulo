"""Stable owner for ``clair3``."""

from .legacy import _Clair3Contract


class Clair3Node(_Clair3Contract):
    NODE_ID = "clair3"
