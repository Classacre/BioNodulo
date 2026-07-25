"""Stable owner for the ``text_template`` node."""

from .adapter import _TextTemplateContract


class TextTemplateNode(_TextTemplateContract):
    NODE_ID = "text_template"
    UPSTREAM_SYMBOL = "TextTemplateNode"
