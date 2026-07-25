"""Focused owner for ``cherri_eval``."""

from .adapter import _CheRRIEvalContract


class CheRRIEvalNode(_CheRRIEvalContract):
    NODE_ID = "cherri_eval"
    UPSTREAM_SYMBOL = "CheRRIEvalNode"
