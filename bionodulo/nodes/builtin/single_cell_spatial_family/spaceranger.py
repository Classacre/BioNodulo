"""Compatibility alias for the focused Space Ranger count owner."""

from .spaceranger_count import SpaceRangerNode


class SpaceRangerCompatibilityNode(SpaceRangerNode):
    """Preserve the original ``spaceranger`` node ID and output namespace."""

    NODE_ID = "spaceranger"
    DISPLAY_NAME = "Space Ranger"
    DESCRIPTION = "Process one 10x Visium capture area with Space Ranger count."
