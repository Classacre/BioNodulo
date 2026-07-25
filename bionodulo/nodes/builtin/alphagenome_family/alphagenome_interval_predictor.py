"""Focused owner for ``alphagenome_interval_predictor``."""

from .adapter import AlphaGenomeIntervalPredictorNode as _NodeContract


class AlphaGenomeIntervalPredictorNode(_NodeContract):
    NODE_ID = "alphagenome_interval_predictor"
