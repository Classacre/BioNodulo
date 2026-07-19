"""Generic file workflow input node."""

from .adapter import _InputFileContract


class InputFileNode(_InputFileContract):
    """Import a generic file."""

    NODE_ID = "input_file"
