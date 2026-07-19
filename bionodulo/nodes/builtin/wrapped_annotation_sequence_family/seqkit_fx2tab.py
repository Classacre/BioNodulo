"""Stable owner for ``seqkit_fx2tab``."""

from .legacy import _SeqKitFx2tabContract


class SeqKitFx2tabNode(_SeqKitFx2tabContract):
    NODE_ID = "seqkit_fx2tab"
