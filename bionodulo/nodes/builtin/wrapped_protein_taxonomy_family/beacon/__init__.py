"""Focused Beacon2 endpoint owners."""

from .beacon2_analyses import Beacon2AnalysesNode
from .beacon2_biosamples import Beacon2BiosamplesNode
from .beacon2_bracket import Beacon2BracketNode
from .beacon2_cnv import Beacon2CNVNode
from .beacon2_cohorts import Beacon2CohortsNode
from .beacon2_datasets import Beacon2DatasetsNode
from .beacon2_gene import Beacon2GeneNode
from .beacon2_individuals import Beacon2IndividualsNode
from .beacon2_range import Beacon2RangeNode
from .beacon2_runs import Beacon2RunsNode
from .beacon2_sequence import Beacon2SequenceNode

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
]
