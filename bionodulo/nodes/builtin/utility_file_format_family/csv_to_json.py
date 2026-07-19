"""Stable owner for the ``csv_to_json`` node."""

from .adapter import _CSVToJSONContract


class CSVToJSONNode(_CSVToJSONContract):
    NODE_ID = "csv_to_json"
    UPSTREAM_SYMBOL = "CSVToJSONNode"
