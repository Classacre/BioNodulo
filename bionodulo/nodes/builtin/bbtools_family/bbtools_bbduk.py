"""Focused owner for ``bbtools_bbduk``."""

from .adapter import BBToolsBBDukNode as _NodeContract


class BBToolsBBDukNode(_NodeContract):
    NODE_ID = "bbtools_bbduk"
