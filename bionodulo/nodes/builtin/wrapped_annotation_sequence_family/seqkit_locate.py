"""Stable owner for ``seqkit_locate``."""

from .legacy import _SeqKitLocateContract


class SeqKitLocateNode(_SeqKitLocateContract):
    NODE_ID = "seqkit_locate"
    OUTPUT_NAME_BY_BASENAME = {
        "locate.tsv": "tabular",
        "locate.bed": "bed",
        "locate.gtf": "gtf",
    }
