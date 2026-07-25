"""Compatibility checks for the historical proteomics import path."""

from bionodulo.nodes.builtin import proteomics
from bionodulo.nodes.builtin import proteomics_family


def test_proteomics_facade_reexports_focused_owners() -> None:
    names = (
        "MaxQuantNode",
        "MSFraggerNode",
        "FragPipeWorkflowNode",
        "CometNode",
        "OpenMSFeatureFinderNode",
        "OpenMSFeatureNode",
        "DIANNNode",
        "DIANNAliasNode",
        "SageSearchNode",
        "PercolatorNode",
    )
    for name in names:
        assert getattr(proteomics, name) is getattr(proteomics_family, name)
