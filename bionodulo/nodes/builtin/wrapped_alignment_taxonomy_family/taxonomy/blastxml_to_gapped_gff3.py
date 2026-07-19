"""Stable owner for ``blastxml_to_gapped_gff3``."""

from .adapter import _BlastxmlToGappedGff3Contract


class BlastxmlToGappedGff3Node(_BlastxmlToGappedGff3Contract):
    NODE_ID = "blastxml_to_gapped_gff3"
    UPSTREAM_SYMBOL = "BlastxmlToGappedGff3Node"
