"""Stable owner for ``sniffles2_call``."""

from .legacy import _Sniffles2CallContract


class Sniffles2CallNode(_Sniffles2CallContract):
    NODE_ID = "sniffles2_call"
