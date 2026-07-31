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
from bionodulo.nodes.builtin.aegean_family import (
    AegeanCanonGff3Node,
    AegeanGaevalNode,
    AegeanLocusPocusNode,
    AegeanParsevalNode,
)
from bionodulo.nodes.builtin.annotation_family.amrfinderplus import AMRFinderPlusNode
from bionodulo.nodes.builtin.arriba_family import (
    ArribaDrawFusionsNode,
    ArribaGetFiltersNode,
    ArribaNode,
)
from bionodulo.nodes.builtin.artic_family import ArticGuppyplexNode, ArticMinionNode
from bionodulo.nodes.builtin.assembly_family.busco import BUSCONode
from bionodulo.nodes.builtin.augustus_family import AugustusNode, AugustusTrainingNode
from bionodulo.nodes.builtin.pangenomics_family.roary import RoaryNode
from bionodulo.nodes.builtin.rna_seq_family.htseq_count import HTSeqCountNode
from bionodulo.nodes.builtin.seqkit_family import (
    SeqKitFx2tabNode,
    SeqKitGrepNode,
    SeqKitHeadNode,
    SeqKitLocateNode,
    SeqKitSortNode,
    SeqKitSplit2Node,
    SeqKitStatsNode,
    SeqKitTranslateNode,
)

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "AMRFinderPlusNode",
    "AegeanCanonGff3Node",
    "AegeanGaevalNode",
    "AegeanLocusPocusNode",
    "AegeanParsevalNode",
    "ArribaDrawFusionsNode",
    "ArribaGetFiltersNode",
    "ArribaNode",
    "ArticGuppyplexNode",
    "ArticMinionNode",
    "AugustusNode",
    "AugustusTrainingNode",
    "BUSCONode",
    "FeatureCountsNode",
    "HTSeqCountNode",
    "RoaryNode",
    "SeqKitFx2tabNode",
    "SeqKitGrepNode",
    "SeqKitHeadNode",
    "SeqKitLocateNode",
    "SeqKitSortNode",
    "SeqKitSplit2Node",
    "SeqKitStatsNode",
    "SeqKitTranslateNode",
    "SeqTKCompNode",
    "SeqTKCutNNode",
    "SeqTKDropSENode",
    "SeqTKFqchkNode",
    "SeqTKHetyNode",
    "SeqTKListHetNode",
    "SeqTKMergeFANode",
    "SeqTKMergePENode",
    "SeqTKMutFANode",
    "SeqTKRandBaseNode",
    "SeqTKSampleNode",
    "SeqTKSeqNode",
    "SeqTKSubseqNode",
    "SeqTKTeloNode",
    "SeqTKTrimFQNode",
]
