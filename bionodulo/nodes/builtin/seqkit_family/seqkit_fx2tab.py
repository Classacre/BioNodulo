"""Focused owner for ``seqkit_fx2tab``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _SeqKitFx2tabContract


class SeqKitFx2tabNode(_SeqKitFx2tabContract):
    NODE_ID = "seqkit_fx2tab"
