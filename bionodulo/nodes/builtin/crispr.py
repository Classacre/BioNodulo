"""Compatibility imports for the focused CRISPR family."""

# ruff: noqa: F401
from bionodulo.nodes.builtin.crispr_family.cas_offinder import CasOffinderNode
from bionodulo.nodes.builtin.crispr_family.crispresso2 import CRISPRESSO2Node
from bionodulo.nodes.builtin.crispr_family.guide_rna_design import GuideRNADesignNode
from bionodulo.nodes.builtin.crispr_family.mageck_count import MAGeCKCountNode
from bionodulo.nodes.builtin.crispr_family.mageck_test import MAGeCKTestNode

# Preserve the historical class import while the stable node ID remains ``crispresso2``.
CRISPRESSONode = CRISPRESSO2Node
