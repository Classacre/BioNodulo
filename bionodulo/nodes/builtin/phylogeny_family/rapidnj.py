"""Focused owner for ``rapidnj``."""

from .classic_adapter import RapidNJNode as _NodeContract


class RapidNJNode(_NodeContract):
    NODE_ID = "rapidnj"
