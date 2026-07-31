"""Compatibility facade for focused protein and taxonomy wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.beacon2_family import (
    Beacon2AnalysesNode,
    Beacon2BiosamplesNode,
    Beacon2BracketNode,
    Beacon2CNVNode,
    Beacon2CohortsNode,
    Beacon2DatasetsNode,
    Beacon2GeneNode,
    Beacon2IndividualsNode,
    Beacon2RangeNode,
    Beacon2RunsNode,
    Beacon2SequenceNode,
)
from bionodulo.nodes.builtin.centrifuge_family import CentrifugeNode
from bionodulo.nodes.builtin.diamond_family import (
    DiamondAlignNode,
    DiamondMakeDBNode,
    GalaxyDiamondMakeDBNode,
    GalaxyDiamondNode,
    GalaxyDiamondViewNode,
)
from bionodulo.nodes.builtin.hmmer_family import (
    HMMERAlimaskNode,
    HMMERHmmalignNode,
    HMMERHmmbuildNode,
    HMMERHmmconvertNode,
    HMMERHmmemitNode,
    HMMERHmmfetchNode,
    HMMERHmmscanNode,
    HMMERHmmsearchNode,
    HMMERJackhmmerNode,
    HMMERNhmmerNode,
    HMMERNhmmscanNode,
    HMMERPhmmerNode,
)
from bionodulo.nodes.builtin.kaiju_family import (
    Kaiju2KronaNode,
    Kaiju2TableNode,
    KaijuAddTaxonNamesNode,
    KaijuMergeOutputsNode,
    KaijuNode,
)
from bionodulo.nodes.builtin.kraken_family import (
    KrakenFilterNode,
    KrakenMpaReportNode,
    KrakenNode,
    KrakenReportNode,
    KrakenTranslateNode,
)
from bionodulo.nodes.builtin.mmseqs2_family import (
    MMseqs2EasyClusterNode,
    MMseqs2EasyLinclustNode,
    MMseqs2EasyLinsearchNode,
    MMseqs2EasyRBHNode,
    MMseqs2EasySearchNode,
    MMseqs2EasyTaxonomyNode,
    MMseqs2TaxonomyAssignmentNode,
)

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "Beacon2AnalysesNode",
    "Beacon2BiosamplesNode",
    "Beacon2BracketNode",
    "Beacon2CNVNode",
    "Beacon2CohortsNode",
    "Beacon2DatasetsNode",
    "Beacon2GeneNode",
    "Beacon2IndividualsNode",
    "Beacon2RangeNode",
    "Beacon2RunsNode",
    "Beacon2SequenceNode",
    "CentrifugeNode",
    "DiamondAlignNode",
    "DiamondMakeDBNode",
    "GalaxyDiamondMakeDBNode",
    "GalaxyDiamondNode",
    "GalaxyDiamondViewNode",
    "HMMERAlimaskNode",
    "HMMERHmmalignNode",
    "HMMERHmmbuildNode",
    "HMMERHmmconvertNode",
    "HMMERHmmemitNode",
    "HMMERHmmfetchNode",
    "HMMERHmmscanNode",
    "HMMERHmmsearchNode",
    "HMMERJackhmmerNode",
    "HMMERNhmmerNode",
    "HMMERNhmmscanNode",
    "HMMERPhmmerNode",
    "Kaiju2KronaNode",
    "Kaiju2TableNode",
    "KaijuAddTaxonNamesNode",
    "KaijuMergeOutputsNode",
    "KaijuNode",
    "KrakenFilterNode",
    "KrakenMpaReportNode",
    "KrakenNode",
    "KrakenReportNode",
    "KrakenTranslateNode",
    "MMseqs2EasyClusterNode",
    "MMseqs2EasyLinclustNode",
    "MMseqs2EasyLinsearchNode",
    "MMseqs2EasyRBHNode",
    "MMseqs2EasySearchNode",
    "MMseqs2EasyTaxonomyNode",
    "MMseqs2TaxonomyAssignmentNode",
]
