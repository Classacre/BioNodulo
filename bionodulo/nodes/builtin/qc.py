"""Compatibility imports for focused quality-control nodes."""

from bionodulo.nodes.builtin.qc_family.qualimap import (
    QualiMapAliasNode,
    QualiMapNode,
)

__all__ = ["QualiMapAliasNode", "QualiMapNode"]
