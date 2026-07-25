"""Stable owner for the ``regex_extract`` node."""

from .adapter import _RegexExtractContract


class RegexExtractNode(_RegexExtractContract):
    NODE_ID = "regex_extract"
    UPSTREAM_SYMBOL = "RegexExtractNode"
