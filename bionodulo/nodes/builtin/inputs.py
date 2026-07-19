"""Compatibility facade for focused workflow input nodes."""

from bionodulo.nodes.builtin.input_family import (
    InputDirectoryNode,
    InputFASTANode,
    InputFASTQNode,
    InputFileNode,
    InputGFFNode,
    InputVCFNode,
    SampleSheetNode,
)
from bionodulo.nodes.builtin.input_family.adapter import _ncbi_efetch_url

__all__ = [
    "InputDirectoryNode",
    "InputFASTANode",
    "InputFASTQNode",
    "InputFileNode",
    "InputGFFNode",
    "InputVCFNode",
    "SampleSheetNode",
    "_ncbi_efetch_url",
]
