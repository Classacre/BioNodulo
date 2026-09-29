"""Focused vcflib node owners.

One node per executable in the vcflib package, generated from each tool's own
``--help`` output by ``scripts/generate_vcflib_nodes.py``.
"""

from .adapter import VcflibBase

__all__ = ["VcflibBase"]
