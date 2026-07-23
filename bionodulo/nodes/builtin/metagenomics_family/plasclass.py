"""Focused owner for ``plasclass``."""

from bionodulo.nodes.builtin.assembly_family.assembly_qc_adapter import (
    PlasClassNode as _NodeContract,
)


class PlasClassNode(_NodeContract):
    NODE_ID = "plasclass"
