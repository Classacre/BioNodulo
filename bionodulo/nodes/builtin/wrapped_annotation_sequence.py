"""Compatibility facade for focused annotation and sequence wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.rna_seq_family.featurecounts import FeatureCountsNode
from bionodulo.nodes.builtin.seqtk_family.comp import SeqTKCompNode
from bionodulo.nodes.builtin.seqtk_family.cutn import SeqTKCutNNode
from bionodulo.nodes.builtin.seqtk_family.dropse import SeqTKDropSENode
from bionodulo.nodes.builtin.seqtk_family.fqchk import SeqTKFqchkNode
from bionodulo.nodes.builtin.seqtk_family.hety import SeqTKHetyNode
from bionodulo.nodes.builtin.seqtk_family.listhet import SeqTKListHetNode
from bionodulo.nodes.builtin.seqtk_family.mergefa import SeqTKMergeFANode
from bionodulo.nodes.builtin.seqtk_family.mergepe import SeqTKMergePENode
from bionodulo.nodes.builtin.seqtk_family.mutfa import SeqTKMutFANode
from bionodulo.nodes.builtin.seqtk_family.randbase import SeqTKRandBaseNode
from bionodulo.nodes.builtin.seqtk_family.sample import SeqTKSampleNode
from bionodulo.nodes.builtin.seqtk_family.seq import SeqTKSeqNode
from bionodulo.nodes.builtin.seqtk_family.subseq import SeqTKSubseqNode
from bionodulo.nodes.builtin.seqtk_family.telo import SeqTKTeloNode
from bionodulo.nodes.builtin.seqtk_family.trimfq import SeqTKTrimFQNode
from bionodulo.nodes.builtin.wrapped_annotation_sequence_family import (
    AegeanCanonGff3Node,
    AegeanGaevalNode,
    AegeanLocusPocusNode,
    AegeanParsevalNode,
    AMRFinderPlusNode,
    ArribaDrawFusionsNode,
    ArribaGetFiltersNode,
    ArribaNode,
    ArticGuppyplexNode,
    ArticMinionNode,
    AugustusNode,
    AugustusTrainingNode,
    BUSCONode,
    HTSeqCountNode,
    RoaryNode,
    SeqKitFx2tabNode,
    SeqKitGrepNode,
    SeqKitHeadNode,
    SeqKitLocateNode,
    SeqKitSortNode,
    SeqKitSplit2Node,
    SeqKitStatsNode,
    SeqKitTranslateNode,
)

__all__ = [name for name in globals() if name.endswith("Node")]
