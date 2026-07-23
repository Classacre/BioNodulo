"""Focused registered node for ``openms_feature_finder``."""

import bionodulo.nodes.builtin.proteomics_family.openms_feature_finder_adapter as _adapter
from bionodulo.nodes.builtin.proteomics_family.openms_feature_finder_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.proteomics_family.openms_feature_finder_adapter import OpenMSFeatureFinderNode as _NodeContract
globals().pop('OpenMSFeatureNode', None)


class OpenMSFeatureFinderNode(_NodeContract):
    NODE_ID = 'openms_feature_finder'

__all__ = ['OpenMSFeatureFinderNode', 'OpenMSFeatureNode']  # noqa: F405


def __getattr__(name: str):
    if name == 'OpenMSFeatureNode':
        from bionodulo.nodes.builtin.proteomics_family.openms_feature import OpenMSFeatureNode

        return OpenMSFeatureNode
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_adapter)))
