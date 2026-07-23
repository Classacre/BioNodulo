"""Stable owner for ``taxonomy_krona_chart``."""

from .adapter import _TaxonomyKronaChartContract


class TaxonomyKronaChartNode(_TaxonomyKronaChartContract):
    NODE_ID = "taxonomy_krona_chart"
    UPSTREAM_SYMBOL = "TaxonomyKronaChartNode"
