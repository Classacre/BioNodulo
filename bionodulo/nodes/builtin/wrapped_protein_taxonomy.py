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

__all__ = [name for name in globals() if name.endswith("Node")]
