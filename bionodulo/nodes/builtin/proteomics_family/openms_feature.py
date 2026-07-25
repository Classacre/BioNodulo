"""Focused registered node for ``openms_feature``."""

from bionodulo.nodes.builtin.proteomics_family.openms_feature_finder_adapter import OpenMSFeatureNode as _NodeContract
from bionodulo.nodes.builtin.proteomics_family.openms_feature_finder import OpenMSFeatureFinderNode


class OpenMSFeatureNode(_NodeContract, OpenMSFeatureFinderNode):
    NODE_ID = 'openms_feature'
