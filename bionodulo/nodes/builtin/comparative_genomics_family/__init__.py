"""Focused whole-genome comparison wrapper owners."""
# ruff: noqa: F401

from .fastani import FastANINode

__all__ = [name for name in globals() if name.endswith("Node")]
