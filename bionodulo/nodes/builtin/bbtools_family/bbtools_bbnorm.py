"""Focused owner for ``bbtools_bbnorm``."""

from .adapter import BBToolsBBNormNode as _NodeContract


class BBToolsBBNormNode(_NodeContract):
    NODE_ID = "bbtools_bbnorm"
