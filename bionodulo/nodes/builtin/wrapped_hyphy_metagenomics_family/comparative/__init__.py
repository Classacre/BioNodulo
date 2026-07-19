"""Focused whole-genome comparison wrapper owners."""
# ruff: noqa: F401

from .fastani import FastANINode
from .mashmap import MashMapNode

__all__ = [name for name in globals() if name.endswith("Node")]
