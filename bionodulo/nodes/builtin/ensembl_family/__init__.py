"""Focused Ensembl REST operations."""

from .gene_lookup import EnsemblGeneLookupNode
from .vep import EnsemblVEPNode

__all__ = ["EnsemblGeneLookupNode", "EnsemblVEPNode"]
