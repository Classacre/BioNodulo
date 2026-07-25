"""Focused owner for ``chewbbaca_joinprofiles``."""

from .adapter import _ChewBBACAJoinProfilesContract


class ChewBBACAJoinProfilesNode(_ChewBBACAJoinProfilesContract):
    NODE_ID = "chewbbaca_joinprofiles"
    UPSTREAM_SYMBOL = "ChewBBACAJoinProfilesNode"
