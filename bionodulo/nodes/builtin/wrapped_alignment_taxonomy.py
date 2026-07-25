"""Compatibility facade for focused alignment and taxonomy wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.alignment_family.bwameth import BwaMethNode
from bionodulo.nodes.builtin.alignment_family.cawlign import CawlignNode
from bionodulo.nodes.builtin.annotation_family.blastxml_to_gapped_gff3 import (
    BlastxmlToGappedGff3Node,
)
from bionodulo.nodes.builtin.bctools_family import (
    BctoolsConvertToBinaryBarcodeNode,
    BctoolsExtractAlignmentEndsNode,
    BctoolsExtractBarcodesNode,
    BctoolsExtractCrosslinkedNucleotidesNode,
    BctoolsMergePcrDuplicatesNode,
    BctoolsRemoveSpuriousEventsNode,
    BctoolsRemoveTailNode,
)
from bionodulo.nodes.builtin.cat_family import (
    CatAddNamesNode,
    CatBinsNode,
    CatContigsNode,
    CatPrepareNode,
    CatSummariseNode,
)
from bionodulo.nodes.builtin.crossmap_family import (
    CrossMapBamNode,
    CrossMapBedNode,
    CrossMapBigWigNode,
    CrossMapGffNode,
    CrossMapRegionNode,
    CrossMapVcfNode,
    CrossMapWigNode,
)
from bionodulo.nodes.builtin.data_transform_family.calculate_numeric_param import (
    CalculateNumericParamNode,
)
from bionodulo.nodes.builtin.data_transform_family.collection_column_join import (
    CollectionColumnJoinNode,
)
from bionodulo.nodes.builtin.data_transform_family.collection_element_identifiers import (
    CollectionElementIdentifiersNode,
)
from bionodulo.nodes.builtin.data_transform_family.column_maker import ColumnMakerNode
from bionodulo.nodes.builtin.data_transform_family.compose_text_param import ComposeTextParamNode
from bionodulo.nodes.builtin.data_transform_family.compress_file import CompressFileNode
from bionodulo.nodes.builtin.qc_family.coverage_report import CoverageReportNode
from bionodulo.nodes.builtin.sequence_family import BarcodeSplitterNode, ExtractGenomicDnaNode
from bionodulo.nodes.builtin.variant_family.happy_sompy import HappySompyNode
from bionodulo.nodes.builtin.visualization_family.calculate_contrast_threshold import (
    CalculateContrastThresholdNode,
)

__all__ = [name for name in globals() if name.endswith("Node")]
