"""Focused owner for ``chewbbaca_allelecallevaluator``."""

from .adapter import _ChewBBACAAlleleCallEvaluatorContract


class ChewBBACAAlleleCallEvaluatorNode(_ChewBBACAAlleleCallEvaluatorContract):
    NODE_ID = "chewbbaca_allelecallevaluator"
    UPSTREAM_SYMBOL = "ChewBBACAAlleleCallEvaluatorNode"
