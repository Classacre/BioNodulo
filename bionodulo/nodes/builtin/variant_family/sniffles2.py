"""Stable owner for ``sniffles2``."""

from .legacy import _Sniffles2Contract


class Sniffles2Node(_Sniffles2Contract):
    NODE_ID = "sniffles2"
