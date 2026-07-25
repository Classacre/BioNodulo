"""Focused owner for ``alphagenome_sequence_predictor``."""

from .adapter import AlphaGenomeSequencePredictorNode as _NodeContract


class AlphaGenomeSequencePredictorNode(_NodeContract):
    NODE_ID = "alphagenome_sequence_predictor"
