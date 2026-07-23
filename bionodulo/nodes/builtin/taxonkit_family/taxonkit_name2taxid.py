"""Stable owner for ``taxonkit_name2taxid``."""

from bionodulo.nodes.builtin.taxonomy_family.adapter import _TaxonKitName2TaxidContract


class TaxonKitName2TaxidNode(_TaxonKitName2TaxidContract):
    NODE_ID = "taxonkit_name2taxid"
    UPSTREAM_SYMBOL = "TaxonKitName2TaxidNode"
