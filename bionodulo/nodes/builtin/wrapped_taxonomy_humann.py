"""Compatibility facade for focused taxonomy and HUMAnN wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.biom_family import (
    BiomAddMetadataNode,
    BiomConvertNode,
    BiomFromUcNode,
    BiomNormalizeTableNode,
    BiomSubsetTableNode,
    BiomSummarizeTableNode,
)
from bionodulo.nodes.builtin.humann_family import (
    HUMAnNBarplotNode,
    HUMAnNJoinTablesNode,
    HUMAnNReduceTableNode,
    HUMAnNRegroupTableNode,
    HUMAnNRenameTableNode,
    HUMAnNRenormTableNode,
    HUMAnNSplitStratifiedTableNode,
    HUMAnNSplitTableNode,
    HUMAnNUnpackPathwaysNode,
)
from bionodulo.nodes.builtin.hybpiper_family import HybPiperNode
from bionodulo.nodes.builtin.krakentools_family import (
    KrakentoolsAlphaDiversityNode,
    KrakentoolsBetaDiversityNode,
    KrakentoolsCombineKreportsNode,
    KrakentoolsExtractKrakenReadsNode,
    KrakentoolsKreport2KronaNode,
    KrakentoolsKreport2MpaNode,
    MothurTaxonomyToKronaNode,
    TaxonomyKronaChartNode,
)
from bionodulo.nodes.builtin.taxonkit_family import (
    TaxonKitName2TaxidNode,
    TaxonKitProfile2CamiNode,
)
from bionodulo.nodes.builtin.taxonomy_family import (
    BMTaggerNode,
    BrackenEstAbundanceNode,
    MagicBlastNode,
    RecentrifugeNode,
    TaxpastaNode,
)
from bionodulo.nodes.builtin.tracy_family import (
    TracyAlignNode,
    TracyAssembleNode,
    TracyBasecallNode,
    TracyDecomposeNode,
)

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "BMTaggerNode",
    "BiomAddMetadataNode",
    "BiomConvertNode",
    "BiomFromUcNode",
    "BiomNormalizeTableNode",
    "BiomSubsetTableNode",
    "BiomSummarizeTableNode",
    "BrackenEstAbundanceNode",
    "HUMAnNBarplotNode",
    "HUMAnNJoinTablesNode",
    "HUMAnNReduceTableNode",
    "HUMAnNRegroupTableNode",
    "HUMAnNRenameTableNode",
    "HUMAnNRenormTableNode",
    "HUMAnNSplitStratifiedTableNode",
    "HUMAnNSplitTableNode",
    "HUMAnNUnpackPathwaysNode",
    "HybPiperNode",
    "KrakentoolsAlphaDiversityNode",
    "KrakentoolsBetaDiversityNode",
    "KrakentoolsCombineKreportsNode",
    "KrakentoolsExtractKrakenReadsNode",
    "KrakentoolsKreport2KronaNode",
    "KrakentoolsKreport2MpaNode",
    "MagicBlastNode",
    "MothurTaxonomyToKronaNode",
    "RecentrifugeNode",
    "TaxonKitName2TaxidNode",
    "TaxonKitProfile2CamiNode",
    "TaxonomyKronaChartNode",
    "TaxpastaNode",
    "TracyAlignNode",
    "TracyAssembleNode",
    "TracyBasecallNode",
    "TracyDecomposeNode",
]
