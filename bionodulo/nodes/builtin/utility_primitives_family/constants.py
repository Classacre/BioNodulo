"""Named constants utility node."""

from .adapter import ConstantsNode as _ConstantsContract


class ConstantsNode(_ConstantsContract):
    """Emit one named mathematical or bioinformatics constant."""

    NODE_ID = "constants"
