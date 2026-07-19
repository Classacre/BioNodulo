"""Stable owner for ``taxonkit_profile2cami``."""

from .adapter import _TaxonKitProfile2CamiContract


class TaxonKitProfile2CamiNode(_TaxonKitProfile2CamiContract):
    NODE_ID = "taxonkit_profile2cami"
    UPSTREAM_SYMBOL = "TaxonKitProfile2CamiNode"
