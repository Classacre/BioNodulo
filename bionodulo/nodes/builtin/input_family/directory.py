"""Directory workflow input node."""

from .adapter import _InputDirectoryContract


class InputDirectoryNode(_InputDirectoryContract):
    """Import a directory recursively."""

    NODE_ID = "input_directory"
